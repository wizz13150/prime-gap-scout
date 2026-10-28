"""Portable Windows NVRTC fallback for the exact public Périg comparison.

Import/FILES/--help never load CUDA.  Root must execute the diagnostic in its
normal bounded child owner; this module itself never tunes hardware or uploads.
The CUDA source and corpus are frozen artifacts of the delivered comparison.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import csv
import ctypes as C
import hashlib
import json
import os
import struct
import sys
import time
import uuid

SOURCE_COMMIT = "9d41f2709666d240c073439c37722c6ff6cb5b44"
SOURCE_SHA = "FF261951156A7855141A743D7423B4E07A512E8C73085E8EFC525D032C6C374C"
INPUT_SHA = "A7082B9897EF430BD0124D0E65869AF2C3F641C0B0C3445A7E0D41F885BDA6C4"
GOLD_SHA = "A55E93D2D58837C2A1D53BE0F615E8A4D755E781D7C65009F5081BE2F0F7E630"
PREDICATE = "Euler/Jacobi base 2: 2^(N>>1) mod N = Jacobi(2,N), not Fermat N-1"
GUARD = bytes([0xD3]) * 32


def _roots():
    roots = [Path(__file__).resolve().parent]
    if getattr(sys, "frozen", False):
        roots.insert(0, Path(sys.executable).resolve().parent)
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        roots.append(Path(bundled))
    return list(dict.fromkeys(roots))


def _assets():
    for root in _roots():
        folder = root / "data" / "diagnostic"
        if (folder / "comparison.cu").is_file():
            return folder
    raise FileNotFoundError("Diagnostic source files are missing from data/diagnostic.")


def verify_files():
    """File validation only: no compiler, CUDA runtime or driver is loaded."""
    folder = _assets()
    result = {}
    for name, wanted in [("comparison.cu", SOURCE_SHA), ("lows.bin", INPUT_SHA),
                         ("expected-euler-jacobi.bin", GOLD_SHA)]:
        p = folder / name
        if p.stat().st_size > 131072:
            raise ValueError("Oversized diagnostic source asset: " + name)
        data = p.read_bytes()
        if hashlib.sha256(data).hexdigest().upper() != wanted:
            raise ValueError("Diagnostic source hash differs: " + name)
        result[name] = data
    if len(result["lows.bin"]) != 274 * 8 or len(result["expected-euler-jacobi.bin"]) != 274 * 4:
        raise ValueError("Invalid diagnostic corpus size.")
    return result


def _independent_gold(inputs, saved):
    actual = []
    for (low,) in struct.iter_unpack("<Q", inputs):
        if low & 1 == 0:
            raise ValueError("Expected odd H10 diagnostic input.")
        n = (10 << 64) + low
        wanted = n - 1 if ((low >> 1) ^ (low >> 2)) & 1 else 1
        actual.append(int(pow(2, n >> 1, n) == wanted))
    if set(actual) != {0, 1}:
        raise ValueError("The corpus must contain true and false predicates.")
    gold = struct.pack("<274I", *actual)
    if gold != saved:
        raise ValueError("Independent Python-integer oracle rejected packaged expectations.")
    return gold


def _nvrtc_path():
    for root in _roots():
        for subdir in ("lib", "bin", "_internal/lib"):
            folder = root / subdir
            exact = folder / "nvrtc64_120_0.dll"
            if exact.is_file():
                return exact
    raise FileNotFoundError("The Windows comparison requires the bundled lib/nvrtc64_120_0.dll and its matching nvrtc-builtins DLL.")


def _compile(nvrtc_path, source, sm, output):
    """Exact source; only the target SM and compilation packaging vary."""
    # Retain DLL directory handles until compilation finishes.  No system paths
    # or user-installed CUDA toolkit are required by the distribution.
    search = []
    if hasattr(os, "add_dll_directory"):
        search.append(os.add_dll_directory(str(nvrtc_path.parent)))
    try:
        # NVRTC loads its builtins through its own Windows LoadLibrary path.
        # Python's AddDllDirectory is insufficient for every vendor loader mode
        # (and a frozen executable may have a different current directory).
        # Preload the exact companion by absolute path and retain this handle
        # through nvrtcCompileProgram; Windows then resolves that loaded basename.
        builtins_path = nvrtc_path.parent / "nvrtc-builtins64_128.dll"
        if not builtins_path.is_file():
            raise FileNotFoundError("The exact NVRTC 12.8 companion is missing: " + str(builtins_path))
        builtins_dll = C.WinDLL(str(builtins_path.resolve()))
        dll = C.WinDLL(str(nvrtc_path))
        I, P, S = C.c_int, C.c_void_p, C.c_size_t
        signatures = {
            "nvrtcVersion": [C.POINTER(I), C.POINTER(I)],
            "nvrtcCreateProgram": [C.POINTER(P), C.c_char_p, C.c_char_p, I, C.POINTER(C.c_char_p), C.POINTER(C.c_char_p)],
            "nvrtcCompileProgram": [P, I, C.POINTER(C.c_char_p)],
            "nvrtcGetProgramLogSize": [P, C.POINTER(S)],
            "nvrtcGetProgramLog": [P, P],
            "nvrtcGetCUBINSize": [P, C.POINTER(S)],
            "nvrtcGetCUBIN": [P, P],
            "nvrtcDestroyProgram": [C.POINTER(P)],
        }
        fn = {}
        for name, args in signatures.items():
            f = getattr(dll, name); f.argtypes = args; f.restype = I; fn[name] = f
        program = P()
        major, minor = I(), I()
        if fn["nvrtcVersion"](C.byref(major), C.byref(minor)):
            raise RuntimeError("Cannot obtain the bundled NVRTC version.")
        code = fn["nvrtcCreateProgram"](C.byref(program), source, b"perig-pgn-exact-comparison.cu", 0, None, None)
        if code:
            raise RuntimeError("nvrtcCreateProgram returned " + str(code))
        try:
            options = [b"--std=c++17", b"--device-int128", ("--gpu-architecture=sm_" + str(sm)).encode(), b"--generate-line-info"]
            array = (C.c_char_p * len(options))(*options)
            code = fn["nvrtcCompileProgram"](program, len(options), array)
            logsize = S(); log = ""
            if fn["nvrtcGetProgramLogSize"](program, C.byref(logsize)) == 0 and logsize.value:
                if logsize.value > 1048576:
                    raise RuntimeError("NVRTC compiler log exceeds the bounded diagnostic limit.")
                buf = C.create_string_buffer(logsize.value)
                if fn["nvrtcGetProgramLog"](program, C.cast(buf, P)) == 0:
                    log = buf.value.decode("utf-8", "replace")
            (output / "compiler.log").write_text(log, encoding="utf-8")
            if code:
                raise RuntimeError("NVRTC compilation failed (code " + str(code) + "). See compiler.log.")
            size = S()
            if fn["nvrtcGetCUBINSize"](program, C.byref(size)) or not 0 < size.value <= 16 * 1024 * 1024:
                raise RuntimeError("Invalid NVRTC CUBIN size.")
            buf = C.create_string_buffer(size.value)
            if fn["nvrtcGetCUBIN"](program, C.cast(buf, P)):
                raise RuntimeError("Cannot retrieve the compiled CUDA module.")
            module = buf.raw
            if module[:4] != b"\x7fELF" or struct.unpack_from("<HH", module, 16) != (2, 190):
                raise RuntimeError("The new CUDA module is not loadable ELF ET_EXEC/EM_CUDA.")
            info = {"version": [major.value, minor.value], "options": [x.decode() for x in options],
                    "source_sha256": SOURCE_SHA, "module_sha256": hashlib.sha256(module).hexdigest().upper(),
                    "module_bytes": len(module), "reference_commit": SOURCE_COMMIT}
            (output / "compiler.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
            return module, info
        finally:
            fn["nvrtcDestroyProgram"](C.byref(program))
    finally:
        for handle in search:
            handle.close()


class DriverFailure(RuntimeError):
    pass


def run_diagnostic(gpu: int, output: Path) -> int:
    """Run the exact finite comparison; returns 0 on success and logs failures.

    A visibility mask supplied by the CLI is preserved; in that case CUDA
    ordinal zero denotes the chosen GPU.  No kernel or driver calls happen at
    import time or during file verification.
    """
    result = {"schema": "pgn68-perig-nvrtc-comparison-1", "available": False, "passed": False,
              "predicate": PREDICATE, "reference_commit": SOURCE_COMMIT,
              "pgn_source_parent": "A6F62BC90379A40C65F2ADAC5E44EADAF497193272D2F2A409668111CFB96CEA",
              "hardware_tuning": False, "clock_normalization": False,
              "scope": "CUDA-event arithmetic component timings, not Native prime-gap search throughput",
              "actual_clock_samples": None}
    folder = Path(output) / "perig-nvrtc"
    if folder.exists():
        print("[FERMAT-COMPARE] Output directory already exists: " + str(folder), file=sys.stderr)
        return 1
    folder.mkdir(parents=True)
    start = time.monotonic()
    if os.name != "nt":
        result["error"] = "This fallback is for Windows; use the native Linux diagnostic."
        (folder / "fermat-benchmark.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        return 3
    tainted = False
    context = C.c_void_p(); mod = C.c_void_p(); allocations = []; events = []
    fn = {}
    I, U, Q, P, S = C.c_int, C.c_uint, C.c_uint64, C.c_void_p, C.c_size_t
    class UUID(C.Structure):
        _fields_ = [("bytes", C.c_ubyte * 16)]
    def call(name, *args):
        nonlocal tainted
        if tainted:
            raise DriverFailure("Driver context is tainted; additional calls suppressed.")
        try:
            code = fn[name](*args)
        except BaseException:
            tainted = True
            raise
        if code:
            tainted = True
            raise DriverFailure(name + " returned " + str(code))
    try:
        assets = verify_files(); gold = _independent_gold(assets["lows.bin"], assets["expected-euler-jacobi.bin"])
        nvrtc_path = _nvrtc_path()
        driver_path = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32" / "nvcuda.dll"
        dll = C.WinDLL(str(driver_path))
        signatures = {
            "cuInit": [U], "cuDeviceGetCount": [C.POINTER(I)], "cuDeviceGet": [C.POINTER(I), I],
            "cuDeviceGetName": [P, I, I], "cuDeviceComputeCapability": [C.POINTER(I), C.POINTER(I), I],
            "cuDriverGetVersion": [C.POINTER(I)], "cuDeviceTotalMem_v2": [C.POINTER(S), I],
            "cuCtxCreate_v2": [C.POINTER(P), U, I], "cuCtxDestroy_v2": [P],
            "cuModuleLoadData": [C.POINTER(P), P], "cuModuleUnload": [P],
            "cuModuleGetFunction": [C.POINTER(P), P, C.c_char_p],
            "cuMemAlloc_v2": [C.POINTER(Q), S], "cuMemFree_v2": [Q],
            "cuMemsetD8_v2": [Q, C.c_ubyte, S], "cuMemcpyHtoD_v2": [Q, P, S], "cuMemcpyDtoH_v2": [P, Q, S],
            "cuLaunchKernel": [P] + [U] * 7 + [P, C.POINTER(P), C.POINTER(P)], "cuCtxSynchronize": [],
            "cuEventCreate": [C.POINTER(P), U], "cuEventRecord": [P, P],
            "cuEventSynchronize": [P], "cuEventElapsedTime": [C.POINTER(C.c_float), P, P], "cuEventDestroy_v2": [P],
        }
        for name, args in signatures.items():
            f = getattr(dll, name); f.argtypes = args; f.restype = I; fn[name] = f
        uname = "cuDeviceGetUuid_v2" if hasattr(dll, "cuDeviceGetUuid_v2") else "cuDeviceGetUuid"
        f = getattr(dll, uname); f.argtypes = [C.POINTER(UUID), I]; f.restype = I; fn[uname] = f
        call("cuInit", 0); count = I(); call("cuDeviceGetCount", C.byref(count))
        ordinal = 0 if os.environ.get("CUDA_VISIBLE_DEVICES") else int(gpu)
        if not 0 <= ordinal < count.value:
            raise ValueError("Selected GPU is not visible to the diagnostic.")
        dev = I(); call("cuDeviceGet", C.byref(dev), ordinal)
        major, minor = I(), I(); call("cuDeviceComputeCapability", C.byref(major), C.byref(minor), dev.value)
        sm = major.value * 10 + minor.value
        if sm not in (86, 120):
            raise ValueError("This qualified comparison supports sm86 and sm120; detected sm" + str(sm))
        name = C.create_string_buffer(256); call("cuDeviceGetName", C.cast(name, P), len(name), dev.value)
        uid = UUID(); call(uname, C.byref(uid), dev.value)
        driver = I(); call("cuDriverGetVersion", C.byref(driver)); memory = S(); call("cuDeviceTotalMem_v2", C.byref(memory), dev.value)
        device = {"name": name.value.decode("utf-8", "replace"), "uuid": "GPU-" + str(uuid.UUID(bytes=bytes(uid.bytes))),
                  "compute_capability": [major.value, minor.value], "sm": sm, "driver_cuda_version": driver.value,
                  "total_memory_bytes": memory.value, "requested_gpu": gpu, "selected_visible_ordinal": ordinal,
                  "visibility_mask_applied": bool(os.environ.get("CUDA_VISIBLE_DEVICES"))}
        result["device"] = device
        module, compiler = _compile(nvrtc_path, assets["comparison.cu"], sm, folder)
        result["compiler"] = compiler
        call("cuCtxCreate_v2", C.byref(context), 0, dev.value)
        module_buf = C.create_string_buffer(module); call("cuModuleLoadData", C.byref(mod), C.cast(module_buf, P))
        reference, pgn = P(), P()
        call("cuModuleGetFunction", C.byref(reference), mod, b"phase0_perig_reference")
        call("cuModuleGetFunction", C.byref(pgn), mod, b"m600_same_euler_jacobi")
        def allocate(data, is_input):
            q = Q(); call("cuMemAlloc_v2", C.byref(q), len(data) + 64); allocations.append(q.value)
            call("cuMemsetD8_v2", q.value, 0xD3, len(data) + 64)
            if is_input:
                host = C.create_string_buffer(data); call("cuMemcpyHtoD_v2", q.value + 32, C.cast(host, P), len(data))
            else:
                call("cuMemsetD8_v2", q.value + 32, 0xCD, len(data))
            return q.value
        def capture(ptr, expected):
            host = C.create_string_buffer(len(expected) + 64); call("cuMemcpyDtoH_v2", C.cast(host, P), ptr, len(host)); got = host.raw
            if got != GUARD + expected + GUARD:
                raise RuntimeError("Full numerical output/input or allocation guard mismatch.")
            return got
        def retire():
            while allocations:
                call("cuMemFree_v2", allocations[-1]); allocations.pop()
        def launch(kernel, inp, out, n, reps, cache):
            cells = [Q(inp + 32), Q(out + 32), U(n), U(reps), U(cache)]
            params = (P * 5)(*[C.addressof(x) for x in cells])
            call("cuLaunchKernel", kernel, 512, 1, 1, 256, 1, 1, 0, None, params, None)
        lowdata = assets["lows.bin"]
        inp = allocate(lowdata, True); doubled = b"".join(gold[i:i+4] * 2 for i in range(0, len(gold), 4)); out = allocate(doubled, False)
        numeric = []
        for label, kernel, cache in [("PERIG", reference, 0), ("PGN_COLD", pgn, 0), ("PGN_WARM", pgn, 1)]:
            call("cuMemsetD8_v2", out + 32, 0xCD, len(doubled)); launch(kernel, inp, out, 274, 2, cache); call("cuCtxSynchronize")
            got = capture(out, doubled); capture(inp, lowdata)
            poisoned = bytearray(GUARD + doubled + GUARD); poisoned[-33] ^= 1
            if got == poisoned:
                raise RuntimeError("The numerical comparator accepted a poisoned last value.")
            numeric.append({"implementation": label, "queries": 548, "all_outputs_equal": True, "input_immutable": True, "guards": True})
        retire()
        result.update(available=True, numeric_pass=True, numeric=numeric, true_and_false=True,
                      warm_semantics="Within-thread state is reused from the second repeat; first repeat pays preparation.")
        n, reps = 131072, 32; queries = n * reps
        tiled = (lowdata * ((n + 273) // 274))[:n * 8]
        gold_cycle = b"".join(gold[i:i+4] * reps for i in range(0, len(gold), 4))
        timed_gold = (gold_cycle * ((n + 273) // 274))[:queries * 4]
        inp = allocate(tiled, True); out = allocate(timed_gold, False)
        result["peak_explicit_device_bytes"] = len(tiled) + len(timed_gold) + 128
        if result["peak_explicit_device_bytes"] > 32 * 1024 * 1024:
            raise ValueError("Unexpected diagnostic allocation size.")
        for _ in range(2):
            event = P(); call("cuEventCreate", C.byref(event), 0); events.append(event)
        blocks = []
        with (folder / "fermat-benchmark-blocks.csv").open("w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=["mode", "order", "implementation", "queries", "gpu_ms"]); writer.writeheader()
            for mode, cache in [("cold", 0), ("warm", 1)]:
                for order, (label, kernel, actual_cache) in enumerate([("PERIG", reference, 0), ("PGN", pgn, cache), ("PGN", pgn, cache), ("PERIG", reference, 0)]):
                    if time.monotonic() - start > 25:
                        raise RuntimeError("The finite comparison exceeded its soft 25-second execution budget; no additional launch issued.")
                    call("cuMemsetD8_v2", out + 32, 0xCD, len(timed_gold))
                    call("cuEventRecord", events[0], None); launch(kernel, inp, out, n, reps, actual_cache)
                    call("cuEventRecord", events[1], None); call("cuEventSynchronize", events[1])
                    ms = C.c_float(); call("cuEventElapsedTime", C.byref(ms), events[0], events[1])
                    if not 0 < ms.value <= 500:
                        raise RuntimeError("A finite diagnostic launch has an invalid or excessive elapsed time.")
                    capture(out, timed_gold); capture(inp, tiled)
                    row = {"mode": mode, "order": order, "implementation": label, "queries": queries, "gpu_ms": ms.value}
                    blocks.append(row); writer.writerow(row); csvfile.flush()
        speedups = {}
        for mode in ("cold", "warm"):
            ref_ms = sum(x["gpu_ms"] for x in blocks if x["mode"] == mode and x["implementation"] == "PERIG")
            pgn_ms = sum(x["gpu_ms"] for x in blocks if x["mode"] == mode and x["implementation"] == "PGN")
            speedups[mode] = {"reference_gpu_ms": ref_ms, "pgn_gpu_ms": pgn_ms,
                              "queries_per_implementation": queries * 2, "speedup": ref_ms / pgn_ms}
        result.update(passed=True, blocks=blocks, timings=speedups, all_launch_outputs_checked=True,
                      query_count_per_launch=queries, timing_order="PERIG,PGN,PGN,PERIG independently for cold and warm")
        print("[FERMAT-COMPARE] PASS: cold %.4fx, warm %.4fx (GPU-event component only)." % (speedups["cold"]["speedup"], speedups["warm"]["speedup"]))
    except BaseException as error:
        result.update(passed=False, error=str(error))
        print("[FERMAT-COMPARE] " + str(error), file=sys.stderr)
    finally:
        # The first failing Driver call taints the context.  Do NOT call any
        # Driver free/unload/destroy after it, even from cleanup code.
        if not tainted and fn:
            try:
                for event in reversed(events): call("cuEventDestroy_v2", event)
                while allocations:
                    call("cuMemFree_v2", allocations[-1]); allocations.pop()
                if mod: call("cuModuleUnload", mod)
                if context: call("cuCtxDestroy_v2", context)
            except BaseException as error:
                result.update(passed=False, cleanup_error=str(error))
        result.update(driver_tainted=tainted, host_total_seconds=time.monotonic() - start)
        (folder / "fermat-benchmark.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0 if result["passed"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-files", action="store_true", help="verify packaged inputs without loading CUDA")
    parser.add_argument("--gpu", type=int, default=0)
    parser.add_argument("--output", type=Path, default=Path("diagnostics"))
    args = parser.parse_args(argv)
    if args.verify_files:
        files = verify_files()
        print(json.dumps({"files_verified": True, "count": 274, "Driver": False, "GPU": False,
                          "source_sha256": hashlib.sha256(files["comparison.cu"]).hexdigest().upper()}))
        return 0
    return run_diagnostic(args.gpu, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
