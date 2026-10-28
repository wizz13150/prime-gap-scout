from pgn_terminal_input import terminal_size
"""Console presentation only: enable VT before ANSI, no trailing prompt line."""
import ctypes
import io
import os
import re
import sys

_vt=None
_last_frame=None
_last_caret=None
_cursor_visible=None
_caret_style_owned=False
_native_cursor_saved=None


def invalidate():
    global _last_frame
    _last_frame=None


def enable_vt():
    global _vt
    if _vt is not None:return _vt
    if not sys.stdout.isatty():_vt=False;return False
    if os.name!='nt':_vt=os.environ.get('TERM')!='dumb';return _vt
    import msvcrt
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.GetConsoleMode.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint)]
    k.SetConsoleMode.argtypes=[ctypes.c_void_p,ctypes.c_uint]
    handle=msvcrt.get_osfhandle(sys.stdout.fileno());mode=ctypes.c_uint()
    _vt=bool(k.GetConsoleMode(handle,ctypes.byref(mode)) and k.SetConsoleMode(handle,mode.value|4))
    return _vt


def cursor(visible):
    global _cursor_visible,_last_caret,_caret_style_owned
    if not sys.stdout.isatty():return
    _last_caret=None
    if enable_vt():
        reset='\x1b[0 q' if visible and _caret_style_owned else ''
        if reset:_caret_style_owned=False
        sys.stdout.write(reset+('\x1b[?25h' if visible else '\x1b[?25l'));sys.stdout.flush()
    elif not _native_caret(None,visible=visible):
        from rich.console import Console
        Console().show_cursor(visible)
    _cursor_visible=bool(visible)


def _native_caret(position,*,visible):
    """Legacy Windows fallback: use the console cursor, never a fake glyph.

    Blink cadence remains controlled by the terminal/OS. No system preference
    or global cursor setting is changed. VT is preferred on modern hosts.
    """
    global _native_cursor_saved
    if os.name!='nt':return False
    try:
        import msvcrt
        from ctypes import wintypes
        class Info(ctypes.Structure):
            _fields_=[('size',wintypes.DWORD),('visible',wintypes.BOOL)]
        class Coord(ctypes.Structure):
            _fields_=[('x',ctypes.c_short),('y',ctypes.c_short)]
        k=ctypes.WinDLL('kernel32',use_last_error=True);handle=msvcrt.get_osfhandle(sys.stdout.fileno())
        k.GetConsoleCursorInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(Info)]
        k.SetConsoleCursorInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(Info)]
        k.SetConsoleCursorPosition.argtypes=[ctypes.c_void_p,Coord]
        from pgn_terminal_input import _SCREEN_INFO
        k.GetConsoleScreenBufferInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(_SCREEN_INFO)]
        old=Info()
        if not k.GetConsoleCursorInfo(handle,ctypes.byref(old)):return False
        if position is not None and _native_cursor_saved is None:_native_cursor_saved=(handle,old.size)
        size=25 if position is not None else (_native_cursor_saved[1] if _native_cursor_saved else old.size)
        info=Info(size,bool(visible))
        if not k.SetConsoleCursorInfo(handle,ctypes.byref(info)):return False
        if position is not None:
            screen=_SCREEN_INFO()
            if not k.GetConsoleScreenBufferInfo(handle,ctypes.byref(screen)):return False
            absolute=Coord(position[0]+screen.window.Left,position[1]+screen.window.Top)
            if not k.SetConsoleCursorPosition(handle,absolute):return False
        if position is None:_native_cursor_saved=None
        return True
    except (OSError,ValueError,AttributeError):return False


def paint_caret(caret,width,height,*,vt=None):
    """Honor renderer-provided zero-based terminal cells after frame paint.

    A caret-only move writes a position command; it never repaints the frame.
    With no editable field, the terminal cursor stays hidden in menus.
    """
    global _last_caret,_cursor_visible,_caret_style_owned
    if not sys.stdout.isatty():return
    valid=isinstance(caret,dict) and bool(caret.get('visible'))
    x=caret.get('x') if valid else None;y=caret.get('y') if valid else None
    valid=valid and type(x)is int and type(y)is int and 0<=x<width and 0<=y<height
    signature=(id(sys.stdout),x,y,bool(caret.get('blink',True))) if valid else (id(sys.stdout),False)
    if signature==_last_caret:return
    vt=enable_vt() if vt is None else vt
    if not valid:
        if vt:
            output=('\x1b[0 q' if _caret_style_owned else '')+('\x1b[?25l' if _cursor_visible is not False else '')
            if output:sys.stdout.write(output);sys.stdout.flush()
            _caret_style_owned=False
        else:_native_caret(None,visible=False)
        _cursor_visible=False;_last_caret=signature;return
    if vt:
        blink=bool(caret.get('blink',True))
        style='' if _caret_style_owned and _last_caret and _last_caret[-1]==blink else ('\x1b[5 q' if blink else '\x1b[6 q')
        sys.stdout.write(style+f'\x1b[{y+1};{x+1}H\x1b[?25h');sys.stdout.flush();_caret_style_owned=True
    elif not _native_caret((x,y),visible=True):
        # A host lacking both VT and native cursor positioning keeps the normal
        # keyboard editor. Do not simulate blink with repaint timers or glyphs.
        return
    _cursor_visible=True;_last_caret=signature



def back_button_regions(rendered_text,width,height,existing=()):
    """Fallback for legacy footers; current views publish their own Back rect.

    Derive coordinates from actual rendered cells. Never invent a fixed position
    or install a duplicate on top of the new explicit key=ESC button.
    """
    from pgn_terminal_input import HitRegion,Rect
    if any(region.key in ('ESC','0') for region in existing):return []
    from rich.cells import cell_len
    clean=re.sub(r'\x1b\][^\x07]*(?:\x07|\x1b\\)','',rendered_text)
    clean=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',clean)
    lines=clean.splitlines()[:height]
    # Only a footer is eligible: body text mentioning Back is not a button.
    for y in range(len(lines)-1,max(-1,len(lines)-5),-1):
        for label in ('[Esc Back]','[ Back ]','‹ Back'):
            start=lines[y].find(label)
            if start>=0:
                x=cell_len(lines[y][:start]);length=min(cell_len(label),width-x)
                if 0<=x<width and length>0:
                    return [HitRegion(Rect(x,y,length,1),'footer',key='ESC')]
    return []


def paint(renderable):
    global _last_frame
    from rich.console import Console
    from pgn_terminal_input import HitMap,HitRegion,Rect,set_hit_map
    set_hit_map(HitMap(0,0))
    vt=enable_vt()
    import shutil
    viewport=getattr(renderable,'pgn_viewport',None)
    if viewport is None:viewport=terminal_size(fallback=(120,36))
    width,height=int(viewport[0]),int(viewport[1])
    # One measured viewport drives projection, pixels, hit regions and caret.
    console=Console(file=sys.stdout,width=width,height=height,force_terminal=vt,color_system='truecolor' if vt and 'NO_COLOR' not in os.environ else None,legacy_windows=False)
    with console.capture() as capture:console.print(renderable,end='')
    text=capture.get()
    if vt:
        # Layout itself may emit a last line; remove only final line breaks,
        # preserving color resets. No extra prompt/cursor row is emitted.
        text=re.sub(r'(?:\r?\n)+(?=(?:\x1b\[[0-9;]*m)*$)','',text)
        frame=(text,console.size.width,console.size.height,id(sys.stdout))
        if frame!=_last_frame:
            cursor(False)
            if _last_frame is None or frame[1:]!=_last_frame[1:]:
                output='\x1b[2J\x1b[H'+text
            else:
                previous=_last_frame[0].splitlines();current=text.splitlines();parts=[]
                for row in range(max(len(previous),len(current))):
                    before=previous[row] if row<len(previous) else ''
                    after=current[row] if row<len(current) else ''
                    if before!=after:parts.append(f'\x1b[{row+1};1H\x1b[0m\x1b[2K'+after)
                output=''.join(parts)
            sys.stdout.write(output);sys.stdout.flush();_last_frame=frame
    else:
        console.clear(home=True)
        sys.stdout.write(text);sys.stdout.flush()

    # Root's frame regions are computed by the same renderer as the pixels.
    regions=[]
    for item in getattr(renderable,'pgn_hit_regions',[]):
        regions.append(HitRegion(Rect(int(item['x']),int(item['y']),int(item['width']),int(item['height'])),
            item.get('target',''),index=item.get('index'),key=item.get('key','ENTER'),
            disabled=bool(item.get('disabled',False)),scrollable=bool(item.get('scrollable',False))))
    from pgn_interaction import focused_panel
    if focused_panel()=='report' and getattr(renderable,'children',None):
        mapped=getattr(renderable,'render_map',{}).get(renderable.children[1]) if len(renderable.children)>1 else None
        if mapped:
            region=mapped.region
            regions.insert(0,HitRegion(Rect(region.x,region.y,region.width,region.height),'report',key='IGNORE',scrollable=True))
    builder=getattr(renderable,'_pgn_hit_map_builder',None)
    frame=builder(console.size.width,console.size.height,renderable) if callable(builder) else None
    frame=frame if frame is not None else HitMap(console.size.width,console.size.height,regions)
    extras=back_button_regions(text,console.size.width,console.size.height,frame.regions)
    if extras:frame=HitMap(console.size.width,console.size.height,frame.regions+tuple(extras))
    set_hit_map(frame)
    paint_caret(getattr(renderable,'pgn_caret',None),console.size.width,console.size.height,vt=vt)
