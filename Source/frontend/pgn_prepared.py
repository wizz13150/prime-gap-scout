"""Crash-idempotent explicit NEW before any worker has ever started.

The old immutable configuration is never rewritten. A journalled plan binds a
new session ID and sibling folder before creation; old resume redirects to it.
"""
from pathlib import Path
import copy,hashlib,json,re,uuid
from pgn_session import SessionStore,SessionControllerLock


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def _check_idle(store):
    if int(store.meta.get('positions',0)) or store.meta.get('current_chunk') or store.meta.get('completed_chunk_count',0) or len(store.gaps):
        raise ValueError('This session has started. Use the explicit safe NEW transition instead of editing its configuration.')


def _validate(store,plan):
    identity=plan.get('session_id','')
    if not isinstance(identity,str) or re.fullmatch(r'[0-9a-f]{32}',identity) is None:raise ValueError('Invalid prepared replacement identity')
    expected=(store.folder.parent/('pgn68-prepared-'+identity)).resolve()
    if expected.parent!=store.folder.parent.resolve() or Path(plan.get('folder','')).resolve()!=expected:raise ValueError('Prepared replacement escaped its results root')
    payload={key:value for key,value in plan.items() if key!='sha256'}
    if digest(payload)!=plan.get('sha256'):raise ValueError('Prepared replacement binding changed')
    config=plan['configuration'];start,end=int(config['start']),int(config['end'])
    if not (10<<64)<=start<end<(11<<64) or (start&((1<<64)-1))<20:raise ValueError('Prepared replacement is outside H10 origin bounds')
    if plan.get('next_range') and end!=int(store.meta['configuration']['end']):raise ValueError('Changing the current end would move queued plans. Remove the queue explicitly first.')
    return expected


def recover_prepared_replacement(store):
    plan=store.meta.get('prepared_replacement')
    if not plan:return None
    _check_idle(store);folder=_validate(store,plan)
    folder.mkdir(parents=False,exist_ok=True)
    lock=SessionControllerLock(folder)
    target=None
    try:
        if SessionStore.exists(folder):
            target=SessionStore.load(folder)
            if target.meta['session_id']!=plan['session_id'] or target.configuration_hash()!=digest(plan['configuration']) or target.meta['device']!=plan['device']:
                raise ValueError('Existing prepared replacement does not match its durable plan')
        else:target=SessionStore.create(folder,copy.deepcopy(plan['configuration']),copy.deepcopy(plan['device']),session_id=plan['session_id'])
        incoming=copy.deepcopy(plan.get('next_range') or {})
        if incoming:incoming['parent_session_id']=target.meta['session_id']
        existing=target.meta.get('next_range') or {}
        committed=target.meta.get('prepared_from')
        if committed not in (None,store.meta['session_id']):raise ValueError('Prepared replacement belongs to another session')
        if committed is None:
            if existing and existing!=incoming:raise ValueError('Prepared replacement queue changed unexpectedly')
            if incoming and not existing:
                target.append('next_range',entry=incoming);target.meta['next_range']=copy.deepcopy(incoming)
        target.meta['prepared_from']=store.meta['session_id'];target.save()
        if store.meta.get('next_range'):
            store.append('next_range',entry={});store.meta['next_range']={}
        store.meta['replaced_by']={'session_id':plan['session_id'],'folder':str(folder)}
        store.closed('REPLACED_BEFORE_START',0,0)
        return folder
    finally:
        if target:target.close()
        lock.release()


def replace_prepared(store,configuration,device):
    _check_idle(store)
    if store.meta.get('prepared_replacement'):return recover_prepared_replacement(store)
    from pgn_queue import pending_ranges
    if any((Path(entry['folder'])/'session.json').exists() for entry in pending_ranges(store)):
        raise ValueError('A queued child already exists; this prepared session cannot be replaced.')
    identity=uuid.uuid4().hex
    plan={'session_id':identity,'folder':str(store.folder.parent/('pgn68-prepared-'+identity)),
          'configuration':copy.deepcopy(configuration),'device':copy.deepcopy(device),'next_range':copy.deepcopy(store.meta.get('next_range') or {})}
    plan['sha256']=digest(plan);_validate(store,plan)
    store.append('prepared_replacement',plan=plan);store.meta['prepared_replacement']=plan;store.save()
    return recover_prepared_replacement(store)
