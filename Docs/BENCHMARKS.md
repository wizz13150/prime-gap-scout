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
[the benchmark data](BENCHMARKS.json). Results depend on the GPU, clocks,
cutoff and starting integer; other integers of the same bit width can select
a different backend. These retained measurements are not a new speed claim
from the 1.3.1 completion-file hotfix. See [release validation](VALIDATION.md).

