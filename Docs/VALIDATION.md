# Release validation — 1.3.5

This record separates completed checks from hardware and flows that have not
been exercised. Benchmark values in the README remain the retained GPU-active
measurements; short regression runs are not new speed records.

## Resident worker and publication integrity

The final native source manifest is
`96C600D3486DED57B400FCD4428E904F6A3743E49F587DC85E93847D9FFDDE13`.
Its Windows SM86 image completed 5,000 consecutive CPU-only resident commands
in one process. Two additional isolated Windows command/receipt stress tests
completed 5,000 commands each. These checks exercise immutable command reads,
atomic completion publication and per-job identity, without GPU arithmetic.

The final Windows image passed 132 independent dense exact-reference cases
covering 66 numeric regions and their clipped tails, 11 threshold transitions,
and six production searches at 68, 80 and 95 bits. Physical pieces retain
distinct nonces and an ordered committed prefix. Pause and shutdown release
the device lease; a completed resident job does not imply process exit.

The assembled Python source passes 90 tests on Windows with no skipped cases.
These include locked/missing/corrupt completion receipts, startup state,
statistics/layout, durable ownership and session recovery. Artifact-cache
checks confirm that Windows rejects modification or deletion of a leased
engine while allowing execution, and that checkpoints are never cached.
The four artifact-lease checks also pass under Ubuntu.

The artifact-lease frontend completed 64 consecutive 1e12-position pieces
(64e12 total) in 101.844 seconds, using one native PID and 127 distinct job
nonces including planning. Native search jobs accounted for 72.791 seconds.
Median host handoff was 346.8 ms (maximum 631.2 ms); this is not claimed as
zero-time handoff. The preceding build took 254.390 seconds on the same test.
The default 64e12-position physical pieces amortize this bounded coordination
cost over much longer GPU work, while keeping the context resident.

The final frozen frontend also completed four 1e12-position pieces at each
of 80 and 95 bits. The complete 4e12-position output sets match the independent
ABBA reference: 24 gaps at 80 bits and 18 at 95 bits. The 95-bit check exercises
the bundled exact-prime runtime while release artifacts are read-leased.

After explicit command-guard retirement was added, the final frozen frontend
repeated those same 64 pieces in 106.218 seconds, with exactly the same full
gap set. Its handle count was 213 in the early sampled portion and at most
222 near completion, rather than growing by one guard per command.

## Matched performance regression

An ABBA comparison used the preceding qualified engine and this native image
on identical 4e12-position ranges, with identical output gap sets. Every
recorded core/memory sample was 1500/5001 MHz. Mean GPU-active throughput:

| Bits | Previous engine (Gpos/s) | Resident engine (Gpos/s) | Change |
|---:|---:|---:|---:|
| 68 | 934.33 | 938.33 | +0.43% |
| 80 | 732.83 | 731.44 | −0.19% |
| 95 | 544.19 | 548.23 | +0.74% |

These finite 4e12-position checks establish regression behavior on the tested
RTX 3090. The README chart uses a different retained 24e12-position campaign;
its absolute numbers must not be substituted for these short-run measurements.
The final executable device code is not byte-identical to the old image, so
no claim of complete machine-code identity is made.

## Platform scope

Windows SM86 CUDA execution was tested on an RTX 3090. Both SM86 and SM120
images compile for Windows and Ubuntu. The frozen Ubuntu frontend starts and
passes its version/help checks. Physical Ubuntu CUDA execution and SM120
hardware execution have not been tested. Compilation alone is not represented
as hardware qualification.

Search supports logical intervals in [2^66, 2^95), with optimized dispatch
throughout, automatic bit/high-word/threshold transitions, and exact handling
of short alignment fragments. Independent finite cases verify reported gaps
and counters; they are not a mathematical proof of exhaustive coverage.

The application observes GPU clocks but does not tune hardware settings or
upload scientific results. Release archives exclude saved user sessions.

## Live menu status

The controlled session owns the progress title. A stale outer/saved failure
cannot override its active Searching state. An actual controlled-session
failure remains Failed. Four production-renderer regressions cover these
conflicting snapshots, pause, and failure without an active session.
The clean-checkout Ubuntu suite passes 81 tests, with nine Windows-only tests
skipped; all 90 pass on Windows. The prefix-recovery fixture uses an independent
integer-pow oracle within the deterministic MR13 bound, without requiring
installed native libraries. Shipped 95-bit proof-runtime integration is checked
separately.
