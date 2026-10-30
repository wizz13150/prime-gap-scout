"""Temporary passive GPU diagnostic. Import/default construction never queries hardware.
Only opted-in runtime sampling invokes the existing nvidia-smi query interface.
No CUDA/NVML Python bindings, setting changes, process inventory, or profiler.
"""

from pathlib import Path
import csv, datetime as dt, io, json, math, os, re, shutil, subprocess, threading, time

METRICS = {
    "gpu_util_percent": ("utilization.gpu",),
    "memory_activity_percent": ("utilization.memory",),
    "memory_used_mib": ("memory.used",),
    "memory_total_mib": ("memory.total",),
    "sm_mhz": ("clocks.sm", "clocks.current.sm"),
    "memory_mhz": ("clocks.mem", "clocks.current.memory"),
    "power_w": ("power.draw",),
    "temperature_c": ("temperature.gpu",),
}
REASON_FIELDS = ("clocks_event_reasons.active", "clocks_throttle_reasons.active")
# Stable historical bits; retain every unknown bit without interpreting it.
REASONS = {
    1: "gpu_idle",
    2: "applications_clocks",
    4: "software_power_cap",
    8: "hardware_slowdown",
    16: "sync_boost",
    32: "software_thermal",
    64: "hardware_thermal",
    128: "hardware_power_brake",
    256: "display_clocks",
}
UUID_RE = re.compile(r"GPU-[0-9a-fA-F][0-9a-fA-F-]{7,79}\Z")
MAX_BYTES = 4 * 1024 * 1024


def validate_uuid(uuid):
    if not isinstance(uuid, str) or not UUID_RE.fullmatch(uuid):
        raise ValueError("One explicit GPU UUID required")
    return uuid


def number(text):
    try:
        value = float(text.strip())
        return value if math.isfinite(value) else None
    except (ValueError, AttributeError):
        return None


def property_selection(help_text):
    if len(help_text) > 131072:
        raise ValueError("Unexpected help size")

    def present(name):
        return bool(re.search(r"(?<![\w.])" + re.escape(name) + r"(?![\w.])", help_text))

    if not present("uuid"):
        raise ValueError("UUID query unavailable")
    selected = {"uuid": "uuid"}
    for key, aliases in METRICS.items():
        selected[key] = next((name for name in aliases if present(name)), None)
    selected["clock_reasons_active_hex"] = next(
        (name for name in REASON_FIELDS if present(name)), None
    )
    return selected


def query_arguments(uuid, selected):
    validate_uuid(uuid)
    fields = [name for name in selected.values() if name is not None]
    if not fields or fields[0] != "uuid":
        raise ValueError("UUID must be queried")
    return ["--id=" + uuid, "--query-gpu=" + ",".join(fields), "--format=csv,noheader,nounits"]


def parse_sample(stdout, selected, uuid):
    validate_uuid(uuid)
    if len(stdout) > 4096:
        raise ValueError("Unexpected query output size")
    rows = list(csv.reader(io.StringIO(stdout.strip())))
    keys = [key for key, name in selected.items() if name is not None]
    if len(rows) != 1 or len(rows[0]) != len(keys):
        raise ValueError("Unexpected query shape")
    values = {key: value.strip() for key, value in zip(keys, rows[0])}
    if values.get("uuid", "").casefold() != uuid.casefold():
        raise ValueError("GPU UUID mismatch")
    sample = {key: None for key in METRICS}
    for key in METRICS:
        value = number(values.get(key, ""))
        if value is not None:
            if key in ("gpu_util_percent", "memory_activity_percent") and not 0 <= value <= 100:
                value = None
            elif key != "temperature_c" and value < 0:
                value = None
        sample[key] = value
    raw = values.get("clock_reasons_active_hex", "")
    try:
        mask = int(raw, 0)
        mask = mask if 0 <= mask < 1 << 64 else None
    except ValueError:
        mask = None
    sample["clock_reasons_active_hex"] = None if mask is None else hex(mask)
    sample["clock_reasons"] = (
        None if mask is None else [name for bit, name in REASONS.items() if mask & bit]
    )
    known = sum(REASONS)
    sample["clock_reasons_unknown_hex"] = None if mask is None else hex(mask & ~known)
    return sample


def from_existing_telemetry_row(row, uuid):
    """Pure optional adapter for the existing nine-column GPU CSV (no extra query)."""
    if len(row) != 9:
        raise ValueError("Expected nine GPU CSV columns")
    # timestamp, uuid, sm, memoryclock, temperature, power, utilization, used, total
    selected = {
        "uuid": "uuid",
        "sm_mhz": "clocks.sm",
        "memory_mhz": "clocks.mem",
        "temperature_c": "temperature.gpu",
        "power_w": "power.draw",
        "gpu_util_percent": "utilization.gpu",
        "memory_used_mib": "memory.used",
        "memory_total_mib": "memory.total",
    }
    stream = io.StringIO()
    csv.writer(stream).writerow(row[1:])
    return parse_sample(stream.getvalue(), selected, uuid)


class RunningSummary:
    def __init__(self):
        self.samples = 0
        self.values = {
            k: {"count": 0, "missing": 0, "sum": 0.0, "min": None, "max": None}
            for k in (*METRICS, "query_ms")
        }
        self.reasons = {name: 0 for name in REASONS.values()}
        self.reason_samples = 0
        self.unknown_reason_samples = 0

    def add(self, sample):
        self.samples += 1
        for key, s in self.values.items():
            value = sample.get(key)
            if value is None:
                s["missing"] += 1
                continue
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("Nonfinite aggregate")
            s["count"] += 1
            s["sum"] += value
            s["min"] = value if s["min"] is None else min(s["min"], value)
            s["max"] = value if s["max"] is None else max(s["max"], value)
        if sample.get("clock_reasons") is not None:
            self.reason_samples += 1
            for name in sample["clock_reasons"]:
                if name in self.reasons:
                    self.reasons[name] += 1
            if sample.get("clock_reasons_unknown_hex") not in (None, "0x0"):
                self.unknown_reason_samples += 1

    def result(self):
        fields = {
            k: {
                "count": v["count"],
                "missing": v["missing"],
                "mean": None if not v["count"] else v["sum"] / v["count"],
                "min": v["min"],
                "max": v["max"],
            }
            for k, v in self.values.items()
        }
        return {
            "samples": self.samples,
            "metrics": fields,
            "clock_reason_observations": self.reason_samples,
            "clock_reason_active_sample_counts": self.reasons,
            "unknown_reason_sample_count": self.unknown_reason_samples,
        }


class PassiveGpuDiagnostic:
    """Telemetry-compatible optional test-build adapter; no console output."""

    def __init__(self, folder, uuid, enabled=False, *, max_samples=900):
        self.uuid = validate_uuid(uuid)
        self.stop_event = threading.Event()
        self.latest = {}
        self.thread = None
        self.error = None
        self.summary = None
        self.enabled = bool(enabled)
        self.max_samples = int(max_samples)
        if not 1 <= self.max_samples <= 3600:
            raise ValueError("Sample bound1..3600")
        self.folder = Path(folder) / "gpu-diag"
        self.path = self.folder / "gpu-diag.jsonl"
        self.summary_path = self.folder / "gpu-diag-summary.json"
        if not self.enabled:
            return
        self.tool = shutil.which("nvidia-smi.exe" if os.name == "nt" else "nvidia-smi")
        if not self.tool:
            self.error = "nvidia-smi unavailable; diagnostic disabled"
            return
        try:
            self.folder.mkdir(exist_ok=False)
        except OSError:
            self.error = "Diagnostic output exists or cannot be created"
            return
        self.thread = threading.Thread(
            target=self._sample, name="pgn-passive-gpu-diag", daemon=True
        )
        self.thread.start()

    def _command(self, args, timeout):
        # This is the only subprocess boundary: fixed read-only flags, exact one GPU.
        kwargs = {"creationflags": 0x08000000} if os.name == "nt" else {}
        return subprocess.run(
            [self.tool, *args],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
            **kwargs,
        )

    def _sample(self):
        started = time.monotonic()
        acc = RunningSummary()
        written = 0
        selected = None
        reason = "sample_limit"
        query_exit = None
        overruns = 0
        null_fields = []
        try:
            # Discover property spellings once, without enumerating GPUs or processes.
            help_result = self._command(["--help-query-gpu"], 2.0)
            if help_result.returncode:
                raise RuntimeError("nvidia-smi help exit " + str(help_result.returncode))
            selected = property_selection(help_result.stdout)
            null_fields = [k for k, v in selected.items() if v is None]
            with self.path.open("x", encoding="utf-8", newline="\n") as stream:
                header = {
                    "kind": "header",
                    "schema": "PGN_TEMP_PASSIVE_GPU_DIAG_V1",
                    "gpu_uuid": self.uuid,
                    "period_target_s": 1,
                    "max_samples": self.max_samples,
                    "unsupported_property_fields": null_fields,
                    "query_properties": selected,
                    "interpretation": "Sparse driver observations; utilization is not SM occupancy or proof of optimal performance. Means are unweighted sample means.",
                }
                line = json.dumps(header, separators=(",", ":"), allow_nan=False) + "\n"
                stream.write(line)
                written += len(line.encode())
                while acc.samples < self.max_samples and not self.stop_event.is_set():
                    before = time.monotonic()
                    result = self._command(query_arguments(self.uuid, selected), 1.5)
                    query_exit = result.returncode
                    if result.returncode:
                        raise RuntimeError("nvidia-smi query exit " + str(result.returncode))
                    sample = parse_sample(result.stdout, selected, self.uuid)
                    sample["query_ms"] = (time.monotonic() - before) * 1000
                    sample.update(
                        kind="sample",
                        utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                        elapsed_s=round(time.monotonic() - started, 3),
                    )
                    line = json.dumps(sample, separators=(",", ":"), allow_nan=False) + "\n"
                    if written + len(line.encode()) > MAX_BYTES - 16384:
                        reason = "file_limit"
                        break
                    stream.write(line)
                    stream.flush()
                    written += len(line.encode())
                    acc.add(sample)
                    self.latest = {
                        k: sample[k]
                        for k in ("sm_mhz", "memory_mhz", "gpu_util_percent", "memory_used_mib")
                    }
                    spent = time.monotonic() - before
                    if spent > 1:
                        overruns += 1
                    self.stop_event.wait(max(0, 1 - spent))
                if self.stop_event.is_set():
                    reason = "requested_stop"
        except subprocess.TimeoutExpired:
            self.error = "nvidia-smi bounded query timed out"
            reason = "query_timeout"
        except Exception as error:
            self.error = (
                str(error)[:160]
                if isinstance(error, (ValueError, RuntimeError))
                else "Diagnostic " + type(error).__name__
            )
            reason = "diagnostic_error"
        finally:
            summary = {
                "kind": "summary",
                "schema": "PGN_TEMP_PASSIVE_GPU_DIAG_SUMMARY_V1",
                "gpu_uuid": self.uuid,
                **acc.result(),
                "elapsed_s": round(time.monotonic() - started, 3),
                "reason": reason,
                "error": self.error,
                "last_query_exit": query_exit,
                "period_target_s": 1,
                "query_overruns": overruns,
                "unsupported_property_fields": null_fields,
                "claims": {
                    "optimal_100_percent_proved": False,
                    "benchmark_gain": False,
                    "clock_or_power_changes": False,
                    "process_inventory_collected": False,
                },
            }
            self.summary = summary
            try:
                if self.path.exists():
                    with self.path.open("a", encoding="utf-8", newline="\n") as stream:
                        stream.write(
                            json.dumps(summary, separators=(",", ":"), allow_nan=False) + "\n"
                        )
                temporary = self.summary_path.with_suffix(".tmp")
                with temporary.open("x", encoding="utf-8") as stream:
                    json.dump(summary, stream, separators=(",", ":"), allow_nan=False)
                os.replace(temporary, self.summary_path)
            except OSError:
                if self.error is None:
                    self.error = "Cannot write diagnostic summary"

    def finish(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)
        if self.thread and self.thread.is_alive():
            self.error = "Diagnostic sampler still stopping; do not claim closure"
        return self.summary
