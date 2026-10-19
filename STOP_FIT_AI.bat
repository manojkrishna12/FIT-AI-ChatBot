@echo off
setlocal EnableExtensions
title FIT-AI Stop

rem ============================================================
rem  FIT-AI stop script
rem  - Stops ONLY this project's Streamlit process (port 8631)
rem  - Never touches MongoDB
rem  - Never touches unrelated Python or Streamlit processes
rem ============================================================

set "PS=powershell -NoProfile -ExecutionPolicy Bypass"

rem ---- 1) Find the process listening on port 8631 ----
set "FITAI_PID="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8631 " ^| findstr "LISTENING"') do set "FITAI_PID=%%P"

if not defined FITAI_PID (
    echo FIT-AI is not running - nothing to stop.
    timeout /t 3 /nobreak >nul 2>&1
    exit /b 0
)

rem ---- 2) Verify it really is this project's Streamlit app ----
%PS% -Command "$p = Get-CimInstance Win32_Process -Filter 'ProcessId=%FITAI_PID%' -ErrorAction SilentlyContinue; if($p -and $p.CommandLine -match 'streamlit' -and $p.CommandLine -match 'app\.py' -and $p.CommandLine -match 'Fit_AI_Version_2\.0|\.venv|8631'){ exit 0 }; exit 1"
if errorlevel 1 (
    echo [X] PID %FITAI_PID% is using port 8631, but it does not look like this project's Streamlit app.
    echo     Nothing was stopped. Close it manually if you are sure.
    pause
    exit /b 1
)

rem ---- 3) Stop it ----
echo Stopping FIT-AI ^(PID %FITAI_PID%^) ...
taskkill /PID %FITAI_PID% /F >nul 2>&1
if errorlevel 1 (
    echo [X] Could not stop PID %FITAI_PID% - it may have already exited.
    timeout /t 3 /nobreak >nul 2>&1
    exit /b 1
)

echo FIT-AI has been stopped. MongoDB and everything else were left running.
timeout /t 3 /nobreak >nul 2>&1
exit /b 0
