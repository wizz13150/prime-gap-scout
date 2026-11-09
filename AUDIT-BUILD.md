# Prime Gap Scout 1.3.6-audit.2 — temporary scientific comparison build

Windows x64, RTX SM86 / SM120. Extract the complete folder before launching.
This is the temporary low-threshold build requested for Brian and Robert's
comparison. Keep your normal Scout folder and all existing sessions separately.

Start a NEW session. At start 1.53e20 you can choose MIN GAP 720 (or 950).
Leave COUNT GAP and DETAIL GAP blank to inherit that exact minimum. An explicitly
lower advanced override intentionally lowers the effective search threshold.
The native plan displays and binds the actual effective minimum; there is no
hidden fixed minimum of 800. For example:

    Windows\pgn68.exe --start 1.53e20 --length 2e15 --min-gap 720

The temporary retained-merit floor is 15, rather than the normal release policy.
AUTO therefore uses this temporary policy. Use an explicit minimum for the
comparison. Existing sessions retain their own immutable configuration; this
build does not reinterpret a normal session as an audit session.

The CUDA workers and their proof/runtime dependencies are the exact binaries
from Scout 1.3.5. This change does not alter primality tests or pseudoprime work.
The final SQLite checkpoint now copies committed WAL rows into the main database
on pause/chunk/session closure. Copy results after stopping normally. During a
live run, keep SQLite's -wal and -shm files with the database or use a SQLite
backup; do not discard its journal. An external reader holding a transaction can
delay checkpointing; the committed journal is retained.

The end-boundary regression also verifies a last gap whose lower prime belongs
to the requested range and whose upper prime is beyond the exclusive endpoint.
The supplied 10,841-row export plus all twelve terminal values was replayed through the durable journal: the standalone copy contained 10,853 rows after closure, with no missing supplied row. A blocked final checkpoint now raises an explicit error and retains its WAL.

There is no Scout updater in this build. This prerelease is temporary; the normal
release remains separate. Source and the focused regression are included.
See the original documentation and upstream notices in Docs/.
