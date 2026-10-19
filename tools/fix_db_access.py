"""
FIT-AI database reachability fixer.

BSNL rotates the home public IP from time to time; MongoDB Atlas then
rejects the TLS handshake for every IP that is not on the project's
Network Access allowlist and the app shows
"Database unavailable — cannot sign in right now."

This script:
  1. Pings Atlas using the project's own MONGODB_URI (.env).
  2. If reachable — prints OK and exits 0. Nothing else happens.
  3. If unreachable — detects the current public IP and:
       - with ATLAS_PUBLIC_KEY / ATLAS_PRIVATE_KEY / ATLAS_GROUP_ID in
         .env (one-time setup, see below) it adds the current IP to the
         project access list via the Atlas Admin API automatically;
       - without them it prints the exact value to paste into the Atlas
         Network Access page.

One-time setup for the automatic path:
  Atlas UI -> Project Access Manager -> API Keys -> Create API Key
  (role: Project Owner) -> copy both keys, and take the Project ID from
  Project Settings. Then add to the repo-root .env:

      ATLAS_PUBLIC_KEY=<public key>
      ATLAS_PRIVATE_KEY=<private key>
      ATLAS_GROUP_ID=<project id>

Secrets are read from .env only and are never printed.

Usage:  .venv/Scripts/python.exe tools/fix_db_access.py [--wait]
        (--wait retries the ping for up to ~60 s after a successful
         allowlist change, for use from START_FIT_AI.bat)
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "AI_Gym_Project"))

ATLAS_API = "https://cloud.mongodb.com/api/atlas/v2"
CURRENT_IP_SERVICES = ("https://api.ipify.org", "https://ifconfig.me")


def load_env() -> dict[str, str]:
    env: dict[str, str] = dict(os.environ)
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env.setdefault(key.strip(), value.strip())
    return env


def current_public_ip() -> str:
    for service in CURRENT_IP_SERVICES:
        try:
            with urllib.request.urlopen(service, timeout=8) as resp:
                ip = resp.read().decode().strip()
            ipaddress.ip_address(ip)  # validate
            return ip
        except Exception:
            continue
    return ""


def ping_mongodb(uri: str, timeout_ms: int = 8000) -> tuple[bool, str]:
    try:
        from pymongo import MongoClient
        from pymongo.errors import PyMongoError
    except ImportError:
        return False, "pymongo is not installed in this environment"
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=timeout_ms)
        client.admin.command("ping")
        client.close()
        return True, "ping OK"
    except PyMongoError as exc:
        return False, f"{type(exc).__name__}: {str(exc).splitlines()[0][:160]}"


def atlas_add_ip(env: dict[str, str], ip: str) -> tuple[bool, str]:
    """Add one /32 entry to the project access list via the Admin API."""
    import requests

    public_key = env.get("ATLAS_PUBLIC_KEY", "").strip()
    private_key = env.get("ATLAS_PRIVATE_KEY", "").strip()
    group_id = env.get("ATLAS_GROUP_ID", "").strip()
    if not (public_key and private_key and group_id):
        return False, "missing ATLAS_PUBLIC_KEY / ATLAS_PRIVATE_KEY / ATLAS_GROUP_ID in .env"

    url = f"{ATLAS_API}/groups/{group_id}/accessList"
    try:
        resp = requests.post(
            url,
            auth=requests.auth.HTTPDigestAuth(public_key, private_key),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            data=json.dumps({"ipAddress": ip, "comment": "FIT-AI auto (BSNL dynamic IP)"}),
            timeout=20,
        )
        if resp.status_code in (200, 201):
            return True, "added via Atlas API"
        if resp.status_code == 409 or "already exists" in resp.text.lower():
            return True, "already on the access list"
        return False, f"Atlas API HTTP {resp.status_code}: {resp.text[:160]}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {str(exc)[:160]}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--wait", action="store_true", help="retry ping up to ~60 s after a fix")
    args = parser.parse_args()

    env = load_env()
    uri = env.get("MONGODB_URI", "").strip()
    if not uri:
        print("DB-CHECK: MONGODB_URI is not configured in .env")
        return 1

    ok, detail = ping_mongodb(uri)
    if ok:
        print("DB-CHECK: database reachable.")
        return 0

    ip = current_public_ip()
    print(f"DB-CHECK: database unreachable ({detail})")
    print(f"DB-CHECK: current public IP: {ip or 'could not detect'}")

    if not ip:
        return 1

    added, how = atlas_add_ip(env, ip)
    if not added:
        if "missing ATLAS" in how:
            print("DB-FIX: automatic allowlist update is not configured.")
            print()
            print("  MANUAL STEP (takes 30 seconds):")
            print("   1. Open https://cloud.mongodb.com -> your project")
            print("   2. NETWORK ACCESS -> ADD IP ADDRESS")
            print(f"   3. Enter this single address:  {ip}/32")
            print("   4. Confirm, then double-click START_FIT_AI.bat again.")
            print("      (Never use 0.0.0.0/0.)")
            print()
            print("  To stop doing this by hand, add ATLAS_PUBLIC_KEY,")
            print("  ATLAS_PRIVATE_KEY and ATLAS_GROUP_ID to .env (see the")
            print("  header of tools/fix_db_access.py for the one-time setup).")
            return 1
        print(f"DB-FIX: automatic update failed ({how}) — use the manual step above.")
        return 1

    print(f"DB-FIX: current IP {ip}/32 allowlisted ({how}).")
    if not args.wait:
        return 0

    deadline = time.time() + 60
    while time.time() < deadline:
        ok, detail = ping_mongodb(uri, timeout_ms=5000)
        if ok:
            print("DB-CHECK: database reachable.")
            return 0
        time.sleep(5)
    print("DB-CHECK: still unreachable after 60 s (Atlas entry can take a minute to apply).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
