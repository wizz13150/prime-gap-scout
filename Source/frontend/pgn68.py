"""PGN 68 local, mono-GPU command line. Python standard library only."""
from __future__ import annotations

import argparse
from bisect import bisect_right
import contextlib
import csv
import ctypes
import datetime as dt
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import math
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import struct
import sys
import tempfile
import threading
import time
import zipfile

# Source execution remains isolated but can import its own shipped modules.
sys.path.insert(0,str(Path(__file__).resolve().parent))
# Load the shipped console projection from its explicit package location.
_ui_dir = Path(sys.executable).resolve().parent / "ui"
if getattr(sys, "frozen", False) and (_ui_dir / "console_ui.py").is_file():
    import importlib.util as _ui_import
    for _ui_name in ("pgn_dashboard_rc7", "console_ui"):
        _ui_spec = _ui_import.spec_from_file_location(_ui_name, _ui_dir / (_ui_name + ".py"))
        _ui_module = _ui_import.module_from_spec(_ui_spec)
        sys.modules[_ui_name] = _ui_module
        _ui_spec.loader.exec_module(_ui_module)
    Dashboard = sys.modules["console_ui"].Dashboard
else:
    from console_ui import Dashboard
from pgn_output import default_output_base, complete_counts_text, top_rows
from pgn_session import SessionStore,SessionControllerLock,read_session_metadata
from pgn_start_failures import remember_start_failure,restore_start_failure
from pgn_ui_options import display_rows
from pgn_native_contract import PROTOCOL,requested_gap,resolve_args,config_fields,reset_new_args,resume_args,require_new_configuration,checked_checkpoint

VERSION = "1.2.0-rc1"
H10_MIN = 10 << 64
H10_END = 11 << 64
MR_LIMIT = 3317044064679887385961981
MR_BASES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41)
COUNTERS = re.compile(r"\[pgn-counters\].*?\bpositions=(\d+)\b.*?\btests=(\d+)\b")
GAP = re.compile(r"\bGAP merit=([0-9.eE+\-]+) gap=(\d+) lower=(\d+) upper=(\d+)")
UTC = dt.timezone.utc


def exact_integer(text):
    """Scientific notation is accepted only when its Decimal value is integral."""
    if len(str(text)) > 128:
        raise argparse.ArgumentTypeError("Number is too long")
    try:
        value = Decimal(str(text))
        if not value.is_finite() or value < 0 or value.adjusted() > 39:
            raise ValueError
        if value != value.to_integral_value():
            raise ValueError
        return int(value)
    except (InvalidOperation, ValueError, OverflowError):
        raise argparse.ArgumentTypeError("Use a nonnegative, exact integer (scientific notation is allowed)")


def apply_new_parameters(args,values):
    """Explicit NEW only; a live session's durable filters remain immutable."""
    args.start=values['start'];args.end=values['end'];args.length=None;args.resume=None
    args.gpu=values.get('gpu',args.gpu);args.min_gap=values.get('min_gap',args.min_gap)
    args.count_gap=values.get('count_gap',args.min_gap);args.detail_gap=values.get('detail_gap',args.min_gap)
    for name in ('bins','report_top','display_rows','target_merit','name','profile','chunk_length','debug','telemetry','archive','skip_self_test','headless'):
        if name in values:setattr(args,name,values[name])
    for name in ('output','worker'):
        if name in values:setattr(args,name,Path(values[name]) if values[name] else None)
    args._plan_id=values.get('plan_id');args._plan_root=values.get('plan_root')
    # Start now is the explicit submission; MENU remains a next-launch setting.
    reset_new_args(args,values)
    args.menu=False


def argument_parser():
    parser = argparse.ArgumentParser(
        description="Local67..80-bit prime-gap search on one CUDA GPU; no PGN network submission.",
        epilog="Runtime67..80 domain; actual Native plan, threshold echo, image metadata and low64/halo guards are mandatory. Unimplemented seams are rejected, never skipped. GPU sm86 or sm120. No clock/power/fan changes.")
    parser.add_argument("--version", action="version", version="PGN 68 " + VERSION)
    parser.add_argument("--gpu", type=int, default=0, metavar="INDEX", help="Choose a visible GPU index from --list-gpus (default0); no automatic best-GPU selection")
    parser.add_argument("--list-gpus", action="store_true", help="List visible CUDA devices and exit")
    parser.add_argument("--start", type=exact_integer, default=exact_integer("2e20"), help="Exact starting integer, default2e20; scientific notation is accepted without float rounding")
    bounds = parser.add_mutually_exclusive_group()
    bounds.add_argument("--end", type=exact_integer, help="Exclusive endpoint; omit both end/length for START+1e15")
    bounds.add_argument("--length", type=exact_integer, help="Exact interval length instead of --end")
    parser.add_argument("--min-gap",type=requested_gap,default="auto",help="Auto uses the pinned67..80 integer table; manual integer954..2147483647. Actual worker plan and checkpoint must bind the effective value")
    parser.add_argument("--count-gap", type=exact_integer, default=None, help="Advanced count override; omitted inherits --min-gap")
    parser.add_argument("--detail-gap", type=exact_integer, default=None, help="Advanced detail override; omitted inherits --min-gap")
    parser.add_argument("--report-top", type=exact_integer, default=100, help="Maximum detailed rows in the human report (default100); counts remain complete")
    parser.add_argument("--display-rows", type=display_rows, default=10, help="Rows in BOTH Best and Recent tables: integer10..30 (default10); reports/CSV/science remain unchanged")
    parser.add_argument("--target-merit", type=float, default=32.0, help="Display merit goal and medal colors (default32)")
    parser.add_argument("--bins", type=exact_integer, default=100, help="Number of exact integer range pieces (default100, max1000000)")
    parser.add_argument("--output", type=Path, default=None, help="Output parent; blank uses the results folder beside the program, with no silent fallback")
    parser.add_argument("--resume", type=Path, help="Resume this durable session directory; input/worker/K/journal binding is verified")
    parser.add_argument("--profile", choices=("auto", "8", "16", "32", "64"), default="auto", help="Native K/chunk profile: auto uses actual --plan bytes; this never selects a different GPU")
    parser.add_argument("--chunk-length", type=exact_integer, default=None, help="Advanced maximum positions per automatic memory chunk")
    parser.add_argument("--debug", action="store_true", help="Opt in to verbose raw Native logs; normal logs contain summaries only")
    parser.add_argument("--headless", action="store_true", help="Exit after the run; never wait for interactive keys or menu")
    startup=parser.add_mutually_exclusive_group()
    startup.add_argument("--menu", action="store_true", help="Open the menu before a new run; COMPLETE still waits for explicit M")
    startup.add_argument("--idle", action="store_true", help="Open the complete Idle console without GPU discovery or starting a search")
    parser.add_argument("--name", default="Robert", help="Name printed in the Brian-compatible report")
    parser.add_argument("--worker", type=Path, help="Advanced: explicit local pgn68-worker path")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--self-test", action="store_true", help="Run the worker self-test and exit")
    modes.add_argument("--fermat-diagnostic", action="store_true", help="Run the worker Fermat diagnostic and exit")
    parser.add_argument("--skip-self-test", action="store_true", help="Advanced: explicitly skip the pre-search self-test")
    parser.add_argument("--telemetry", action="store_true", help="Read nvidia-smi once per second into a CSV; never change settings")
    parser.add_argument("--archive", action="store_true", help="Also create a ZIP of this new run directory")
    return parser


def validate_range(args,parser):
    if args.gpu<0:parser.error('--gpu must be a nonnegative visible device index')
    if not 1<=args.bins<=1000000:parser.error('--bins must be from1 through1000000')
    if not 1<=args.report_top<=1000000:parser.error('--report-top must be from1 through1000000')
    if args.chunk_length is not None and args.chunk_length<=0:parser.error('--chunk-length must be positive')
    end=args.start+args.length if args.length is not None else args.end
    if end is None:end=args.start+exact_integer('1e15')
    try:resolve_args(args,end)
    except (ValueError,TypeError,KeyError)as error:parser.error(str(error))
    return end


def resolve_worker(explicit=None, architecture=None, profile=None):
    if explicit:
        worker = explicit.expanduser().resolve()
        if not worker.is_file():
            raise RuntimeError(f"Worker not found: {worker}")
        return worker
    extension = ".exe" if os.name == "nt" else ""
    # Device-info is host-only, so an sm86 executable can enumerate an sm120 GPU.
    names = ([f"pgn68-worker-{architecture}-k{profile}{extension}"] if profile is not None else
             [f"pgn68-worker-{architecture}-k64{extension}", f"pgn68-worker-{architecture}{extension}", "pgn68-worker" + extension]
             if architecture else ["pgn68-worker-sm86-k64" + extension, "pgn68-worker-sm120-k64" + extension,
                                   "pgn68-worker-sm86" + extension, "pgn68-worker-sm120" + extension,
                                   "pgn68-worker" + extension])
    roots = [Path(sys.executable).resolve().parent] if getattr(sys, "frozen", False) else [Path(__file__).resolve().parent]
    if hasattr(sys, "_MEIPASS"):
        roots.append(Path(sys._MEIPASS))
    for name in names:
        for root in roots:
            worker = root / "bin" / name
            if worker.is_file():
                return worker.resolve()
    raise RuntimeError(f"Missing bin/{names[0]} next to this program. Keep the release directory intact.")


def child_options():
    # Isolate Ctrl+C: the frontend publishes stop.request instead of killing CUDA.
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
    return {"start_new_session": True}


def resolve_checkpoint_worker(identity,architecture,profile):
    """Resume with the exact installed image that produced the checkpoint."""
    expected=str(identity.get('worker_sha256','')).upper()
    if not re.fullmatch(r'[0-9A-F]{64}',expected):raise ValueError('Invalid checkpoint worker identity')
    if profile not in (8,16,32,64) or not re.fullmatch(r'sm[0-9]{2,3}',str(architecture)):raise ValueError('Invalid checkpoint architecture/profile')
    current=resolve_worker(None,architecture,profile)
    if file_sha256(current)==expected:return current
    root=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False)else Path(__file__).resolve().parent
    suffix='.exe'if os.name=='nt'else''
    candidate=root/'bin'/'compat'/expected/f'pgn68-worker-{architecture}-k{profile}{suffix}'
    if candidate.is_file()and file_sha256(candidate)==expected:return candidate
    raise RuntimeError('This checkpoint requires its original worker image. Keep bin/compat from the complete release; the saved range has not been changed.')


def enumerate_gpus(worker):
    result = subprocess.run([str(worker), "--device-info"], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=30, **child_options())
    if result.returncode:
        raise RuntimeError("GPU discovery failed: " + (result.stderr.strip() or result.stdout.strip()))
    try:
        info = json.loads(result.stdout)
        devices = info["devices"]
        required = ("index", "model", "uuid", "cc_major", "cc_minor", "vram_bytes")
        if not isinstance(devices, list) or any(not isinstance(d, dict) or any(k not in d for k in required) for d in devices):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise RuntimeError("Worker --device-info did not return its expected device JSON")
    return info, devices


def select_gpu(devices, index):
    found = [d for d in devices if d.get("index") == index]
    if len(found) != 1:
        raise RuntimeError(f"GPU {index} is not visible; use --list-gpus")
    device = found[0]
    if (device.get("cc_major"), device.get("cc_minor")) not in ((8, 6), (12, 0)):
        raise RuntimeError("Selected GPU is unsupported: this release admits sm86 or sm120 only")
    uuid = device.get("uuid", "")
    if not re.fullmatch(r"GPU-[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", uuid):
        raise RuntimeError("Worker did not provide an authentic device UUID; refusing ambiguous GPU selection")
    environment = os.environ.copy()
    environment["CUDA_VISIBLE_DEVICES"] = uuid
    return device, environment


def new_run_directory(parent):
    if parent is None:
        parent = default_output_base()
    parent = parent.expanduser().resolve()
    parent.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%fZ")
    return Path(tempfile.mkdtemp(prefix="pgn68-" + stamp + "-", dir=parent))


def atomic_text(path, text):
    # A leftover from an interrupted write must not poison the next session.
    # Use our own same-directory file; keep the old published report intact.
    fd,name=tempfile.mkstemp(prefix=path.name+".",suffix=".pending",dir=path.parent)
    pending=Path(name)
    try:
        with os.fdopen(fd,"w",encoding="utf-8",newline="\n") as stream:
            stream.write(text);stream.flush();os.fsync(stream.fileno())
        deadline=time.monotonic()+1
        while True:
            try:os.replace(pending,path);break
            except PermissionError:
                if os.name!="nt" or time.monotonic()>=deadline:raise
                time.sleep(.02)  # A concurrent results reader can briefly deny replacement.
    finally:
        pending.unlink(missing_ok=True)


def exact_prime(n):
    """Deterministic MR13 on the stated strict domain; final-boundary repair only."""
    if not 0 <= n < MR_LIMIT:
        raise ValueError("Final-tail integer is outside the deterministic MR13 admission bound")
    if n < 2:
        return False
    if n in MR_BASES:
        return True
    if any(n % p == 0 for p in MR_BASES):
        return False
    odd = n - 1
    shifts = 0
    while odd % 2 == 0:
        odd //= 2
        shifts += 1
    for base in MR_BASES:
        residue = pow(base, odd, n)
        if residue in (1, n - 1):
            continue
        for _ in range(shifts - 1):
            residue = residue * residue % n
            if residue == n - 1:
                break
        else:
            return False
    return True


def final_boundary_pair(processed_end):
    """P is STRICTLY below processed_end; Q is >= it, including an end prime."""
    if processed_end <= 2:
        raise ValueError("Final boundary has no lower prime")
    lower = processed_end - 1
    if lower > 2 and lower % 2 == 0:
        lower -= 1
    while not exact_prime(lower):
        lower -= 2 if lower > 3 else 1
    upper = processed_end
    if upper > 2 and upper % 2 == 0:
        upper += 1
    while not exact_prime(upper):
        upper += 2 if upper >= 3 else 1
    return lower, upper


class GapRecords:
    def __init__(self, start, end, minimum, stream, detail_minimum=None, count_minimum=None):
        self.start, self.end, self.minimum, self.stream = start, end, minimum, stream
        self.detail_minimum = minimum if detail_minimum is None else detail_minimum
        self.count_minimum = minimum if count_minimum is None else count_minimum
        self.retention_minimum = min(minimum, self.count_minimum, self.detail_minimum)
        self.by_lower = {}
        self.rows = []
        self.details = []
        self.retained_rows = []

    def add(self, lower, upper, source):
        gap = upper - lower
        if lower < self.start or lower >= self.end or gap < 800:
            raise RuntimeError("Worker gap is outside its admitted ownership/profile")
        prior = self.by_lower.get(lower)
        if prior is not None:
            if prior[0] != gap:
                raise RuntimeError(f"Conflicting gaps for lower prime {lower}: {prior[0]} and {gap}")
            return False
        # Remember even filtered rows, so a conflict cannot hide behind min-gap.
        self.by_lower[lower] = (gap, upper, source)
        merit = gap / math.log(lower)
        if gap >= self.retention_minimum:
            self.retained_rows.append((gap, merit, lower))
        if gap >= self.detail_minimum:
            self.details.append((gap, merit, lower))
            self.stream.write(f"Gap {gap} {merit:.4f} {lower}\n")
            self.stream.flush()
        if gap >= self.count_minimum:
            self.rows.append((gap, merit, lower))
            return True
        return False


def bin_counts(start, end, bins, rows):
    """Ownership by lower prime, using exact floor endpoints, including ties."""
    length = end - start
    boundaries = [start + length * i // bins for i in range(bins + 1)]
    counts = [0] * bins
    for _, _, lower in rows:
        if not start <= lower < end:
            raise ValueError("Gap lower prime lies outside the requested bin range")
        index = bisect_right(boundaries, lower) - 1
        counts[index] += 1
    return boundaries, counts


def write_bin_outputs(folder, args, end, position, status, rows):
    processed_end = args.start + position
    accepted = [r for r in rows if r[2] < processed_end]
    boundaries, counts = bin_counts(args.start, end, args.bins, accepted)
    if status == "COMPLETE":
        if position != end - args.start:
            raise RuntimeError("Final count list requires the complete exact range")
        name = f"counts_ge{args.count_gap}.csv"
        atomic_text(folder / name, complete_counts_text(counts))
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(("index", "start", "end", "count"))
        writer.writerows((i + 1, boundaries[i], boundaries[i + 1], counts[i]) for i in range(args.bins))
        atomic_text(folder / "bins.csv", output.getvalue())
        return {"counts_csv": name, "bins_csv": "bins.csv", "partial_csv": None}
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("index", "start", "end", "count_observed", "coverage", "covered_end"))
    for i, count in enumerate(counts):
        left, right = boundaries[i], boundaries[i + 1]
        coverage = "COMPLETE" if right <= processed_end else "PARTIAL" if left < processed_end else "UNSEARCHED"
        writer.writerow((i + 1, left, right, "" if coverage == "UNSEARCHED" else count, coverage,
                         min(right, max(left, processed_end))))
    name = f"counts_ge{args.count_gap}.partial.csv"
    atomic_text(folder / name, output.getvalue())
    return {"counts_csv": None, "bins_csv": None, "partial_csv": name}


class ProcessClock:
    """Whole worker lifetime: Windows creation/exit FILETIMEs, POSIX launch wall."""
    def __init__(self, process, monotonic_begin, utc_begin):
        self.process = process
        self.begin = monotonic_begin
        self.started = utc_begin
        self._kernel = None
        self._creation = None
        self._finished = None
        self._finish_lock = threading.Lock()
        if os.name == "nt":
            from ctypes import wintypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.GetProcessTimes.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
            kernel.GetProcessTimes.restype = wintypes.BOOL
            kernel.GetSystemTimeAsFileTime.argtypes = (ctypes.POINTER(wintypes.FILETIME),)
            kernel.GetSystemTimeAsFileTime.restype = None
            self._ft = wintypes.FILETIME
            self._kernel = kernel
            creation, _ = self._times()
            now = self._ft()
            kernel.GetSystemTimeAsFileTime(ctypes.byref(now))
            self._creation = creation
            self.begin = time.monotonic() - max(0.0, (self._value(now) - creation) / 1e7)
            self.started = dt.datetime.fromtimestamp(creation / 1e7 - 11644473600, UTC)

    @staticmethod
    def _value(value):
        return (int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime)

    def _times(self):
        values = [self._ft() for _ in range(4)]
        if not self._kernel.GetProcessTimes(int(self.process._handle), *(ctypes.byref(v) for v in values)):
            raise OSError(ctypes.get_last_error(), "GetProcessTimes failed")
        return self._value(values[0]), self._value(values[1])

    def elapsed(self):
        if self._finished is not None:
            return self._finished[0]
        return max(0.0, time.monotonic() - self.begin)

    def finish(self):
        with self._finish_lock:
            if self._finished is not None:
                return self._finished
            if self._kernel:
                creation, exit_time = self._times()
                if not exit_time:
                    raise RuntimeError("No process exit FILETIME after worker closure")
                self._finished = ((exit_time - creation) / 1e7, dt.datetime.fromtimestamp(exit_time / 1e7 - 11644473600, UTC))
            else:
                self._finished = (self.elapsed(), dt.datetime.now(UTC))
            return self._finished


class PauseKeys:
    """One nonblocking reader, including mouse records, while mining."""
    def __init__(self):self.reader=None;self.available=bool(sys.stdin.isatty());self.suspended=True
    def __enter__(self):
        self.suspended=False
        if self.available:
            from pgn_input import TerminalInput
            from pgn_interaction import focus_panel
            from pgn_terminal_input import HitMap,set_hit_map
            focus_panel(None);set_hit_map(HitMap(0,0))
            self.reader=TerminalInput();self.reader.__enter__()
        return self
    def poll(self):
        if self.reader is None or self.suspended:return None
        for _ in range(64):
            from pgn_interaction import translate
            value=translate(self.reader.read(timeout=0))
            if value=='TICK':return None
            if isinstance(value,str) and value.lower() in ('p','m','f','q'):return value.lower()
        return None
    def __exit__(self,*args):
        self.suspended=True
        if self.reader:self.reader.__exit__(*args);self.reader=None


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def check_resume_checkpoint(path,start,length,position,tests,gap_min=None):
    if gap_min is None:raise ValueError('Legacy CP is history-only; an effective Native gap identity is required')
    identity={'native_protocol':PROTOCOL,'gap_min':int(gap_min),'start':str(start),'length':str(length)}
    checked_checkpoint(Path(path).read_bytes(),identity,position,tests)


class Telemetry:
    def __init__(self, folder, uuid, enabled):
        self.stop_event = threading.Event()
        self.latest = {}
        self.thread = None
        self.error = None
        self.path = folder / "telemetry.csv"
        if not enabled:
            return
        tool = shutil.which("nvidia-smi.exe" if os.name == "nt" else "nvidia-smi")
        if not tool:
            self.error = "nvidia-smi unavailable; telemetry disabled"
            return
        self.thread = threading.Thread(target=self._sample, args=(tool, uuid), daemon=True)
        self.thread.start()

    def _sample(self, tool, uuid):
        fields = "timestamp,uuid,clocks.sm,clocks.mem,temperature.gpu,power.draw,utilization.gpu,memory.used,memory.total"
        try:
            with self.path.open("x", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["utc_observed", "gpu_timestamp", "gpu_uuid", "sm_mhz", "memory_mhz", "temperature_c", "power_w", "utilization_percent", "memory_used_mib", "memory_total_mib"])
                while not self.stop_event.is_set():
                    before = time.monotonic()
                    result = subprocess.run([tool, "--id=" + uuid, "--query-gpu=" + fields, "--format=csv,noheader,nounits"],
                                            capture_output=True, text=True, timeout=4, **child_options())
                    if result.returncode:
                        raise RuntimeError(result.stderr.strip() or "nvidia-smi query failed")
                    row = next(csv.reader([result.stdout.strip()]))
                    if len(row) != 9 or row[1].strip().lower() != uuid.lower():
                        raise RuntimeError("Unexpected telemetry CSV shape")
                    writer.writerow([dt.datetime.now(UTC).isoformat()] + row)
                    stream.flush()
                    self.latest = {"sm_mhz": row[2].strip(), "memory_mhz": row[3].strip()}
                    self.stop_event.wait(max(0.0, 1.0 - (time.monotonic() - before)))
        except Exception as error:
            self.error = str(error)

    def finish(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=6)


def terminate_owned(process):
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()  # This exact Popen child only; no process-name/group kills.
        process.wait(timeout=10)


def run_diagnostic(worker, environment, folder, benchmark=False):
    folder.mkdir(exist_ok=False)
    worker_sha = file_sha256(worker)
    mode = "--fermat-diagnostic" if benchmark else "--self-test"
    command = [str(worker), mode, "--device", "0", "--output-directory", str(folder)]
    from pgn_owned import run_checked
    gpu_uuid=environment['CUDA_VISIBLE_DEVICES']
    with (folder / "worker.log").open("x", encoding="utf-8") as output:
        code, owner_receipt = run_checked(command,environment,gpu_uuid,folder,output,timeout=180)
    if file_sha256(worker) != worker_sha:
        raise RuntimeError("Worker bytes changed during the diagnostic")
    native_code = code
    fallback_used = False
    if benchmark and os.name == "nt" and native_code == 3:
        # Only the explicit unsupported-reference result AFTER a genuine PGN
        # self-test can take this route. Never mask math or Driver exit1/2.
        self_path = folder / "fermat-selftest.json"
        compare_path = folder / "fermat-benchmark.json"
        if self_path.stat().st_size > 65536 or compare_path.stat().st_size > 65536:
            raise RuntimeError("Oversized native diagnostic status; fallback refused")
        native_self = json.loads(self_path.read_text(encoding="utf-8"))
        native_compare = json.loads(compare_path.read_text(encoding="utf-8"))
        if not (native_self.get("schema") == "pgn68-fermat-selftest-1"
                and native_self.get("passed") is True and native_self.get("mismatches") == 0
                and native_self.get("cases") == 274 and native_self.get("guards_checked") is True
                and native_self.get("cold_and_warm_state_words_checked") is True
                and native_self.get("public_perig_compiled") is False
                and native_compare.get("available") is False):
            raise RuntimeError("Exit3 was not a verified unsupported-reference result after PGN self-test; fallback refused")
        print("PGN self-test passed. Running the exact public reference with Windows NVRTC...")
        # The NVRTC/Driver code runs in a separately owned child, never here.
        fallback_environment=environment.copy()
        fallback_environment.pop('PGN_R5_LAUNCHER',None)
        fallback_environment['PGN_R5_INTERNAL_NVRTC_OUTPUT']=str(folder)
        fallback_command=[sys.executable] if getattr(sys,'frozen',False) else [sys.executable,str(Path(__file__).resolve())]
        fallback_owner=folder/'nvrtc-owner';fallback_owner.mkdir()
        with (folder/'nvrtc-fallback.log').open('x',encoding='utf-8') as output:
            code, fallback_owner_receipt=run_checked(fallback_command,fallback_environment,gpu_uuid,fallback_owner,output,timeout=180)
        fallback_used=True
        if code not in (0,1,3):raise RuntimeError('Windows NVRTC child returned an unexpected status')
    receipt = {"command": command, "worker_sha256": worker_sha, "native_exit_code": native_code,
               "fallback_used": fallback_used, "fallback_exit_code": code if fallback_used else None,
               "fallback_owned_process": fallback_owner_receipt if fallback_used else None,
               "exit_code": code, "status": "PASSED" if code == 0 else "FAILED", "worker_closed": owner_receipt["closed"], "owned_process": owner_receipt}
    atomic_text(folder / "frontend-receipt.json", json.dumps(receipt, indent=2) + "\n")
    if code:
        raise RuntimeError(f"{mode} failed (native exit {native_code}, effective exit {code}); search was not started. See {folder}")
    return receipt


def report_positions(value):
    value = int(value)
    if value == 0:
        return "0e0"
    digits = str(abs(value))
    tail = digits[1:].rstrip("0")
    mantissa = digits[0] + ("." + tail if tail else "")
    return ("-" if value < 0 else "") + mantissa + "e" + str(len(digits) - 1)


def brian_report(name, started, ended, device, args, end, position, status, elapsed, rows, paused_seconds=0.0, counted_gaps=None):
    selected = top_rows(rows, args.report_top)
    full = "\n".join(f"{gap:d} {merit:.4f} {lower:d}" for gap, merit, lower in selected) or "(No gaps)"
    largest = max((row[0] for row in rows), default=0)
    best = "\n".join(f"{gap:d} {merit:.4f} {lower:d}" for gap, merit, lower in selected if gap == largest) or "(No gaps)"
    clean_name = str(name).replace("\r", " ").replace("\n", " ")
    return ("======== PRIME GAP REPORT ========\n\n"
            f"Name: {clean_name}\nStart time: {started.isoformat()}\nEnd time: {ended.isoformat()}\n"
            f"GPU: {device['model']}\nGPU index: {args.gpu}\nCUDA capability: {device['cc_major']}.{device['cc_minor']}\n"
            f"GPU UUID: {device['uuid']}\nSession ID: {getattr(args, '_session_id', '--')}\n"
            f"GPU memory: {int(device['vram_bytes']) // (1024 * 1024)} MiB\nCUDA driver API version: {device.get('cuda_driver_api_version', device.get('driver_version', '--'))}\n"
            f"Target gap size: {args.detail_gap}\nCount threshold: {args.count_gap}\n"
            f"Gaps >= {args.count_gap}: {counted_gaps if counted_gaps is not None else len(rows)}\n"
            f"Detailed gaps >= {args.detail_gap}: {getattr(args, '_detail_total_count', len(rows))}\nRange pieces: {args.bins}\n"
            f"Minimum gap setting: {args.min_gap}\n"
            f"Positions processed: {report_positions(position)}\n"
            f"Range searched: {args.start} - {args.start + position}\n"
            f"Requested range: {args.start} - {end}\nStatus: {status}\n"
            f"Active worker wall seconds (all instances, initialization included): {elapsed:.7f}\n"
            f"Paused seconds (excluded from active rate): {paused_seconds:.7f}\nNetwork: local search; no PGN submission\n\n"
            f"Largest gap:\n{best}\n\nTop {args.report_top} detailed gaps >= {args.detail_gap} (largest first; counts are complete):\n{full}\n")


def archive_run(folder):
    target = folder.with_suffix(".zip")
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                archive.write(path, Path(folder.name) / path.relative_to(folder))
    return target


def idle_menu_before_gpu(args,parser):
    """Browse/edit before admission. Only explicit Start/Resume may leave here."""
    from pgn_menu import menu,MenuAction
    from pgn_parameter_editor import prepare_browser_queue
    end=validate_range(args,parser)
    output=(args.output or default_output_base()).expanduser().resolve()
    config={key:getattr(args,key) for key in ('min_gap','count_gap','detail_gap','bins','report_top','display_rows','target_merit','name','profile','chunk_length')}
    config.update(start=args.start,end=end,length=end-args.start,gpu=args.gpu,output=str(output))
    config.update(config_fields(args,end))
    context={'status':'Idle','active_session':None,'start':args.start,'end':end,'position':0,'tests':0,
             'min_gap':args.min_gap,'bins':args.bins,'top':args.report_top,'configuration':config,
             'gpu_index':args.gpu,'gpu_name':None,'output_root':str(output),'session_roots':[str(output)],
             'queued_ranges':[],'queue_tail_end':end,'files':{},'_ui_state':{},
             '_parser_factory':argument_parser,'_range_validator':validate_range}
    def submit(action):
        if action.kind=='display_rows':
            args.display_rows=display_rows(action.values['display_rows']);context['display_rows']=args.display_rows
            config['display_rows']=args.display_rows
            return {'ok':True,'message':'Display rows applied; no worker or export settings changed.'}
        if action.kind in ('new','resume','activate_queued'):return action
        if action.kind in ('queue','queue_edit','queue_delete'):
            return {'ok':True,'message':prepare_browser_queue(context,action)}
        raise ValueError('No search is active. Start a search explicitly before recording its device diagnostics.')
    previous=getattr(args,'_idle_menu_context',None)
    if previous:
        for key in ('_ui_state','workspace_focus','saved_drafts','prepared_request','prepared_request_saved_id','queued_ranges','queue_tail_end','output_root','session_roots','launcher_path'):
            if key in previous:context[key]=previous[key]
    context['global_defaults']=dict(context['_ui_state'].get('global_defaults_override',globals().get('_global_defaults',{})))
    context['_submit_action']=submit
    from pgn_ui8_controller import catalog_sessions
    resumable=next((session for session in catalog_sessions(context) if session.resumable),None)
    if resumable:context['resume_folder']=str(resumable.folder)
    restore_start_failure(context)
    args._idle_menu_context=context
    if not args.idle:
        while True:
            choice=menu(context)
            if choice.kind in ('new','resume','activate_queued'):return choice
            if choice.kind=='quit':return None
    from pgn_menu import file_menu
    state={'status':'Idle','gpu_name':'No GPU selected','gpu_index':None,'vram_mib':None,'driver':None,
           'host':'local','start':args.start,'end':end,'position':0,'tests':0,'elapsed':0,'rate':None,
           'gaps':[],'gap_count':0,'minimum_gap':args.count_gap,'detailed_min_gap':args.detail_gap,
            'display_rows':args.display_rows,'target_merit':args.target_merit,'outputfile':str(output),'key_help':'M menu | F sessions | Q quit',
            'resume_folder':context.get('resume_folder')}
    desk=Dashboard()
    try:
        with PauseKeys() as keys:
            desk.update(state,force=True)
            if not keys.available:return None
            while True:
                desk.update(state)  # Refresh viewport/hit map/hover even while no worker runs.
                pressed=keys.poll()
                if pressed=='q':return None
                if pressed=='p' and context.get('resume_folder'):return MenuAction('resume',{'folder':context['resume_folder']})
                if pressed in ('m','f'):
                    desk.finish()
                    choice=menu(context) if pressed=='m' else file_menu(context)
                    if choice and choice.kind in ('new','resume','activate_queued'):return choice
                    if choice and choice.kind=='quit':return None
                    desk=Dashboard();desk.update(state,force=True)
                # Pause is deliberately inert: there is no worker to pause.
                time.sleep(.03)
    finally:desk.finish()


def _main(argv=None):
    global _last_session_folder
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='backslashreplace')
    if argv is None and os.environ.get('PGN_R5_LAUNCHER')=='1':
        from pgn_launcher import argv_from_environment
        try:supplied=argv_from_environment(os.environ)
        except ValueError as error:
            print('Launcher settings:',error,file=sys.stderr);return 2
    else:supplied=list(sys.argv[1:] if argv is None else argv)
    provided={part.split('=',1)[0] for part in supplied if part.startswith('--')}
    parser=argument_parser();args=parser.parse_args(supplied)
    args._idle_was_requested=bool(args.idle)
    if args.idle and (args.resume or args.headless or args.list_gpus or args.self_test or args.fermat_diagnostic):parser.error('--idle cannot be combined with resume, headless or diagnostic/device actions')
    if not (0<args.target_merit<float('inf')):parser.error('--target-merit must be finite and positive')
    end=validate_range(args,parser)
    global _global_defaults
    _global_defaults={name:getattr(args,name) for name in ('start','gpu','bins','report_top','display_rows','target_merit','name','profile','chunk_length','debug','telemetry','archive','skip_self_test','headless')}
    _global_defaults.update(end=end,length=end-args.start,min_gap=args.min_gap_requested,count_gap=args.count_gap_requested,detail_gap=args.detail_gap_requested,output=str(args.output) if args.output else '')
    from pgn_startup_recovery import pending_same_range,recover_closed_sessions
    if not args.headless and not any((args.list_gpus,args.self_test,args.fermat_diagnostic)):
        recover_closed_sessions(args.output or default_output_base())
    unfinished=pending_same_range(args,end,args.output or default_output_base())
    if unfinished:
        args.idle=True;args.menu=False;args._idle_was_requested=True
    from pgn_engine import run as run_engine
    from pgn_menu import menu,final_screen_text
    import copy
    last=None
    while True:
        if (args.menu or args.idle) and not args.resume:
            try:choice=idle_menu_before_gpu(args,parser)
            except KeyboardInterrupt:return 130
            if choice is None:return 0
            if choice.kind=='new':
                retained=getattr(args,'_idle_menu_context',{})
                retained['prepared_request']=dict(choice.values)
                retained['configuration']={**retained.get('configuration',{}),**choice.values}
            if choice.kind=='activate_queued':
                args.resume=Path(choice.values['parent_folder']);args._activate_queued_request=dict(choice.values);args.worker=None;args.menu=False;args.idle=False;provided=set()
            elif choice.kind=='resume':args.resume=Path(choice.values['folder']);args.worker=None;args.menu=False;args.idle=False;provided=set()
            else:
                apply_new_parameters(args,choice.values);end=validate_range(args,parser);args.menu=False;args.idle=False;provided=set()
        controller=None;store=None;startup_phase='open session'
        try:
            if args.resume:
                controller=SessionControllerLock(args.resume)
                require_new_configuration(read_session_metadata(args.resume)['configuration'])
            store=SessionStore.load(args.resume) if args.resume else None
            if store and store.meta.get('prepared_replacement'):
                from pgn_prepared import recover_prepared_replacement
                target=recover_prepared_replacement(store)
                store.close();args.resume=target;args.worker=None;provided=set();continue
            if store:
                config=store.meta['configuration']
                if provided&{'--min-gap','--count-gap','--detail-gap'}:raise ValueError('Resume uses its frozen threshold policy; omit all threshold overrides')
                resume_args(args,config)
                for name in ('min_gap','count_gap','detail_gap','profile','chunk_length'):
                    flag='--'+name.replace('_','-')
                    if flag in provided and getattr(args,name)!=config.get(name):
                        raise ValueError('Saved session filters/profile are pinned; use a NEW range to change '+flag)
                if args.worker:raise ValueError('Durable resume resolves only packaged/profile workers, not --worker paths from a session')
                for name in ('min_gap','count_gap','detail_gap','bins','report_top','display_rows','target_merit','name','profile','chunk_length'):
                    if name in config and not (name in ('bins','report_top','display_rows') and '--'+name.replace('_','-') in provided):setattr(args,name,config[name])
                args.start=int(config['start']);end=int(config['end']);args.end=end;args.length=None
                validate_range(args,parser)
            startup_phase='resolve worker'
            discovery=resolve_worker(args.worker)
            startup_phase='discover GPUs'
            gpu_info,devices=enumerate_gpus(discovery)
            if args.list_gpus:
                for dev in devices:print(f"{dev['index']}: {dev['model']} | sm{dev['cc_major']}{dev['cc_minor']} | {int(dev['vram_bytes'])//(1024*1024):,} MiB")
                return 0
            if store:
                matches=[d for d in devices if d['uuid']==store.meta['device']['uuid']]
                if len(matches)!=1:raise RuntimeError('Saved session GPU UUID is not visible; select that device before resume')
                args.gpu=matches[0]['index']
            startup_phase='select GPU'
            device,environment=select_gpu(devices,args.gpu)
            device=dict(device,cuda_driver_api_version=gpu_info.get('driver_version'),runtime_version=gpu_info.get('runtime_version'))
            if store is None:
                startup_phase='create durable session'
                folder=new_run_directory(args.output)
                controller=SessionControllerLock(folder)
                config={k:getattr(args,k) for k in ('min_gap','count_gap','detail_gap','bins','report_top','display_rows','target_merit','name','profile','chunk_length')}
                config.update(start=str(args.start),end=str(end),emit_min_gap=min(args.count_gap,args.detail_gap),ownership='OS_GPU_LEASE_V1')
                config.update(config_fields(args,end))
                if getattr(args,'_plan_id',None):config.update(plan_id=args._plan_id,plan_root=getattr(args,'_plan_root',None))
                store=SessionStore.create(folder,config,device)
            folder=store.folder
            _last_session_folder=folder
            args._session_id=store.meta['session_id']
            if args.headless or not sys.stdout.isatty():
                print('PGN 68 | Session',args._session_id,'| actual GPU',device['model'])
                print('Actual output folder:',folder)
            if args.self_test or args.fermat_diagnostic:
                worker=resolve_worker(args.worker,f"sm{device['cc_major']}{device['cc_minor']}",64)
                diagnostic=folder/('diagnostic-'+str(time.time_ns()))
                run_diagnostic(worker,environment,diagnostic,benchmark=args.fermat_diagnostic)
                store.closed('DIAGNOSTIC_COMPLETE',0,0)
                print('Diagnostic passed:',diagnostic)
                return 0
            if args.menu and not args.headless and sys.stdin.isatty():
                from pgn_menu import MenuAction
                from pgn_queue import pending_ranges,queue_tail_end
                from pgn_queue_control import apply_queue_request
                context={'session_id':args._session_id,'folder':str(folder),'status':'Ready','start':args.start,'end':end,
                         'min_gap':args.min_gap,'bins':args.bins,'top':args.report_top,'files':{},'active_session':None,
                         'gpu_uuid':device['uuid'],'gpu_name':device['model'],'configuration':dict(config),'worker_active_seconds':0.0,'rate_positions':0,
                         'output_root':str(folder.parent),'queued_ranges':pending_ranges(store),'queue_tail_end':queue_tail_end(store)}
                from pgn_developer_diag import DeveloperRecorder
                initial_developer=DeveloperRecorder()
                def initial_request(action):
                    if action.kind=='display_rows':
                        args.display_rows=display_rows(action.values['display_rows']);context['display_rows']=args.display_rows
                        return {'ok':True,'message':'Display rows applied; no search binding changed.'}
                    if action.kind in ('diagnostic_start','diagnostic_stop'):
                        state=initial_developer.start(context) if action.kind=='diagnostic_start' else initial_developer.stop(context)
                        context['developer_diagnostics']=state
                        return {'ok':True,'message':state['status']}
                    if action.kind in ('queue','queue_edit','queue_delete'):
                        from pgn_plan import query_plan
                        check=None  # A queued plan is not a Native-admitted search.
                        apply_queue_request(store,action,args.gpu,check,lambda index:select_gpu(devices,index)[0]['uuid'])
                        context.update(queued_ranges=pending_ranges(store),queue_tail_end=queue_tail_end(store))
                        return {'ok':True,'message':'Queue saved. Idle. Start now explicitly starts the prepared search.'}
                    if action.kind!='new':return action
                    wanted=copy.copy(args);apply_new_parameters(wanted,action.values);wanted_end=validate_range(wanted,parser)
                    if not (0<wanted.target_merit<float('inf')):raise ValueError('TARGET_MERIT must be finite and positive')
                    desired,_=select_gpu(devices,wanted.gpu)
                    desired=dict(desired,cuda_driver_api_version=gpu_info.get('driver_version'),runtime_version=gpu_info.get('runtime_version'))
                    wanted_config={key:getattr(wanted,key) for key in ('min_gap','count_gap','detail_gap','bins','report_top','display_rows','target_merit','name','profile','chunk_length')}
                    wanted_config.update(start=str(wanted.start),end=str(wanted_end),emit_min_gap=min(wanted.count_gap,wanted.detail_gap),ownership='OS_GPU_LEASE_V1')
                    wanted_config.update(config_fields(wanted,wanted_end))
                    wanted_root=(wanted.output or default_output_base()).expanduser().resolve()
                    same_root=wanted_root==folder.parent.resolve()
                    if wanted_config==store.meta['configuration'] and desired['uuid']==device['uuid'] and same_root:
                        args.__dict__.update(vars(wanted));return MenuAction('start_current')
                    if not same_root:
                        if pending_ranges(store):raise ValueError('Remove queued plans explicitly before moving this prepared search to another OUTPUT root.')
                        return action
                    from pgn_prepared import replace_prepared
                    target=replace_prepared(store,wanted_config,desired)
                    args.__dict__.update(vars(wanted));args.resume=target;args.worker=None
                    return MenuAction('resume',{'folder':str(target)})
                context['_submit_action']=initial_request
                try:
                    while True:
                        choice=menu(context)
                        if choice.kind!='return':break
                finally:
                    if initial_developer.collector:initial_developer.stop(context)
                args.menu=False
                if choice.kind=='quit':store.close();return 0
                if choice.kind=='new':
                    store.close();apply_new_parameters(args,choice.values);end=validate_range(args,parser);provided=set();continue
                if choice.kind=='resume':
                    store.close();args.resume=Path(choice.values['folder']);args.worker=None;provided=set();continue
                if choice.kind=='activate_queued':
                    store.close();args.resume=Path(choice.values['parent_folder']);args._activate_queued_request=dict(choice.values);args.worker=None;provided=set();continue
            startup_phase='start search engine'
            queued_request=getattr(args,'_activate_queued_request',None)
            if queued_request:
                from pgn_queue import activate_next,activation_entry
                if queued_request['parent_session_id']!=store.meta['session_id'] or Path(queued_request['parent_folder']).resolve()!=store.folder:raise ValueError('Queued activation parent identity changed')
                entry=activation_entry(store,queued_request['child_session_id'])
                index=int(entry['configuration'].get('gpu_index',args.gpu))
                actual,_=select_gpu(devices,index);actual=dict(actual,cuda_driver_api_version=gpu_info.get('driver_version'),runtime_version=gpu_info.get('runtime_version'))
                child=activate_next(store,actual,selected_child=entry['child_session_id'],allow_incomplete=True)
                args._activate_queued_request=None;store.close();args.resume=child;args.worker=None;provided=set();continue
            last=run_engine(store,args,device,environment,gpu_info,sys.modules[__name__])
            action=last.get('action')
            if action and action.kind=='activate_queued':
                values=action.values
                if values['parent_session_id']!=store.meta['session_id'] or Path(values['parent_folder']).resolve()!=store.folder:raise ValueError('Queued activation parent identity changed')
                store.close();args.resume=Path(values['parent_folder']);args._activate_queued_request=dict(values);args.worker=None;provided=set();continue
            if action and action.kind=='activate_next':
                from pgn_queue import activate_next
                entry=store.meta['next_range']
                desired_gpu=int(entry['configuration'].get('gpu_index',args.gpu))
                fresh_info,fresh_devices=enumerate_gpus(resolve_worker(args.worker))
                if entry['configuration'].get('gpu_uuid'):
                    match=[d for d in fresh_devices if d['uuid']==entry['configuration']['gpu_uuid']]
                    if len(match)!=1:raise RuntimeError('Queued GPU UUID is no longer visible')
                    desired_gpu=match[0]['index']
                actual_next_device,_=select_gpu(fresh_devices,desired_gpu)
                actual_next_device=dict(actual_next_device,cuda_driver_api_version=fresh_info.get('driver_version'),runtime_version=fresh_info.get('runtime_version'))
                child=activate_next(store,actual_next_device)
                store.close()
                args.resume=child;args.worker=None;provided=set()
                continue
            store.close()
            if args.archive:print('Archive:',archive_run(folder))
            if action and action.kind=='resume_current':
                args.resume=folder;args.worker=None;provided=set();continue
            if action and action.kind=='new':
                apply_new_parameters(args,action.values);end=validate_range(args,parser)
                provided=set()
                args._confirm_plan=False  # Start already explicitly submitted this range.
                continue
            if action and action.kind=='resume':args.resume=Path(action.values['folder']);args.worker=None;provided=set();continue
            if action and action.kind=='settings':
                args.min_gap=action.values.get('min_gap',args.min_gap);args.count_gap=args.detail_gap=args.min_gap
                for field in ('bins','report_top','display_rows','target_merit'):
                    if field in action.values:setattr(args,field,action.values[field])
                provided=set()
                # Settings are next-range only: return to the explicit menu.
                args.menu=True;args.resume=None;args.start=end;end=args.start+10**15;args.end=end;args.length=None
                continue
            return 0 if last['status']=='COMPLETE' else 130 if last['status'] in ('PAUSED','STOPPED') else 1
        except KeyboardInterrupt:
            print('\nInterrupted. No second worker will be started.')
            return 130
        except Exception as error:
            print('PGN 68:',error,file=sys.stderr)
            context=getattr(args,'_idle_menu_context',None)
            if context is None:
                root=(args.output or default_output_base()).expanduser().resolve()
                context={'status':'Idle','active_session':None,'position':0,'tests':0,'start':args.start,'end':end,
                         'min_gap':args.min_gap,'bins':args.bins,'top':args.report_top,'files':{},
                         'output_root':str(root),'session_roots':[str(root)],'_ui_state':{},
                         '_parser_factory':argument_parser,'_range_validator':validate_range}
            context.update(status='Idle',active_session=None,position=0,tests=0)
            if not context.get('configuration'):
                context['configuration']={n:getattr(args,n) for n in ('start','end','min_gap','count_gap','detail_gap','profile','gpu')}
            context['configuration']['start']=args.start;context['configuration']['end']=end
            remember_start_failure(context,error,startup_phase,getattr(store,'folder',None))
            if store is not None:store.close();store=None
            if args.headless or not sys.stdin.isatty():return 1
            # Admission failure never consumes or relocates a saved Ready range.
            # Keep the same collection root, IDs and field drafts for retry.
            args._idle_menu_context=context
            from pgn_menu import startup_failure_menu
            choice=startup_failure_menu(context)
            if choice is None:
                args.idle=getattr(args,'_idle_was_requested',False);args.menu=not args.idle;args.resume=None
                continue
            if choice.kind=='quit':
                print(final_screen_text(context));return 1
            if choice.kind=='activate_queued':
                args.resume=Path(choice.values['parent_folder']);args._activate_queued_request=dict(choice.values);args.worker=None;args.menu=False;args.idle=False;provided=set()
            elif choice.kind=='resume':args.resume=Path(choice.values['folder']);args.worker=None;provided=set()
            elif choice.kind=='new':
                apply_new_parameters(args,choice.values);end=validate_range(args,parser);provided=set()
            elif choice.kind=='settings':
                args.min_gap=choice.values.get('min_gap',args.min_gap);args.count_gap=args.detail_gap=args.min_gap
                for field in ('bins','report_top','display_rows','target_merit'):
                    if field in choice.values:setattr(args,field,choice.values[field])
                provided=set()
            else:args.idle=getattr(args,'_idle_was_requested',False);args.menu=not args.idle;args.resume=None
        finally:
            if controller:controller.release()


def main(argv=None):
    supplied=list(sys.argv[1:] if argv is None else argv)
    if argv is None and os.environ.get('PGN_R5_LAUNCHER')=='1':
        from pgn_launcher import argv_from_environment
        try:supplied=argv_from_environment(os.environ)
        except ValueError:return _main(argv)
    simple={'--headless','--help','-h','--version','--list-gpus','--self-test','--fermat-diagnostic'}
    if not sys.stdin.isatty() or not sys.stdout.isatty() or any(value.split('=')[0] in simple for value in supplied):return _main(argv)
    from pgn_terminal_input import TerminalScreen,reset_input_state
    from pgn_input import TerminalInput
    try:
        with TerminalScreen(),TerminalInput():result=_main(argv)
    finally:reset_input_state()
    last=globals().get('_last_session_folder')
    if last:
        snapshot=Path(last)/'finalscreen.txt'
        try:
            if snapshot.is_file() and snapshot.stat().st_size<=262144:print('Saved final results\n'+snapshot.read_text(encoding='utf-8'))
        except OSError:pass
    return result


if __name__=='__main__':
    if os.environ.get('PGN_PRIVATE_OWNER_BOOTSTRAP'):
        from pgn_detached_worker import boot_main
        raise SystemExit(boot_main(os.environ['PGN_PRIVATE_OWNER_BOOTSTRAP']))
    if os.environ.get('PGN_R5_INTERNAL_NVRTC_OUTPUT'):
        from fermat_compare_nvrtc import run_diagnostic as _nvrtc_child
        raise SystemExit(_nvrtc_child(0,Path(os.environ['PGN_R5_INTERNAL_NVRTC_OUTPUT'])))
    raise SystemExit(main())
