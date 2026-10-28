from pgn_terminal_input import terminal_size
"""Small real terminal editor: immediate Esc, no input() cancellation trap."""
import os
import sys
import threading


from pgn_terminal_input import TerminalInput as _TerminalInput,InputCancelled
from pgn_interaction import translate,focus_panel,pointer

_reader_lock=threading.RLock()
_physical_reader=None
_reader_leases=0
_read_lock=threading.Lock()
_input_shutdown=threading.Event()


class _Cancellation:
    def __init__(self,page):self.page=page
    def is_set(self):return _input_shutdown.is_set() or bool(self.page and self.page.is_set())
    def wait(self,timeout):
        if self.is_set():return True
        _input_shutdown.wait(timeout)
        return self.is_set()


class TerminalInput:
    """Borrow one physical input reader across UI threads and nested pages.

    The application's outer scope owns the mode lifetime. Main-menu helpers,
    dashboard keys and the menu thread take leases without changing modes or
    losing queued input. Reading is exclusive; no second consumer can drain it.
    """
    def __init__(self):self._reader=None;self._entered=False;self._owner=False
    def __enter__(self):
        global _physical_reader,_reader_leases
        if self._entered:raise RuntimeError('Terminal lease already entered')
        with _reader_lock:
            if _physical_reader is None:
                candidate=_TerminalInput();candidate.__enter__();_physical_reader=candidate
                _input_shutdown.clear()
                self._owner=True
            self._reader=_physical_reader;_reader_leases+=1;self._entered=True
        return self
    def __exit__(self,*args):
        global _physical_reader,_reader_leases
        if not self._entered:return
        with _reader_lock:
            reader=self._reader;self._entered=False;self._reader=None
            if reader is not _physical_reader:return
            _reader_leases-=1
            if self._owner or _reader_leases==0:
                closing=_physical_reader;_physical_reader=None
                _reader_leases=0
                _input_shutdown.set()
                # The low-level reader polls cancellation in bounded intervals;
                # restore modes only after an active page read has unwound.
                locked=_read_lock.acquire(timeout=.5)
                try:
                    if closing:closing.__exit__(*args)
                finally:
                    if locked:_read_lock.release()
                if not locked:raise RuntimeError('Terminal input did not relinquish its outer scope')
    def read(self,timeout=.2,cancel=None):
        from pgn_ui_service import current_cancel,MenuCancelled
        if self._reader is None or self._reader is not _physical_reader:raise RuntimeError('Terminal reader needs an active owning scope')
        if not _read_lock.acquire(blocking=False):
            raise RuntimeError('Another UI page already owns the terminal read')
        try:
            if self._reader is not _physical_reader:raise RuntimeError('Terminal reader needs an active owning scope')
            try:return translate(self._reader.read(timeout=timeout,cancel=_Cancellation(cancel or current_cancel())))
            except InputCancelled:raise MenuCancelled() from None
        finally:_read_lock.release()


def clear_page():
    if sys.stdout.isatty():
        from pgn_ui8_terminal import enable_vt
        if enable_vt():print('\x1b[2J\x1b[H',end='',flush=True)
        else:
            from rich.console import Console
            Console().clear(home=True)


def key(allowed,events=None):
    if events is not None:
        value=next(events)
        return '0' if value=='ESC' else value.lower()
    with TerminalInput() as reader:
        while True:
            value=reader.read()
            if value=='ESC':return '0'
            if value.lower() in allowed:return value.lower()


def form(title,fields,validate,*,events=None,context=None):
    """fields=(key,label,initial,help). Esc cancels from ANY text field."""
    values={name:str(initial) for name,label,initial,help_text in fields}
    focus=0;cursor=len(values[fields[0][0]])
    def draw():
        clear_page()
        errors=[]
        result=None
        try:result=validate(values)
        except (ValueError,TypeError) as error:errors=[str(error)]
        display=[]
        import shutil
        available=max(12,terminal_size(fallback=(100,30)).columns-36)
        for i,(name,label,initial,help_text) in enumerate(fields):
            text=values[name]
            if name=='end' and not text and values.get('length') and values.get('start'):
                try:
                    from decimal import Decimal
                    text=str(int(Decimal(values['start']))+int(Decimal(values['length'])))+' (AUTO from LENGTH)'
                except (ValueError,ArithmeticError):pass
            if i==focus:
                left=max(0,cursor-available+1);right=left+available
                text=('...' if left else '')+text[left:cursor]+'▏'+text[cursor:right]
            display.append((name,label,text,help_text))
        try:
            from rich.console import Console
            from pgn_ui8_views import render_form
            from pgn_ui8_terminal import paint
            summary={}
            if isinstance(result,dict):
                for name in ('start','end','length','min_gap','gpu'):
                    if name in result:summary[name.replace('_',' ').title()]=str(result[name])
            paint(render_form(title,display,focused=focus,error=errors[0] if errors else None,
              preview={'context':context or {},'summary':summary}))
            return
        except ImportError:pass
        print('PGN 68  >  '+title+'\n')
        for i,(name,label,initial,help_text) in enumerate(fields):
            marker='>' if i==focus else ' '
            print(f'{marker} {label:<20} {values[name]}\r')
            if i==focus:print('  '+help_text+'\r')
        print('\r\n'+('Check: '+errors[0] if errors else 'Ready: Enter on the final field continues.')+'\r')
        print('\r\n[Esc Back]  [Tab / Up / Down: field]  [Enter: commit/next]  [Ctrl+U: clear]\r',flush=True)
    reader=TerminalInput() if events is None else None
    if reader:reader.__enter__()
    if sys.stdout.isatty():
        from pgn_ui8_terminal import cursor as terminal_cursor
        terminal_cursor(False)
    try:
        while True:
            focus_panel('form');draw();event=reader.read() if reader else next(events)
            routed=pointer()
            if routed is not None and routed.target=='form' and routed.index is not None:
                focus=max(0,min(len(fields)-1,int(routed.index)));cursor=len(values[fields[focus][0]])
            name=fields[focus][0];text=values[name]
            if event=='ESC':return None
            if event in ('TAB','DOWN','UP'):
                focus=(focus+(-1 if event=='UP' else 1))%len(fields);cursor=len(values[fields[focus][0]])
            elif event=='ENTER':
                if focus<len(fields)-1:focus+=1;cursor=len(values[fields[focus][0]])
                else:
                    try:
                        import inspect
                        return validate(values,commit=True) if 'commit' in inspect.signature(validate).parameters else validate(values)
                    except (ValueError,TypeError):pass
            elif event=='LEFT':cursor=max(0,cursor-1)
            elif event=='RIGHT':cursor=min(len(text),cursor+1)
            elif event=='HOME':cursor=0
            elif event=='END':cursor=len(text)
            elif event=='CLEAR':values[name]='';cursor=0
            elif event=='BACKSPACE' and cursor:values[name]=text[:cursor-1]+text[cursor:];cursor-=1
            elif event=='DELETE':values[name]=text[:cursor]+text[cursor+1:]
            elif len(event)==1 and event.isprintable():values[name]=text[:cursor]+event+text[cursor:];cursor+=1
    finally:
        if reader:reader.__exit__(None,None,None)
        if sys.stdout.isatty() and not (context or {}).get('_menu_cursor_owned'):
            from pgn_ui8_terminal import cursor as terminal_cursor
            terminal_cursor(True)
