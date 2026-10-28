"""Generate exhaustive editable launchers; build argv without shell interpolation.

The launcher environment is only a transport for public argparse options. Paths
remain one argv element, including spaces and CMD metacharacters. Native worker
internal flags are never exposed here.
"""
from pathlib import Path

GROUPS = (
 ("EVERYDAY - the usual settings", ("gpu","start","length","end","min_gap","output","resume")),
 ("REPORT AND DISPLAY", ("display_rows","report_top","bins","target_merit","name")),
 ("ADVANCED - optional; leave blank/0 unless needed", ("profile","chunk_length","count_gap","detail_gap","worker",
    "debug","telemetry","archive","skip_self_test","headless","menu","idle","list_gpus","self_test","fermat_diagnostic","help","version")),
)
DEFAULTS = {"gpu":"0","start":"2e20","length":"1e15","end":"","min_gap":"auto","output":"","resume":"",
 "display_rows":"10","report_top":"100","bins":"100","target_merit":"32","name":"Robert","profile":"auto","chunk_length":"",
 "count_gap":"","detail_gap":"","worker":"","telemetry":"1"}
BOOLS = {"debug","telemetry","archive","skip_self_test","headless","menu","idle","list_gpus","self_test","fermat_diagnostic","help","version"}


def variable(dest):return dest.upper()


def validate_coverage(parser):
    actions={a.dest:a for a in parser._actions if a.option_strings}
    configured={name for _,names in GROUPS for name in names}
    if set(actions)!=configured:
        raise ValueError("Launcher/parser coverage mismatch: missing="+str(sorted(set(actions)-configured))+" obsolete="+str(sorted(configured-set(actions))))
    return actions


def argv_from_environment(environment):
    value=lambda key:environment.get(variable(key),"")
    flag=lambda key:value(key)=="1"
    if flag("help"):return ["--help"]
    if flag("version"):return ["--version"]
    modes=[name for name in ("list_gpus","self_test","fermat_diagnostic") if flag(name)]
    if len(modes)>1:raise ValueError("Choose only one action: LIST_GPUS, SELF_TEST or FERMAT_DIAGNOSTIC")
    result=[]
    def add(name):
        if value(name):result.extend(("--"+name.replace("_","-"),value(name)))
    if modes:
        for name in ("gpu","worker","output"):add(name)
        result.append("--"+modes[0].replace("_","-"))
        return result
    if value("resume"):
        if any(value(name) for name in ("count_gap","detail_gap","worker")):
            raise ValueError("RESUME uses its saved filters/worker. Clear COUNT_GAP/DETAIL_GAP/WORKER overrides")
        add("resume");add("display_rows")
    else:
        if value("length") and value("end"):
            raise ValueError("Set LENGTH or END, never both. END is exclusive")
        for name in ("gpu","start","length","end","min_gap","output","display_rows","report_top","bins","target_merit","name",
                     "profile","chunk_length","count_gap","detail_gap","worker"):add(name)
    for name in ("debug","telemetry","archive","skip_self_test","headless","menu","idle"):
        if name=='idle' and (value('resume') or flag('headless')):continue
        if flag(name):result.append("--"+name.replace("_","-"))
    if flag("menu") and flag("idle"):raise ValueError("MENU and IDLE cannot both be1")
    if flag("headless") and flag("menu"):raise ValueError("HEADLESS cannot be combined with MENU")
    return result


def generate(parser,directory):
    actions=validate_coverage(parser)
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    cmd=['@echo off','chcp 65001 >nul',
         'setlocal EnableExtensions DisableDelayedExpansion','cd /d "%~dp0" || exit /b 1',
         'REM Edit values below. Navigation is one key; typed form values use Enter.',
         'REM OUTPUT blank = the results folder beside this program. RESUME blank = a new session.',
         'REM LENGTH and END are mutually exclusive. END is exclusive. Leave END blank for default1P.',
         'REM Empty COUNT_GAP/DETAIL_GAP inherit MIN_GAP. RESUME keeps saved input/filter/profile.']
    sh=['#!/usr/bin/env bash','set -eu','cd -- "$(dirname -- "$0")"',
        'chmod u+x ./pgn68 || { echo "Cannot make pgn68 executable; extract the whole Ubuntu package into a writable folder." >&2; exit 1; }',
        'for worker in ./bin/pgn68-worker-*; do',
        '  [ -f "$worker" ] || continue',
        '  case "$worker" in *.exe) continue ;; esac',
        '  chmod u+x "$worker" || { echo "Cannot set executable permission on $worker" >&2; exit 1; }',
        'done',
        '# Edit values below. OUTPUT blank = the results folder beside this program. RESUME blank = a new session.',
        '# LENGTH and END are mutually exclusive. END is exclusive. Leave END blank for default1P.',
        '# Empty COUNT_GAP/DETAIL_GAP inherit MIN_GAP. RESUME keeps saved input/filter/profile.']
    reference=['PGN68 R5 PUBLIC PARAMETER REFERENCE - generated from argparse','']
    for title,names in GROUPS:
        cmd+=['','REM '+title];sh+=['','# '+title];reference+=[title]
        for name in names:
            action=actions[name]
            if not action.help:raise ValueError('Public option lacks its English help sentence: '+name)
            from pgn_parameters import description
            text=description(name,action).replace('\n',' ')
            options=', '.join(action.option_strings)
            default=DEFAULTS.get(name,'0' if name in BOOLS else '')
            explanation=options+': '+text
            if name in BOOLS:explanation+=' Set1 to enable,0 to leave off.'
            cmd+=['REM '+explanation,'set "'+variable(name)+'='+default+'"']
            # Single-quoted values are editable and literal; argv is built by Python.
            sh+=['# '+explanation,"export "+variable(name)+"='"+default.replace("'","'\"'\"'")+"'"]
            reference+=['  '+options+' | '+variable(name)+'='+default+' | '+text]
    cmd+=['','set "PGN_R5_LAUNCHER=1"','"%~dp0pgn68.exe"','set "PGN_R5_EXIT=%ERRORLEVEL%"',
          'set "PGN_R5_LAUNCHER="','echo.','echo PGN68 returned to this persistent prompt. Close the window only when YOU want.',
          'if "%HEADLESS%"=="1" goto finished','"%ComSpec%" /d /k',':finished',
          'endlocal & exit /b %PGN_R5_EXIT%']
    sh+=['',"export PGN_R5_LAUNCHER=1",'set +e','./pgn68','result=$?',
         'if [ -t 0 ] && [ -t 1 ]; then',
         '  printf "\\nPGN68 returned to a persistent prompt. Close the window when YOU want.\\n"',
         '  exec /bin/bash -i','fi','exit "$result"']
    (directory/'Start-PGN68.cmd').write_bytes(('\r\n'.join(cmd)+'\r\n').encode('utf-8'))
    (directory/'Start-PGN68.sh').write_text('\n'.join(sh)+'\n',encoding='utf-8')
    (directory/'PUBLIC-PARAMETERS.txt').write_text('\n'.join(reference)+'\n',encoding='utf-8')
    return {name:actions[name].option_strings for _,names in GROUPS for name in names}
