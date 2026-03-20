@echo off
setlocal

set SCRIPT_ARGS=

:parse
if "%~1"=="" goto run
if /I "%~1"=="--onedir" (
  set SCRIPT_ARGS=%SCRIPT_ARGS% --onedir
  shift
  goto parse
)
if /I "%~1"=="--no-clean" (
  set SCRIPT_ARGS=%SCRIPT_ARGS% --no-clean
  shift
  goto parse
)

echo Unknown argument: %~1
exit /b 1

:run
where py >nul 2>nul
if %errorlevel%==0 (
  py scripts\build_release.py %SCRIPT_ARGS%
) else (
  python scripts\build_release.py %SCRIPT_ARGS%
)
