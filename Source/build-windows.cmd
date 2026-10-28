@echo off
cd /d "%~dp0" || exit /b 1
python build.py --archs 86,120 --package
exit /b %ERRORLEVEL%
