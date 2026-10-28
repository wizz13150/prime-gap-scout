"""Pure threshold policy data/verification. No worker or session is launched here."""
import hashlib,json
TABLE={67:954,68:960,69:982,70:994,71:1008,72:1022,73:1036,74:1050,75:1062,76:1076,77:1090,78:1104,79:1116,80:1130}
POLICY_ID='ROBERT_68_80_PLUS_EXTRAPOLATED67_954_V2'
def _sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest().upper()
def requested(value):
    if str(value).strip().lower()=='auto':return 'auto'
    if isinstance(value,bool):raise ValueError('MIN_GAP must be Auto or an integer >=954')
    n=int(value)
    if str(value).strip()!=str(n) or not 954<=n<=2147483647:raise ValueError('Manual MIN_GAP must be an integer954..2147483647')
    return n
def pin_range(start,end,value='auto',count_override=None,detail_override=None):
    start,end=int(start),int(end)
    if not start<end:raise ValueError('Increasing range required')
    value=requested(value)
    overrides=[requested(x) if x is not None else None for x in (count_override,detail_override)]
    if 'auto' in overrides:raise ValueError('COUNT/DETAIL override is an integer or blank, not Auto')
    segments=[];position=start
    while position<end:
        bits=position.bit_length()
        if bits not in TABLE:raise ValueError('Threshold table is scoped to67..80 bits')
        stop=min(end,1<<bits);base=TABLE[bits]if value=='auto'else value
        count=base if overrides[0]is None else overrides[0];detail=base if overrides[1]is None else overrides[1]
        segments.append({'start':str(position),'end':str(stop),'bits':bits,'base_gap':base,'count_gap':count,'detail_gap':detail,'effective_gap_min':min(base,count,detail)})
        position=stop
    pin={'schema':'PGN_THRESHOLD_POLICY_V1','policy_id':POLICY_ID,'requested':value,'count_override':overrides[0],'detail_override':overrides[1],
         'start':str(start),'end':str(end),'segments':segments}
    pin['sha256']=_sha(pin);return pin
def verify_pin(pin,start=None,end=None):
    body=dict(pin);digest=body.pop('sha256',None)
    if body.get('schema')!='PGN_THRESHOLD_POLICY_V1' or digest!=_sha(body):raise ValueError('Threshold policy pin changed')
    if start is not None and int(body['start'])!=int(start):raise ValueError('Threshold start changed')
    if end is not None and int(body['end'])!=int(end):raise ValueError('Threshold end changed')
    if not isinstance(body.get('segments'),list) or not 1<=len(body['segments'])<=14:raise ValueError('Invalid threshold segment count')
    cursor=int(body['start'])
    for segment in body['segments']:
        if int(segment['start'])!=cursor or not cursor<int(segment['end']) or cursor.bit_length()!=int(segment['bits']) or (int(segment['end'])-1).bit_length()!=int(segment['bits']):raise ValueError('Invalid threshold segment')
        if not 954<=int(segment['effective_gap_min'])<=2147483647 or int(segment['effective_gap_min'])!=min(int(segment[k])for k in ('base_gap','count_gap','detail_gap')):raise ValueError('Invalid effective threshold')
        cursor=int(segment['end'])
    if cursor!=int(body['end']):raise ValueError('Threshold coverage incomplete')
    # Deliberately DO NOT re-evaluate TABLE on resume: pinned values are authoritative.
    return pin
def at_position(pin,position):
    verify_pin(pin);position=int(position)
    for s in pin['segments']:
        if int(s['start'])<=position<int(s['end']):return s
    if position==int(pin['end']):return pin['segments'][-1]
    raise ValueError('Position outside threshold pin')
def require_backend_binding(plan,pin,position):
    segment=at_position(pin,position)
    if plan.get('threshold_policy_sha256')!=pin['sha256'] or plan.get('gap_min')!=segment['effective_gap_min'] or plan.get('threshold_schema')!='PGN_THRESHOLD_BINDING_V1':
        raise ValueError('Native threshold binding is absent or differs from the pinned segment')
    return {'schema':'PGN_THRESHOLD_BINDING_V1','policy_sha256':pin['sha256'],'segment_start':segment['start'],'segment_end':segment['end'],
            'gap_min':segment['effective_gap_min'],'verified':True}
def view(configuration,start,end,position=None,binding=None):
    cfg=configuration or {};pin=cfg.get('threshold_policy')
    if pin:verify_pin(pin,start,end)
    else:pin=pin_range(start,end,cfg.get('min_gap_requested',cfg.get('min_gap','auto')),
                      cfg.get('count_gap_requested') if 'count_gap_requested' in cfg else cfg.get('count_gap'),
                      cfg.get('detail_gap_requested') if 'detail_gap_requested' in cfg else cfg.get('detail_gap'))
    selected=at_position(pin,start if position is None else position)
    mode='Auto' if pin['requested']=='auto'else 'Manual'
    desired=f"{mode} >= {selected['effective_gap_min']}"
    actual=None
    if binding and binding.get('verified') and binding.get('schema')=='PGN_THRESHOLD_BINDING_V1' and binding.get('policy_sha256')==pin['sha256'] and binding.get('gap_min')==selected['effective_gap_min'] and binding.get('segment_start')==selected['start'] and binding.get('segment_end')==selected['end']:
        actual=int(binding['gap_min'])
    return {'requested':desired,'actual_gap_min':actual,'actual_label':f'Worker >= {actual}'if actual is not None else 'Worker threshold: not bound',
            'segment_count':len(pin['segments']),'bits':selected['bits'],'count_gap':selected['count_gap'],'pin':pin,
            'summary':desired+(' / '+str(len(pin['segments']))+' pinned segments'if len(pin['segments'])>1 else '')}

def safe_view(configuration,start,end,position=None,binding=None):
    try:return view(configuration,start,end,position,binding)
    except (ValueError,KeyError,TypeError,AttributeError) as error:
        cfg=configuration or {};minimum=cfg.get('count_gap',cfg.get('min_gap',TABLE[67]))
        try:minimum=int(minimum)
        except (ValueError,TypeError):minimum=TABLE[67]
        return {'requested':'Legacy / unavailable','actual_gap_min':None,'actual_label':'Worker threshold: not bound',
                'count_gap':minimum,'segment_count':0,'bits':None,'pin':None,'error':str(error),'summary':'Threshold policy needs admission'}
