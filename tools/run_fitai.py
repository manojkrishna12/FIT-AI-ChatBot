"""
FIT-AI Streamlit launcher wrapper (Windows crash fix).

The default Windows asyncio *proactor* event loop raises
`OSError: [WinError 64] The specified network name is no longer available`
inside Streamlit's socket-accept loop when a client disconnects abruptly,
repeatedly destabilizing the server (seen in fix_boot.log and this restore).

This wrapper switches to the *selector* event loop (the documented
workaround) and then hands control to the streamlit CLI unchanged.
No application code is modified.

Usage:
  python run_fitai.py <repo_root>
"""
import os
import sys
from dotenv import load_dotenv

if sys.platform == "win32":
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
root = os.path.abspath(root)
app_dir = os.path.abspath(os.path.join(root, "AI_Gym_Project"))

# Streamlit scripts run with cwd = app_dir, so the app's own load_dotenv()
# would look there and miss the repo-root .env (which carries the real
# MONGODB_URI, i.e. mongod on port 27018). Load it here so the server
# process environment — and every script it runs — inherits it.
load_dotenv(os.path.join(root, ".env"), override=False)

sys.path.insert(0, app_dir)
os.chdir(app_dir)

from streamlit.web import cli as stcli  # noqa: E402  (import after loop policy)

if __name__ == "__main__":
    sys.argv = [
        "streamlit",
        "run",
        os.path.join(app_dir, "app.py"),
        "--server.port", "8631",
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
    ]
    sys.exit(stcli.main())
