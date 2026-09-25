@echo off
setlocal enabledelayedexpansion

rem ---------------------------------------------------------------------
rem  Frontend-only launcher (Windows)
rem
rem  Serves just the standalone admin frontend (frontend/admin.html) over
rem  a plain local HTTP server, with NO mock backend involved -- point its
rem  own "Backend target & DATEV connection settings" card at whatever
rem  DATEV-compatible target you actually want (this project's FastAPI or
rem  Java mock, a real DATEV Desktop API, or someone else's compatible
rem  mock) once it's open. See the README FAQ ("Can I use just the
rem  frontend, with no backend running at all?").
rem
rem  Uses Python's built-in `http.server` module (no third-party
rem  dependency) rather than opening frontend/admin.html directly via
rem  file:// -- a real http:// origin avoids that scheme's stricter,
rem  browser-dependent cross-origin request handling. Unlike start.bat's
rem  own zero-prerequisites portable-Python bootstrap, this script assumes
rem  a Python already on PATH -- reasonable for a narrow, single-purpose
rem  convenience script that (unlike the full mock) doesn't need any
rem  third-party packages, only the standard library.
rem ---------------------------------------------------------------------

cd /d "%~dp0"

set "PORT=8000"
if defined DATEV_MOCK_FRONTEND_PORT set "PORT=%DATEV_MOCK_FRONTEND_PORT%"

:parse_args
if "%~1"=="" goto :args_done
if /i "%~1"=="--port" (
    set "PORT=%~2"
    shift
    shift
    goto :parse_args
)
echo ERROR: Unknown argument "%~1"
echo Usage: start_only_frontend.bat [--port PORT]
echo        (or set the DATEV_MOCK_FRONTEND_PORT environment variable)
pause
exit /b 1
:args_done

set "PYTHON_EXE="
where python >nul 2>&1
if not errorlevel 1 set "PYTHON_EXE=python"
if not defined PYTHON_EXE (
    where py >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=py -3"
)
if not defined PYTHON_EXE (
    echo ERROR: No Python found on PATH.
    echo        This script only serves one static file locally and
    echo        deliberately doesn't bootstrap a portable Python for that
    echo        ^(see start.bat if you want the full mock's zero-prerequisites
    echo        installer instead^). Install Python 3, or just open
    echo        frontend\admin.html directly in your browser via file://.
    pause
    exit /b 1
)

echo Starting the standalone frontend on http://127.0.0.1:%PORT%/admin.html ...
echo (serving frontend\ only -- no mock backend is running; configure a
echo  target in the page's own "Backend target" card once it opens.)
echo.

start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "Start-Sleep -Seconds 1; Start-Process 'http://127.0.0.1:%PORT%/admin.html'"

%PYTHON_EXE% -m http.server %PORT% --directory frontend
set "SERVER_EXIT=%errorlevel%"
if not "%SERVER_EXIT%"=="0" (
    echo.
    echo The local server exited with an error ^(code %SERVER_EXIT%^).
    pause
)
exit /b %SERVER_EXIT%
