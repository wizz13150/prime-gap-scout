"""Release67..80 Python/Native threshold and checkpoint contract.
No Driver import. Native observations are bound by query_plan after execution.
Cross-low64 seams are intentionally NOT admitted by this first adapter.
"""
from pathlib import Path
import hashlib,json,re,struct
from pgn_threshold_policy import pin_range,verify_pin,at_position
PROTOCOL='PGN_NATIVE_GAP_RUNTIME_V1'
MODULE_SCHEMA='PGN_NATIVE_MODULE_METADATA_V1'
LOW=1<<66
HIGH=1<<80
MAX_GAP=2147483647
def admitted_range(start,end):
    start,end=int(start),int(end)
    if not LOW<=start<end<=HIGH:raise ValueError('Require2^66 <= START < END <=2^80 (67..80-bit range)')
    if start>>64!=(end-1)>>64:
        raise ValueError('UNPAID NATIVE SEAM: this worker accepts one low64 window. No positions were searched; split/bridge ownership and halo must be implemented before this crossing is admitted.')
    return start,end
def requested_gap(value):
    if str(value).strip().lower()=='auto':return 'auto'
    if isinstance(value,bool):raise ValueError('MIN_GAP is Auto or integer954..2147483647')
    text=str(value).strip()
    if not text.isdecimal() or not 954<=int(text)<=MAX_GAP:raise ValueError('MIN_GAP is Auto or integer954..2147483647')
    return int(text)
def override_gap(value):
    if value is None or value=='':return None
    gap=requested_gap(value)
    if gap=='auto':raise ValueError('COUNT_GAP/DETAIL_GAP are blank or integer954..2147483647')
    return gap
def fields(start,end,minimum='auto',count=None,detail=None,pin=None):
    start,end=admitted_range(start,end)
    if pin is None:pin=pin_range(start,end,requested_gap(minimum),override_gap(count),override_gap(detail))
    else:verify_pin(pin,start,end)
    if len(pin['segments'])!=1:raise ValueError('Bit-boundary Native adapter is unpaid; no partial launch is admitted')
    s=pin['segments'][0]
    for key in ('base_gap','count_gap','detail_gap','effective_gap_min'):
        if not 954<=int(s[key])<=MAX_GAP:raise ValueError('Pinned threshold exceeds Native integer domain')
    return {'native_protocol':PROTOCOL,'threshold_policy':pin,'min_gap_requested':pin['requested'],
            'count_gap_requested':pin['count_override'],'detail_gap_requested':pin['detail_override'],
            'min_gap':int(s['base_gap']),'count_gap':int(s['count_gap']),'detail_gap':int(s['detail_gap']),
            'effective_gap_min':int(s['effective_gap_min']),'emit_min_gap':min(int(s['count_gap']),int(s['detail_gap']))}
def resolve_args(args,end):
    pin=getattr(args,'_threshold_pin',None)
    minimum=getattr(args,'min_gap_requested',args.min_gap)
    count=getattr(args,'count_gap_requested',args.count_gap)
    detail=getattr(args,'detail_gap_requested',args.detail_gap)
    result=fields(args.start,end,minimum,count,detail,pin)
    for k,v in result.items():setattr(args,k,v)
    args._threshold_pin=result['threshold_policy']
    return result
def config_fields(args,end):
    resolve_args(args,end)
    return {k:getattr(args,k)for k in ('native_protocol','threshold_policy','min_gap_requested','count_gap_requested','detail_gap_requested','effective_gap_min')}
def reset_new_args(args,values):
    args._threshold_pin=values.get('threshold_policy')
    args.min_gap_requested=values.get('min_gap_requested',values.get('min_gap','auto'))
    args.count_gap_requested=values.get('count_gap_requested',values.get('count_gap'))
    args.detail_gap_requested=values.get('detail_gap_requested',values.get('detail_gap'))
    args.min_gap=args.min_gap_requested;args.count_gap=args.count_gap_requested;args.detail_gap=args.detail_gap_requested
def resume_args(args,configuration):
    require_new_configuration(configuration)
    args._threshold_pin=configuration['threshold_policy']
    for k in ('min_gap_requested','count_gap_requested','detail_gap_requested'):
        setattr(args,k,configuration[k])
def require_new_configuration(config):
    if config.get('native_protocol')!=PROTOCOL or not isinstance(config.get('threshold_policy'),dict):
        raise ValueError('Legacy session/checkpoint is preserved as read-only history. It cannot resume on the new dynamic-threshold worker; an explicit compatible migration is required.')
    f=fields(int(config['start']),int(config['end']),pin=config['threshold_policy'])
    for key in ('min_gap','count_gap','detail_gap'):
        if int(config[key])!=f[key]:raise ValueError('Saved scalar threshold differs from its frozen policy: '+key)
    for key in ('min_gap_requested','count_gap_requested','detail_gap_requested'):
        if config.get(key)!=f[key]:raise ValueError('Saved raw threshold request changed: '+key)
    return f
def magic(gap):
    gap=int(gap)
    if not 954<=gap<=MAX_GAP:raise ValueError('Invalid Native checkpoint gap')
    return b'PGNS'+struct.pack('<I',gap)
def checked_checkpoint(data,identity,position=None,tests=None):
    if len(data)!=64:raise ValueError('Native checkpoint must be exactly64 bytes')
    if identity.get('native_protocol')!=PROTOCOL:raise ValueError('Legacy checkpoint is history-only, not a dynamic-worker resume')
    m,low,high,length,p,t,last_low,last_high=struct.unpack('<8s7Q',data)
    start=int(identity['start'])
    if (m,low,high,length)!=(magic(identity['gap_min']),start&((1<<64)-1),start>>64,int(identity['length'])):
        raise ValueError('Checkpoint/input/effective-gap identity mismatch')
    if not 0<=p<=length or (position is not None and p!=int(position)) or (tests is not None and t!=int(tests)):
        raise ValueError('Checkpoint/progress identity mismatch')
    return p,t
def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb')as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest().upper()
def _digest(value):
    text=str(value).upper()
    if not re.fullmatch('[0-9A-F]{64}',text) or len(set(text))<2:raise ValueError('Missing/unpaid module fingerprint')
    return text
def module_metadata(worker):
    worker=Path(worker).resolve();sidecar=worker.with_name(worker.name+'.module.json')
    if not sidecar.is_file()or sidecar.stat().st_size>32768:raise ValueError('Missing/oversized portable module metadata: '+str(sidecar))
    m=json.loads(sidecar.read_text(encoding='utf-8'))
    if m.get('schema')!=MODULE_SCHEMA or m.get('gap_runtime_schema')!=PROTOCOL:raise ValueError('Unbound Native module metadata schema')
    m['image_sha256']=_digest(m.get('image_sha256'));m['source_manifest_sha256']=_digest(m.get('source_manifest_sha256'))
    if int(m.get('profile_k',0))not in (8,16,32,64) or int(m.get('build_arch',0))not in (86,120):raise ValueError('Invalid module profile/architecture metadata')
    if file_sha(worker)!=m['image_sha256']:raise ValueError('Native image differs from module metadata')
    return m
def bind_plan(raw,metadata,observed_sha,start,length,gap,pin=None):
    gap=int(gap);admitted_range(start,int(start)+int(length))
    if raw.get('schema')!='pgn-memory-plan-1' or raw.get('gap_runtime_schema')!=PROTOCOL:
        raise ValueError('Native plan lacks the actual dynamic-gap echo/schema; old worker plans are not admitted')
    if type(raw.get('gap_min'))is not int or raw['gap_min']!=gap:raise ValueError('Native actual gap_min echo mismatch')
    if int(raw.get('start',-1))!=int(start)or int(raw.get('length',-1))!=int(length):raise ValueError('Native plan input echo mismatch')
    if int(raw.get('profile_k',0))!=int(metadata['profile_k'])or int(raw.get('build_arch',0))!=int(metadata['build_arch']):
        raise ValueError('Native plan/image profile or architecture mismatch')
    if observed_sha!=metadata['image_sha256']:raise ValueError('Native image changed around plan execution')
    if type(raw.get('range_valid'))is not bool or type(raw.get('fits'))is not bool:raise ValueError('Native plan admission flags must be actual booleans')
    result=dict(raw);result.update(observed_worker_sha256=observed_sha,worker_source_sha256=metadata['source_manifest_sha256'])
    if pin is not None:
        segment=at_position(pin,start)
        if int(start)+int(length)>int(segment['end'])or gap!=segment['effective_gap_min']:raise ValueError('Native plan crosses or changes a pinned threshold segment')
        if not raw['range_valid'] or not raw['fits']:return result
        result.update(threshold_schema='PGN_THRESHOLD_BINDING_V1',threshold_policy_sha256=pin['sha256'])
        from pgn_threshold_policy import require_backend_binding
        binding=require_backend_binding(result,pin,start)
        binding.update(image_sha256=observed_sha,source_manifest_sha256=metadata['source_manifest_sha256'],native_protocol=PROTOCOL,profile_k=raw['profile_k'],build_arch=raw['build_arch'])
        result['threshold_binding']=binding
    return result

def rebase_pin(pin,start,end):
    import copy
    verify_pin(pin);start,end=admitted_range(start,end)
    if len(pin['segments'])!=1 or start.bit_length()!=pin['segments'][0]['bits'] or (end-1).bit_length()!=pin['segments'][0]['bits']:
        raise ValueError('A policy/bit seam requires an explicit new admitted range')
    p=copy.deepcopy(pin);p['start']=str(start);p['end']=str(end);p['segments'][0].update(start=str(start),end=str(end))
    p.pop('sha256',None);p['sha256']=hashlib.sha256(json.dumps(p,sort_keys=True,separators=(',',':')).encode()).hexdigest().upper()
    verify_pin(p,start,end);return p
