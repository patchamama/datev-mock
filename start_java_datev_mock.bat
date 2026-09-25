@echo off
setlocal enabledelayedexpansion

rem ---------------------------------------------------------------------
rem  Java (Spring Boot) DATEV-Mock launcher (Windows)
rem
rem  This starts the *Java* mock (spring-boot/). For the Python/FastAPI
rem  mock, use the separate start.bat at the repo root instead -- the two
rem  are independent backends and this script never touches start.bat.
rem
rem  Java 21+ detection order (stops at the first Java 21+ hit):
rem    a) C:\ELO\java\bin\java.exe            (this project's known default)
rem    b) %JAVA_HOME%\bin\java.exe            (if JAVA_HOME is set)
rem    c) java.exe already resolvable on PATH
rem    d) Common OS-default install locations:
rem       C:\Program Files\Java\*, C:\Program Files\Eclipse Adoptium\*,
rem       C:\Program Files\Zulu\*
rem  Only if none of the above yields Java 21+, a portable JDK 21 build
rem  (Eclipse Temurin/Adoptium) is downloaded into the project-local,
rem  gitignored spring-boot\.jdk21-portable\ and used for this launch only
rem  -- nothing is installed system-wide and JAVA_HOME/PATH outside this
rem  script's own process are never touched.
rem
rem  If spring-boot\target\datev-mock-*.jar doesn't exist yet, it is built
rem  first with the resolved Java, mirroring spring-boot\RUNBOOK.md's
rem  documented mvnw.cmd invocation (explicit path, not a bare name --
rem  see RUNBOOK.md's NoDefaultCurrentDirectoryInExePath note).
rem ---------------------------------------------------------------------

cd /d "%~dp0"
set "REPO_ROOT=%CD%"
set "SPRING_DIR=%REPO_ROOT%\spring-boot"

rem F6 (odd/tasks/datev-mock-standalone-frontend.md): default changed from
rem 58553 to 53000. PORT_EXPLICIT tracks whether the caller asked for a
rem specific port (--port or DATEV_MOCK_JAVA_PORT) -- only the *default*
rem ever falls back to 53001 below; an explicit request is always respected
rem as-is, never silently overridden.
set "PORT=53000"
set "PORT_EXPLICIT=0"
if defined DATEV_MOCK_JAVA_PORT (
    set "PORT=%DATEV_MOCK_JAVA_PORT%"
    set "PORT_EXPLICIT=1"
)

set "JAVA_EXE="
set "JAVA_HOME_RESOLVED="

:parse_args
if "%~1"=="" goto :args_done
if /i "%~1"=="--port" (
    set "PORT=%~2"
    set "PORT_EXPLICIT=1"
    shift
    shift
    goto :parse_args
)
echo ERROR: Unknown argument "%~1"
echo Usage: start_java_datev_mock.bat [--port PORT]
echo        (or set the DATEV_MOCK_JAVA_PORT environment variable)
pause
exit /b 1
:args_done

echo [1/4] Detecting a usable Java 21+ install ...

rem --- a) ELO's own known default install location -----------------------
if exist "C:\ELO\java\bin\java.exe" (
    call :check_java_version "C:\ELO\java\bin\java.exe"
    if "!VERSION_OK!"=="1" (
        set "JAVA_EXE=C:\ELO\java\bin\java.exe"
        set "JAVA_HOME_RESOLVED=C:\ELO\java"
        echo       Found Java !JAVA_MAJOR! at C:\ELO\java ^(this project's ELO default location^).
        goto :java_found
    )
)

rem --- b) JAVA_HOME ----------------------------------------------------------
if defined JAVA_HOME (
    if exist "%JAVA_HOME%\bin\java.exe" (
        call :check_java_version "%JAVA_HOME%\bin\java.exe"
        if "!VERSION_OK!"=="1" (
            set "JAVA_EXE=%JAVA_HOME%\bin\java.exe"
            set "JAVA_HOME_RESOLVED=%JAVA_HOME%"
            echo       Found Java !JAVA_MAJOR! via JAVA_HOME ^(%JAVA_HOME%^).
            goto :java_found
        )
    )
)

rem --- c) java already on PATH -------------------------------------------
set "PATH_JAVA_EXE="
where java >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%P in ('where java') do (
        if not defined PATH_JAVA_EXE set "PATH_JAVA_EXE=%%P"
    )
)
if defined PATH_JAVA_EXE (
    call :check_java_version "!PATH_JAVA_EXE!"
    if "!VERSION_OK!"=="1" (
        set "JAVA_EXE=!PATH_JAVA_EXE!"
        for %%P in ("!PATH_JAVA_EXE!") do set "JAVA_BIN_DIR=%%~dpP"
        pushd "!JAVA_BIN_DIR!.."
        set "JAVA_HOME_RESOLVED=!CD!"
        popd
        echo       Found Java !JAVA_MAJOR! on PATH ^(!PATH_JAVA_EXE!^).
        goto :java_found
    )
)

rem --- d) common OS-default install locations -----------------------------
for %%R in ("C:\Program Files\Java" "C:\Program Files\Eclipse Adoptium" "C:\Program Files\Zulu") do (
    if not defined JAVA_EXE (
        if exist "%%~R" (
            for /d %%D in ("%%~R\*") do (
                if not defined JAVA_EXE (
                    if exist "%%D\bin\java.exe" (
                        call :check_java_version "%%D\bin\java.exe"
                        if "!VERSION_OK!"=="1" (
                            set "JAVA_EXE=%%D\bin\java.exe"
                            set "JAVA_HOME_RESOLVED=%%D"
                            echo       Found Java !JAVA_MAJOR! at %%D.
                        )
                    )
                )
            )
        )
    )
)
if defined JAVA_EXE goto :java_found

echo       No usable Java 21+ install found anywhere on this machine.
goto :download_portable_jdk

:java_found
goto :after_detection

rem ---------------------------------------------------------------------
rem  Downloads a portable JDK 21 (Eclipse Temurin, via the Adoptium API)
rem  into spring-boot\.jdk21-portable\ and uses it for this launch only.
rem ---------------------------------------------------------------------
:download_portable_jdk
echo [2/4] Bootstrapping a portable, project-local JDK 21 ^(no system install^) ...

set "PORTABLE_JAVA_EXE="
for /f "delims=" %%J in ('dir /s /b "%SPRING_DIR%\.jdk21-portable\java.exe" 2^>nul') do (
    if not defined PORTABLE_JAVA_EXE set "PORTABLE_JAVA_EXE=%%J"
)
if defined PORTABLE_JAVA_EXE (
    echo       Reusing previously bootstrapped portable JDK in spring-boot\.jdk21-portable\ ...
    set "JAVA_EXE=%PORTABLE_JAVA_EXE%"
    for %%B in ("%PORTABLE_JAVA_EXE%\..\..") do set "JAVA_HOME_RESOLVED=%%~fB"
    goto :after_detection
)

set "JDK_ARCH=x64"
if /i "%PROCESSOR_ARCHITECTURE%"=="ARM64" set "JDK_ARCH=aarch64"

set "JDK_URL=https://api.adoptium.net/v3/binary/latest/21/ga/windows/%JDK_ARCH%/jdk/hotspot/normal/eclipse"
set "JDK_ZIP=%TEMP%\datev-mock-jdk21.zip"

echo       Downloading portable JDK 21 ^(%JDK_ARCH%^) from Eclipse Temurin/Adoptium ...
echo       %JDK_URL%
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try { Invoke-WebRequest -Uri '%JDK_URL%' -OutFile '%JDK_ZIP%' -UseBasicParsing } catch { exit 1 }"
if errorlevel 1 (
    echo ERROR: Failed to download the portable JDK 21 from %JDK_URL%.
    echo        Check your internet connection, or install Java 21 yourself
    echo        ^(or set JAVA_HOME^) and re-run this script.
    exit /b 1
)

if not exist "%SPRING_DIR%\.jdk21-portable" mkdir "%SPRING_DIR%\.jdk21-portable"
echo       Extracting portable JDK into spring-boot\.jdk21-portable\ ...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try { Expand-Archive -LiteralPath '%JDK_ZIP%' -DestinationPath '%SPRING_DIR%\.jdk21-portable' -Force } catch { exit 1 }"
if errorlevel 1 (
    echo ERROR: Failed to extract the portable JDK 21 archive.
    exit /b 1
)
del /q "%JDK_ZIP%" >nul 2>&1

set "PORTABLE_JAVA_EXE="
for /f "delims=" %%J in ('dir /s /b "%SPRING_DIR%\.jdk21-portable\java.exe" 2^>nul') do (
    if not defined PORTABLE_JAVA_EXE set "PORTABLE_JAVA_EXE=%%J"
)
if not defined PORTABLE_JAVA_EXE (
    echo ERROR: Portable JDK extraction did not produce a java.exe binary.
    exit /b 1
)
set "JAVA_EXE=%PORTABLE_JAVA_EXE%"
for %%B in ("%PORTABLE_JAVA_EXE%\..\..") do set "JAVA_HOME_RESOLVED=%%~fB"

:after_detection
call :check_java_version "%JAVA_EXE%"
echo.
echo Using Java !JAVA_MAJOR! at "%JAVA_EXE%"
echo.

echo [3/4] Locating the Spring Boot jar ...
set "JAR_PATH="
for %%F in ("%SPRING_DIR%\target\datev-mock-*.jar") do set "JAR_PATH=%%~fF"

if not defined JAR_PATH (
    echo       No jar found in spring-boot\target\ -- building it now ...
    set "JAVA_HOME=%JAVA_HOME_RESOLVED%"
    pushd "%SPRING_DIR%"
    call ".\mvnw.cmd" clean package
    set "BUILD_EXIT=%errorlevel%"
    popd
    if not "%BUILD_EXIT%"=="0" (
        echo ERROR: Maven build failed ^(exit code %BUILD_EXIT%^).
        exit /b 1
    )
    for %%F in ("%SPRING_DIR%\target\datev-mock-*.jar") do set "JAR_PATH=%%~fF"
    if not defined JAR_PATH (
        echo ERROR: Build succeeded but no spring-boot\target\datev-mock-*.jar was found.
        exit /b 1
    )
) else (
    echo       Found existing jar: %JAR_PATH%
)

rem F6: only check/fall back on the *default* port -- never when the caller
rem explicitly asked for one via --port/DATEV_MOCK_JAVA_PORT. Exactly one
rem fallback level (53000 -> 53001), not an open-ended scan. Reuses this
rem repo's own existing Get-NetTCPConnection technique (already used by
rem start.bat) but only to *check* here, never to kill anything -- a
rem different, explicit design choice from start.bat's own kill-and-reuse
rem behavior for the Python mock.
if "%PORT_EXPLICIT%"=="0" (
    powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue) { exit 1 } else { exit 0 }"
    if errorlevel 1 (
        echo       Port %PORT% is already in use -- falling back to port 53001.
        set "PORT=53001"
    )
)

echo [4/4] Starting the Java DATEV mock ...
echo       Java:    %JAVA_EXE% ^(version !JAVA_MAJOR!^)
echo       Jar:     %JAR_PATH%
echo       Port:    %PORT%
echo       ^(override the port with --port PORT or the DATEV_MOCK_JAVA_PORT env var^)
echo.
echo Starting the DATEV mock server on http://127.0.0.1:%PORT% ...

rem F6: auto-open the default browser a couple seconds after launch, the
rem same non-blocking Start-Process pattern start.bat already uses for the
rem Python mock -- but pointed at this repo's standalone frontend.html via a
rem file:// URL (Java doesn't serve /admin itself, per F1's own documented
rem decision), passing the resolved connection details as query params so
rem the frontend's own self-detect/query-param logic (F6) pre-fills and
rem saves them -- see frontend/admin.html's resolveConnectionSettingsForThisLoad().
set "FRONTEND_HTML=%REPO_ROOT%\frontend\admin.html"
set "FRONTEND_URL_PATH=%FRONTEND_HTML:\=/%"
set "BROWSER_URL=file:///%FRONTEND_URL_PATH%?protocol=http&host=127.0.0.1&port=%PORT%"
start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process '%BROWSER_URL%'"

"%JAVA_EXE%" -jar "%JAR_PATH%" --server.port=%PORT%
set "JAVA_EXIT=%errorlevel%"
if not "%JAVA_EXIT%"=="0" (
    echo.
    echo Java process exited with an error ^(code %JAVA_EXIT%^) -- see the
    echo output above for details.
    pause
)
exit /b %JAVA_EXIT%

rem ---------------------------------------------------------------------
rem  :check_java_version <path-to-java.exe>
rem  Runs "<path> -version", parses the major version number, and sets
rem  JAVA_MAJOR and VERSION_OK (1 if >= 21, else 0).
rem ---------------------------------------------------------------------
:check_java_version
set "VERSION_OK=0"
set "JAVA_MAJOR="
set "RAWVER="
set "CANDIDATE=%~1"
rem Redirect "-version" output to a temp file rather than piping it
rem directly inside a FOR /F command string -- a candidate path quoted
rem with its own double quotes (needed for paths containing spaces, e.g.
rem "C:\Program Files\Java\...") clashes with FOR /F's own single-quote
rem command-string delimiter and fails with a bogus syntax error.
set "JAVAVER_TMP=%TEMP%\datev-mock-javaver-%RANDOM%.txt"
"%CANDIDATE%" -version >"%JAVAVER_TMP%" 2>&1
for /f "tokens=3" %%V in ('findstr /I "version" "%JAVAVER_TMP%" 2^>nul') do (
    if not defined RAWVER set "RAWVER=%%V"
)
del /q "%JAVAVER_TMP%" >nul 2>&1
if not defined RAWVER exit /b 0
set "RAWVER=%RAWVER:"=%"
set "VMAJOR="
set "VMINOR="
for /f "tokens=1,2 delims=." %%A in ("%RAWVER%") do (
    set "VMAJOR=%%A"
    set "VMINOR=%%B"
)
if not defined VMAJOR exit /b 0
if "%VMAJOR%"=="1" (
    set "JAVA_MAJOR=%VMINOR%"
) else (
    set "JAVA_MAJOR=%VMAJOR%"
)
if not defined JAVA_MAJOR exit /b 0
echo %JAVA_MAJOR%| findstr /r "^[0-9][0-9]*$" >nul
if errorlevel 1 exit /b 0
if %JAVA_MAJOR% GEQ 21 set "VERSION_OK=1"
exit /b 0
