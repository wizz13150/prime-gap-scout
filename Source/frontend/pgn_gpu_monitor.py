"""Low-cost, read-only clock observations for the live dashboard.

Display sampling is independent of optional telemetry file recording. NVML
observes the selected UUID and never changes clocks, fans, power, or voltage.
"""

import ctypes
import os
import re
import threading
import time


class NvmlClocks:
    SM_CLOCK = 1
    MEMORY_CLOCK = 2

    def __init__(self, uuid):
        if not re.fullmatch(r"GPU-[0-9a-fA-F-]{36}", uuid):
            raise ValueError("A GPU UUID is required for clock sampling")
        self.library = (
            ctypes.WinDLL("nvml.dll") if os.name == "nt" else ctypes.CDLL("libnvidia-ml.so.1")
        )
        self.initialized = False
        self.library.nvmlInit_v2.argtypes = []
        self.library.nvmlInit_v2.restype = ctypes.c_int
        self.library.nvmlShutdown.argtypes = []
        self.library.nvmlShutdown.restype = ctypes.c_int
        self.library.nvmlDeviceGetHandleByUUID.argtypes = [
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        self.library.nvmlDeviceGetHandleByUUID.restype = ctypes.c_int
        self.library.nvmlDeviceGetClockInfo.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.POINTER(ctypes.c_uint),
        ]
        self.library.nvmlDeviceGetClockInfo.restype = ctypes.c_int
        self._require(self.library.nvmlInit_v2(), "initialize")
        self.initialized = True
        self.handle = ctypes.c_void_p()
        try:
            self._require(
                self.library.nvmlDeviceGetHandleByUUID(
                    uuid.encode("ascii"), ctypes.byref(self.handle)
                ),
                "select GPU",
            )
        except Exception:
            self.close()
            raise

    @staticmethod
    def _require(code, operation):
        if code:
            raise RuntimeError(f"GPU clock observation could not {operation} (NVML {code})")

    def read(self):
        values = {}
        for name, clock in (("sm_mhz", self.SM_CLOCK), ("memory_mhz", self.MEMORY_CLOCK)):
            value = ctypes.c_uint()
            code = self.library.nvmlDeviceGetClockInfo(self.handle, clock, ctypes.byref(value))
            # A driver may expose only one clock. Preserve that observation and
            # mark an unsupported field unavailable rather than invent a value.
            values[name] = value.value if code == 0 else None
        return values

    def close(self):
        if self.initialized:
            self.library.nvmlShutdown()
            self.initialized = False


class GpuClockMonitor:
    def __init__(self, uuid, *, reader_factory=NvmlClocks, period=1.0, clock=time.monotonic):
        self.stop_event = threading.Event()
        self.latest = {}
        self.observed_at = None
        self.error = None
        self.clock = clock
        self.period = float(period)
        if not 0.1 <= self.period <= 10:
            raise ValueError("Invalid clock observation period")
        self.thread = threading.Thread(
            target=self._run, args=(uuid, reader_factory), name="gpu-clock-monitor", daemon=True
        )
        self.thread.start()

    def _run(self, uuid, reader_factory):
        reader = None
        try:
            reader = reader_factory(uuid)
            while not self.stop_event.is_set():
                self.latest = reader.read()
                self.observed_at = self.clock()
                self.stop_event.wait(self.period)
        except Exception as error:
            self.error = str(error)
            self.latest = {}
        finally:
            if reader is not None:
                reader.close()

    def snapshot(self):
        if (
            self.observed_at is None
            or self.clock() - self.observed_at > 3 * self.period
            or self.error
        ):
            return {"sm_mhz": None, "memory_mhz": None}
        return dict(self.latest)

    def finish(self):
        self.stop_event.set()
        self.thread.join(timeout=2)
