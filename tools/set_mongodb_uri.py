"""
Update MONGODB_URI in the root .env without exposing the secret.

Prompts for the connection string with getpass (no echo), validates it
loosely, replaces only the MONGODB_URI line, and reports success without
ever printing the value. Run from the repo root:

    .venv/Scripts/python.exe tools/set_mongodb_uri.py
"""
import getpass
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
BACKUP_PATH = ROOT / ".env.pre-atlas-bak"

# Loosely confirm it *looks* like a mongodb URI - only the scheme is checked.
_URI_SCHEME_RE = re.compile(r"^(mongodb(\+srv)?://)\S+$")


def main() -> int:
    if not ENV_PATH.exists():
        print(f"ERROR: {ENV_PATH} not found.")
        return 1

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print(
            "ERROR: this helper needs an interactive terminal for hidden input.\r\n"
            "Open Command Prompt yourself and run:\r\n"
            "  cd /d D:\\Fit_AI_Version_2.0\r\n"
            "  .venv\\Scripts\\python.exe tools\\set_mongodb_uri.py"
        )
        return 1

    uri = getpass.getpass(
        "Paste your Atlas connection string (input hidden, not echoed): "
    ).strip()

    if not _URI_SCHEME_RE.match(uri):
        print("ERROR: that does not look like a mongodb:// or mongodb+srv:// URI.")
        return 1
    if "..." in uri or "<" in uri or ">" in uri:
        print("ERROR: the string still contains placeholder text - copy the full "
              "real URI from Atlas 'Connect > Drivers'.")
        return 1

    if not BACKUP_PATH.exists():
        shutil.copyfile(ENV_PATH, BACKUP_PATH)
        print(f"Backup saved: {BACKUP_PATH.name} (URI line not shown).")

    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    replaced = False
    new_lines = []
    for line in lines:
        if line.strip().startswith("MONGODB_URI"):
            new_lines.append(f"MONGODB_URI={uri}")
            replaced = True
        else:
            new_lines.append(line)
    if not replaced:
        new_lines.append(f"MONGODB_URI={uri}")

    ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    host = uri.split("@")[1].split("/")[0] if "@" in uri else "(unknown host)"
    print(f"OK: MONGODB_URI updated in .env (host now: {host}); value not printed.")
    print("Next: tell the assistant it's set, and it will ping-test and restart the app.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
