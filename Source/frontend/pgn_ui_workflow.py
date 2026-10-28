"""Pure UI policy. Backend snapshots own execution status; no worker/DB access."""
from copy import deepcopy
from decimal import Decimal

ACTIVE=frozenset(('STARTING','SEARCHING','PAUSING','STOP_REQUESTED'))
def phase(context):
    active=context.get('active_session') or context
    value=str(context.get('status') or active.get('status') or '').split('|',1)[0].strip().upper().replace(' ','_')
    if value=='RUNNING':return 'SEARCHING'
    if value=='STOPPED':return 'PAUSED'
    return value or ('SEARCHING' if active.get('job_active') else 'IDLE')

def new_defaults(context):
    override=context.get('_ui_state',{}).get('global_defaults_override')
    source=deepcopy(override if override is not None else context.get('global_defaults') or {})
    # Do not source settings from active/selected/pinned session configuration.
    cfg={'debug':False,'telemetry':False,'archive':False,'skip_self_test':False,'headless':False,'menu':False,'worker':None,'name':'Robert','profile':'auto','min_gap':'auto','count_gap':None,'detail_gap':None,'bins':100,'report_top':100,
         'display_rows':10,'target_merit':32,'gpu':context.get('gpu_index',0),'start':2*10**20,'length':10**15}
    cfg.update(source)
    for key in ('threshold_policy','threshold_binding','threshold_policy_sha256','session_id','resume'):
        cfg.pop(key,None)
    for key,raw in (('min_gap','min_gap_requested'),('count_gap','count_gap_requested'),('detail_gap','detail_gap_requested')):
        if raw in cfg:cfg[key]=cfg[raw]
    start=int(Decimal(str(cfg['start'])))
    end=int(Decimal(str(cfg['end']))) if cfg.get('end') is not None else start+int(Decimal(str(cfg.get('length') or 10**15)))
    cfg.update(start=start,end=end,length=end-start)
    return cfg

def set_global_defaults(context,configuration):
    cfg=deepcopy(configuration)
    for key in ('threshold_policy','threshold_binding','threshold_policy_sha256','resume','plan_id'):
        cfg.pop(key,None)
    for key,raw in (('min_gap','min_gap_requested'),('count_gap','count_gap_requested'),('detail_gap','detail_gap_requested')):
        if raw in cfg:cfg[key]=cfg[raw]
    context.setdefault('_ui_state',{})['global_defaults_override']=cfg
    context['global_defaults']=deepcopy(cfg)
    return cfg

def category(card):
    if card.get('kind')=='queued':return 'Queued'
    if card.get('kind')=='draft':return 'Ready'
    status=str(card.get('status','')).upper().replace(' ','_')
    if card.get('kind')=='current' and status in ACTIVE:return 'Processing'
    if status in ('PAUSED','STOPPED','SUSPENDED')or card.get('can_resume'):return 'Suspended'
    if status in ('COMPLETE','COMPLETED'):return 'Complete'
    if status in ('FAILED','ERROR'):return 'Failed'
    return 'Processing'

def primary(card,context):
    if not card:return {'label':'New range','enabled':True,'kind':'new_form','values':{}}
    if context.get('browser_only'):
        return {'label':'View / edit','enabled':True,'kind':'edit','values':{}}
    active=context.get('active_session') or {}
    if context.get('_ui_state',{}).get('pending_worker_request'):
        return {'label':'Working…','enabled':False,'reason':'A coordinator request is pending.'}
    if phase(context) in ('PAUSING','STOP_REQUESTED'):
        return {'label':'Pausing…','enabled':False,'reason':'Waiting for the safe Native boundary and checkpoint.'}
    kind=category(card);busy=phase(context)in ACTIVE
    if kind=='Processing':
        return {'label':'Open progress','enabled':True,'kind':'return','values':{}}
    if kind=='Suspended' and card.get('can_resume') and card.get('folder'):
        return {'label':'Switch & resume'if busy else'Resume','enabled':True,'kind':'resume','values':{'folder':card['folder']}}
    if kind=='Queued':
        folder=card.get('parent_folder')or active.get('folder')or context.get('folder')
        identity=card.get('parent_session_id')or active.get('session_id')or context.get('session_id')
        if not folder or not identity:return {'label':'Start queued','enabled':False,'reason':'Open its owning local session first.'}
        return {'label':'Switch to queued'if busy else'Start queued','enabled':True,'kind':'activate_queued',
                'values':{'parent_folder':str(folder),'parent_session_id':identity,'child_session_id':card['id']}}
    if kind=='Ready':
        return {'label':'Switch to range'if busy else'Start','enabled':True,'kind':'new','values':dict(card.get('configuration')or{}),'plan_id':card.get('id')if card.get('draft_source')=='local_saved'else None}
    return {'label':'View results','enabled':bool(card.get('can_results')),'kind':'results','values':{}}

def pause_control(context):
    status=phase(context)
    if context.get('_ui_state',{}).get('pending_worker_request'):return {'label':'Pausing…'if status=='PAUSING'else'Pending…','key':'p','shortcut':'P','enabled':False}
    if status in ('STARTING','SEARCHING'):return {'label':'Pause','key':'p','shortcut':'P','enabled':True}
    if status in ('PAUSING','STOP_REQUESTED'):return {'label':'Pausing…','key':'p','shortcut':'P','enabled':False}
    if status=='PAUSED':return {'label':'Resume','key':'p','shortcut':'P','enabled':True}
    if status=='IDLE' and context.get('resume_folder'):return {'label':'Resume','key':'p','shortcut':'P','enabled':True}
    return {'label':'Pause','key':'p','shortcut':'P','enabled':False}
