@echo off
setlocal enabledelayedexpansion

rem ---------------------------------------------------------------------
rem  DATEV-Mock launcher (Windows)
rem
rem  Works with zero prerequisites: if a usable system Python (>= 3.9) is
rem  found on PATH, it is used via a project-local .venv. Otherwise this
rem  script downloads a portable, project-local Python (the official
rem  Windows embeddable package) into python-portable\ and uses that
rem  instead. Nothing is installed system-wide and no admin rights are
rem  required.
rem ---------------------------------------------------------------------

cd /d "%~dp0"

set "PYTHON_EXE="
set "USE_VENV="

echo [1/5] Checking for a usable system Python (>= 3.9)...

call :find_system_python
if defined SYSTEM_PYTHON_CMD (
    echo       Found system Python: !SYSTEM_PYTHON_CMD! ^(!SYSTEM_PYTHON_VERSION!^)
    set "USE_VENV=1"
    goto :setup_venv
)

echo       No usable system Python found on PATH.
goto :check_portable_existing

rem ---------------------------------------------------------------------
:setup_venv
if not exist ".venv\Scripts\python.exe" (
    echo [2/5] Creating virtual environment in .venv ...
    !SYSTEM_PYTHON_CMD! -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create the virtual environment with !SYSTEM_PYTHON_CMD!.
        exit /b 1
    )
) else (
    echo [2/5] Virtual environment .venv already exists.
)

set "PYTHON_EXE=.venv\Scripts\python.exe"

echo [3/5] Installing dependencies into .venv ...
"%PYTHON_EXE%" -m pip install --quiet --upgrade pip
"%PYTHON_EXE%" -m pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies from requirements.txt.
    exit /b 1
)
goto :ensure_cert

rem ---------------------------------------------------------------------
:check_portable_existing
if exist "python-portable\python.exe" (
    echo [2/5] Reusing previously bootstrapped portable Python in python-portable\ ...
    set "PYTHON_EXE=python-portable\python.exe"
    goto :ensure_cert
)
goto :bootstrap_portable

rem ---------------------------------------------------------------------
:bootstrap_portable
echo [2/5] Bootstrapping a portable, project-local Python ^(no system install^) ...

set "EMBED_URL=https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"
set "EMBED_ZIP=%TEMP%\datev-mock-python-embed.zip"

echo       Downloading embeddable Python from python.org ...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try { Invoke-WebRequest -Uri '%EMBED_URL%' -OutFile '%EMBED_ZIP%' -UseBasicParsing } catch { exit 1 }"
if errorlevel 1 (
    echo ERROR: Failed to download the portable Python package from %EMBED_URL%.
    echo        Check your internet connection and try again, or install Python
    echo        manually from https://www.python.org/downloads/ and re-run this script.
    exit /b 1
)

echo       Extracting portable Python into python-portable\ ...
if not exist "python-portable" mkdir "python-portable"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try { Expand-Archive -LiteralPath '%EMBED_ZIP%' -DestinationPath 'python-portable' -Force } catch { exit 1 }"
if errorlevel 1 (
    echo ERROR: Failed to extract the portable Python package.
    exit /b 1
)
del /q "%EMBED_ZIP%" >nul 2>&1

if not exist "python-portable\python.exe" (
    echo ERROR: Portable Python extraction did not produce python-portable\python.exe.
    exit /b 1
)

rem The embeddable distro ships with site-packages imports disabled via a
rem "._pth" file (a commented-out "#import site" line). Without uncommenting
rem it, pip and installed packages cannot be imported at all.
echo       Enabling site-packages support in the portable Python ...
for %%F in (python-portable\python3*._pth) do set "PTH_FILE=%%F"
if not defined PTH_FILE (
    echo ERROR: Could not locate the ._pth file in python-portable\.
    exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "(Get-Content -LiteralPath '%PTH_FILE%') -replace '^#import site$', 'import site' | Set-Content -LiteralPath '%PTH_FILE%'"
if errorlevel 1 (
    echo ERROR: Failed to enable site-packages support in the portable Python.
    exit /b 1
)

echo       Downloading get-pip.py ...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try { Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'python-portable\get-pip.py' -UseBasicParsing } catch { exit 1 }"
if errorlevel 1 (
    echo ERROR: Failed to download get-pip.py.
    exit /b 1
)

echo       Bootstrapping pip into the portable Python ...
python-portable\python.exe python-portable\get-pip.py --quiet
if errorlevel 1 (
    echo ERROR: Failed to bootstrap pip into the portable Python.
    exit /b 1
)

set "PYTHON_EXE=python-portable\python.exe"

echo [3/5] Installing dependencies into the portable Python ...
"%PYTHON_EXE%" -m pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies from requirements.txt.
    exit /b 1
)
goto :ensure_cert

rem ---------------------------------------------------------------------
:ensure_cert
if exist "certs\cert.pem" if exist "certs\key.pem" (
    echo [4/5] TLS certificate already present in certs\.
    goto :start_server
)

echo [4/5] Generating a self-signed TLS certificate for 127.0.0.1 ...
"%PYTHON_EXE%" certs\generate_cert.py
if errorlevel 1 (
    echo ERROR: Failed to generate the TLS certificate.
    exit /b 1
)

rem ---------------------------------------------------------------------
:start_server
echo [5/5] Starting the DATEV mock server on https://127.0.0.1:58452 ...
"%PYTHON_EXE%" -m uvicorn app.main:app --host 127.0.0.1 --port 58452 --ssl-keyfile certs/key.pem --ssl-certfile certs/cert.pem
exit /b %errorlevel%

rem ---------------------------------------------------------------------
rem  Locates a usable system Python (python or py -3) reporting >= 3.9.
rem  Sets SYSTEM_PYTHON_CMD and SYSTEM_PYTHON_VERSION on success, leaves
rem  both undefined on failure.
rem ---------------------------------------------------------------------
:find_system_python
set "SYSTEM_PYTHON_CMD="
set "SYSTEM_PYTHON_VERSION="

where python >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=2 delims= " %%V in ('python --version 2^>^&1') do set "CANDIDATE_VERSION=%%V"
    call :version_is_ok "!CANDIDATE_VERSION!"
    if "!VERSION_OK!"=="1" (
        set "SYSTEM_PYTHON_CMD=python"
        set "SYSTEM_PYTHON_VERSION=!CANDIDATE_VERSION!"
        exit /b 0
    )
)

where py >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=2 delims= " %%V in ('py -3 --version 2^>^&1') do set "CANDIDATE_VERSION=%%V"
    call :version_is_ok "!CANDIDATE_VERSION!"
    if "!VERSION_OK!"=="1" (
        set "SYSTEM_PYTHON_CMD=py -3"
        set "SYSTEM_PYTHON_VERSION=!CANDIDATE_VERSION!"
        exit /b 0
    )
)

exit /b 1

rem ---------------------------------------------------------------------
rem  Checks whether a "X.Y.Z" version string is >= 3.9. Sets VERSION_OK
rem  to 1 or 0.
rem ---------------------------------------------------------------------
:version_is_ok
set "VERSION_OK=0"
set "VSTR=%~1"
if "%VSTR%"=="" exit /b 0

for /f "tokens=1,2 delims=." %%A in ("%VSTR%") do (
    set "VMAJOR=%%A"
    set "VMINOR=%%B"
)

if not defined VMAJOR exit /b 0
if not defined VMINOR set "VMINOR=0"

if %VMAJOR% GTR 3 (
    set "VERSION_OK=1"
    exit /b 0
)
if %VMAJOR% EQU 3 if %VMINOR% GEQ 9 (
    set "VERSION_OK=1"
    exit /b 0
)
exit /b 0
