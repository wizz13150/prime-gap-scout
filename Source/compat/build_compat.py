"""Rebuild a historical worker for source review; never replace pinned resume images."""
from pathlib import Path
import argparse,os,shutil,subprocess,tempfile
ROOT=Path(__file__).resolve().parent
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--arch',type=int,choices=(86,120),required=True);p.add_argument('--floor',type=int,choices=(954,960),default=960);p.add_argument('--out',type=Path,required=True);p.add_argument('--compiler');a=p.parse_args()
 if a.floor==954 and os.name!='nt':p.error('The historical954 snapshot was Windows only')
 nvcc=shutil.which('nvcc')
 if not nvcc and os.environ.get('CUDA_PATH'):nvcc=str(Path(os.environ['CUDA_PATH'])/'bin/nvcc.exe')
 if not nvcc:raise SystemExit('Install CUDA Toolkit and put nvcc on PATH. Use a VS x64 developer prompt on Windows.')
 a.out=a.out.resolve();a.out.parent.mkdir(parents=True,exist_ok=True)
 flags=['-O3','--std=c++17','--threads','1','-lineinfo','-dlto','-rdc=true','--cudart','shared','-lcudadevrt',f'-arch=sm_{a.arch}',f'-DPGN_RELEASE_BUILD_ARCH={a.arch}','-DPGN_RELEASE_ENABLE_PUBLIC_PERIG=0','--ptxas-options=-v','-DPGN_DESCRIPTOR_LANES=2','-DPGN_DESCRIPTOR_BLOCKS=64','-DPGN_EULER96_LAZY','-DPGN_PRESIEVE_GROUPS=1','-DPGN_MARK_FULL_FAST','-DPGN_MARK_BANK_ROTATE','-DPGN_FUSED_SIEVE','-DPGN_EULER96','-DPGN_EULER96_FIXED_HIGH10','-DPGN_VERIFY_GAPS']
 if a.compiler:flags+=['-ccbin',a.compiler]
 if os.name=='nt':flags+=['-Xcompiler=/MT','-Xcompiler=/utf-8','-Xlinker=/MANIFEST:EMBED','-Xlinker=/MANIFESTINPUT:pgn68.manifest']
 else:flags+=['-Xlinker=-rpath','-Xlinker=$ORIGIN/../lib']
 with tempfile.TemporaryDirectory(prefix='scout-compat-source-')as stage:
  src=Path(stage)/'native';shutil.copytree(ROOT/'common960/native',src)
  if a.floor==954:shutil.copyfile(ROOT/'windows954/continuous-gpu-runtime.cu',src/'continuous-gpu-runtime.cu')
  subprocess.run([nvcc,*flags,'continuous-gpu-runtime.cu','-o',str(a.out)],cwd=src,check=True)
 print('Built source-review worker:',a.out)
