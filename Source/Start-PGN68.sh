#!/usr/bin/env bash
set -eu
cd -- "$(dirname -- "$0")"
chmod u+x ./pgn68 || { echo "Cannot make pgn68 executable; extract the whole Ubuntu package into a writable folder." >&2; exit 1; }
for worker in ./bin/pgn68-worker-*; do
  [ -f "$worker" ] || continue
  case "$worker" in *.exe) continue ;; esac
  chmod u+x "$worker" || { echo "Cannot set executable permission on $worker" >&2; exit 1; }
done
# Edit values below. OUTPUT blank = the results folder beside this program. RESUME blank = a new session.
# LENGTH and END are mutually exclusive. END is exclusive. Leave END blank for default1P.
# Empty COUNT_GAP/DETAIL_GAP inherit MIN_GAP. RESUME keeps saved input/filter/profile.

# EVERYDAY - the usual settings
# --gpu: Role: Choose a visible GPU index from --list-gpus (default0); no automatic best-GPU selection. Default: 0. Choices/bounds: integer 0 or greater; choose a visible index from List GPUs. Example: 0.
export GPU='0'
# --start: Role: Exact starting integer, default2e20; scientific notation is accepted without float rounding. Default: 2e20. Choices/bounds: exact67..95-bit integer; work automatically crosses bit and threshold boundaries. Example: 2e20.
export START='2e20'
# --length: Role: Exact interval length instead of --end. Default: 1e15. Choices/bounds: positive exact integer; mutually exclusive with END. Example: 1e15.
export LENGTH='1e15'
# --end: Role: Exclusive endpoint; omit both end/length for START+1e15. Default: blank → START+LENGTH (or START+1e15). Choices/bounds: exclusive67..95-bit endpoint; mutually exclusive with LENGTH. Example: 2.00001e20.
export END=''
# --min-gap: Role: Auto follows the local retained-merit policy in steps of two. Manual bounds are shown in parameter help; each worker plan binds its local effective value. Default: auto. Choices/bounds: Auto or integer938..2147483647. Example: auto.
export MIN_GAP='auto'
# --output: Role: Output parent; blank uses the results folder beside the program, with no silent fallback. Default: blank → results beside this program. Choices/bounds: local directory path; no silent fallback if not writable. Example: D:/PGN-results or /home/user/PGN-results.
export OUTPUT=''
# --resume: Role: Resume this durable session directory; input/worker/K/journal binding is verified. Default: blank → new run. Choices/bounds: blank for a new session, or a genuine durable local session folder. Example: results/<actual-session-folder>.
export RESUME=''

# REPORT AND DISPLAY
# --display-rows: Role: Rows in BOTH Best and Recent tables: integer10..30 (default10); reports/CSV/science remain unchanged. Default: 10. Choices/bounds: integer10..30; BOTH Best and Recent, independent of reports. Example: 20.
export DISPLAY_ROWS='10'
# --report-top: Role: Maximum detailed rows in the human report (default100); counts remain complete. Default: 100. Choices/bounds: integer 1..1000000. Example: 100.
export REPORT_TOP='100'
# --bins: Role: Number of exact integer range pieces (default100, max1000000). Default: 100. Choices/bounds: integer 1..1000000. Example: 100.
export BINS='100'
# --target-merit: Role: Display merit goal and medal colors (default32). Default: 32. Choices/bounds: finite number greater than 0; display only. Example: 32.
export TARGET_MERIT='32'
# --name: Role: Name printed in the Brian-compatible report. Default: blank. Choices/bounds: text printed in the report. Example: Researcher.
export NAME=''

# ADVANCED - optional; leave blank/0 unless needed
# --profile: Role: Native K/chunk profile: auto uses actual --plan bytes; this never selects a different GPU. Default: auto. Choices/bounds: auto, 8, 16, 32, 64. Example: auto.
export PROFILE='auto'
# --chunk-length: Role: Advanced maximum positions per automatic memory chunk. Default: blank. Choices/bounds: blank for actual memory planning, or a positive exact integer. Example: 2e12.
export CHUNK_LENGTH=''
# --count-gap: Role: Advanced count override; omitted inherits --min-gap. Default: blank → MIN_GAP. Choices/bounds: blank inherits local policy, or integer938..2147483647. Example: 1000.
export COUNT_GAP=''
# --detail-gap: Role: Advanced detail override; omitted inherits --min-gap. Default: blank → MIN_GAP. Choices/bounds: blank inherits local policy, or integer938..2147483647. Example: 1100.
export DETAIL_GAP=''
# --worker: Role: Advanced: explicit local pgn68-worker path. Default: blank. Choices/bounds: blank for packaged profile selection, or an explicit trusted local worker file. Example: bin/pgn68-worker-sm120-k64. Queue inherits the running process logging/mode flags; Start now or Save launcher applies this setting.
export WORKER=''
# --debug: Role: Opt in to verbose raw Native logs; normal logs contain summaries only. Default: 0. Choices/bounds: 0 off / 1 on. Example: 1 to enable, 0 to disable. Queue inherits the running process logging/mode flags; Start now or Save launcher applies this setting. Set1 to enable,0 to leave off.
export DEBUG='0'
# --telemetry: Role: Read nvidia-smi once per second into a CSV; never change settings. Default: 1. Choices/bounds: 0 off / 1 on. Example: 1 to enable, 0 to disable. Queue inherits the running process logging/mode flags; Start now or Save launcher applies this setting. Set1 to enable,0 to leave off.
export TELEMETRY='1'
# --archive: Role: Also create a ZIP of this new run directory. Default: 0. Choices/bounds: 0 off / 1 on. Example: 1 to enable, 0 to disable. Queue inherits the running process logging/mode flags; Start now or Save launcher applies this setting. Set1 to enable,0 to leave off.
export ARCHIVE='0'
# --skip-self-test: Role: Advanced: explicitly skip the pre-search self-test. Default: 0. Choices/bounds: 0 off / 1 on. Example: 1 to enable, 0 to disable. Queue inherits the running process logging/mode flags; Start now or Save launcher applies this setting. Set1 to enable,0 to leave off.
export SKIP_SELF_TEST='0'
# --headless: Role: Exit after the run; never wait for interactive keys or menu. Default: 0. Choices/bounds: 0 off / 1 on. Example: 1 to enable, 0 to disable. Queue inherits the running process logging/mode flags; Start now or Save launcher applies this setting. Set1 to enable,0 to leave off.
export HEADLESS='0'
# --menu: Role: Open the menu before a new run; COMPLETE still waits for explicit M. Default: 0. Choices/bounds: 0 off / 1 on. Example: 1 to enable, 0 to disable. Queue inherits the running process logging/mode flags; Start now or Save launcher applies this setting. Set1 to enable,0 to leave off.
export MENU='0'
# --idle: Role: Open the Idle console with read-only GPU discovery; search starts only on Start or Resume. Default: 0. Choices/bounds: 0 off / 1 on. Example: 1 to enable, 0 to disable. Queue inherits the running process logging/mode flags; Start now or Save launcher applies this setting. Set1 to enable,0 to leave off.
export IDLE='1'
# --list-gpus: Role: List visible CUDA devices and exit. Default: 0. Choices/bounds: 0 off / 1 on. Example: 1 to enable, 0 to disable. Queue inherits the running process logging/mode flags; Start now or Save launcher applies this setting. Set1 to enable,0 to leave off.
export LIST_GPUS='0'
# --self-test: Role: Run the worker self-test and exit. Default: 0. Choices/bounds: 0 off / 1 on. Example: 1 to enable, 0 to disable. Queue inherits the running process logging/mode flags; Start now or Save launcher applies this setting. Set1 to enable,0 to leave off.
export SELF_TEST='0'
# --fermat-diagnostic: Role: Run the worker Fermat diagnostic and exit. Default: 0. Choices/bounds: 0 off / 1 on. Example: 1 to enable, 0 to disable. Queue inherits the running process logging/mode flags; Start now or Save launcher applies this setting. Set1 to enable,0 to leave off.
export FERMAT_DIAGNOSTIC='0'
# -h, --help: Role: show this help message and exit. Default: 0. Choices/bounds: 0 off / 1 on. Example: 1 to enable, 0 to disable. Queue inherits the running process logging/mode flags; Start now or Save launcher applies this setting. Set1 to enable,0 to leave off.
export HELP='0'
# --version: Role: show program's version number and exit. Default: 0. Choices/bounds: 0 off / 1 on. Example: 1 to enable, 0 to disable. Queue inherits the running process logging/mode flags; Start now or Save launcher applies this setting. Set1 to enable,0 to leave off.
export VERSION='0'

export SCOUT_LAUNCHER=1
set +e
./pgn68
result=$?
if [ -t 0 ] && [ -t 1 ]; then
  printf "\nPrime Gap Scout returned to a persistent prompt. Close the window when YOU want.\n"
  exec /bin/bash -i
fi
exit "$result"
