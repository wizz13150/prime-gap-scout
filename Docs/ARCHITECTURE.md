# Architecture

The frontend owns one session coordinator and its durable SQLite journal. It
validates an exact integer interval and a pinned threshold policy, obtains an
actual Native memory plan, then starts one owned CUDA worker. UI pages consume
snapshots and send typed actions to the coordinator; they do not own searches.

## Search pipeline

`native/search_worker.cu` owns allocation, conditional CUDA graph construction,
immutable result consumption, exact endpoint proof, and checkpoint publication.
`native/search_pipeline.cuh` implements marking, walking, interior verification,
and ordered descriptor advancement. Two descriptor lanes use disjoint bitmap
versions: a future mark may overlap a completed version's walk, while advancement
joins proof completion and next-version readiness.

`native/segmented_sieve.cuh` retains complete class-30 coverage and the fixed
cyclic event representation. `candidate_walk.cuh` expresses interval ownership
and candidate stepping. `memory_plan.h` computes allocation before submission.

`specialized_engines.def` is the inventory of exact high-word domains, automatic
thresholds, and state sizes. It drives kernel declarations, dispatch and public
capabilities. Arithmetic lives under `arithmetic/bits_N/prime_test.cuh`; shared
pipeline bodies do not replace or average the individually optimized arithmetic.
The 67/68 radix-16 and 69 carry-aware paths retain their specific state layouts.

## Proof and publication

GPU tests use exact integer modular arithmetic. A failed congruence rejects a
composite interior integer. Positive endpoint screens below
`3317044064679887385961981` are certified by the deterministic first13-prime-base
Miller–Rabin bound. Larger endpoints are proved using `fmpz_is_prime` from the
bundled FLINT runtime. The entire descriptor's endpoint proofs succeed before
its rows are emitted or its prefix is credited. A rejection exits without
crediting that descriptor. Python uses the same proved predicate for final
range-boundary repair. Runtime libraries and worker metadata carry fingerprints.

These checks certify reported gap endpoints and interiors. They do not promote
a finite test corpus into a proof of exhaustive search coverage.

## Session and UI boundaries

The session coordinator performs safe pause/drain/checkpoint/owner closure
before switching ranges. Committed result identity is the lower prime; replay
cannot silently replace a conflicting gap. Launcher defaults, editable prepared
ranges and pinned active sessions are distinct objects. Existing format IDs are
compatibility contracts rather than experimental version labels.

Mining and menus share action rendering and input dispatch. A background NVML
reader observes core and memory clocks without CSV recording or setting changes.
Stale observations become unavailable. Developer recording and archival remain
explicit local actions. They never upload data.

## Building

The same CUDA source targets Windows and Ubuntu, with isolated include guards
for per-width headers on POSIX. `Source/VERSION` generates public version constants.
`build.py` records exact native inputs and worker fingerprints, preserves device
LTO and geometry, and bundles the proof runtime and redistributable CUDA libraries.
See `Source/BUILD.txt` for the explicit dependency and packaging commands.
