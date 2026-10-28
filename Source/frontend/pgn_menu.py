"""UI8 three-choice menu; real saved sessions remain separate from controlled work."""
from dataclasses import dataclass,field
from decimal import Decimal,InvalidOperation
from pathlib import Path
import os,subprocess,sys
from pgn_input import key
from pgn_ui8_terminal import paint,cursor
from pgn_ui8_controller import refresh_context,search_page,sessions_page,files_page,catalog_sessions,event,diagnostics_page,display_settings_page

def render_main(context):
    from pgn_ui8_views import render_main as project
    return project(context)

@dataclass
class MenuAction:
    kind:str
    values:dict=field(default_factory=dict)

def integer(text):
    try:
        value=Decimal(str(text))
        if not value.is_finite() or value<0 or value.adjusted()>39 or value!=value.to_integral_value():raise ValueError
        return int(value)
    except (InvalidOperation,ValueError,TypeError,OverflowError):raise ValueError('Use an exact whole number such as2e20 or1e15') from None

def read_key(allowed,input_fn=input):
    if input_fn is not input:return input_fn('Choice: ').strip().lower()[:1]
    return key(allowed)

def open_local(path):
    path=Path(path).resolve()
    if not path.exists():raise FileNotFoundError(str(path))
    if os.name=='nt':os.startfile(str(path));return
    import shutil
    if os.environ.get('WSL_DISTRO_NAME') and shutil.which('explorer.exe'):
        translated=subprocess.run(['wslpath','-w',str(path)],capture_output=True,text=True,check=True).stdout.strip()
        subprocess.Popen(['explorer.exe',translated]);return
    subprocess.Popen(['xdg-open',str(path)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def prepare_context(context,preview=False):
    context['_menu_cursor_owned']=True
    context.setdefault('browser_only',preview)
    state=context.setdefault('_ui_state',{})
    for name in ('selected_session_id','prepared_request'):
        if name in state:context[name]=state[name]
    if not context.get('active_session') and not context.get('browser_only') and context.get('session_id'):
        context['active_session']={name:context.get(name) for name in ('session_id','status','start','end','position','tests','gpu_name','gpu_index','folder','next_range')}
        context['active_session']['job_active']=False  # owner drains before menu
    if not context.get('_parser_factory'):
        from pgn68 import argument_parser,validate_range
        context['_parser_factory']=argument_parser;context['_range_validator']=validate_range
    if not context.get('output_root') and context.get('folder'):context['output_root']=str(Path(context['folder']).parent)
    if not context.get('output_root') and not context.get('browser_only'):
        from pgn_output import default_output_base
        context['output_root']=str(default_output_base())
    if not context.get('launcher_path'):
        filename='Start-PGN68.cmd' if os.name=='nt' else 'Start-PGN68.sh'
        app=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
        for candidate in (app/filename,app/'package-common'/filename):
            if candidate.is_file():context['launcher_path']=str(candidate);break
    refresh_context(context)
    if context.get('selected_session_id'):state['selected_session_id']=context['selected_session_id']
    return context

def render_menu(context,preview=False):
    prepare_context(context,preview);paint(render_main(context))

def file_menu(context,preview=False,input_fn=input):
    prepare_context(context,preview);cursor(False)
    if context.get('session_id'):context['selected_session_id']=context['session_id']
    return sessions_page(context)

def show_files(context,preview=False):return file_menu(context,preview)

def startup_failure_menu(context):
    """The attempted card remains visible; Back never retries the backend."""
    from pgn_ui8_terminal import invalidate
    from pgn_input import TerminalInput
    prepare_context(context);invalidate();cursor(False)
    focus=context.get('prepared_request_saved_id') or 'parameter-draft'
    context['_ui_state'].setdefault('workspace',{})['focus_id']=focus
    with TerminalInput():return search_page(context)

def _menu(context,preview=False,input_fn=input):
    prepare_context(context,preview);cursor(False)
    try:
        while True:
            from pgn_interaction import focus_panel,pointer
            focus_panel('main');refresh_context(context);paint(render_main(context))
            pressed=event() if input_fn is input else input_fn('')
            state=context['_ui_state'];focus=state.get('main_focus',0)
            routed=pointer()
            if routed is not None and routed.target=='main' and routed.key=='SCROLL':
                state['main_focus']=max(0,min(2,focus+int(routed.dy)))
                continue
            if routed is not None and routed.target=='main' and routed.index is not None and routed.key!='HOVER':
                focus=max(0,min(2,int(routed.index)));state['main_focus']=focus
            if pressed in ('UP','DOWN'):
                state['main_focus']=(focus+(-1 if pressed=='UP' else 1))%3
                continue
            selected=str(focus+1) if pressed=='ENTER' else str(pressed)
            if selected in ('ESC','0'):return MenuAction('return')
            if selected in ('1','2','3'):state['main_focus']=int(selected)-1
            if selected=='1':
                action=search_page(context)
                if action:return action
            elif selected=='2':
                action=sessions_page(context)
                if action:return action
            elif selected=='3':diagnostics_page(context)
    finally:
        if not context.get('browser_only'):cursor(True)

def menu(context,preview=False,input_fn=input):
    from pgn_ui8_terminal import invalidate
    invalidate()
    if input_fn is not input:return _menu(context,preview,input_fn)
    from pgn_input import TerminalInput
    with TerminalInput():return _menu(context,preview,input_fn)


def final_screen_text(context):
    return ('PGN 68 | LAST RESULTS\nSession: '+str(context.get('session_id','--'))+'\nStatus: '+str(context.get('status','--'))+
            '\nRange: '+str(context.get('start','--'))+' -> '+str(context.get('end','--'))+
            '\nCompleted positions: '+str(context.get('position','--'))+'\nPRP tests: '+str(context.get('tests','--'))+
            '\nOutput: '+str(context.get('folder','--'))+'\n[M] Menu  [F] Files  [Q] Quit\n')
