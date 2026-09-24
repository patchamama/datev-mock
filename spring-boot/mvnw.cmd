@echo off
setlocal EnableDelayedExpansion

set "MAVEN_PROJECTBASEDIR=%~dp0"
set "WRAPPER_JAR=%MAVEN_PROJECTBASEDIR%.mvn\wrapper\maven-wrapper.jar"
set "WRAPPER_PROPERTIES=%MAVEN_PROJECTBASEDIR%.mvn\wrapper\maven-wrapper.properties"

if not exist "%WRAPPER_JAR%" (
  for /f "tokens=1,* delims==" %%A in ('findstr /b wrapperUrl "%WRAPPER_PROPERTIES%"') do set "WRAPPER_URL=%%B"
  if not defined WRAPPER_URL (
    echo Could not find wrapperUrl in "%WRAPPER_PROPERTIES%" 1>&2
    exit /b 1
  )
  echo Downloading Maven Wrapper ...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -UseBasicParsing -Uri '!WRAPPER_URL!' -OutFile '!WRAPPER_JAR!'"
  if errorlevel 1 exit /b 1
)

if defined JAVA_HOME (
  set "JAVA_EXE=%JAVA_HOME%\bin\java.exe"
) else (
  set "JAVA_EXE=java.exe"
)

"%JAVA_EXE%" %MAVEN_OPTS% -classpath "%WRAPPER_JAR%" -Dmaven.multiModuleProjectDirectory="%MAVEN_PROJECTBASEDIR%" org.apache.maven.wrapper.MavenWrapperMain %*
exit /b %ERRORLEVEL%
