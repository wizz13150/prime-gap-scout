"""Explicit OS folder dialog for OUTPUT/RESUME; manual paths always remain valid.

Import does not open a dialog or query hardware. Windows uses IFileOpenDialog;
Linux uses an already-installed desktop helper. No Tk, PowerShell or installer.
"""
from pathlib import Path
import ctypes
import os
import shutil
import subprocess
import sys
import uuid


def _result(status,*,path=None,backend=None,message=None):
    return {'status':status,'path':path,'backend':backend,'message':message}


def _initial_folder(initial):
    """Nearest existing directory is only a dialog starting point, never a write."""
    if initial is None or str(initial)=='':return None
    if '\x00' in str(initial):raise ValueError('Folder path contains a null character.')
    path=Path(initial).expanduser().absolute()
    for candidate in (path,*path.parents):
        if candidate.is_dir():return str(candidate)
    return None


def _selected(path,backend):
    if not isinstance(path,str) or not path or '\x00'in path:
        return _result('error',backend=backend,message='The folder dialog did not return a valid directory path. Enter it manually.')
    if not Path(path).is_absolute() or not Path(path).is_dir():
        return _result('error',backend=backend,message='The selected folder is no longer available. Enter a directory path manually.')
    return _result('selected',path=path,backend=backend)


class _GUID(ctypes.Structure):
    _fields_=[('Data1',ctypes.c_uint32),('Data2',ctypes.c_uint16),('Data3',ctypes.c_uint16),('Data4',ctypes.c_ubyte*8)]
    @classmethod
    def from_text(cls,value):return cls.from_buffer_copy(uuid.UUID(value).bytes_le)


def _hresult(value):return int(value)&0xffffffff


def _check(value,operation):
    if _hresult(value)&0x80000000:raise OSError(operation+' failed (0x'+f'{_hresult(value):08X}'+').')


def _method(pointer,index,restype,*argtypes):
    """COM vtable order verified against the Windows SDK ShObjIdl_core.h."""
    if not pointer:raise OSError('Folder dialog interface is unavailable.')
    table=ctypes.cast(pointer,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    return ctypes.WINFUNCTYPE(restype,ctypes.c_void_p,*argtypes)(table[index])


def _release(pointer):
    if pointer:_method(pointer,2,ctypes.c_uint32)(pointer)


def _windows_choose(initial,title,owner_window):
    backend='windows-ifileopendialog';ole=None;dialog=ctypes.c_void_p();item=ctypes.c_void_p();folder=ctypes.c_void_p();text=ctypes.c_void_p();initialized=False
    HRESULT=ctypes.c_int32;P=ctypes.c_void_p;UINT=ctypes.c_uint32
    clsid=_GUID.from_text('DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7')
    iid_dialog=_GUID.from_text('D57C7288-D4AD-4768-BE02-9D969532D960')
    iid_shell=_GUID.from_text('43826D1E-E718-42EE-BC55-A1E261C37BFE')
    try:
        ole=ctypes.WinDLL('ole32',use_last_error=True);shell=ctypes.WinDLL('shell32',use_last_error=True)
        ole.CoInitializeEx.argtypes=[P,UINT];ole.CoInitializeEx.restype=HRESULT
        ole.CoCreateInstance.argtypes=[ctypes.POINTER(_GUID),P,UINT,ctypes.POINTER(_GUID),ctypes.POINTER(P)];ole.CoCreateInstance.restype=HRESULT
        ole.CoTaskMemFree.argtypes=[P];ole.CoTaskMemFree.restype=None
        ole.CoUninitialize.argtypes=[];ole.CoUninitialize.restype=None
        shell.SHCreateItemFromParsingName.argtypes=[ctypes.c_wchar_p,P,ctypes.POINTER(_GUID),ctypes.POINTER(P)];shell.SHCreateItemFromParsingName.restype=HRESULT
        hr=ole.CoInitializeEx(None,0x2|0x4)  # STA plus DISABLE_OLE1DDE
        if _hresult(hr)==0x80010106:
            return _result('unavailable',backend=backend,message='This UI thread has an incompatible COM apartment. Enter the folder path manually.')
        _check(hr,'COM initialization');initialized=True
        _check(ole.CoCreateInstance(ctypes.byref(clsid),None,1,ctypes.byref(iid_dialog),ctypes.byref(dialog)),'Create folder dialog')
        options=UINT();_check(_method(dialog,10,HRESULT,ctypes.POINTER(UINT))(dialog,ctypes.byref(options)),'Get folder dialog options')
        flags=options.value|0x20|0x40|0x800|0x02000000  # PICKFOLDERS, FORCEFILESYSTEM, PATHMUSTEXIST, DONTADDTORECENT
        flags&=~0x200  # one folder only; never an implicit multi-selection
        _check(_method(dialog,9,HRESULT,UINT)(dialog,flags),'Set folder dialog options')
        _check(_method(dialog,17,HRESULT,ctypes.c_wchar_p)(dialog,title),'Set folder dialog title')
        _check(_method(dialog,18,HRESULT,ctypes.c_wchar_p)(dialog,'Select folder'),'Set folder selection label')
        if initial:
            hr=shell.SHCreateItemFromParsingName(initial,None,ctypes.byref(iid_shell),ctypes.byref(folder))
            if not _hresult(hr)&0x80000000 and folder:
                # A stale/unavailable starting directory is not a failed choice.
                _method(dialog,12,HRESULT,P)(dialog,folder)
        owner=P(owner_window) if owner_window is not None else None
        hr=_method(dialog,3,HRESULT,P)(dialog,owner)
        if _hresult(hr)==0x800704c7:return _result('cancelled',backend=backend)
        _check(hr,'Show folder dialog')
        _check(_method(dialog,20,HRESULT,ctypes.POINTER(P))(dialog,ctypes.byref(item)),'Get selected folder')
        _check(_method(item,5,HRESULT,UINT,ctypes.POINTER(P))(item,0x80058000,ctypes.byref(text)),'Get folder filesystem path')
        return _selected(ctypes.wstring_at(text) if text else None,backend)
    except (OSError,ValueError,TypeError,AttributeError) as problem:
        return _result('error',backend=backend,message=str(problem)+' Enter the folder path manually.')
    finally:
        if text and ole:ole.CoTaskMemFree(text)
        for pointer in (item,folder,dialog):_release(pointer)
        if initialized:ole.CoUninitialize()


def _linux_backend():
    if not(os.environ.get('DISPLAY')or os.environ.get('WAYLAND_DISPLAY')):
        return None,None,'No graphical desktop is available. Enter the folder path manually.'
    # WSLg is the Linux desktop route; no Windows interop helper is claimed.
    preferred=('kdialog','zenity') if 'kde'in os.environ.get('XDG_CURRENT_DESKTOP','').lower() else ('zenity','kdialog')
    for name in preferred:
        executable=shutil.which(name)
        if executable:return name,executable,None
    return None,None,'No supported folder dialog helper is installed (Zenity or KDialog). Enter the folder path manually.'


def _linux_choose(initial,title):
    backend,tool,message=_linux_backend()
    if not backend:return _result('unavailable',message=message)
    if backend=='zenity':
        args=[tool,'--file-selection','--directory','--title='+title]
        if initial:args.append('--filename='+initial+os.sep)
    else:args=[tool,'--title',title,'--getexistingdirectory',initial or '.']
    try:
        # Waiting is explicitly modal user interaction, not a background poll.
        # The coordinator's search worker is independent of this UI thread.
        process=subprocess.run(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace',shell=False)
    except (OSError,ValueError) as problem:
        return _result('error',backend=backend,message='Cannot open folder dialog: '+str(problem)+'. Enter the path manually.')
    if process.returncode==1:
        error_text=(process.stderr or '').lower()
        if any(phrase in error_text for phrase in ('cannot open display','could not connect to display','failed to open display')):
            return _result('unavailable',backend=backend,message='The folder dialog cannot connect to the desktop. Enter the path manually.')
        return _result('cancelled',backend=backend)
    if process.returncode!=0:return _result('error',backend=backend,message='Folder dialog exited with code '+str(process.returncode)+'. Enter the path manually.')
    return _selected(process.stdout.rstrip('\r\n'),backend)


def choose_folder(*,initial=None,title='Select folder',field=None,owner_window=None):
    """Open one OS directory chooser only after an explicit Browse action.

    Returns status/path/backend/message. Only ``selected`` changes a field;
    ``cancelled`` is a total no-op. Existing keyboard path entry stays available.
    ``field`` is optional context (OUTPUT/RESUME), never a shell command.
    """
    try:
        title=str(title)
        if '\x00'in title or len(title)>200:raise ValueError('Folder dialog title is invalid.')
        start=_initial_folder(initial)
        if owner_window is not None and (type(owner_window)is not int or owner_window<0):raise ValueError('Folder dialog owner handle is invalid.')
        if os.name=='nt':return _windows_choose(start,title,owner_window)
        if sys.platform.startswith('linux'):return _linux_choose(start,title)
        return _result('unavailable',message='A folder dialog is unavailable on this platform. Enter the path manually.')
    except (OSError,ValueError,TypeError) as problem:
        return _result('error',message=str(problem)+' Enter the folder path manually.')
