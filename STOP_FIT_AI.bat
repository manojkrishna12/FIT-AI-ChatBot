@echo off
setlocal EnableExtensions
title FIT-AI Stop

rem ============================================================
rem  FIT-AI stop script
rem  - Stops ONLY this project's Streamlit process(es) on 8631
rem    (works for both `streamlit run app.py` and the
rem     tools\run_fitai.py wrapper launch)
rem  - Never touches MongoDB or unrelated processes
rem ============================================================

set "PS=powershell -NoProfile -ExecutionPolicy Bypass"

%PS% -Command ^
 "$conn = Get-NetTCPConnection -LocalPort 8631 -State Listen -ErrorAction SilentlyContinue;" ^
 "if(-not $conn){ Write-Output 'FIT-AI is not running - nothing to stop.'; exit 0 }" ^
 "$pids = $conn | Select-Object -ExpandProperty OwningProcess -Unique;" ^
 "$killed = 0; $foreign = 0;" ^
 "foreach($procId in $pids){" ^
 "  $p = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $procId) -ErrorAction SilentlyContinue;" ^
 "  if($p -and $p.CommandLine -match 'streamlit|run_fitai' -and $p.CommandLine -match 'app\.py|run_fitai\.py' -and $p.CommandLine -match 'Fit_AI_Version_2\.0|\.venv|8631'){" ^
 "    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue; $killed++" ^
 "  } else { $foreign++ }" ^
 "};" ^
 "if($killed -gt 0){ Write-Output ('FIT-AI has been stopped (' + $killed + ' process(es) stopped). MongoDB and everything else were left running.') }" ^
 "elseif($foreign -gt 0){ Write-Output '[X] Port 8631 is used by an unrecognized process - nothing was stopped. Close it manually if you are sure.'; exit 1 }"

timeout /t 2 /nobreak >nul 2>&1
exit /b %ERRORLEVEL%
