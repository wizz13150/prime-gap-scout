# PGN 68-bit arithmetic diagnostic

This is a source delivery for request BASE845. No compiler, CUDA driver, GPU,
WSL, remote host, or hardware tuning was invoked by its author.

## Runtime API

Include `release-selftest.cuh` in the CUDA translation unit and call:

```cpp
int status = pgn_release_diagnostic(device, fresh_output_directory, benchmark);
```

The caller owns device selection, compute-capability validation, and the initial
`cudaSetDeviceFlags(cudaDeviceMapHost)`. The diagnostic does not reset the device
or change clocks, voltage, power, fan speeds, or networking.

`benchmark=false` runs the arithmetic self-test. `benchmark=true` also runs the
matched Périg/PGN comparison after the self-test passes. Any nonzero return must
stop that command. Use a fresh output directory; existing self-test output is
preserved.

## Predicate and qualified domain

Both implementations in this comparison evaluate the Euler/Jacobi base-2
predicate `2^(N>>1) mod N == Jacobi(2,N)` on odd `N=10*2^64+LOW64` (68 bits).
The exact public routine stops its exponent loop at `bit>1` and compares the
Montgomery residue against the Jacobi-dependent sign. Despite the historical
name `ciosFermatTest128`, this is not the base-2 Fermat `N-1` predicate and is not
a deterministic primality proof.

The public block is from Brian Kehrig's repository commit
`9d41f2709666d240c073439c37722c6ff6cb5b44`, frozen in the previously delivered
comparison archive. Device-only packaging removes its `__host__` annotations;
the integer operations and exponent bits are unchanged. PGN calls the exact
retained M600 `pgn_stateful_u160::test` entry with its original State8 cache
meaning. The rejected µ35 state format is not used.

## Independent verification

- The 274 input values are frozen inputs from the prior comparison.
- Their frozen golds were computed with independent CPU integer `pow`.
- `generate-release-diagnostic.py` normally recomputes those golds with Python
  `pow` before writing `diagnostic_data.h`; Root must execute it in its bounded
  CPU owner before qualification. `--metadata-only` merely repackages existing
  independently computed golds and is not an oracle run.
- On every end-user self-test, a second portable host-integer implementation
  computes the same predicate using 68-bit binary modular multiplication. It
  uses no `__int128`, candidate arithmetic, GPU output, or CUDA math.
- Cold and warm PGN booleans and both State8 words are captured and checked.
  The expected cache quotient `floor(2^96/N_bucket_max)` is independently
  recomputed by binary long division on the host.
- All inputs, outputs, and both guards are recaptured. A modified last value
  must be rejected. The corpus must contain both true and false verdicts.

## Windows native-int128 capability

The exact public reference uses device-native `unsigned __int128` and `%`.
Its source is guarded by `defined(__CUDA_ARCH__)` so MSVC's host pass cannot see
that type. Root must still compile the native Windows capability probe and
then the real CUDA translation unit. CUDA compiler support is not inferred
from the source.

If the actual Windows CUDA compiler rejects this device-only packaging, compile
with `PGN_RELEASE_ENABLE_PUBLIC_PERIG=0` to preserve the PGN self-test. Comparison
mode then returns status 3 and writes `available:false`. It must not be labelled
a completed Périg comparison. No slow software-int128 shim substitutes for the
exact public benchmark. An NVRTC-backed exact comparison could be added
separately if needed, but is not silently included here.

## Output

- `fermat-selftest.json`: GPU name/UUID/CC/VRAM, driver/runtime API versions,
  source identity, case counts, verdict mix, guard/state results, and pass/fail.
- `fermat-selftest.csv`: every independent expected verdict and GPU result.
- `fermat-benchmark.json`: reference and PGN aggregate CUDA-event times and
  observed cold/warm speed ratios.
- `fermat-benchmark-blocks.csv`: actual reference/PGN/PGN/reference order for
  each mode, query counts, and individual event timings.
- `fermat-error.json`: a failed CUDA boundary or benchmark validation, where
  writing that file is possible.

Benchmark throughput is an arithmetic component measurement. It is not native
gap-search Gpos/s, a graph point, or a promised speed ratio on the RTX 5070 Ti.
No frequency normalization is applied. Actual clock sampling is explicitly
marked uncollected in this header; the frontend can collect an optional
read-only `nvidia-smi` log externally.

## Acceptance still required by Root

1. Fresh CPU gold regeneration and portable host-oracle comparison.
2. Actual Windows/Ubuntu CUDA builds, including `sm_120`, and resource checks.
3. Actual numeric self-test on the available qualified GPU and an error path.
4. Actual Périg comparison if its exact native-int128 reference builds.
5. Separate whole-search smoke/finite-gap checks. This arithmetic self-test
   does not prove graph scheduling, range completeness, or tail ownership.
6. On Robert's actual RTX 5070 Ti, self-test before search and captured logs;
   this source delivery is not a claim that his physical GPU was tested here.

The diagnostic returns immediately after the first CUDA error and makes no
further CUDA cleanup calls. Successful cleanup is explicit; there are no CUDA
RAII destructors that could run later in a tainted context.
