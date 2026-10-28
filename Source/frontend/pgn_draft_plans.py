"""Local prepared plans only: no session, mirror, queue or worker mutations."""
from pathlib import Path
from datetime import datetime,timezone
import copy,json,os,re,uuid

SCHEMA='PGN_LOCAL_DRAFT_PLANS_V1'


def location(context):
    from pgn_output import default_output_base
    target=Path(context['draft_plans_path']).expanduser().resolve() if context.get('draft_plans_path') else (Path(context.get('output_root') or default_output_base()).expanduser().resolve()/'.pgn68-draft-plans.json')
    if context.get('sessions_catalog'):
        mirror=Path(context['sessions_catalog']).resolve().parent
        if target==mirror or mirror in target.parents:raise ValueError('Saved-session mirrors are read-only. Choose a local results root for drafts.')
    return target


def load(context):
    path=location(context)
    if not path.exists():return []
    if path.stat().st_size>1048576:raise ValueError('Local draft plans file exceeds its 1 MiB limit.')
    value=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value,dict) or value.get('schema')!=SCHEMA or not isinstance(value.get('plans'),list):raise ValueError('Invalid local draft plans file.')
    plans=value['plans'];seen=set()
    for plan in plans:
        if not isinstance(plan,dict) or not isinstance(plan.get('configuration'),dict):raise ValueError('Invalid local draft record.')
        identity=plan.get('id','')
        if not isinstance(identity,str) or not re.fullmatch('[0-9a-f]{32}',identity) or identity in seen:raise ValueError('Invalid or duplicate local draft identity.')
        seen.add(identity);cfg=plan['configuration'];start,end=int(cfg['start']),int(cfg['end'])
        if not (1<<66)<=start<end<=(1<<80):raise ValueError('Local draft has an invalid67..80-bit range.')
    return plans


def publish(context,plans):
    path=location(context);path.parent.mkdir(parents=True,exist_ok=True)
    encoded=(json.dumps({'schema':SCHEMA,'plans':plans},sort_keys=True,indent=2)+'\n').encode('utf-8')
    if len(encoded)>1048576:raise ValueError('Local draft plans exceed the 1 MiB limit. Remove unused drafts first.')
    temporary=path.with_name(path.name+'.tmp-'+uuid.uuid4().hex)
    try:
        with temporary.open('xb') as stream:stream.write(encoded);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        if temporary.exists():temporary.unlink()
    context['saved_drafts']=copy.deepcopy(plans)


def save(context,configuration,identity=None):
    plans=load(context);now=datetime.now(timezone.utc).isoformat()
    if identity is not None and not re.fullmatch('[0-9a-f]{32}',identity):raise ValueError('Invalid local draft identity.')
    existing=next((plan for plan in plans if plan['id']==identity),None)
    if identity and existing is None:raise ValueError('This draft no longer exists. Create a new draft explicitly.')
    if existing is None:
        existing={'id':uuid.uuid4().hex,'created_utc':now};plans.append(existing)
    existing.update(configuration=copy.deepcopy(configuration),updated_utc=now)
    publish(context,plans);context['workspace_focus']=existing['id']
    context.setdefault('_ui_state',{}).setdefault('workspace',{})['focus_id']=existing['id']
    return existing['id']


def remove(context,identity):
    plans=load(context);remaining=[plan for plan in plans if plan['id']!=identity]
    if len(remaining)==len(plans):raise ValueError('This draft no longer exists.')
    publish(context,remaining)
