"""Stdlib terminal input and geometric mouse routing; no application imports.

Keys keep PGN's string API. MouseEvent is the sole additional return type.
Coordinates are zero-based terminal CELLS, never pixels. Motion selects only the
hit item, without activating it. One left press produces one ENTER-equivalent.
"""

from collections import deque
from dataclasses import dataclass
import ctypes
import os
import re
import select
import sys
import threading
import time


class InputCancelled(Exception):
    """Translate to the application's MenuCancelled at its input boundary."""


@dataclass(frozen=True)
class MouseEvent:
    kind: str  # click, move, wheel
    x: int
    y: int
    button: int = 0  # 1=left, 2=middle, 3=right; 0 for motion/wheel
    dy: int = 0  # negative=up, positive=down, in logical wheel detents
    dx: int = 0  # negative=left, positive=right
    modifiers: frozenset = frozenset()


def _key(char):
    return {
        "\x03": "INTERRUPT",
        "\x1b": "ESC",
        "\r": "ENTER",
        "\n": "ENTER",
        "\t": "TAB",
        "\b": "BACKSPACE",
        "\x7f": "BACKSPACE",
        "\x15": "CLEAR",
        "\x13": "SAVE",
    }.get(char, char)


class EventBuffer:
    """Coalesce adjacent motion/wheel only; never lose/reorder clicks or keys.

    Native key repeats use a count rather than allocating repeated strings.
    The OS reader takes bounded batches; no background polling/thread exists.
    """

    def __init__(self):
        self.items = deque()

    def push(self, event, count=1):
        if not count or event == "IGNORE":
            return
        if self.items and isinstance(event, MouseEvent):
            previous, n = self.items[-1]
            if isinstance(previous, MouseEvent):
                if event.kind == previous.kind == "move":
                    self.items[-1] = (event, 1)
                    return
                if event.kind == previous.kind == "wheel" and (
                    event.x,
                    event.y,
                    event.modifiers,
                ) == (previous.x, previous.y, previous.modifiers):
                    self.items[-1] = (
                        MouseEvent(
                            "wheel",
                            event.x,
                            event.y,
                            dy=previous.dy + event.dy,
                            dx=previous.dx + event.dx,
                            modifiers=event.modifiers,
                        ),
                        1,
                    )
                    return
        self.items.append((event, count))

    def pop(self):
        event, count = self.items.popleft()
        if count > 1:
            self.items.appendleft((event, count - 1))
        return event

    def __bool__(self):
        return bool(self.items)


class VTParser:
    """Incremental UTF-8 + CSI/SS3 + SGR1006 parser, bounded escape frames.

    Call expire() after escape_timeout without more bytes to distinguish a lone
    Esc. The timeout concerns incomplete escape sequences only, not Unicode.
    """

    escape_timeout = 0.025
    _mouse = re.compile(rb"\x1b\[<(\d{1,6});(\d{1,6});(\d{1,6})([Mm])\Z")
    _simple = {
        "A": "UP",
        "B": "DOWN",
        "C": "RIGHT",
        "D": "LEFT",
        "H": "HOME",
        "F": "END",
        "Z": "BACKTAB",
    }
    _tilde = {
        1: "HOME",
        2: "INSERT",
        3: "DELETE",
        4: "END",
        5: "PGUP",
        6: "PGDN",
        7: "HOME",
        8: "END",
    }

    def __init__(self):
        self.pending = bytearray()
        self.escape_since = None
        self.buttons = set()

    def feed(self, data, now=None):
        now = time.monotonic() if now is None else now
        self.pending.extend(data)
        result = []
        while self.pending:
            first = self.pending[0]
            if first == 27:
                if self.escape_since is None:
                    self.escape_since = now
                if len(self.pending) == 1:
                    break
                if self.pending[1] not in (ord("["), ord("O")):
                    del self.pending[0]
                    result.append("ESC")
                    self.escape_since = None
                    continue
                sgr = self.pending[1:3] == b"[<"
                end = next(
                    (
                        i
                        for i in range(2, min(len(self.pending), 65))
                        if (
                            self.pending[i] in (ord("M"), ord("m"))
                            if sgr
                            else 0x40 <= self.pending[i] <= 0x7E
                        )
                    ),
                    None,
                )
                if end is None:
                    if len(self.pending) <= 64:
                        break
                    self.pending.clear()  # one malformed control frame
                    self.escape_since = None
                    continue
                frame = bytes(self.pending[: end + 1])
                del self.pending[: end + 1]
                self.escape_since = None
                mouse = self._mouse.fullmatch(frame)
                if mouse:
                    code, x, y = (int(mouse[i]) for i in (1, 2, 3))
                    if x and y:
                        event = self._mouse_event(code, x - 1, y - 1, mouse[4] == b"m")
                        if event is not None:
                            result.append(event)
                    continue
                if frame.startswith(b"\x1b[<"):
                    continue  # malformed mouse must never become text/Enter
                final = chr(frame[-1])
                if final in self._simple:
                    result.append(self._simple[final])
                elif final == "~":
                    head = frame[2:-1].split(b";")[0]
                    if head.isdigit():
                        value = self._tilde.get(int(head))
                        if value:
                            result.append(value)
                continue
            self.escape_since = None
            size = (
                1
                if first < 128
                else (
                    2
                    if 0xC2 <= first <= 0xDF
                    else 3 if 0xE0 <= first <= 0xEF else 4 if 0xF0 <= first <= 0xF4 else 1
                )
            )
            if len(self.pending) < size:
                break
            raw = bytes(self.pending[:size])
            try:
                char = raw.decode("utf-8")
            except UnicodeDecodeError:
                size, char = 1, "\ufffd"
            del self.pending[:size]
            result.append(_key(char))
        return result

    def expire(self, now=None):
        now = time.monotonic() if now is None else now
        if self.escape_since is None or now - self.escape_since < self.escape_timeout:
            return []
        lone = self.pending == b"\x1b"
        self.pending.clear()
        self.escape_since = None
        return ["ESC"] if lone else []

    def _mouse_event(self, code, x, y, released):
        modifiers = frozenset(
            name for bit, name in ((4, "shift"), (8, "alt"), (16, "ctrl")) if code & bit
        )
        base = code & 3
        if code & 64:
            if released:
                return None
            return MouseEvent(
                "wheel",
                x,
                y,
                dy=(-1 if base == 0 else 1) if base < 2 else 0,
                dx=(-1 if base == 2 else 1) if base >= 2 else 0,
                modifiers=modifiers,
            )
        if code & 128:
            return None  # unsupported auxiliary buttons, never synthesize Enter
        button = base + 1
        if code & 32 and not released:
            return MouseEvent("move", x, y, modifiers=modifiers)
        if released or base == 3:
            self.buttons.discard(button)
            if base == 3:
                self.buttons.clear()
            return None
        if button in self.buttons:
            return None
        self.buttons.add(button)
        return MouseEvent("click", x, y, button=button, modifiers=modifiers)


# Explicit-width types keep the Win32 ABI testable even on a POSIX Python.
WORD, DWORD, BOOL = ctypes.c_uint16, ctypes.c_uint32, ctypes.c_int32


class COORD(ctypes.Structure):
    _fields_ = [("X", ctypes.c_int16), ("Y", ctypes.c_int16)]


class KEY_EVENT_RECORD(ctypes.Structure):
    _fields_ = [
        ("bKeyDown", BOOL),
        ("wRepeatCount", WORD),
        ("wVirtualKeyCode", WORD),
        ("wVirtualScanCode", WORD),
        ("UnicodeChar", WORD),
        ("dwControlKeyState", DWORD),
    ]


class MOUSE_EVENT_RECORD(ctypes.Structure):
    _fields_ = [
        ("dwMousePosition", COORD),
        ("dwButtonState", DWORD),
        ("dwControlKeyState", DWORD),
        ("dwEventFlags", DWORD),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("KeyEvent", KEY_EVENT_RECORD),
        ("MouseEvent", MOUSE_EVENT_RECORD),
        ("WindowSize", COORD),
        ("unused", DWORD),
    ]


class INPUT_RECORD(ctypes.Structure):
    _anonymous_ = ("Event",)
    _fields_ = [("EventType", WORD), ("Event", _INPUT_UNION)]


class _SMALL_RECT(ctypes.Structure):
    _fields_ = [(name, ctypes.c_int16) for name in ("Left", "Top", "Right", "Bottom")]


class _SCREEN_INFO(ctypes.Structure):
    _fields_ = [
        ("size", COORD),
        ("cursor", COORD),
        ("attributes", WORD),
        ("window", _SMALL_RECT),
        ("maximum", COORD),
    ]


def active_console_geometry(stream=None, fallback=(120, 36)):
    """Measure the active Windows buffer, including VT alternate screens.

    The inherited stdout handle can still describe the inactive main buffer
    after switching screens. Coordinates and layout must share this viewport.
    """
    stream = sys.stdout if stream is None else stream
    if os.name == "nt" and getattr(stream, "isatty", lambda: False)():
        from ctypes import wintypes as T

        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.CreateFileW.argtypes = [T.LPCWSTR, T.DWORD, T.DWORD, T.LPVOID, T.DWORD, T.DWORD, T.HANDLE]
        k.CreateFileW.restype = T.HANDLE
        k.GetConsoleScreenBufferInfo.argtypes = [T.HANDLE, ctypes.POINTER(_SCREEN_INFO)]
        k.GetConsoleScreenBufferInfo.restype = T.BOOL
        k.CloseHandle.argtypes = [T.HANDLE]
        handle = k.CreateFileW("CONOUT$", 0x80000000, 3, None, 3, 0, None)
        if handle not in (None, T.HANDLE(-1).value):
            try:
                info = _SCREEN_INFO()
                if k.GetConsoleScreenBufferInfo(handle, ctypes.byref(info)):
                    return (
                        os.terminal_size(
                            (
                                max(1, info.window.Right - info.window.Left + 1),
                                max(1, info.window.Bottom - info.window.Top + 1),
                            )
                        ),
                        (info.window.Left, info.window.Top),
                    )
            finally:
                k.CloseHandle(handle)
    try:
        return os.get_terminal_size(stream.fileno()), (0, 0)
    except (OSError, ValueError, AttributeError):
        import shutil

        return shutil.get_terminal_size(fallback), (0, 0)


def terminal_size(*, fallback=(120, 36), stream=None):
    return active_console_geometry(stream, fallback)[0]


class NativeDecoder:
    """Pure Win32-record translation; button releases never activate controls."""

    _keys = {
        0x25: "LEFT",
        0x27: "RIGHT",
        0x26: "UP",
        0x28: "DOWN",
        0x24: "HOME",
        0x23: "END",
        0x21: "PGUP",
        0x22: "PGDN",
        0x2E: "DELETE",
        0x2D: "INSERT",
        0x1B: "ESC",
        0x0D: "ENTER",
        0x08: "BACKSPACE",
        0x09: "TAB",
    }

    def __init__(self):
        self.buttons = 0
        self.high_surrogate = None
        self.wheel_remainder = {4: 0, 8: 0}

    def feed(self, record, origin=(0, 0)):
        if record.EventType == 1:
            item = record.KeyEvent
            if not item.bKeyDown:
                return []
            repeat = max(1, item.wRepeatCount)
            ctrl, alt = bool(item.dwControlKeyState & 12), bool(item.dwControlKeyState & 3)
            if ctrl and not alt and item.wVirtualKeyCode in (0x43, 0x53, 0x55):
                return [
                    ({0x43: "INTERRUPT", 0x53: "SAVE", 0x55: "CLEAR"}[item.wVirtualKeyCode], repeat)
                ]
            named = self._keys.get(item.wVirtualKeyCode)
            if named:
                if named == "TAB" and item.dwControlKeyState & 16:
                    named = "BACKTAB"
                self.high_surrogate = None
                return [(named, repeat)]
            unit = item.UnicodeChar
            if not unit:
                return []
            if 0xD800 <= unit <= 0xDBFF:
                self.high_surrogate = unit
                return []
            if 0xDC00 <= unit <= 0xDFFF and self.high_surrogate is not None:
                char = chr(0x10000 + ((self.high_surrogate - 0xD800) << 10) + (unit - 0xDC00))
            else:
                char = chr(unit) if not 0xDC00 <= unit <= 0xDFFF else "\ufffd"
            self.high_surrogate = None
            return [(_key(char), repeat)]
        if record.EventType == 4:
            self.buttons = 0
            return [("RESIZE", 1)]
        if record.EventType != 2:
            return []
        item = record.MouseEvent
        x, y = item.dwMousePosition.X - origin[0], item.dwMousePosition.Y - origin[1]
        modifiers = frozenset(
            name
            for mask, name in ((16, "shift"), (3, "alt"), (12, "ctrl"))
            if item.dwControlKeyState & mask
        )
        flags = item.dwEventFlags
        state = item.dwButtonState & 0x1F
        if flags in (4, 8):
            delta = ctypes.c_int16(item.dwButtonState >> 16).value
            self.wheel_remainder[flags] += delta
            steps = int(self.wheel_remainder[flags] / 120)  # high-resolution wheels accumulate
            self.wheel_remainder[flags] -= steps * 120
            if steps:
                return [
                    (
                        MouseEvent(
                            "wheel",
                            x,
                            y,
                            dy=-steps if flags == 4 else 0,
                            dx=steps if flags == 8 else 0,
                            modifiers=modifiers,
                        ),
                        1,
                    )
                ]
            return []
        previous, self.buttons = self.buttons, state
        if flags == 1:
            return [(MouseEvent("move", x, y, modifiers=modifiers), 1)]
        if flags not in (0, 2):
            return []
        return [
            (MouseEvent("click", x, y, button=button, modifiers=modifiers), 1)
            for mask, button in ((1, 1), (4, 2), (2, 3))
            if state & mask and not previous & mask
        ]


class _WinAPI:
    def __init__(self):
        self.k = ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "GetConsoleMode": ([ctypes.c_void_p, ctypes.POINTER(DWORD)], BOOL),
            "SetConsoleMode": ([ctypes.c_void_p, DWORD], BOOL),
            "WaitForSingleObject": ([ctypes.c_void_p, DWORD], DWORD),
            "ReadConsoleInputW": (
                [ctypes.c_void_p, ctypes.POINTER(INPUT_RECORD), DWORD, ctypes.POINTER(DWORD)],
                BOOL,
            ),
            "GetConsoleScreenBufferInfo": ([ctypes.c_void_p, ctypes.POINTER(_SCREEN_INFO)], BOOL),
        }
        for name, (args, result) in signatures.items():
            getattr(self.k, name).argtypes = args
            getattr(self.k, name).restype = result

    def mode(self, handle):
        value = DWORD()
        if not self.k.GetConsoleMode(handle, ctypes.byref(value)):
            raise ctypes.WinError(ctypes.get_last_error())
        return value.value

    def set_mode(self, handle, mode):
        if not self.k.SetConsoleMode(handle, mode):
            raise ctypes.WinError(ctypes.get_last_error())


_output_lock = threading.RLock()
_output_states = {}
_input_lock = threading.Lock()
_input_states = {}
_input_owners = {}


class _OutputScope:
    """Reference-count mode/capture ownership across screen and reader scopes."""

    def __init__(self, stream, mouse=False, screen=False):
        self.stream, self.mouse, self.screen = stream, mouse, screen
        self.key = None
        self.supported = False

    def __enter__(self):
        # Windows console capabilities are authoritative. OpenSSH and launcher
        # environments can retain TERM=dumb while GetConsoleMode/VT succeeds.
        if not self.stream.isatty() or (os.name != "nt" and os.environ.get("TERM") == "dumb"):
            return self
        self.key = self.stream.fileno()
        with _output_lock:
            state = _output_states.get(self.key)
            if state is None:
                api, handle, saved = None, None, None
                if os.name == "nt":
                    import msvcrt

                    api = _WinAPI()
                    handle = msvcrt.get_osfhandle(self.key)
                    try:
                        saved = api.mode(handle)
                        api.set_mode(handle, saved | 1 | 4 | 8)
                    except OSError:
                        self.key = None
                        return self
                state = {
                    "count": 0,
                    "mouse": 0,
                    "screen": 0,
                    "api": api,
                    "handle": handle,
                    "saved": saved,
                }
                _output_states[self.key] = state
            state["count"] += 1
            self.supported = True
            sequence = ""
            if self.screen:
                if not state["screen"]:
                    sequence += "\x1b[?1049h\x1b[?25l\x1b[?7l"
                state["screen"] += 1
            if self.mouse:
                if not state["mouse"]:
                    sequence += "\x1b[?1000h\x1b[?1003h\x1b[?1006h"
                state["mouse"] += 1
            try:
                if sequence:
                    self._write(sequence)
            except BaseException:
                self.__exit__(None, None, None)
                raise
        return self

    def _write(self, value):
        self.stream.write(value)
        self.stream.flush()

    def __exit__(self, *_):
        if self.key is None:
            return
        with _output_lock:
            state = _output_states.get(self.key)
            if state is None:
                return
            sequence = ""
            try:
                if self.mouse:
                    state["mouse"] -= 1
                    if not state["mouse"]:
                        sequence += "\x1b[?1006l\x1b[?1003l\x1b[?1000l"
                if self.screen:
                    state["screen"] -= 1
                    if not state["screen"]:
                        sequence += "\x1b[0m\x1b[?7h\x1b[?25h\x1b[?1049l"
                if sequence:
                    self._write(sequence)
            finally:
                state["count"] -= 1
                if not state["count"]:
                    del _output_states[self.key]
                    if state["api"] is not None:
                        state["api"].set_mode(state["handle"], state["saved"])
                self.key = None


class TerminalScreen(_OutputScope):
    """Outer interactive lifetime: alternate screen, no wrap, mouse capture.

    Keep this scope alive while mining, final results, menus and subpages switch.
    After intentional exit, print the final snapshot/results on the main screen.
    Normal entry precondition: ordinary shell modes, cursor visible, wrapping on,
    mouse modes off. Do not nest another TUI with unknown private-mode ownership.
    """

    def __init__(self, stream=None, *, mouse=True):
        super().__init__(sys.stdout if stream is None else stream, mouse=mouse, screen=True)


class TerminalInput:
    """PGN-compatible key reader with nonblocking/cancellable native mouse input.

    One reader may own stdin at a time. Close PauseKeys before the menu reader;
    hold TerminalScreen outside both to keep capture/alternate screen continuous.
    """

    def __init__(self, *, stream=None, output=None, mouse=True):
        self.stream = sys.stdin if stream is None else stream
        self.output = sys.stdout if output is None else output
        self.mouse = mouse
        self.events = EventBuffer()
        self.parser = VTParser()
        self.decoder = NativeDecoder()
        self.saved = None
        self.api = None
        self.backend = None
        self.fallback_reason = None
        self._output_scope = None
        self._input_key = None

    def __enter__(self):
        if not self.stream.isatty():
            raise RuntimeError(
                "Interactive pages need a terminal; use CLI/headless options otherwise"
            )
        self.fd = self.stream.fileno()
        with _input_lock:
            key = (os.name, self.fd)
            if key in _input_owners:
                raise RuntimeError("Terminal input already has an active reader")
            _input_owners[key] = self
            self._input_key = key
            self.events, self.parser, self.decoder = _input_states.setdefault(
                key, (EventBuffer(), VTParser(), NativeDecoder())
            )
        try:
            if os.name == "nt":
                import msvcrt

                self.api = _WinAPI()
                self.handle = msvcrt.get_osfhandle(self.fd)
                try:
                    previous = self.api.mode(self.handle)
                    mode = (previous | 0x80 | 8 | (0x10 if self.mouse else 0)) & ~(
                        1 | 2 | 4 | 0x40 | 0x200
                    )
                    self.api.set_mode(self.handle, mode)
                    self.saved, self.backend = previous, "win32"
                except OSError as error:
                    self.backend, self.fallback_reason = "keyboard", str(error)
            else:
                import termios
                import tty

                self.saved = termios.tcgetattr(self.fd)
                tty.setraw(self.fd, termios.TCSANOW)
                mode = termios.tcgetattr(self.fd)
                mode[1] = self.saved[1]  # preserve output newline processing
                termios.tcsetattr(self.fd, termios.TCSANOW, mode)
                self.backend = "posix"
            self._output_scope = _OutputScope(
                self.output, mouse=self.mouse and self.backend != "keyboard"
            )
            self._output_scope.__enter__()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_):
        try:
            if self._output_scope is not None:
                self._output_scope.__exit__(None, None, None)
                self._output_scope = None
        finally:
            try:
                if self.saved is not None:
                    if os.name == "nt":
                        self.api.set_mode(self.handle, self.saved)
                    else:
                        import termios

                        termios.tcsetattr(self.fd, termios.TCSANOW, self.saved)
                    self.saved = None
            finally:
                if self._input_key is not None:
                    with _input_lock:
                        _input_owners.pop(self._input_key, None)
                    self._input_key = None

    def _origin(self):
        if self.backend == "win32":
            return active_console_geometry(self.output)[1]
        try:
            import msvcrt

            info = _SCREEN_INFO()
            handle = msvcrt.get_osfhandle(self.output.fileno())
            if self.api.k.GetConsoleScreenBufferInfo(handle, ctypes.byref(info)):
                return info.window.Left, info.window.Top
        except (OSError, ValueError):
            pass
        return (0, 0)

    def _native_event(self, event, repeat=1):
        """Decode VT characters delivered as Win32 KEY_EVENT_RECORDs.

        Windows OpenSSH/ConPTY can deliver SGR mouse escapes as ordinary key
        records even though GetConsoleMode succeeds. Do not leak their digits
        or final M into application shortcuts. Real mouse/key records remain.
        """
        if event == "ESC":
            if self.parser.pending:
                for parsed in self.parser.expire(time.monotonic() + self.parser.escape_timeout):
                    self.events.push(parsed)
            if repeat > 1:
                self.events.push("ESC", repeat - 1)
            for parsed in self.parser.feed(b"\x1b"):
                self.events.push(parsed)
        elif isinstance(event, str) and len(event) == 1 and self.parser.pending:
            for parsed in self.parser.feed(event.encode("utf-8")):
                self.events.push(parsed)
            if repeat > 1:
                self.events.push(event, repeat - 1)
        else:
            if self.parser.pending:
                for parsed in self.parser.expire(time.monotonic() + self.parser.escape_timeout):
                    self.events.push(parsed)
            self.events.push(event, repeat)

    def read(self, timeout=None, cancel=None):
        """Return key/MouseEvent/TICK. timeout=0 polls; cancellation ≤20ms.

        Ctrl+C raises KeyboardInterrupt on both platforms. ESC is returned.
        Do not put msvcrt.kbhit/select in front: they are not native mouse gates.
        """
        until = None if timeout is None else time.monotonic() + max(0, timeout)
        while True:
            if cancel is not None and cancel.is_set():
                raise InputCancelled()
            if self.events:
                result = self.events.pop()
                if result == "INTERRUPT":
                    raise KeyboardInterrupt
                return result
            remaining = 0.02 if until is None else min(0.02, max(0, until - time.monotonic()))
            if self.backend == "win32":
                status = self.api.k.WaitForSingleObject(self.handle, max(0, int(remaining * 1000)))
                if status == 0:
                    records = (INPUT_RECORD * 64)()
                    count = DWORD()
                    if not self.api.k.ReadConsoleInputW(
                        self.handle, records, 64, ctypes.byref(count)
                    ):
                        raise ctypes.WinError(ctypes.get_last_error())
                    origin = self._origin()
                    for record in records[: count.value]:
                        for event, repeat in self.decoder.feed(record, origin):
                            self._native_event(event, repeat)
                elif status != 258:
                    raise OSError("Console input wait failed: " + str(status))
            elif self.backend == "keyboard":
                import msvcrt

                if msvcrt.kbhit():
                    char = msvcrt.getwch()
                    if char in ("\x00", "\xe0"):
                        char = {
                            "K": "LEFT",
                            "M": "RIGHT",
                            "G": "HOME",
                            "O": "END",
                            "S": "DELETE",
                            "H": "UP",
                            "P": "DOWN",
                            "I": "PGUP",
                            "Q": "PGDN",
                        }.get(msvcrt.getwch(), "IGNORE")
                    self._native_event(_key(char))
                elif remaining:
                    if cancel is None:
                        time.sleep(remaining)
                    else:
                        cancel.wait(remaining)
            elif self.backend == "posix":
                if select.select([self.fd], [], [], remaining)[0]:
                    raw = os.read(self.fd, 4096)
                    if not raw:
                        raise EOFError("Terminal input closed")
                    for event in self.parser.feed(raw):
                        self.events.push(event)
                for event in self.parser.expire():
                    self.events.push(event)
            else:
                raise RuntimeError("TerminalInput must be entered before read()")
            if self.backend in ("win32", "keyboard"):
                for event in self.parser.expire():
                    self.events.push(event)
            if self.events:
                continue
            if until is not None and time.monotonic() >= until:
                return "TICK"


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    def contains(self, x, y):
        return self.x <= x < self.x + self.width and self.y <= y < self.y + self.height


@dataclass(frozen=True)
class HitRegion:
    rect: Rect
    target: str
    index: int | None = None  # absolute item index, already includes scroll offset
    key: str = "ENTER"  # same command used by the keyboard path
    disabled: bool = False
    scrollable: bool = False


@dataclass(frozen=True)
class RoutedEvent:
    key: str = "IGNORE"
    target: str | None = None
    index: int | None = None
    dy: int = 0
    dx: int = 0


class HitMap:
    """Immutable-by-convention frame geometry; install AFTER successful paint.

    Regions are in drawing order, topmost last. A panel region may precede its
    item regions. Wheel resolves only to a scrollable panel or explicit focus.
    Resize invalidates the frame; publish a new map after the new frame paints.
    """

    def __init__(self, width, height, regions=()):
        self.viewport = Rect(0, 0, width, height)
        self.regions = tuple(regions)

    def route(self, event, focused=None):
        if not isinstance(event, MouseEvent):
            return RoutedEvent(key=event)
        inside = self.viewport.contains(event.x, event.y)
        hits = [r for r in reversed(self.regions) if inside and r.rect.contains(event.x, event.y)]
        if event.kind == "move":
            _remember_pointer(event.x, event.y)
            # Hover is selection-only: NEVER return region.key here because it
            # may be ENTER, a digit or an immediate shortcut. Disabled controls
            # and decorative scroll panels do not become hovered actions.
            region = next(
                (r for r in hits if not r.disabled and (r.index is not None or r.key != "IGNORE")),
                None,
            )
            _set_hover_region(region)
            return RoutedEvent(
                "HOVER", region.target if region else None, region.index if region else None
            )
        if event.kind == "click" and event.button == 1:
            region = hits[0] if hits else None
            if region is not None and not region.disabled:
                return RoutedEvent(region.key, region.target, region.index)
        if event.kind == "wheel":
            region = next((r for r in hits if r.scrollable and not r.disabled), None)
            if region is None and focused is not None:
                region = next(
                    (
                        r
                        for r in reversed(self.regions)
                        if r.target == focused and r.scrollable and not r.disabled
                    ),
                    None,
                )
            if region is not None:
                return RoutedEvent("SCROLL", region.target, dy=event.dy, dx=event.dx)
        return RoutedEvent()


def bounded_scroll(offset, total, page_size, delta):
    """Scroll an application list/panel; this function never touches a terminal."""
    return max(0, min(max(0, total - max(1, page_size)), offset + delta))


def reset_input_state(fd=None):
    """Optional final-lifetime cleanup; never discard events during page changes.

    Pending bytes/records persist across sequential per-key reader scopes so the
    existing with TerminalInput(): read() API cannot drop prefetched keystrokes.
    """
    key = (os.name, sys.stdin.fileno() if fd is None else fd)
    with _input_lock:
        if key in _input_owners:
            raise RuntimeError("Cannot reset an active terminal reader")
        _input_states.pop(key, None)


_hit_map_lock = threading.Lock()
_hit_map = HitMap(0, 0)


def set_hit_map(frame):
    global _hit_map
    with _hit_map_lock:
        _hit_map = frame
    # A resize may invalidate geometry just before the last mouse movement.
    # Re-resolve its position after publishing new geometry, without activating.
    position = _last_pointer_position
    region = None
    if position is not None and frame.viewport.contains(*position):
        region = next(
            (
                r
                for r in reversed(frame.regions)
                if r.rect.contains(*position)
                and not r.disabled
                and (r.index is not None or r.key != "IGNORE")
            ),
            None,
        )
    _set_hover_region(region)


def get_hit_map():
    with _hit_map_lock:
        return _hit_map


_hover_lock = threading.Lock()
_hover_region = None
_last_pointer_position = None


def _remember_pointer(x, y):
    global _last_pointer_position
    _last_pointer_position = (x, y)


def _set_hover_region(region):
    global _hover_region
    with _hover_lock:
        _hover_region = region


def get_hover_region():
    """Last pointer's actionable region, for a visual hover style only.

    The controller's selected item remains authoritative. The renderer must not
    turn this observation into an activation, field commit or popup.
    """
    with _hover_lock:
        return _hover_region
