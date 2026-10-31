"""Keep our classic console, including its caption, inside its monitor work area."""

from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path


_window_icons = {}


@dataclass(frozen=True)
class Rectangle:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self):
        return self.right-self.left

    @property
    def height(self):
        return self.bottom-self.top


def contained_rectangle(window, work):
    """Screen origins may be negative on secondary monitors."""
    if min(window.width, window.height, work.width, work.height) <= 0:
        raise ValueError("Positive window and work-area dimensions required")
    width, height = min(window.width, work.width), min(window.height, work.height)
    left = max(work.left, min(window.left, work.right-width))
    top = max(work.top, min(window.top, work.bottom-height))
    return Rectangle(left, top, left+width, top+height)


class ConsoleWindow:
    """Never infer ownership from the foreground window or a process name.

    Pseudoconsole hosts own their outer window; leave that host untouched.
    All geometry queries use the same thread DPI context.
    """

    def __init__(self):
        import ctypes as C
        from ctypes import wintypes as T

        self.C, self.T = C, T
        self.kernel = C.WinDLL("kernel32", use_last_error=True)
        self.user = C.WinDLL("user32", use_last_error=True)
        self.kernel.GetConsoleWindow.restype = T.HWND
        self.handle = self.kernel.GetConsoleWindow()
        self.user.GetClassNameW.argtypes = [T.HWND,T.LPWSTR,C.c_int]
        name = C.create_unicode_buffer(256)
        if not self.handle or not self.user.GetClassNameW(self.handle,name,len(name)) or name.value != "ConsoleWindowClass":
            raise OSError("The terminal host controls its own outer window")
        self.user.GetWindowRect.argtypes = [T.HWND,C.POINTER(T.RECT)]
        self.user.MonitorFromWindow.argtypes = [T.HWND,T.DWORD]
        self.user.MonitorFromWindow.restype = T.HANDLE
        self.user.SetWindowPos.argtypes = [T.HWND,T.HWND,C.c_int,C.c_int,C.c_int,C.c_int,T.UINT]
        if hasattr(self.user,"SetThreadDpiAwarenessContext"):
            self.user.SetThreadDpiAwarenessContext.argtypes = [T.HANDLE]
            self.user.SetThreadDpiAwarenessContext.restype = T.HANDLE
        self._application_icon()

    def _application_icon(self):
        """Set the requested artwork on our own classic-console window only."""
        if self.handle in _window_icons:
            return
        icon = Path(__file__).resolve().parent / "data" / "horizon.ico"
        if not icon.is_file():
            return
        C, T = self.C, self.T
        shell = C.WinDLL("shell32",use_last_error=True)
        shell.ExtractIconExW.argtypes = [T.LPCWSTR,C.c_int,
            C.POINTER(T.HICON),C.POINTER(T.HICON),T.UINT]
        large,small = T.HICON(),T.HICON()
        if not shell.ExtractIconExW(str(icon),0,C.byref(large),C.byref(small),1):
            return
        self.user.SendMessageW.argtypes = [T.HWND,T.UINT,T.WPARAM,T.LPARAM]
        self.user.SendMessageW.restype = T.LPARAM
        for kind,handle in ((0,small.value or large.value),(1,large.value or small.value)):
            self.user.SendMessageW(self.handle,0x0080,kind,handle)  # WM_SETICON
        # The window keeps both handles for the process lifetime. The OS frees
        # them at exit; repeated reflows reuse this same pair.
        _window_icons[self.handle] = (large,small)

    @contextmanager
    def _pixels(self):
        previous = None
        if hasattr(self.user,"SetThreadDpiAwarenessContext"):
            previous = self.user.SetThreadDpiAwarenessContext(self.T.HANDLE(-4))
        try:
            yield
        finally:
            if previous:
                self.user.SetThreadDpiAwarenessContext(previous)

    def _snapshot(self):
        C, T = self.C, self.T

        class MonitorInfo(C.Structure):
            _fields_ = [("size",T.DWORD),("monitor",T.RECT),("work",T.RECT),("flags",T.DWORD)]

        self.user.GetMonitorInfoW.argtypes = [T.HANDLE,C.POINTER(MonitorInfo)]
        outer = T.RECT();info = MonitorInfo();info.size = C.sizeof(info)
        monitor = self.user.MonitorFromWindow(self.handle,2)  # nearest monitor
        if not monitor or not self.user.GetWindowRect(self.handle,C.byref(outer)) or not self.user.GetMonitorInfoW(monitor,C.byref(info)):
            raise OSError(C.get_last_error(),"Cannot read the console's monitor bounds")
        convert = lambda r: Rectangle(r.left,r.top,r.right,r.bottom)
        return convert(outer),convert(info.work)

    def snapshot(self):
        with self._pixels():
            return self._snapshot()

    def hide_scrollbars(self):
        """Conhost can retain these styles even after buffer and view agree."""
        T = self.T
        self.user.GetWindowLongW.argtypes = [T.HWND,self.C.c_int]
        if not self.user.GetWindowLongW(self.handle,-16) & 0x00300000:
            return False
        self.user.ShowScrollBar.argtypes = [T.HWND,self.C.c_int,T.BOOL]
        return bool(self.user.ShowScrollBar(self.handle,3,False))  # SB_BOTH

    def maximum_rows(self, current_rows, cell_height):
        with self._pixels():
            outer, work = self._snapshot()
            # Current outer height already includes the caption, borders and
            # scrollbars. Reserve those pixels before growing the viewport.
            return max(2,current_rows+(work.height-outer.height)//max(1,cell_height))

    def maximum_viewport(self, columns, rows, cell_width, cell_height):
        """Available cells after reserving the whole caption and window frame."""
        with self._pixels():
            outer, work = self._snapshot()
            return (max(2, columns + (work.width-outer.width)//max(1,cell_width)),
                    max(2, rows + (work.height-outer.height)//max(1,cell_height)))

    def contain(self):
        with self._pixels():
            for _ in range(3):
                outer,work = self._snapshot()
                target = contained_rectangle(outer,work)
                if outer == target:
                    return True
                # Do not activate, change z-order, or move another application.
                if not self.user.SetWindowPos(self.handle,None,target.left,target.top,
                        target.width,target.height,0x0014):
                    return False
            outer,work = self._snapshot()
            return contained_rectangle(outer,work) == outer

    def resize_for_rows(self, current_rows, target_rows, cell_height):
        """Move and resize the complete frame in one operation before reflow."""
        with self._pixels():
            outer,work = self._snapshot()
            height = outer.height+(target_rows-current_rows)*max(1,cell_height)
            target = contained_rectangle(Rectangle(outer.left,outer.top,outer.right,
                                                   outer.top+height),work)
            return bool(self.user.SetWindowPos(self.handle,None,target.left,target.top,
                            target.width,target.height,0x0014))

    def resize_for_viewport(self, columns, rows, target_columns, target_rows,
                            cell_width, cell_height):
        """Fit both viewport axes; a tall, narrow fallback is not a usable layout."""
        with self._pixels():
            outer, work = self._snapshot()
            width = outer.width + (target_columns-columns)*max(1,cell_width)
            height = outer.height + (target_rows-rows)*max(1,cell_height)
            target = contained_rectangle(Rectangle(outer.left,outer.top,
                outer.left+width,outer.top+height),work)
            return bool(self.user.SetWindowPos(self.handle,None,target.left,target.top,
                target.width,target.height,0x0014))


def console_window():
    if os.name != "nt":
        return None
    try:
        return ConsoleWindow()
    except (OSError,AttributeError):
        return None
