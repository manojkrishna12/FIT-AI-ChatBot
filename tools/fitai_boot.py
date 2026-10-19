"""
FIT-AI Python boot script for the desktop shortcut.

Run by pythonw.exe (windowless) when the FIT-AI desktop shortcut is
double-clicked:
  1. Starts MongoDB on 127.0.0.1:27018 with the preserved .mongodb-data
     directory — only if not already listening.
  2. Starts Streamlit on 8631 via tools/run_fitai.py (selector-loop
     wrapper that prevents the Windows WinError 64 crash) — only if the
     port is not already serving the app; kills a stuck offender first.
  3. Opens http://localhost:8631 in the default browser.

Diagnostics: tools\\shortcut_launch.log
Pure-python port checks and hidden process starts — no console window.
"""
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from datetime import datetime

ROOT = r"D:\Fit_AI_Version_2.0"
MONGO_EXE = os.path.join(ROOT, "tools", "mongodb-bin", "mongod.exe")
DATA_DIR = os.path.join(ROOT, ".mongodb-data")
MONGO_LOG = os.path.join(ROOT, "tools", "mongod_service.log")
PYW_EXE = os.path.join(ROOT, ".venv", "Scripts", "pythonw.exe")
PY_EXE = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
WRAPPER = os.path.join(ROOT, "tools", "run_fitai.py")
DIAG = os.path.join(ROOT, "tools", "shortcut_launch.log")
STREAMLIT_ARGS = [os.path.join(ROOT, "tools", "run_fitai.py"), ROOT]
APP_URL = "http://localhost:8631"


def log(message: str) -> None:
    try:
        stamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        with open(DIAG, "a", encoding="utf-8") as fh:
            fh.write(f"{stamp}: {message}\n")
    except OSError:
        pass


def port_listening(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def health_ok() -> bool:
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:8631/_stcore/health", timeout=4
        ) as resp:
            return b"ok" in resp.read()
    except OSError:
        return False


def start_hidden(exe: str, args: list[str], cwd: str = ROOT) -> None:
    subprocess.Popen(
        [exe, *args],
        cwd=cwd,
        creationflags=subprocess.CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )


def ensure_mongo() -> None:
    if port_listening(27018):
        return
    if not os.path.isfile(MONGO_EXE):
        log(f"mongod.exe not found at {MONGO_EXE}")
        return
    start_hidden(
        MONGO_EXE,
        [
            "--port", "27018",
            "--bind_ip", "127.0.0.1",
            "--dbpath", DATA_DIR,
            "--logpath", MONGO_LOG,
        ],
    )
    deadline = time.time() + 60  # cold WiredTiger recovery can be slow
    while time.time() < deadline and not port_listening(27018):
        time.sleep(0.5)
    if port_listening(27018):
        log("MongoDB started on 27018")
    else:
        log("mongod did not open port 27018 within 60 s")


def ensure_streamlit() -> None:
    if port_listening(8631):
        if health_ok():
            log("Streamlit already healthy; nothing started")
            return
        kill_port_owners(8631)
    if not (os.path.isfile(PY_EXE) and os.path.isfile(WRAPPER)):
        log("python.exe or run_fitai.py missing")
        return
    exe = PYW_EXE if os.path.isfile(PYW_EXE) else PY_EXE
    start_hidden(exe, STREAMLIT_ARGS)
    deadline = time.time() + 90
    while time.time() < deadline and not health_ok():
        time.sleep(0.8)
    if health_ok():
        log("Streamlit started on 8631")
    else:
        log("Streamlit not healthy after 90 s")


def kill_port_owners(port: int) -> None:
    try:
        out = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=15
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return
    pids:set[str] = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[3] == "LISTENING":
            local = parts[1].rsplit(":", 1)[-1]
            if local == str(port):
                pids.add(parts[4])
    for pid in pids:
        subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)
    time.sleep(2)


def main() -> None:
    if not port_listening(27018):
        log("=== shortcut launch (cold Mongo) ===")
    ensure_mongo()
    ensure_streamlit()
    webbrowser.open(APP_URL)


if __name__ == "__main__":
    main()
