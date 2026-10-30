"""Bounded, read-only device discovery. It never starts a mining job."""

import json
import subprocess
import tempfile
import threading
import time


def decode_devices(text):
    try:
        info = json.loads(text)
        devices = info["devices"]
        required = ("index", "model", "uuid", "cc_major", "cc_minor", "vram_bytes")
        if not isinstance(devices, list) or any(
            not isinstance(d, dict) or any(k not in d for k in required) for d in devices
        ):
            raise ValueError
        indices = [d["index"] for d in devices]
        if any(type(i) is not int or i < 0 for i in indices) or len(set(indices)) != len(indices):
            raise ValueError
        return info, devices
    except (ValueError, KeyError, TypeError):
        raise RuntimeError("Worker --device-info did not return its expected device JSON") from None


class IdleDeviceProbe:
    """Poll a specific owned host-info child without blocking terminal input."""

    def __init__(self, command, *, options=None, timeout=8.0, clock=time.monotonic):
        self.clock = clock
        self.deadline = clock() + timeout
        self.stdout = tempfile.TemporaryFile()
        self.stderr = tempfile.TemporaryFile()
        self.process = None
        self.finished = False
        self.error = None
        self.result = None
        self.timer = None
        try:
            self.process = subprocess.Popen(
                command, stdin=subprocess.DEVNULL, stdout=self.stdout, stderr=self.stderr,
                **(options or {}),
            )
            # The deadline still applies while the user is inside a menu and
            # the dashboard's poll loop is suspended.
            self.timer = threading.Timer(timeout, self._expire)
            self.timer.daemon = True
            self.timer.start()
        except OSError as error:
            self.error = str(error)
            self.finished = True

    def _expire(self):
        if self.process is not None and self.process.poll() is None:
            self.error = "GPU discovery timed out; press Start to retry or inspect the menu diagnostics"
            self.process.kill()

    def poll(self):
        if self.finished:
            return self.result
        code = self.process.poll()
        if code is None:
            if self.clock() < self.deadline:
                return None
            self.error = "GPU discovery timed out; press Start to retry or inspect the menu diagnostics"
            self.close()
            return None
        self.finished = True
        if self.timer:
            self.timer.cancel()
        if self.error:
            return None
        self.stdout.seek(0)
        self.stderr.seek(0)
        output, error = self.stdout.read(65537), self.stderr.read(65537)
        try:
            if len(output) > 65536 or len(error) > 65536:
                raise RuntimeError("GPU discovery exceeded its output limit")
            if code:
                raise RuntimeError("GPU discovery failed: " + (error or output).decode("utf-8", "replace").strip())
            self.result = decode_devices(output.decode("utf-8"))
        except (RuntimeError, UnicodeError) as problem:
            self.error = str(problem)
        return self.result

    def close(self):
        if self.timer:
            self.timer.cancel()
        if self.process is not None and self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=2)
        self.finished = True
        self.stdout.close()
        self.stderr.close()
