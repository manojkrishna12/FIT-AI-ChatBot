@echo off
setlocal EnableExtensions
title FIT-AI Launcher

rem ============================================================
rem  FIT-AI one-click launcher
rem  - Opens http://localhost:8631 in the default browser
rem  - Starts the Streamlit app first if it is not running yet
rem  - Uses only this project's own virtualenv Python
rem  - Works no matter which directory it is launched from
rem ============================================================

set "ROOT=%~dp0"
set "APP_DIR=%ROOT%AI_Gym_Project"
set "PYTHON=%ROOT%.venv\Scripts\python.exe"
set "APP_URL=http://localhost:8631"
set "HEALTH_URL=%APP_URL%/_stcore/health"
set "PS=powershell -NoProfile -ExecutionPolicy Bypass"

rem ---- 0) Make sure MongoDB Atlas accepts this computer's IP ----
rem BSNL rotates the public IP; tools\fix_db_access.py auto-adds the
rem current IP to the Atlas allowlist when API keys are configured in
rem .env, otherwise it prints the exact manual step. Never uses 0.0.0.0/0.
if exist "%ROOT%tools\fix_db_access.py" if exist "%PYTHON%" (
    "%PYTHON%" "%ROOT%tools\fix_db_access.py" --wait
    if errorlevel 1 (
        echo.
        echo     The app will still open, but sign-in needs the Atlas step shown above.
        pause
    )
)

rem ---- 1) Is FIT-AI already listening on port 8631? ----
set "RUNNING_PID="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8631 " ^| findstr "LISTENING"') do set "RUNNING_PID=%%P"

if not defined RUNNING_PID goto start_app

%PS% -Command "try{ if((Invoke-WebRequest -UseBasicParsing '%HEALTH_URL%' -TimeoutSec 3).Content -match 'ok'){ exit 0 } }catch{}; exit 1"
if errorlevel 1 (
    echo [X] Port 8631 is already in use ^(PID %RUNNING_PID%^) but FIT-AI is not answering.
    echo     Nothing was started. Run STOP_FIT_AI.bat first, then try again.
    pause
    exit /b 1
)

echo FIT-AI is already running on port 8631 ^(PID %RUNNING_PID%^).
echo Opening %APP_URL% ...
start "" "%APP_URL%"
exit /b 0

:start_app
if not exist "%PYTHON%" (
    echo [X] Project Python was not found:
    echo     "%PYTHON%"
    pause
    exit /b 1
)
if not exist "%APP_DIR%\app.py" (
    echo [X] Application entry point was not found:
    echo     "%APP_DIR%\app.py"
    pause
    exit /b 1
)

echo Starting FIT-AI on port 8631 ...
set "PYTHONIOENCODING=utf-8"
pushd "%APP_DIR%"
%PS% -Command "Start-Process -FilePath '%PYTHON%' -ArgumentList '-m','streamlit','run','app.py','--server.port','8631','--server.headless','true','--browser.gatherUsageStats','false' -WorkingDirectory '%APP_DIR%' -WindowStyle Hidden"
if errorlevel 1 (
    echo     PowerShell start unavailable, using a minimized server window instead ...
    start "FIT-AI Server" /min "%PYTHON%" -m streamlit run app.py --server.port 8631 --server.headless true --browser.gatherUsageStats false
)
popd

echo Waiting for FIT-AI to become ready ...
%PS% -Command "$u='%HEALTH_URL%'; $end=(Get-Date).AddSeconds(60); while((Get-Date) -lt $end){ try{ if((Invoke-WebRequest -UseBasicParsing $u -TimeoutSec 3).Content -match 'ok'){ exit 0 } }catch{}; Start-Sleep -Milliseconds 700 }; exit 1"
if errorlevel 1 (
    echo [X] FIT-AI did not answer within 60 seconds. Opening the browser anyway.
    start "" "%APP_URL%"
    pause
    exit /b 1
)

echo FIT-AI is ready.
start "" "%APP_URL%"
exit /b 0
