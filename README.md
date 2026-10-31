# Prime Gap Scout

A standalone NVIDIA CUDA searcher for prime gaps in **67–95-bit integer ranges**.
It includes a keyboard-and-mouse terminal interface, saved ranges, resumable
checkpoints, reports, and local developer diagnostics. No wallet, pool, or
blockchain connection is required.

![Prime Gap Scout terminal interface](assets/terminal.png)

## Downloads

**Stable release: [v1.3.5](https://github.com/wizz13150/prime-gap-scout/releases/tag/v1.3.5)**

- [Windows x64](https://github.com/wizz13150/prime-gap-scout/releases/download/v1.3.5/PrimeGapScout-1.3.5-Windows-x64.zip)
- [Ubuntu 24.04 x64](https://github.com/wizz13150/prime-gap-scout/releases/download/v1.3.5/PrimeGapScout-1.3.5-Ubuntu-x64.tar.gz)
- [Complete package with source and both platforms](https://github.com/wizz13150/prime-gap-scout/releases/download/v1.3.5/PrimeGapScout-1.3.5-Complete.zip)
- [SHA-256 checksums](https://github.com/wizz13150/prime-gap-scout/releases/download/v1.3.5/SHA256SUMS.txt)

## Packages and first launch

The complete distribution contains portable **Windows x64** and **Ubuntu 24.04
x86_64** applications, corresponding source, launchers, build instructions,
licenses, and validation records. Extract the complete package before starting.
The application needs a compatible NVIDIA driver. The prebuilt searcher does
not require Python or the CUDA Toolkit to be installed.

- Windows: open `Windows/Start-PGN68.cmd`.
- Ubuntu: run `chmod +x Start-PGN68.sh` and `./Start-PGN68.sh` in `Ubuntu`.

The initial screen is the full Idle dashboard, with GPU detection and available
clock observations. Choose **Start [S]** to search the configured range, or open
**Menu → Search ranges → New**, enter a Start and a Length or exclusive End,
then choose **Start**.
**Save range** keeps an editable Ready card for later. Scientific notation is
parsed as an exact integer: `2e20` is exactly `200000000000000000000`.

## Ranges and controls

- **Processing**, **Ready**, **Queued**, and **Suspended** identify each range's state.
- **Pause** changes to **Pausing…**, then **Resume** after the checkpoint is acknowledged.
- Starting another range safely suspends the active range before switching.
- Reopening discovers saved sessions. Compatible interrupted ranges can resume.
- Menu browsing leaves an active search running.
- Mining and menu pages share the same clickable bottom action bar.
- Core and memory frequencies are read-only observations, independent of CSV telemetry.
- **Display Rows** selects 10–30 rows in both Best and Recent; the default is 10.

Results default to a `results` directory beside the application. Keep the entire
application directory, including worker metadata and runtime libraries.

## Included fixes in 1.3.5

- One resident cached worker serves consecutive pieces without reloading the CUDA context or buffers.
- Start and Resume show **STARTING** immediately, including requests made from menus.
- Best and Recent retain their original frames; the third Statistics frame has two internal columns.
- The cumulative counts bar remains present. Window fitting covers 10–30 display rows.
- Windows command reads use a bounded snapshot and completion records use atomic publication.
- The application icon uses the Horizon artwork.

Earlier startup and recovery fixes are retained:

- GPU identity, VRAM and available clocks appear on Idle, before Start.
- A fresh Idle screen has a direct **Start** action; saved suspended work has **Resume**.
- Saved-range previews follow the actual range even when launcher defaults differ.
- Locked derived CSV exports are retried without stopping computation; checkpoints remain strict.
- Speed and ETA use the current computation window, excluding pauses and previous process instances.

## Measured GPU throughput by bit width

**RTX 3090 · core 1,500 MHz · memory 5,001 MHz · 24 trillion positions per row.**
These are the retained optimization-campaign measurements of the whole active
GPU pipeline (sieve, walk and verification), without initialization or pause
time. No clock normalization is applied. 1 Gpos/s = one billion integer
positions per second.

| Bits | Min gap | Gpos/s | Bits | Min gap | Gpos/s | Bits | Min gap | Gpos/s |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 67 | 954 | 1029.20 | 77 | 1090 | 832.27 | 87 | 1224 | 700.48 |
| 68 | 960 | 1003.52 | 78 | 1104 | 817.53 | 88 | 1238 | 676.47 |
| 69 | 982 | 984.24 | 79 | 1116 | 804.43 | 89 | 1252 | 667.85 |
| 70 | 994 | 952.42 | 80 | 1130 | 782.51 | 90 | 1266 | 655.23 |
| 71 | 1008 | 941.48 | 81 | 1144 | 759.51 | 91 | 1278 | 647.20 |
| 72 | 1022 | 921.70 | 82 | 1158 | 751.73 | 92 | 1292 | 648.11 |
| 73 | 1036 | 912.90 | 83 | 1170 | 730.72 | 93 | 1306 | 644.04 |
| 74 | 1050 | 889.01 | 84 | 1184 | 724.74 | 94 | 1318 | 602.66 |
| 75 | 1062 | 876.30 | 85 | 1198 | 717.77 | 95 | 1332 | 575.23 |
| 76 | 1076 | 854.83 | 86 | 1212 | 707.89 |  |  |  |

The measured starting integers and GPU elapsed times are in
[the benchmark data](Docs/BENCHMARKS.json). Results depend on the GPU, clocks,
cutoff and starting integer; other integers of the same bit width can select
a different optimized specialization. These are retained campaign measurements, not a new benchmark claim for this patch. See [release validation](Docs/VALIDATION.md).

## Automatic minimum gap

Auto uses the next even gap above `20.5 × ln(p)` at the current integer, rather than a fixed threshold per bit. A logical range is split at every retained-gap transition; the forms and dashboard show the pinned policy. Existing checkpoints keep their original policy.

The following values are the **retained campaign benchmark cutoffs**, matching the measured throughput table. They are not a lookup table for Auto:

| Bits | Minimum gap | Bits | Minimum gap | Bits | Minimum gap |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 67 | 954 | 77 | 1090 | 87 | 1224 |
| 68 | 960 | 78 | 1104 | 88 | 1238 |
| 69 | 982 | 79 | 1116 | 89 | 1252 |
| 70 | 994 | 80 | 1130 | 90 | 1266 |
| 71 | 1008 | 81 | 1144 | 91 | 1278 |
| 72 | 1022 | 82 | 1158 | 92 | 1292 |
| 73 | 1036 | 83 | 1170 | 93 | 1306 |
| 74 | 1050 | 84 | 1184 | 94 | 1318 |
| 75 | 1062 | 85 | 1198 | 95 | 1332 |
| 76 | 1076 | 86 | 1212 |  |  |

The display merit target is independent of the search threshold. A manual
minimum and optional count/detail thresholds are available in Advanced settings.

## Exact results and compatibility

The GPU searches and checks gap interiors. A failed Euler/Jacobi or Miller–Rabin
congruence is an exact compositeness witness. Reported endpoints use deterministic
MR13 below its strict bound and a bundled FLINT primality proof above that bound;
a probable-prime screening result alone is not accepted as a proved endpoint.

The public numeric domain is `[2^66, 2^95)`. Logical ranges may cross bit, minimum-gap and 64-bit-word boundaries. The coordinator splits them into compatible native pieces and certifies the short class-30 alignment fragments exactly. Native planning validates the halo, descriptor count and available memory. The total search length is not capped at `1e15`.

All admitted 67–95-bit positions use the optimized width-specific CUDA implementations with prepared cached parameters. There is no automatic general arithmetic backend. The resident worker is reused across ordinary pieces; Pause and safe quit close it and release the GPU.

CUDA workers target `sm_86` and `sm_120`. Consult the included validation record
for the distinction between compilation, physical GPU execution, and complete
application tests. Performance depends on hardware, clocks, interval and policy.
Endpoint certification does not by itself establish a new exhaustive-coverage
proof for the underlying probable-prime search algorithm.

## Diagnostics

Open **Menu → Developer diagnostics → Start recording**, reproduce the issue,
then choose **Stop recording**. The application prepares a local diagnostic ZIP
and lists unavailable observations. Nothing is uploaded automatically. The
application never adjusts GPU voltage, fans, power, or clocks.

## Source

| Directory | Responsibility |
| --- | --- |
| `Source/frontend` | Terminal UI, CLI, session ownership, checkpoints and reports |
| `Source/native` | CUDA search pipeline, memory plan and exact endpoint proof bridge |
| `Source/native/optimized_*.cuh` | Individually optimized arithmetic for each width |
| `Source/tests/data` | Reproducible independent diagnostic fixtures |
| `Docs` | User, build, architecture and validation guides |

See [build instructions](Source/BUILD.txt), [architecture](Docs/ARCHITECTURE.md),
and [third-party notices](Source/THIRD-PARTY-NOTICES.txt). File and data format
identifiers needed for existing sessions remain stable. Launcher filenames are
retained for compatibility; they do not restrict the supported bit width.

The downloadable stable release is **1.3.5**. Versions 1.3.3 and 1.3.4 remain withdrawn. The software never uploads reports automatically.
