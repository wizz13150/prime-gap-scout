# Prime Gap Scout

Standalone CUDA prime-gap search for 67–95-bit integer ranges. Scout runs offline and does not contain a wallet, blockchain node or PGN networking.

![Prime Gap Scout terminal interface](assets/terminal.png)

## Downloads

**Stable release: [v1.3.3](https://github.com/wizz13150/prime-gap-scout/releases/tag/v1.3.3)**

- [Windows x64](https://github.com/wizz13150/prime-gap-scout/releases/download/v1.3.3/PrimeGapScout-1.3.3-Windows-x64.zip)
- [Ubuntu24.04 x64](https://github.com/wizz13150/prime-gap-scout/releases/download/v1.3.3/PrimeGapScout-1.3.3-Ubuntu-x64.zip)
- [Complete package with source](https://github.com/wizz13150/prime-gap-scout/releases/download/v1.3.3/PrimeGapScout-1.3.3-Complete.zip)
- [SHA-256 checksums](https://github.com/wizz13150/prime-gap-scout/releases/download/v1.3.3/SHA256SUMS.txt)

## Start

Extract the whole archive. In **Windows**, open `Start-PGN68.cmd`; in **Ubuntu**, run `Start-PGN68.sh`.

The Idle screen detects the selected GPU and observes its clocks without starting a search. Click **Start [S]** to search the configured range, or **Resume [P]** to continue a saved suspended session. **M** opens range management and settings; **P** pauses/resumes active work; **Q** safely quits and preserves progress.

Launcher settings can be edited from the menu. Save and relaunch the launcher to apply them. `IDLE=0` and `MENU=0` request direct startup instead of opening Idle first.

Windows x64 and Ubuntu24.04 x64 binaries include the Python frontend runtime. CUDA workers are provided for NVIDIA compute capabilities8.6 and12.0. The selected range, worker identity and memory plan are checked before execution. Physical validation for this patch used an RTX3090; physical Linux CUDA and sm120 execution are not claimed as tested.

## Version 1.3.3

- Three result panels: **Best**, **Recent** and **Statistics**, all scoped to the same range.
- Complete cumulative gap-size counts and separate merit bands, with one target-or-above total.
- Persistent statistics survive pause, resume, replay and conservative rollback; `statistics.csv` exports them.
- Exact prime coordinates and explicit terminal-size handling; Best/Recent remain configurable from 10 to 30 rows.
- Windows startup supports process hosts that forbid breakaway while preserving parent limits and owned-child cleanup.
- Previous direct Start, Idle GPU/clock discovery, CSV-lock handling and computation-based ETA fixes are retained.
- CUDA engines and published benchmark measurements are unchanged.

## Measured GPU throughput by bit width


**RTX 3090 · core 1,500 MHz · memory 5,001 MHz · 24 trillion positions per row.**
These are the retained optimization-campaign measurements of the whole active
GPU pipeline (sieve, walk and verification), without initialization or pause
time. No clock normalization is applied. 1 Gpos/s = one billion integer
positions per second.

| Bits | Min gap | GPU throughput (Gpos/s) |
| ---: | ---: | ---: |
| 67 | 954 | 1029.20 |
| 68 | 960 | 1003.52 |
| 69 | 982 | 984.24 |
| 70 | 994 | 952.42 |
| 71 | 1008 | 941.48 |
| 72 | 1022 | 921.70 |
| 73 | 1036 | 912.90 |
| 74 | 1050 | 889.01 |
| 75 | 1062 | 876.30 |
| 76 | 1076 | 854.83 |
| 77 | 1090 | 832.27 |
| 78 | 1104 | 817.53 |
| 79 | 1116 | 804.43 |
| 80 | 1130 | 782.51 |
| 81 | 1144 | 759.51 |
| 82 | 1158 | 751.73 |
| 83 | 1170 | 730.72 |
| 84 | 1184 | 724.74 |
| 85 | 1198 | 717.77 |
| 86 | 1212 | 707.89 |
| 87 | 1224 | 700.48 |
| 88 | 1238 | 676.47 |
| 89 | 1252 | 667.85 |
| 90 | 1266 | 655.23 |
| 91 | 1278 | 647.20 |
| 92 | 1292 | 648.11 |
| 93 | 1306 | 644.04 |
| 94 | 1318 | 602.66 |
| 95 | 1332 | 575.23 |

The measured starting integers and GPU elapsed times are in
[the benchmark data](Docs/BENCHMARKS.json). Results depend on the GPU, clocks,
cutoff and starting integer; other integers of the same bit width can select
a different backend. These retained measurements are not a new speed claim
from the 1.3.1 completion-file hotfix. See [release validation](Docs/VALIDATION.md).

## Results and compatibility

Saved ranges retain their original threshold policy and worker identity. Keep `bin/compat` when moving older sessions. Default output is the `results` directory beside the program; exact endpoints and session state remain in the saved session directory. Best/Recent display10 rows by default, configurable from10 to30.

Automatic integer minimum gaps are selected for the requested range. See `Docs/BENCHMARKS.json` for measured starting integers and active GPU timings; these figures are not guarantees for every starting integer or hardware configuration.

## Validation and source

See `Docs/VALIDATION-1.3.3.json` for the sanitized test summary and `Docs/RELEASE-NOTES.txt` for this patch. Native Windows tests covered real CUDA calculations, range creation/switching, pause/reopen/resume, abrupt UI closure, locked-statistics continuation and an 8T-position 95-bit completion with full-index statistics parity. Ubuntu was tested through the real frozen ELF in a PTY; no Linux GPU compute result is asserted.

The complete package includes source, build instructions, tests and third-party notices. Public project: https://github.com/wizz13150/prime-gap-scout
