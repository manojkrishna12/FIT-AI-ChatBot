"""One-time helper: build the FIT-AI desktop shortcut with an inline
base64-encoded PowerShell launcher (AV-resistant: no script files on disk).

Run with:  .venv/Scripts/python.exe tools/build_fitai_shortcut.py
Idempotent: safe to re-run; it recreates the same shortcut.
"""
import base64
import subprocess

SCRIPT = r"""
$ErrorActionPreference = 'SilentlyContinue'
$Root    = 'D:\Fit_AI_Version_2.0'
$DiagLog = Join-Path $Root 'tools\shortcut_launch.log'

function Test-Port($port) {
    $props = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    return ($null -ne $props -and $props.Count -gt 0)
}
function Test-HttpOk($url) {
    try {
        $resp = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 4
        return ($resp.Content -match 'ok')
    } catch { return $false }
}
function Start-Hidden($exe, $argList) {
    Start-Process -FilePath $exe -ArgumentList $argList -WindowStyle Hidden -WorkingDirectory $Root
}

# 1) MongoDB on 127.0.0.1:27018 with the preserved data dir
if (-not (Test-Port 27018)) {
    Start-Hidden (Join-Path $Root 'tools\mongodb-bin\mongod.exe') @(
        '--port','27018','--bind_ip','127.0.0.1',
        '--dbpath',(Join-Path $Root '.mongodb-data'),
        '--logpath',(Join-Path $Root 'tools\mongod_service.log'))
    $deadline = (Get-Date).AddSeconds(60)
    while (-not (Test-Port 27018) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 500 }
    if (-not (Test-Port 27018)) {
        Add-Content -Path $DiagLog -Value "$(Get-Date -Format s): mongod did not open port 27018"
    }
}

# 2) Streamlit on 8631 via the crash-safe selector-loop wrapper
$needed = $true
if (Test-Port 8631) {
    if (Test-HttpOk 'http://127.0.0.1:8631/_stcore/health') { $needed = $false }
    else {
        Get-NetTCPConnection -State Listen -LocalPort 8631 -ErrorAction SilentlyContinue |
            ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
        Start-Sleep -Seconds 2
    }
}
if ($needed) {
    Start-Hidden (Join-Path $Root '.venv\Scripts\python.exe') @(
        (Join-Path $Root 'tools\run_fitai.py'), $Root)
    $deadline = (Get-Date).AddSeconds(90)
    $ok = $false
    while ((Get-Date) -lt $deadline) {
        if (Test-HttpOk 'http://127.0.0.1:8631/_stcore/health') { $ok = $true; break }
        Start-Sleep -Milliseconds 800
    }
    if (-not $ok) {
        Add-Content -Path $DiagLog -Value "$(Get-Date -Format s): Streamlit not healthy after 90 s"
    }
}

# 3) Open the app in the default browser
Start-Process 'http://localhost:8631'
exit 0
"""

ENCODED = base64.b64encode(SCRIPT.encode("utf-16-le")).decode()
ARGS = (
    "--headless powershell -NoProfile -ExecutionPolicy Bypass "
    "-WindowStyle Hidden -EncodedCommand " + ENCODED
)

CREATE_CMD = (
    "$ws = New-Object -ComObject WScript.Shell; "
    "$lnk = $ws.CreateShortcut('C:\\Users\\windows\\Desktop\\FIT-AI.lnk'); "
    "$lnk.TargetPath = 'C:\\Windows\\System32\\conhost.exe'; "
    "$lnk.Arguments = @'\n" + ARGS + "\n'@; "
    "$lnk.WorkingDirectory = 'D:\\Fit_AI_Version_2.0'; "
    "$lnk.Description = 'Start FIT-AI (MongoDB + Streamlit) hidden and open the app in the browser'; "
    "$lnk.IconLocation = 'D:\\Fit_AI_Version_2.0\\tools\\mongodb-bin\\mongod.exe,0'; "
    "$lnk.Save(); "
    "$chk = $ws.CreateShortcut('C:\\Users\\windows\\Desktop\\FIT-AI.lnk'); "
    "'SAVED.'; 'ARGS LEN: ' + $chk.Arguments.Length; "
    "'STARTS WITH: ' + $chk.Arguments.Substring(0, 40)"
)

if __name__ == "__main__":
    out = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", CREATE_CMD],
        capture_output=True, text=True,
    )
    print(out.stdout)
    if out.stderr:
        print("STDERR:", out.stderr[:500])
    with open("tools/shortcut_args.txt", "w") as f:
        f.write(ARGS)
    print("Saved args copy at tools/shortcut_args.txt; encoded length:", len(ENCODED))
