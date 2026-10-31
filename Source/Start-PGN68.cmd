@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0" || exit /b 1
REM Edit values below. Navigation is one key; typed form values use Enter.
REM OUTPUT blank = the results folder beside this program. RESUME blank = a new session.
REM LENGTH and END are mutually exclusive. END is exclusive. Leave END blank for default1P.
REM Empty COUNT_GAP/DETAIL_GAP inherit MIN_GAP. RESUME keeps saved input/filter/profile.

REM EVERYDAY - the usual settings
REM --gpu: Role: Choose a visible GPU index from --list-gpus (default0); no automatic best-GPU selection. Default: 0. Choices/bounds: integer 0 or greater; choose a visible index from List GPUs. Example: 0.
set "GPU=0"
REM --start: Role: Exact starting integer, default2e20; scientific notation is accepted without float rounding. Default: 2e20. Choices/bounds: exact67..95-bit integer; work automatically crosses bit and threshold boundaries. Example: 2e20.
set "START=2e20"
REM --length: Role: Exact interval length instead of --end. Default: 1e15. Choices/bounds: positive exact integer; mutually exclusive with END. Example: 1e15.
set "LENGTH=1e15"
REM --end: Role: Exclusive endpoint; omit both end/length for START+1e15. Default: blank → START+LENGTH (or START+1e15). Choices/bounds: exclusive67..95-bit endpoint; mutually exclusive with LENGTH. Example: 2.00001e20.
set "END="
REM --min-gap: Role: Auto follows the local retained-merit policy in steps of two. Manual bounds are shown in parameter help; each worker plan binds its local effective value. Default: auto. Choices/bounds: Auto or integer938..2147483647. Example: auto.
set "MIN_GAP=auto"
REM --output: Role: Output parent; blank uses the results folder beside the program, with no silent fallback. Default: blank → results beside this program. Choices/bounds: local directory path; no silent fallback if not writable. Example: D:/PGN-results or /home/user/PGN-results.
set "OUTPUT="
REM --resume: Role: Resume this durable session directory; input/worker/K/journal binding is verified. Default: blank → new run. Choices/bounds: blank for a new session, or a genuine durable local session folder. Example: results/<actual-session-folder>.
set "RESUME="

REM REPORT AND DISPLAY
REM --display-rows: Role: Rows in BOTH Best and Recent tables: integer10..30 (default10); reports/CSV/science remain unchanged. Default: 10. Choices/bounds: integer10..30; BOTH Best and Recent, independent of reports. Example: 20.
set "DISPLAY_ROWS=10"
REM --report-top: Role: Maximum detailed rows in the human report (default100); counts remain complete. Default: 100. Choices/bounds: integer 1..1000000. Example: 100.
set "REPORT_TOP=100"
REM --bins: Role: Number of exact integer range pieces (default100, max1000000). Default: 100. Choices/bounds: integer 1..1000000. Example: 100.
set "BINS=100"
REM --target-merit: Role: Display merit goal and medal colors (default32). Default: 32. Choices/bounds: finite number greater than 0; display only. Example: 32.
set "TARGET_MERIT=32"
REM --name: Role: Name printed in the Brian-compatible report. Default: blank. Choices/bounds: text printed in the report. Example: Researcher.
set "NAME="

REM ADVANCED - optional; leave blank/0 unless needed
REM --profile: Role: Native K/chunk profile: auto uses actual --plan bytes; this never selects a different GPU. Default: auto. Choices/bounds: auto, 8, 16, 32, 64. Example: auto.
set "PROFILE=auto"
REM --chunk-length: Role: Advanced maximum positions per automatic memory chunk. Default: blank. Choices/bounds: blank for actual memory planning, or a positive exact integer. Example: 2e12.
set "CHUNK_LENGTH="
REM --count-gap: Role: Advanced count override; omitted inherits --min-gap. Default: blank → MIN_GAP. Choices/bounds: blank inherits local policy, or integer938..2147483647. Example: 1000.
set "COUNT_GAP="
REM --detail-gap: Role: Advanced detail override; omitted inherits --min-gap. Default: blank → MIN_GAP. Choices/bounds: blank inherits local policy, or integer938..2147483647. Example: 1100.
set "DETAIL_GAP="
REM --worker: Role: Advanced: explicit local pgn68-worker path. Default: blank. Choices/bounds: blank for packaged profile selection, or an explicit trusted local worker file. Example: bin/pgn68-worker-sm120-k64. Queue inherits the running process logging/mode flags; Start now or Save launcher applies this setting.
set "WORKER="
REM --debug: Role: Opt in to verbose raw Native logs; normal logs contain summaries only. Default: 0. Choices/bounds: 0 off / 1 on. Example: 1 to enable, 0 to disable. Queue inherits the running process logging/mode flags; Start now or Save launcher applies this setting. Set1 to enable,0 to leave off.
set "DEBUG=0"
REM --telemetry: Role: Read nvidia-smi once per second into a CSV; never change settings. Default: 1. Choices/bounds: 0 off / 1 on. Example: 1 to enable, 0 to disable. Queue inherits the running process logging/mode flags; Start now or Save launcher applies this setting. Set1 to enable,0 to leave off.
set "TELEMETRY=1"
REM --archive: Role: Also create a ZIP of this new run directory. Default: 0. Choices/bounds: 0 off / 1 on. Example: 1 to enable, 0 to disable. Queue inherits the running process logging/mode flags; Start now or Save launcher applies this setting. Set1 to enable,0 to leave off.
set "ARCHIVE=0"
REM --skip-self-test: Role: Advanced: explicitly skip the pre-search self-test. Default: 0. Choices/bounds: 0 off / 1 on. Example: 1 to enable, 0 to disable. Queue inherits the running process logging/mode flags; Start now or Save launcher applies this setting. Set1 to enable,0 to leave off.
set "SKIP_SELF_TEST=0"
REM --headless: Role: Exit after the run; never wait for interactive keys or menu. Default: 0. Choices/bounds: 0 off / 1 on. Example: 1 to enable, 0 to disable. Queue inherits the running process logging/mode flags; Start now or Save launcher applies this setting. Set1 to enable,0 to leave off.
set "HEADLESS=0"
REM --menu: Role: Open the menu before a new run; COMPLETE still waits for explicit M. Default: 0. Choices/bounds: 0 off / 1 on. Example: 1 to enable, 0 to disable. Queue inherits the running process logging/mode flags; Start now or Save launcher applies this setting. Set1 to enable,0 to leave off.
set "MENU=0"
REM --idle: Role: Open the Idle console with read-only GPU discovery; search starts only on Start or Resume. Default: 0. Choices/bounds: 0 off / 1 on. Example: 1 to enable, 0 to disable. Queue inherits the running process logging/mode flags; Start now or Save launcher applies this setting. Set1 to enable,0 to leave off.
set "IDLE=1"
REM --list-gpus: Role: List visible CUDA devices and exit. Default: 0. Choices/bounds: 0 off / 1 on. Example: 1 to enable, 0 to disable. Queue inherits the running process logging/mode flags; Start now or Save launcher applies this setting. Set1 to enable,0 to leave off.
set "LIST_GPUS=0"
REM --self-test: Role: Run the worker self-test and exit. Default: 0. Choices/bounds: 0 off / 1 on. Example: 1 to enable, 0 to disable. Queue inherits the running process logging/mode flags; Start now or Save launcher applies this setting. Set1 to enable,0 to leave off.
set "SELF_TEST=0"
REM --fermat-diagnostic: Role: Run the worker Fermat diagnostic and exit. Default: 0. Choices/bounds: 0 off / 1 on. Example: 1 to enable, 0 to disable. Queue inherits the running process logging/mode flags; Start now or Save launcher applies this setting. Set1 to enable,0 to leave off.
set "FERMAT_DIAGNOSTIC=0"
REM -h, --help: Role: show this help message and exit. Default: 0. Choices/bounds: 0 off / 1 on. Example: 1 to enable, 0 to disable. Queue inherits the running process logging/mode flags; Start now or Save launcher applies this setting. Set1 to enable,0 to leave off.
set "HELP=0"
REM --version: Role: show program's version number and exit. Default: 0. Choices/bounds: 0 off / 1 on. Example: 1 to enable, 0 to disable. Queue inherits the running process logging/mode flags; Start now or Save launcher applies this setting. Set1 to enable,0 to leave off.
set "VERSION=0"

set "SCOUT_LAUNCHER=1"
"%~dp0pgn68.exe"
set "SCOUT_EXIT_STATUS=%ERRORLEVEL%"
set "SCOUT_LAUNCHER="
echo.
echo Prime Gap Scout returned to this persistent prompt. Close the window only when YOU want.
if "%HEADLESS%"=="1" goto finished
"%ComSpec%" /d /k
:finished
endlocal & exit /b %SCOUT_EXIT_STATUS%
