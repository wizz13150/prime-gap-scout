"""Build the shipped CUDA workers and optional portable terminal application."""
from pathlib import Path
import argparse,hashlib,json,os,re,shutil,subprocess,sys

ROOT=Path(__file__).resolve().parent
NATIVE=ROOT/'native'
FRONTEND=ROOT/'frontend'

def digest(path):
    h=hashlib.sha256()
    with path.open('rb')as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest().upper()

def native_manifest(source=NATIVE):
    rows=[]
    for path in sorted(source.rglob('*'),key=lambda path:path.relative_to(source).as_posix().casefold()):
        if path.is_file()and path.suffix.lower()in('.cu','.cuh','.h','.bin','.manifest'):
            rows.append({'file':path.relative_to(source).as_posix(),'bytes':path.stat().st_size,'sha256':digest(path)})
    if not rows:raise RuntimeError('Missing native source inputs')
    manifest=source/'SOURCE-MANIFEST.json'
    manifest.write_text(json.dumps({'schema':'PRIME_GAP_SCOUT_NATIVE_INPUTS_V1','files':rows},indent=2)+'\n',encoding='utf-8',newline='\r\n')
    return digest(manifest)

def build(archs):
    nvcc=shutil.which('nvcc')
    if not nvcc and os.environ.get('CUDA_PATH'):
        candidate=Path(os.environ['CUDA_PATH'])/'bin'/('nvcc.exe'if os.name=='nt'else'nvcc')
        if candidate.is_file():nvcc=str(candidate)
    if not nvcc:raise RuntimeError('nvcc was not found; install CUDA Toolkit and put its bin directory on PATH')
    supported=subprocess.run([nvcc,'--list-gpu-code'],capture_output=True,text=True,check=True).stdout
    source=NATIVE
    if os.name!='nt':
        from prepare_native import prepare
        source=prepare(NATIVE,ROOT/'build')
    source_sha=native_manifest(source);bins=FRONTEND/'bin';bins.mkdir(exist_ok=True)
    flags=['-O3','--std=c++17','--threads','1','-lineinfo','-dlto','-rdc=true','--cudart','shared','-lcudadevrt',
           '-DPGN_RELEASE_ENABLE_PUBLIC_PERIG=0','-DPGN_DESCRIPTOR_LANES=2','-DPGN_DESCRIPTOR_BLOCKS=64',
           '-DPGN_EULER96_LAZY','-DPGN_PRESIEVE_GROUPS=1','-DPGN_MARK_FULL_FAST','-DPGN_MARK_BANK_ROTATE',
           '-DPGN_FUSED_SIEVE','-DPGN_EULER96','-DPGN_EULER96_FIXED_HIGH10','-DPGN_VERIFY_GAPS']
    completed=[]
    for arch in archs:
        if 'sm_'+str(arch)not in supported:
            print('SKIP unsupported nvcc target sm_'+str(arch));continue
        suffix='.exe'if os.name=='nt'else''
        output=bins/f'pgn68-worker-sm{arch}-k64{suffix}'
        command=[nvcc,*flags,f'-arch=sm_{arch}',f'-DPGN_RELEASE_BUILD_ARCH={arch}']
        if os.name=='nt':command+=['-Xcompiler=/MT','-Xcompiler=/utf-8','-Xlinker=/MANIFEST:EMBED','-Xlinker=/MANIFESTINPUT:pgn68.manifest']
        else:
            compiler=os.environ.get('CXX')or shutil.which('g++-13')or shutil.which('g++')
            if compiler:command+=['-ccbin',compiler]
            command+=['-Xlinker=-rpath','-Xlinker=$ORIGIN/../lib']
        command+=['continuous-gpu-runtime.cu','-o',str(output)]
        subprocess.run(command,cwd=source,check=True)
        image_sha=digest(output)
        for profile in(8,16,32,64):
            target=bins/f'pgn68-worker-sm{arch}-k{profile}{suffix}'
            if target!=output:shutil.copyfile(output,target)
            sidecar={'schema':'PGN_NATIVE_MODULE_METADATA_V1','image_sha256':image_sha,'source_manifest_sha256':source_sha,
                     'gap_runtime_schema':'PGN_NATIVE_GAP_RUNTIME_V1','profile_k':profile,'build_arch':arch}
            target.with_name(target.name+'.module.json').write_text(json.dumps(sidecar,indent=2)+'\n')
        completed.append(arch)
    if not completed:raise RuntimeError('No requested architecture compiled')
    cuda=Path(nvcc).resolve().parent.parent
    if os.name=='nt':
        libraries=list((cuda/'bin').glob('cudart64_*.dll'))
        if not libraries:raise RuntimeError('CUDA runtime DLL not found in Toolkit bin')
        for path in libraries:shutil.copyfile(path,bins/path.name)
    else:
        lib=FRONTEND/'lib';lib.mkdir(exist_ok=True)
        libraries=list((cuda/'lib64').glob('libcudart.so.*'))
        if not libraries:raise RuntimeError('CUDA runtime shared library not found')
        for path in libraries:shutil.copyfile(path.resolve(),lib/path.name)
    return completed

def package():
    from PyInstaller.__main__ import run
    from pgn68 import argument_parser
    from pgn_launcher import generate
    dest=ROOT/'build'/('windows'if os.name=='nt'else'ubuntu')
    separator=';'if os.name=='nt'else':'
    args=['--noconfirm','--onedir','--console','--name','pgn68','--distpath',str(dest),'--workpath',str(ROOT/'build/work'),
          '--specpath',str(ROOT/'build/spec'),'--paths',str(FRONTEND),'--collect-all','rich',
          '--hidden-import','sqlite3','--hidden-import','_sqlite3','--add-data',str(FRONTEND/'data/diagnostic')+separator+'data/diagnostic']
    for path in FRONTEND.glob('*.py'):
        if path.name!='pgn68.py':args+=['--hidden-import',path.stem]
    run(args+[str(FRONTEND/'pgn68.py')]);out=dest/'pgn68'
    for name in('bin','lib'):
        if(FRONTEND/name).is_dir():shutil.copytree(FRONTEND/name,out/name,dirs_exist_ok=True)
    (out/'ui').mkdir(exist_ok=True)
    for name in('console_ui.py','pgn_dashboard_rc7.py'):shutil.copyfile(FRONTEND/name,out/'ui'/name)
    generate(argument_parser(),out)
    for path in(out/'Start-PGN68.cmd',out/'Start-PGN68.sh'):
        text=path.read_text().replace('set "IDLE=0"','set "IDLE=1"').replace('export IDLE=0','export IDLE=1').replace("export IDLE='0'","export IDLE='1'")
        path.write_text(text,newline='\r\n'if path.suffix=='.cmd'else'\n')
    print('Complete portable directory:',out)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--archs',default='86,120',help='Comma-separated CUDA targets, default86,120')
    parser.add_argument('--package',action='store_true',help='Also freeze the Python frontend into a portable directory')
    options=parser.parse_args()
    targets=[int(part)for part in options.archs.split(',')]
    if not targets or any(arch not in(86,120)for arch in targets):parser.error('Unsupported requested build target')
    sys.path.insert(0,str(FRONTEND))
    build(targets)
    if options.package:package()
