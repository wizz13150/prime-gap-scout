"""One coordinator owns the worker/DB; a menu thread exchanges bounded messages.

This module never imports CUDA, starts a worker, or opens the session database.
The engine must validate every request using its existing trusted paths/guards.
"""

from dataclasses import dataclass, field
import copy, json, os, queue, select, threading, time
from types import SimpleNamespace


class MenuCancelled(Exception):
    pass


_terminal = threading.local()


def refresh_context_snapshot(context=None):
    context = context if context is not None else getattr(_terminal, "context", None)
    if context is not None and context.get("_snapshot_provider"):
        latest = context["_snapshot_provider"]()
        for key, value in latest.items():
            if not key.startswith("_"):
                context[key] = value
    if context is not None and context.get("_poll_ui_requests"):
        context["_poll_ui_requests"]()


def current_cancel():
    return getattr(_terminal, "cancel", None)


def wait_terminal_ready(fd=None, timeout=0.2):
    """Called before a blocking terminal read. A closed page can always unwind."""
    cancel = getattr(_terminal, "cancel", None)
    if cancel is None:
        return True
    until = time.monotonic() + timeout
    while True:
        if cancel.is_set():
            raise MenuCancelled()
        if os.name == "nt":
            import msvcrt

            if msvcrt.kbhit():
                return True
        elif select.select([fd], [], [], 0)[0]:
            return True
        remaining = until - time.monotonic()
        if remaining <= 0:
            return False
        cancel.wait(min(0.02, remaining))


@dataclass
class MenuRequest:
    number: int
    kind: str
    values: dict
    reply: dict = field(default_factory=dict)
    replied: threading.Event = field(default_factory=threading.Event)


class MenuService:
    """Snapshot publication and request handling belong to the creating thread."""

    allowed = frozenset(
        (
            "queue",
            "queue_edit",
            "queue_delete",
            "display_rows",
            "diagnostic_start",
            "diagnostic_stop",
            "new",
            "resume",
            "activate_queued",
            "pause",
            "stop",
            "quit",
        )
    )

    def __init__(self):
        self.owner = threading.get_ident()
        self._lock = threading.Lock()
        self._snapshot = {}
        self._requests = queue.Queue(maxsize=16)
        self._errors = queue.Queue(maxsize=8)
        self.cancel = threading.Event()
        self.visible = threading.Event()
        self.thread = None
        self.ui_state = {}
        self._sequence = 0
        self._ui_pending = []

    def _coordinator(self):
        if threading.get_ident() != self.owner:
            raise RuntimeError("Only the coordinator may mutate the worker/session")

    def publish(self, state):
        self._coordinator()
        with self._lock:
            self._snapshot = copy.deepcopy(state)

    def snapshot(self):
        with self._lock:
            return copy.deepcopy(self._snapshot)

    def _enqueue(self, action):
        kind = action.kind
        if kind not in self.allowed:
            raise ValueError("Unsupported menu request: " + str(kind))
        values = copy.deepcopy(action.values)
        if len(json.dumps(values, default=str)) > 32768:
            raise ValueError("Oversized menu request")
        self._sequence += 1
        request = MenuRequest(self._sequence, kind, values)
        self._requests.put_nowait(request)
        return request

    def submit(self, action):
        request = self._enqueue(action)
        while not request.replied.wait(0.05):
            if self.cancel.is_set():
                raise MenuCancelled()
        result = copy.deepcopy(request.reply)
        if not result.get("ok"):
            raise ValueError(result.get("message", "Request rejected"))
        return result

    def poll_ui_requests(self):
        remaining = []
        for request in self._ui_pending:
            if not request.replied.is_set():
                remaining.append(request)
                continue
            result = copy.deepcopy(request.reply)
            self.ui_state["request_notice"] = str(result.get("message", "Request finished"))
            if not result.get("ok"):
                self.ui_state["request_error"] = self.ui_state["request_notice"]
        self._ui_pending = remaining
        if not remaining:
            self.ui_state.pop("pending_worker_request", None)

    def submit_ui(self, action):
        # Request acceptance is asynchronous; UI does not invent backend execution status.
        if action.kind not in ("new", "resume", "activate_queued", "pause", "stop", "quit"):
            return self.submit(action)
        self.poll_ui_requests()
        if self._ui_pending:
            raise ValueError("A worker request is already pending; wait for its safe boundary.")
        request = self._enqueue(action)
        self._ui_pending.append(request)
        self.ui_state.pop("request_error", None)
        self.ui_state["pending_worker_request"] = {"number": request.number, "kind": request.kind}
        self.ui_state["request_notice"] = "Request sent; waiting for the coordinator."
        return {"ok": True, "pending": True, "message": self.ui_state["request_notice"]}

    def pending(self):
        self._coordinator()
        result = []
        while True:
            try:
                result.append(self._requests.get_nowait())
            except queue.Empty:
                return result

    def respond(self, request, *, ok, message):
        self._coordinator()
        request.reply.update(ok=bool(ok), message=str(message))
        request.replied.set()

    def errors(self):
        self._coordinator()
        result = []
        while True:
            try:
                result.append(self._errors.get_nowait())
            except queue.Empty:
                return result

    def open(self, state, entry="menu", runner=None):
        self._coordinator()
        self.publish(state)
        if self.visible.is_set():
            return False
        if self.thread and self.thread.is_alive():
            raise RuntimeError("Previous menu thread has not closed")
        self.cancel.clear()
        self.visible.set()

        def draw():
            _terminal.cancel = self.cancel
            try:
                (runner or run_pages)(self, entry)
            except MenuCancelled:
                pass
            except KeyboardInterrupt:
                try:
                    self.submit(SimpleNamespace(kind="stop", values={}))
                except MenuCancelled:
                    pass
            except Exception as error:
                try:
                    self._errors.put_nowait(str(error))
                except queue.Full:
                    pass
            finally:
                _terminal.cancel = None
                self.visible.clear()

        self.thread = threading.Thread(target=draw, name="PGN-menu", daemon=True)
        self.thread.start()
        return True

    def close(self, timeout=2):
        self._coordinator()
        self.cancel.set()
        if self.thread:
            self.thread.join(timeout)
            if self.thread.is_alive():
                raise RuntimeError("Menu did not relinquish the terminal")
        for request in self.pending():
            self.respond(request, ok=False, message="Page closed before the request was accepted")
        self._ui_pending = []
        self.ui_state.pop("pending_worker_request", None)
        self.ui_state.pop("request_notice", None)


def run_pages(service, entry):
    from pgn_input import TerminalInput
    from pgn_ui_terminal import invalidate

    invalidate()
    with TerminalInput():
        return _run_pages(service, entry)


def _run_pages(service, entry):
    from pgn_menu import menu, file_menu

    context = service.snapshot()
    context.update(
        _ui_state=service.ui_state,
        _snapshot_provider=service.snapshot,
        _submit_action=service.submit_ui,
        _poll_ui_requests=service.poll_ui_requests,
    )
    _terminal.context = context
    if entry == "files":
        action = file_menu(context)
        if action is not None and action.kind != "return":
            service.submit(action)
    else:
        while not service.cancel.is_set():
            action = menu(context)
            if action.kind == "return":
                return
            service.submit_ui(action)
