"""Retry replaceable report exports without weakening durable session writes."""

import threading
import time
from pathlib import Path


class DerivedExports:
    """Only report callers use this queue; journal/checkpoint writers stay strict."""

    def __init__(self, writer, on_notice=None):
        self._writer = writer
        self._on_notice = on_notice
        self._pending = {}
        self._lock = threading.RLock()
        self._retry_at = 0.0

    @property
    def notice(self):
        with self._lock:
            names = sorted(path.name for path in self._pending)
            return "Reports waiting for file access: " + ", ".join(names) if names else ""

    def _changed(self, before):
        after = self.notice
        if before != after and self._on_notice:
            self._on_notice(after)

    def write(self, path, text):
        path = Path(path)
        with self._lock:
            before = self.notice
            try:
                self._writer(path, text)
            except PermissionError as error:
                # Windows access/sharing violations on a derived export only.
                # Disk-full, bad paths and SQLite/authoritative write failures
                # are not caught here and cannot turn into apparent success.
                if getattr(error, "winerror", None) not in (5, 32, 33):
                    raise
                size = len(text.encode("utf-8"))
                other = sum(len(value.encode("utf-8")) for key, value in self._pending.items() if key != path)
                if size + other > 16 * 1024 * 1024 or (path not in self._pending and len(self._pending) >= 16):
                    raise RuntimeError("Deferred report export capacity exceeded") from error
                # Replace the previous queued revision, never append stale
                # versions or claim that the locked visible file is current.
                self._pending[path] = text
                self._changed(before)
                return False
            self._pending.pop(path, None)
            self._changed(before)
            return True

    def retry(self):
        with self._lock:
            now = time.monotonic()
            if not self._pending or now < self._retry_at:
                return
            self._retry_at = now + 1.0
            for path, text in list(self._pending.items()):
                self.write(path, text)
