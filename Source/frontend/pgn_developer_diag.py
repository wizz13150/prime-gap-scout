"""Explicit temporary developer recording and a local shareable archive.

No upload, tuning or live statistics page. Only Stop finalizes the archive after
the passive collector has closed. Archive membership is an explicit whitelist.
"""

from pathlib import Path
import datetime as dt
import hashlib
import json
import math
import os
import threading
import uuid
import zipfile
from pgn_session import atomic_bytes
from passive_gpu_diag import PassiveGpuDiagnostic as PassiveTelemetry


_FILES = (
    ("start-context.json", 262144),
    ("end-context.json", 262144),
    ("gpu-diag/gpu-diag.jsonl", 4 * 1024 * 1024),
    ("gpu-diag/gpu-diag-summary.json", 65536),
)
_CATEGORIES = (
    ("gpu_util_percent", "GPU utilization"),
    ("memory_activity_percent", "Memory activity"),
    ("memory_used_mib", "VRAM usage"),
    ("memory_total_mib", "VRAM capacity"),
    ("sm_mhz", "GPU core clock"),
    ("memory_mhz", "GPU memory clock"),
    ("power_w", "GPU power"),
    ("temperature_c", "GPU temperature"),
)
_NOT_COLLECTED = (
    "GPU process inventory",
    "Hardware profiler / SM occupancy counters",
    "Per-kernel timing or instruction trace",
    "CPU utilization and host RAM",
    "VRAM junction or GPU hotspot temperatures",
)


def technical_snapshot(context):
    keys = (
        "session_id",
        "status",
        "start",
        "end",
        "position",
        "tests",
        "gpu_name",
        "gpu_uuid",
        "gpu_index",
        "compute_capability",
        "configuration",
        "native_identity",
        "native_plan",
        "worker_active_seconds",
        "rate_scope",
        "rate_positions",
    )
    result = {key: context.get(key) for key in keys}
    result.update(
        schema="PGN_DEVELOPER_CONTEXT_V1",
        utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        resources=context.get("native_resources"),
        resources_scope="Not collected unless explicitly supplied by the worker/build receipt.",
        transmission="Manual sharing only; no upload.",
        benchmark_gain_claim=False,
    )
    return result


def _finite(value):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return value if math.isfinite(value) else None


def recording_summary(before, after, measured, missing_files, errors):
    """Coverage, not a dashboard: describe only actual observations/context."""
    measured = measured if isinstance(measured, dict) else {}
    raw_samples = _finite(measured.get("samples"))
    samples = max(0, int(raw_samples or 0))
    duration = _finite(measured.get("elapsed_s"))
    source = "sampler" if duration is not None and duration >= 0 else None
    if source is None:
        duration = None
        try:
            duration = max(
                0,
                (
                    dt.datetime.fromisoformat(after["utc"])
                    - dt.datetime.fromisoformat(before["utc"])
                ).total_seconds(),
            )
            source = "context wall time"
        except (KeyError, TypeError, ValueError):
            pass
    recorded = []
    partial = []
    unavailable = []
    for label, keys in (
        ("Device identity", ("gpu_uuid", "gpu_name")),
        ("Search interval", ("start", "end")),
        ("Search configuration", ("configuration",)),
        ("Work counters and rate context", ("position", "tests", "worker_active_seconds")),
        ("Native build/resource receipt", ("native_identity", "resources")),
    ):
        present = [before.get(key) is not None or after.get(key) is not None for key in keys]
        (recorded if all(present) else partial if any(present) else unavailable).append(label)
    metrics = measured.get("metrics") if isinstance(measured.get("metrics"), dict) else {}
    for field, label in _CATEGORIES:
        item = metrics.get(field) if isinstance(metrics.get(field), dict) else {}
        count = _finite(item.get("count")) or 0
        missing = _finite(item.get("missing")) or 0
        if count <= 0:
            unavailable.append(label)
        elif missing > 0 or count < samples:
            partial.append(label)
        else:
            recorded.append(label)
    reason_count = _finite(measured.get("clock_reason_observations")) or 0
    (unavailable if reason_count <= 0 else partial if reason_count < samples else recorded).append(
        "Clock/throttle reasons"
    )
    if measured.get("unknown_reason_sample_count", 0):
        partial.append("Unknown throttle bits retained without interpretation")
    return {
        "duration_seconds": duration,
        "duration_source": source,
        "samples": samples,
        "recorded": recorded,
        "partial": partial,
        "unavailable": unavailable,
        "not_collected": list(_NOT_COLLECTED),
        "missing_files": list(missing_files),
        "errors": list(dict.fromkeys(str(error) for error in errors if error)),
        "throughput_scope": "Coordinator context only; not a qualified Native benchmark.",
        "automatic_upload": False,
        "hardware_settings_changed": False,
    }


def _summary_text(summary):
    seconds = summary.get("duration_seconds")
    duration = "Unavailable" if seconds is None else f"{seconds:.1f} seconds"
    lines = [
        "PGN68 - DEVELOPER DIAGNOSTIC RECORDING",
        "",
        "This local archive is ready for manual sharing with the developer.",
        "Nothing was uploaded. No hardware settings were changed.",
        "",
        "Duration: " + duration + " (" + str(summary.get("duration_source") or "unavailable") + ")",
        "GPU samples: " + str(summary["samples"]),
    ]
    for key, title in (
        ("recorded", "RECORDED"),
        ("partial", "PARTIALLY AVAILABLE"),
        ("unavailable", "UNAVAILABLE"),
        ("not_collected", "NOT COLLECTED"),
        ("missing_files", "MISSING RECORDING FILES"),
        ("errors", "ERRORS"),
    ):
        lines.extend(["", title])
        lines.extend("  - " + value for value in summary[key])
        if not summary[key]:
            lines.append("  None")
    lines.extend(
        [
            "",
            "Sparse driver samples do not prove optimal GPU usage.",
            "This is a diagnostic recording, not a performance benchmark.",
            "The manifest lists the actual files and their SHA-256 hashes.",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


class DeveloperRecorder:
    def __init__(self):
        self.owner = threading.get_ident()
        self.collector = None
        self.folder = None
        self.begin = None
        self.error = None
        self.archive_path = None
        self.archive_status = "Not created"
        self.summary = None
        self._stopping = False
        self.archive_files = []
        self.archive_bytes = None

    def _owner(self):
        if threading.get_ident() != self.owner:
            raise RuntimeError("Developer recording belongs to the coordinator")

    def state(self):
        alive = bool(self.collector and self.collector.thread and self.collector.thread.is_alive())
        error = self.error or (self.collector.error if self.collector else None)
        return {
            "status": (
                ("Stopping" if self._stopping else "Recording")
                if alive
                else "Unavailable" if error else "Stopped"
            ),
            "recording": alive,
            "folder": str(self.folder) if self.folder else None,
            "error": error,
            "path": str(self.collector.path) if self.collector else None,
            "archive_path": str(self.archive_path) if self.archive_path else None,
            "archive_status": self.archive_status,
            "summary": self.summary,
            "archive_files": list(self.archive_files),
            "archive_bytes": self.archive_bytes,
        }

    def start(self, context):
        self._owner()
        if self.state()["recording"]:
            return self.state()
        self.folder = Path(context["folder"]) / ("developer-diagnostics-" + uuid.uuid4().hex[:12])
        self.folder.mkdir(exist_ok=False)
        self.begin = technical_snapshot(context)
        self.error = None
        self.collector = None
        self.archive_path = None
        self.archive_status = "Recording"
        self.summary = None
        self._stopping = False
        self.archive_files = []
        self.archive_bytes = None
        try:
            atomic_bytes(
                self.folder / "start-context.json",
                (json.dumps(self.begin, indent=2, default=str) + "\n").encode(),
            )
            self.collector = PassiveTelemetry(self.folder, context["gpu_uuid"], True)
        except (OSError, ValueError, KeyError, RuntimeError) as problem:
            self.error = "Cannot start diagnostic recording: " + str(problem)
            self.archive_status = "Not created"
        return self.state()

    def _recording_files(self):
        root = self.folder.resolve()
        files = {}
        missing = []
        for name, limit in _FILES:
            path = self.folder / name
            if not path.exists():
                missing.append(name)
                continue
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
                raise OSError("Unsafe diagnostic file: " + name)
            # Parents can be reparse points too; do not silently include a file
            # from somewhere else even if a recording folder was replaced.
            for parent in path.parents:
                if parent == self.folder.parent:
                    break
                if parent.is_symlink() or (getattr(parent.stat(), "st_file_attributes", 0) & 0x400):
                    raise OSError("Reparse point in diagnostic path: " + name)
            with path.open("rb") as stream:
                data = stream.read(limit + 1)
            if len(data) > limit:
                raise OSError("Diagnostic file exceeds its size bound: " + name)
            files[name] = data
        return files, missing

    def stop(self, context):
        self._owner()
        if self.folder is None:
            return self.state()
        if self.archive_path is not None:
            return self.state()
        self._stopping = True
        if self.collector:
            try:
                self.collector.finish()
            except Exception as problem:
                self.error = "Cannot finish diagnostic recorder: " + str(problem)
            if self.collector.thread and self.collector.thread.is_alive():
                self.error = "Diagnostic recorder is still stopping; no archive was created."
                self.archive_status = "Waiting for recorder"
                return self.state()
        self._stopping = False
        end = technical_snapshot(context)
        before = self.begin or {}
        throughput = None
        try:
            seconds0 = before.get("worker_active_seconds")
            seconds1 = end.get("worker_active_seconds")
            numerator0 = before.get("rate_positions")
            numerator1 = end.get("rate_positions")
            if seconds1 > seconds0 and numerator1 >= numerator0:
                throughput = _finite((numerator1 - numerator0) / (seconds1 - seconds0))
        except (TypeError, ValueError, OverflowError, ZeroDivisionError):
            pass
        end.update(
            recording_state=self.state(),
            interval_positions_per_active_worker_second=throughput,
            throughput_note="Observed coordinator delta; initialization remains included. Not a qualified Native benchmark.",
        )
        self.archive_status = "Finalizing"
        try:
            atomic_bytes(
                self.folder / "end-context.json",
                (json.dumps(end, indent=2, default=str) + "\n").encode(),
            )
            files, missing = self._recording_files()
            measured = getattr(self.collector, "summary", None) if self.collector else None
            errors = [
                self.error,
                getattr(self.collector, "error", None) if self.collector else None,
            ]
            summary_name = "gpu-diag/gpu-diag-summary.json"
            if summary_name in files:
                try:
                    disk_summary = json.loads(files[summary_name])
                    assert isinstance(disk_summary, dict)
                    measured = disk_summary
                except (ValueError, AssertionError):
                    errors.append(
                        "Sampler summary file is unreadable; coverage may be unavailable."
                    )
            self.summary = recording_summary(before, end, measured, missing, errors)
            files["SUMMARY.txt"] = _summary_text(self.summary)
            manifest = {
                "schema": "PGN_LOCAL_DEVELOPER_ARCHIVE_V1",
                "utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "collector_closed": True,
                "summary": self.summary,
                "files": [
                    {
                        "path": name,
                        "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest().upper(),
                    }
                    for name, data in sorted(files.items())
                ],
                "membership": "Only explicit files from this one recording; no session database, results or unrelated files.",
                "automatic_upload": False,
                "hardware_settings_changed": False,
            }
            files["DIAGNOSTIC-MANIFEST.json"] = (json.dumps(manifest, indent=2) + "\n").encode(
                "utf-8"
            )
            stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S-%fZ")
            target = self.folder / ("PGN68-diagnostics-" + stamp + ".zip")
            temporary = target.with_suffix(".zip.partial")
            with zipfile.ZipFile(temporary, "x", compression=zipfile.ZIP_DEFLATED) as archive:
                for name, data in sorted(files.items()):
                    archive.writestr(name, data)
            with zipfile.ZipFile(temporary) as archive:
                if archive.testzip() is not None:
                    raise OSError("Diagnostic archive integrity check failed")
                if set(archive.namelist()) != set(files):
                    raise OSError("Diagnostic archive membership check failed")
                for name, data in files.items():
                    if archive.read(name) != data:
                        raise OSError("Diagnostic archive readback failed: " + name)
            os.replace(temporary, target)
            self.archive_path = target
            self.archive_files = [
                {"path": name, "bytes": len(data)} for name, data in sorted(files.items())
            ]
            self.archive_bytes = target.stat().st_size
            self.archive_status = (
                "Ready with limitations"
                if any(
                    self.summary[key]
                    for key in ("partial", "unavailable", "missing_files", "errors")
                )
                else "Ready"
            )
        except (
            OSError,
            ValueError,
            RuntimeError,
            zipfile.BadZipFile,
            zipfile.LargeZipFile,
        ) as problem:
            self.error = "Cannot finalize diagnostic archive: " + str(problem)
            self.archive_status = "Failed"
            self.archive_path = None
        return self.state()
