# Architecture

Prime Gap Scout is a local, single-GPU prime-gap search application. Python owns configuration, sessions and process lifecycle; a CUDA worker performs the main sieve, gap-search PRP work and GPU gap verification. It does not connect to a wallet, pool or PGN network.

## Source organization

Paths below describe the supplied `Source/` tree.

| Location | Responsibility |
| --- | --- |
| `frontend/pgn68.py` | CLI/application entry point, reports and exact CPU boundary repair. |
| `frontend/pgn_parameters.py`, `pgn_threshold_policy.py` | Exact inputs, per-bit policy and pinned effective thresholds. |
| `frontend/pgn_native_contract.py`, `pgn_plan.py` | Image/profile/checkpoint binding and actual Native plan admission. |
| `frontend/pgn_engine.py` | Chunk execution, output consumption, pause/switch sequencing. |
| `frontend/pgn_session.py`, `pgn_index.py` | Single session coordinator, durable journal/checkpoints and SQLite index. |
| `frontend/pgn_publications.py`, `pgn_projection.py`, `pgn_output.py` | Ordered GAP publication, coalesced progress, views and exports. |
| `frontend/pgn_owned.py`, `pgn_detached_worker.py`, `pgn_owner_recovery.py` | OS ownership, detached Windows worker lifecycle and recovery. |
| `frontend/pgn_queue*.py`, `pgn_ui8_*.py`, `pgn_ui_service.py` | Ready/queued sessions, console interactions and coordinator actions. |
| `native/continuous-gpu-runtime.cu` | Worker CLI, table upload, admission, CUDA graphs, checkpoints and output. |
| `native/pgn_conditional_walk.cuh`, `p0_walk_kern.cuh` | Descriptor pipeline, owned-slice Walk and selected verification kernels. |
| `native/M582-counterfree-cycle8-marker.cuh` | Common fused class-30 marker. |
| `native/release-retained67-80.cuh`, `release69/` … `release80/` | Isolated retained arithmetic families and typed context adapters. |
| `compat/` | Historical common source, the 954 runtime overlay and original manifests. |
| `build.py`, `prepare_native.py`, `native/CMakeLists.txt` | Builds, include isolation, architecture targets and packaging inputs. |

## Pipeline

`Pinned range/policy → actual Native plan → pre-sieve/mark → bitmap Walk/PRP → GPU gap verification → ordered publication → durable index/exports`.

The host initializes prime/sieve data. The marker represents the eight classes coprime to 30, combines wheel/periodic/word masks with rolling prime marks, and uses the production prime bank ending at 80,000. A set bitmap bit means **composite**.
A bitmap block has 2^28 slots, occupies 32 MiB and represents 30×2^25 integers. It is divided into16 cohorts of32 shared tiles, each tile containing2^19 bits. Profiles own K blocks plus a halo block. Two conditional-graph lanes use four ring slots; dependency completion governs reuse.
The Walk partitions logical ownership and uses the effective minimum gap/window steps to select PRP work. It is a gap-search controller, not an export of every prime.
The PRP predicate is Euler/Jacobi base2: `2^((N-1)/2) == (2|N) mod N`. It is not itself a primality certificate.
Reported gaps pass GPU endpoint/interior verification using the implementation's deterministic MR13 contract, with strict bound `3317044064679887385961981`. Python additionally repairs finite processed boundaries: the lower prime is strictly below the boundary and the upper is at or above it, including an end prime.
Lower-prime ownership and index deduplication prevent a seam gap from being lost or counted twice.

## Retained point dispatch

Here `H = N >> 64`. Context sizes are persistent local bytes, not residue widths or register-count promises. R160/R166 name reciprocal-scale families. Other admitted high words retain the general Euler96 route.

| Bits | H | Auto base gap | Context | Specialization |
| ---: | ---: | ---: | ---: | --- |
| 67 | 5 | 954 | 8 B | Whole68-derived M600/R64 for H5. |
| 68 | 10 | 960 | 8 B | M600 four-bit R64. |
| 69 | 21 | 982 | 32 B | Retained R64 W4 adapter, including FULLCARRY97. |
| 70 | 43 | 994 | 8 B | Literal-H43 grouped R64. |
| 71 | 81 | 1008 | 8 B | Literal-H81 grouped R64. |
| 72 | 162 | 1022 | 32 B | Fused R160 M378. |
| 73 | 325 | 1036 | 32 B | Fused R160 M378. |
| 74 | 542 | 1050 | 32 B | Narrow/fused R160 M378. |
| 75 | 1084 | 1062 | 32 B | Narrow/fused R160 M365. |
| 76 | 2168 | 1076 | 32 B | `focused76-window1` routes to fused M378; the filename does not imply a W1 execution schedule. |
| 77 | 5421 | 1090 | 32 B | Guarded77/fused R160 M386. |
| 78 | 16263 | 1104 | 8 B | Fused R166 with certified M128 coefficient reconstruction. |
| 79 | 21684 | 1116 | 8 B | Mapped R166 with certified M128 coefficient reconstruction. |
| 80 | 54210 | 1130 | 32 B | Original FastBatch499/exact-scale80; **`P<80>::K = 168`**. |

67's threshold is the explicit project extrapolation, not an independently supplied Robert table entry. Supporting a bit range does not mean every number in it uses the point specialization.
`--plan` echoes `arithmetic_backend`, actual `profile_k`, `gap_min` and admission/memory data. Search startup reports the selected backend; resource queries use the selected kernel.

## Configuration, output and recovery

Threshold policy and its hash are pinned per session/bit segment. The effective Native cutoff is the minimum required by the pinned base/count/detail settings; it drives actual search work, not only report filtering. Resume does not silently reevaluate a new Auto table.
The frontend binds a worker plan to the actual image, profile, range, schema and threshold. K8/K16/K32/K64 aliases can share bytes: the executable filename selects actual K before planning, so identity includes the image hash **and** profile echo.
Native checkpoints are64 bytes (`<8s7Q`); their magic is `PGNS` plus little-endian effective gap. Observed progress may exceed the trusted checkpoint: recovery can recompute uncommitted work.
The coordinator is the single durable writer. GAP order is preserved while progress counters may be coalesced. SQLite/journal state is distinct from disposable reports/UI views. Gaps are keyed by lower prime; rows ahead of a recovered prefix remain retained but are excluded from committed progress.
Normal pause/switch drains the owned worker and seals results/checkpoint before handing ownership to another search. Detached Windows ownership separates worker lifetime from the UI. Recovery validates bindings and durable output; PID alone is insufficient.
Keep the whole session and `bin/compat`: original images, K filenames, sidecars and runtime libraries. Historical Windows4005 has floor954; Windows2B003 and historical Ubuntu workers have floor960. Rebuilding source does not guarantee the pinned image hash; never relabel a rebuilt worker as an old image.
Reports retain actual counts/provenance; Best/Recent display limits and top-report limits are views, not deletion of the full indexed results.

## Preservation and limitations

- Keep typed Walk/verifier contexts and the same admitted predicate; do not reinterpret unrelated state structs.
- Derive coefficient parameters from the actual specialization. Generic formulas do not replace the explicit `P<80>` override.
- Preserve positive/negative whole-PRP fixtures, cold/warm contexts, complete words, guards and input immutability. Matching coefficient golds alone cannot validate the actual caller.
- Arithmetic copies use separate namespaces. The POSIX build stages unique per-path include guards; Windows retains the original headers. `#pragma once` on byte-identical copies can suppress another namespace's definitions under the POSIX CUDA preprocessor.
- Public input is67–80 bits, but Native admission additionally checks origin, halo, descriptor/memory limits and one low64 window. Some boundary-crossing intervals are refused; positions must not be silently discarded.
- Pre-sieve work can remove a test only through a valid composite witness. Reported-gap soundness and exhaustive coverage are separate obligations.
- Component tests, context size or register counts do not establish end-to-end performance. The existing generic diagnostic alone does not prove that every selected production route was exercised.
- SM86/SM120 compilation is not qualification of an untested GPU. The application does not tune clocks, power, voltage or fans.
- Capabilities retain `SOURCE_PRP_INDEPENDENT_PROOF_PENDING`. This document describes contracts, not an independent universal exhaustive-coverage proof.

Original CUDA prime-gap work is credited to **Brian Kehrig**, with CIOS arithmetic attribution to **Périg**: [prime-gaps-cuda](https://github.com/briankehrig/prime-gaps-cuda).
Preserve source acknowledgments and `Source/THIRD-PARTY-NOTICES.txt` with the accompanying licence/copyright texts. Attribution does not invent an upstream licence grant.
