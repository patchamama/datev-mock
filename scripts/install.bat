@echo off
setlocal enabledelayedexpansion

rem ---------------------------------------------------------------------
rem  DATEV-Mock one-line installer (Windows)
rem
rem  Downloads (or updates) the DATEV-Mock repository into a local folder
rem  and hands off to its own start.bat, which bootstraps Python (system
rem  Python if available, otherwise a portable download -- no system-wide
rem  install, no admin rights), installs dependencies, and launches the
rem  mock server.
rem
rem  Usage (run from any directory, cmd.exe or PowerShell):
rem    powershell -c "iwr -useb https://raw.githubusercontent.com/patchamama/datev-mock/main/scripts/install.bat -OutFile install.bat; .\install.bat"
rem
rem  Set DATEV_MOCK_DIR to change where the repo is placed (default: datev-mock).
rem ---------------------------------------------------------------------

set "REPO_URL=https://github.com/patchamama/datev-mock.git"
set "REPO_ARCHIVE_URL=https://github.com/patchamama/datev-mock/archive/refs/heads/main.zip"
if not defined DATEV_MOCK_DIR set "DATEV_MOCK_DIR=datev-mock"
set "TARGET_DIR=%DATEV_MOCK_DIR%"

if exist "%TARGET_DIR%\.git" (
    echo [1/2] %TARGET_DIR% already exists, updating...
    git -C "%TARGET_DIR%" pull --ff-only
    if errorlevel 1 (
        echo ERROR: git pull failed in %TARGET_DIR%.
        exit /b 1
    )
    goto :run_start
)

where git >nul 2>&1
if not errorlevel 1 (
    echo [1/2] Cloning DATEV-Mock into %TARGET_DIR% ...
    git clone --depth 1 "%REPO_URL%" "%TARGET_DIR%"
    if errorlevel 1 (
        echo ERROR: git clone failed.
        exit /b 1
    )
    goto :run_start
)

echo [1/2] git not found, downloading a source archive instead...
if exist "%TARGET_DIR%" (
    echo ERROR: %TARGET_DIR% already exists but is not a git repository.
    echo        Remove it, or set DATEV_MOCK_DIR to a different path, and retry.
    exit /b 1
)

set "ZIP_FILE=%TEMP%\datev-mock-src.zip"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try { Invoke-WebRequest -Uri '%REPO_ARCHIVE_URL%' -OutFile '%ZIP_FILE%' -UseBasicParsing } catch { exit 1 }"
if errorlevel 1 (
    echo ERROR: Failed to download the source archive from %REPO_ARCHIVE_URL%.
    exit /b 1
)

echo       Extracting archive...
set "EXTRACT_DIR=%TEMP%\datev-mock-src-extract"
if exist "%EXTRACT_DIR%" rmdir /s /q "%EXTRACT_DIR%"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try { Expand-Archive -LiteralPath '%ZIP_FILE%' -DestinationPath '%EXTRACT_DIR%' -Force } catch { exit 1 }"
if errorlevel 1 (
    echo ERROR: Failed to extract the source archive.
    exit /b 1
)
del /q "%ZIP_FILE%" >nul 2>&1

set "UNZIPPED_DIR="
for /d %%D in ("%EXTRACT_DIR%\*") do set "UNZIPPED_DIR=%%D"
if not defined UNZIPPED_DIR (
    echo ERROR: Could not locate the extracted source directory.
    exit /b 1
)
move "!UNZIPPED_DIR!" "%TARGET_DIR%" >nul
rmdir /s /q "%EXTRACT_DIR%" >nul 2>&1

:run_start
cd /d "%TARGET_DIR%"
echo [2/2] Handing off to start.bat (installs Python dependencies and launches the mock)...
call start.bat
exit /b %errorlevel%
