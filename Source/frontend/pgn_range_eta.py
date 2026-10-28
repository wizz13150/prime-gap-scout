"""Shared, evidence-only range ETA. No GPU query and no assumed fallback rate."""
from decimal import Decimal,InvalidOperation
from pathlib import Path
import datetime as dt,hashlib,math,re

SCHEMA='PGN_MEASURED_RANGE_RATE_V1'
MAX_AGE_SECONDS=7*86400
_hash_cache={}


def _integer(value):
    number=Decimal(str(value))
    if not number.is_finite() or number!=number.to_integral_value() or number<0 or number.adjusted()>39:raise ValueError()
    return int(number)


def _utc(value):
    result=dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if result.tzinfo is None:raise ValueError()
    return result.astimezone(dt.timezone.utc)


def _filters(config):
    minimum=int(config.get('min_gap',960))
    def threshold(name):
        value=config.get(name)
        return minimum if value in (None,'') else int(value)
    values=(minimum,threshold('count_gap'),threshold('detail_gap'))
    if not all(800<=value<=4294967295 for value in values):raise ValueError()
    # Native emits the lower of the count/detail thresholds; MIN alone is
    # display/configuration policy when explicit overrides keep this floor.
    return (min(values[1:]),values[1],values[2])


def measurement(*,gpu_uuid,worker_sha256,profile_k,configuration,positions,seconds,observed_utc,source,closed=False,driver_api=None):
    """Only the Native counter/ProcessClock producer calls this constructor."""
    try:
        positions=int(positions);seconds=float(seconds);profile_k=int(profile_k);stamp=_utc(observed_utc)
        if not gpu_uuid or not re.fullmatch('[0-9A-Fa-f]{64}',str(worker_sha256)):return None
        if profile_k not in (8,16,32,64) or positions<=0 or not math.isfinite(seconds) or seconds<1:return None
        minimum,count,detail=_filters(configuration)
        return {'schema':SCHEMA,'provenance':'owned_native_counters_and_process_clock','gpu_uuid':str(gpu_uuid),
                'worker_sha256':str(worker_sha256).upper(),'profile_k':profile_k,'domain':'H10','engine':'walk',
                'filters':[minimum,count,detail],'positions':positions,'seconds':seconds,'observed_utc':stamp.isoformat(),
                'source':str(source),'closed':bool(closed),'driver_api':driver_api,'configured_profile':str(configuration.get('profile','auto')),
                'scope':'active worker wall; initialization included'}
    except (ValueError,TypeError,InvalidOperation,OverflowError):return None


def retain(history,sample):
    if sample is None:return list(history or [])[-12:]
    key=(sample['gpu_uuid'],sample['worker_sha256'],tuple(sample['filters']))
    previous=next((item for item in (history or []) if (item.get('gpu_uuid'),item.get('worker_sha256'),tuple(item.get('filters',())))==key),None)
    if previous and str(previous.get('observed_utc',''))>=str(sample.get('observed_utc','')):return list(history)[-12:]
    kept=[item for item in (history or []) if (item.get('gpu_uuid'),item.get('worker_sha256'),tuple(item.get('filters',())))!=key]
    return (kept+[sample])[-12:]


def saved_session_measurement(session):
    """Adapt an existing authentic saved identity/clock scope, not a guessed rate."""
    try:
        metadata=session.metadata;run=session.run;config=session.configuration
        if run.get('status')!='COMPLETE' or run.get('failure') or run.get('current_worker_wall_unknown'):return None
        chunks=metadata.get('closed_chunks') or []
        if not chunks or len(chunks)!=metadata.get('completed_chunk_count',len(chunks)):return None
        identities=[item['identity'] for item in chunks]
        if any(not (item.get('instance') or {}).get('closed') for item in chunks):return None
        bindings={(item['worker_sha256'].upper(),int(item['profile_k'])) for item in identities}
        if len(bindings)!=1:return None
        image,profile=bindings.pop();gpu=(run.get('selected_gpu') or {}).get('uuid')
        if not gpu or gpu!=(metadata.get('device') or {}).get('uuid'):return None
        positions=int(run['positions'])
        if run.get('timing_complete') is not True:
            if run.get('rate_scope')!='SINCE_RESUME' or 'rate_origin_position' not in metadata:return None
            positions-=int(metadata['rate_origin_position'])
        report=Path(session.folder)/('GapReport_details_ge'+str(config.get('detail_gap',config.get('min_gap',960)))+'.txt')
        if not report.is_file() or report.stat().st_size>1024*1024:return None
        with report.open('rb') as stream:header=stream.read(4096).decode('utf-8',errors='strict')
        match=re.search(r'^End time:\s*(.+)$',header,re.MULTILINE)
        if match is None:return None
        return measurement(gpu_uuid=gpu,worker_sha256=image,profile_k=profile,configuration=config,positions=positions,
                           seconds=run['active_seconds'],observed_utc=match[1].strip(),source='saved session '+session.session_id,
                           closed=True,driver_api=(run.get('selected_gpu') or {}).get('cuda_driver_api_version',(run.get('selected_gpu') or {}).get('driver_version')))
    except (ValueError,TypeError,KeyError,OSError,UnicodeError):return None


def _file_hash(path):
    path=Path(path);stat=path.stat()
    if not path.is_file() or not 0<stat.st_size<=128*1024*1024:return None
    key=(str(path.resolve()),stat.st_size,stat.st_mtime_ns)
    if key not in _hash_cache:
        value=hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):value.update(block)
        _hash_cache.clear() if len(_hash_cache)>16 else None
        _hash_cache[key]=value.hexdigest().upper()
    return _hash_cache[key]


def _duration(value):
    seconds=max(1,math.ceil(value));days,seconds=divmod(seconds,86400);hours,seconds=divmod(seconds,3600);minutes,seconds=divmod(seconds,60)
    if days:return f'{days}d {hours}h'
    if hours:return f'{hours}h {minutes}m'
    if minutes:return f'{minutes}m {seconds}s'
    return f'{seconds}s'


def unavailable(reason):return {'available':False,'label':'ETA unavailable','short_label':'ETA unavailable','reason':reason,'seconds':None}


def estimate(start,end,configuration,context,now=None):
    """Same function for live editor text and every prepared range card."""
    try:
        start,end=_integer(start),_integer(end)
        if not (10<<64)+20<=start<end<(11<<64):return unavailable('Enter a valid supported H10 range.')
        if end>(11<<64)-4*1006632960:return unavailable('This edge requires exact Native halo admission before ETA.')
        evidence=context.get('eta_evidence') or {};gpu=evidence.get('gpu_uuid') or context.get('gpu_uuid')
        choice=configuration.get('gpu') if 'gpu' in configuration else configuration.get('gpu_index')
        selected=int(0 if choice in (None,'') else choice)
        current_index=context.get('gpu_index')
        if current_index in (None,''):current_index=evidence.get('gpu_index',0)
        if not gpu or selected!=int(current_index or 0):return unavailable('No measured rate for this selected GPU.')
        profile=str(configuration.get('profile','auto'));identity=context.get('native_identity') or {}
        if profile not in ('auto','8','16','32','64'):return unavailable('Choose a valid Native profile before ETA.')
        actual=int(profile) if profile!='auto' else identity.get('profile_k') or evidence.get('profile_hint')
        if actual is None and profile=='auto':
            known=[item for item in evidence.get('history',[]) if item.get('gpu_uuid')==gpu and item.get('configured_profile')=='auto' and tuple(item.get('filters',()))==_filters(configuration)]
            if known:actual=max(known,key=lambda item:str(item.get('observed_utc','')))['profile_k']
        if actual not in (8,16,32,64):return unavailable('The actual Native profile is not resolved yet.')
        image=None
        if configuration.get('worker'):image=_file_hash(configuration['worker'])
        else:
            path=(evidence.get('worker_paths') or {}).get(str(actual))
            if path:image=_file_hash(path)
            elif identity.get('profile_k')==actual:image=identity.get('worker_sha256')
        if not image:
            path=(evidence.get('worker_paths') or {}).get(str(actual))
            if path:image=_file_hash(path)
        if not image:return unavailable('No authenticated worker image is available for comparison.')
        current=evidence.get('current');candidates=[(current,True)] if current else []
        candidates.extend((item,False) for item in evidence.get('history',[]) if item.get('closed'))
        clock=now or dt.datetime.now(dt.timezone.utc);matches=[]
        for item,live in candidates:
            if not item or item.get('schema')!=SCHEMA or item.get('provenance')!='owned_native_counters_and_process_clock':continue
            if item.get('gpu_uuid')!=gpu or item.get('worker_sha256','').upper()!=str(image).upper() or item.get('profile_k')!=actual:continue
            if item.get('domain')!='H10' or item.get('engine')!='walk' or tuple(item.get('filters',()))!=_filters(configuration):continue
            if evidence.get('driver_api') is not None and item.get('driver_api') is not None and item['driver_api']!=evidence['driver_api']:continue
            age=(clock-_utc(item['observed_utc'])).total_seconds()
            seconds=float(item['seconds']);positions=int(item['positions'])
            if age<0 or age>MAX_AGE_SECONDS or seconds<1 or positions<=0 or not math.isfinite(seconds):continue
            matches.append((age,not live,item))
        if not matches:return unavailable('No recent comparable measured rate is available.')
        age,_,sample=min(matches,key=lambda row:(row[1],row[0]));rate=sample['positions']/sample['seconds'];seconds=(end-start)/rate
        age_text=_duration(age) if age>=1 else '0s';source='live' if sample is current else 'last run'
        assumption=f'auto must keep K{actual}' if profile=='auto' else ''
        return {'available':True,'seconds':seconds,'rate':rate,'positions':end-start,'source':sample['source'],'age_seconds':age,
                'observed_utc':sample['observed_utc'],'worker_sha256':sample['worker_sha256'],'profile_k':actual,
                'label':f'~ ETA {_duration(seconds)} · {source}, {age_text} old'+(' · '+assumption if assumption else ''),
                'short_label':f'~{_duration(seconds)} · {source}, {age_text}','reason':None,'assumption':assumption,
                'scope':'Active worker time estimate; pauses and frontend work excluded.'}
    except (ValueError,TypeError,KeyError,InvalidOperation,OverflowError,OSError,ZeroDivisionError):return unavailable('Incomplete range or missing comparable measurement.')


def estimate_values(values,range_mode,context,now=None):
    try:
        start=_integer(values.get('START',''))
        end=_integer(values.get('END','')) if range_mode=='END' else start+_integer(values.get('LENGTH',''))
        config={key.lower():value for key,value in values.items()}
        return estimate(start,end,config,context,now)
    except (ValueError,TypeError,InvalidOperation,OverflowError):return unavailable('Complete Start and Length or End to estimate.')
