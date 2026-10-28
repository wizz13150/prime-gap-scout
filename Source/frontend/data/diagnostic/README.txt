Windows exact-public-reference fallback
======================================

Public reference commit:
9d41f2709666d240c073439c37722c6ff6cb5b44
https://github.com/briankehrig/prime-gaps-cuda

comparison.cu is byte-for-byte the source from the delivered
FERMAT-Perig-vs-PGN-20261025 comparison. The original credits and comments are
retained. No slower host-compiler arithmetic substitute is used.

Both implementations evaluate Euler/Jacobi base 2 on odd
N = 10 * 2^64 + LOW64. They do not evaluate the full Fermat N-1 predicate.
All 274 expected booleans are recomputed independently using Python integer
pow before any GPU launch. The packaged CPU expectations are also checked.

The native Windows NVCC build cannot parse the exact public device int128
reference. NVRTC 12.8 supports --device-int128, so the fallback compiles the
same existing CUDA source at runtime for the detected sm86 or sm120 GPU.

Distribution files required beside pgn68.exe:
  fermat_compare_nvrtc.py (included by the Python packager)
  data/diagnostic/comparison.cu
  data/diagnostic/lows.bin
  data/diagnostic/expected-euler-jacobi.bin
  lib/nvrtc64_120_0.dll
  lib/the matching NVIDIA nvrtc-builtins64_128.dll

Frontend API:
  from fermat_compare_nvrtc import run_diagnostic
  exit_code = run_diagnostic(selected_gpu, diagnostic_directory)

An existing CUDA_VISIBLE_DEVICES selection is preserved; visible ordinal0 is
used in that case. No clocks, fans, power limits or voltage are changed.
Run in the CLI's finite diagnostic child owner, not while its search worker
is still running. Root's qualification must use its private wall-limit owner.

The destination leaf diagnostic_directory/perig-nvrtc must not already exist.
It receives compiler metadata/logs, full numeric verdict summary, CUDA-event
ABBA arithmetic timings and benchmark CSV. Timings are not Native gap-search
throughput, frequency-normalized results, or a guaranteed speedup on another
card. The first query in each warm thread still pays preparation, followed
by31 reused-state queries in the benchmark32-repeat kernel.

Import, --help and --verify-files do not load NVRTC, the runtime or the driver.
The first failed Driver call taints the diagnostic; no Driver cleanup call is
issued afterward. Full captures and guards are checked after every launch.
