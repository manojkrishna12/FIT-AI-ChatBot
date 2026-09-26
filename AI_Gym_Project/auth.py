"""
Account authentication and per-user fitness profiles.

Accounts live in the `users` collection (env: USER_ACCOUNTS_COLLECTION).
Passwords are hashed with bcrypt. Existing per-user app state in
`user_profiles` is untouched: signing in maps the session onto the
account's user id, so previously saved data for that id keeps working.
Guest (no account) usage remains fully supported.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import streamlit as st

from constants import USER_ACCOUNTS_COLLECTION
from storage import _get_collection, get_active_user_id

try:
    import bcrypt
except ImportError:  # pragma: no cover
    bcrypt = None

_MIN_USERNAME = 3
_MAX_USERNAME = 24
_USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9-_.]*$")

DEFAULT_PROFILE: dict = {
    "name": "",
    "age": 22,
    "gender": "Male",
    "weight_kg": 68.0,
    "height_cm": 170.0,
    "activity": "Moderately Active",
    "goal": "General Fitness",
    "diet_type": "No Restriction",
    "allergies": "None",
}


# ────────────────────────────────────────────────────────────────────────────
# Passwords
# ────────────────────────────────────────────────────────────────────────────


def _hash_password(password: str) -> bytes:
    if bcrypt is None:
        raise RuntimeError("bcrypt is not installed")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12))


def _verify_password(password: str, password_hash: bytes | str) -> bool:
    if bcrypt is None:
        raise RuntimeError("bcrypt is not installed")
    try:
        if isinstance(password_hash, str):
            password_hash = password_hash.encode("utf-8")
        return bcrypt.checkpw(password.encode("utf-8"), password_hash)
    except Exception:
        return False


# ────────────────────────────────────────────────────────────────────────────
# Accounts
# ────────────────────────────────────────────────────────────────────────────


def _accounts_collection():
    return _get_collection(USER_ACCOUNTS_COLLECTION)


def normalize_username(raw: str) -> str:
    """Normalize a username to the same scheme as user ids."""
    cleaned = []
    for char in (raw or "").strip().lower():
        cleaned.append(char if char.isalnum() or char in "-_." else "-")
    normalized = "".join(cleaned).strip("-_.")
    return normalized[:_MAX_USERNAME]


def validate_username(username: str) -> str | None:
    """Return an error message, or None when acceptable."""
    if len(username) < _MIN_USERNAME:
        return f"Username must be at least {_MIN_USERNAME} characters."
    if len(username) > _MAX_USERNAME:
        return f"Username must be at most {_MAX_USERNAME} characters."
    if not _USERNAME_RE.match(username):
        return "Use letters, numbers, dots, dashes or underscores (must start with a letter or number)."
    return None


def register_user(username: str, password: str, display_name: str = "") -> tuple[bool, str]:
    """Create an account. Returns (ok, message)."""
    username = normalize_username(username)
    error = validate_username(username)
    if error:
        return False, error
    if len(password or "") < 8:
        return False, "Password must be at least 8 characters."
    try:
        coll = _accounts_collection()
    except Exception:
        return False, "Database unavailable — cannot create an account right now."

    try:
        if coll.find_one({"_id": username}):
            return False, "That username is already taken."
        doc = {
            "_id": username,
            "password_hash": _hash_password(password).decode("ascii"),
            "display_name": (display_name or username).strip()[:60],
            "profile": dict(DEFAULT_PROFILE),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        coll.insert_one(doc)
    except Exception as exc:
        return False, f"Could not create the account: {exc}"
    return True, "Account created."


def authenticate(username: str, password: str) -> tuple[bool, str]:
    """Verify credentials. Returns (ok, message)."""
    username = normalize_username(username)
    try:
        doc = _accounts_collection().find_one({"_id": username})
    except Exception:
        return False, "Database unavailable — cannot sign in right now."
    if not doc:
        return False, "Unknown username or wrong password."
    if not _verify_password(password or "", doc.get("password_hash", "")):
        return False, "Unknown username or wrong password."
    return True, "ok"


# ────────────────────────────────────────────────────────────────────────────
# Session-backed sign-in state
# ────────────────────────────────────────────────────────────────────────────


def sign_in(username: str) -> None:
    """Bind the session to an account's user id and reload its persisted state."""
    username = normalize_username(username)
    st.session_state["authenticated"] = True
    st.session_state["account_username"] = username
    st.session_state["active_user_id"] = username
    # Force the persisted user state to reload for the new identity.
    st.session_state["_loaded_user_id"] = None


def sign_out() -> None:
    """Return the session to guest mode."""
    st.session_state["authenticated"] = False
    st.session_state.pop("account_username", None)
    st.session_state["active_user_id"] = "guest"
    st.session_state["_loaded_user_id"] = None


def is_authenticated() -> bool:
    return bool(st.session_state.get("authenticated", False))


def current_username() -> str | None:
    return st.session_state.get("account_username")


def get_account_display_name() -> str | None:
    if not is_authenticated():
        return None
    try:
        doc = _accounts_collection().find_one({"_id": current_username()}, {"display_name": 1})
    except Exception:
        return None
    return (doc or {}).get("display_name")


def change_password(username: str, current_password: str, new_password: str) -> tuple[bool, str]:
    """Change the signed-in user's password."""
    ok, msg = authenticate(username, current_password)
    if not ok:
        return False, "Current password is incorrect."
    if len(new_password or "") < 8:
        return False, "New password must be at least 8 characters."
    try:
        _accounts_collection().update_one(
            {"_id": normalize_username(username)},
            {"$set": {"password_hash": _hash_password(new_password).decode("ascii")}},
        )
    except Exception as exc:
        return False, f"Could not update the password: {exc}"
    return True, "Password updated."


# ────────────────────────────────────────────────────────────────────────────
# Fitness profile
# ────────────────────────────────────────────────────────────────────────────


def get_profile(user_id: str | None = None) -> dict:
    """Return the user's fitness profile merged over defaults."""
    user_id = user_id or get_active_user_id()
    profile = dict(DEFAULT_PROFILE)
    try:
        doc = _accounts_collection().find_one({"_id": user_id}, {"profile": 1})
    except Exception:
        doc = None
    if doc and isinstance(doc.get("profile"), dict):
        profile.update({k: v for k, v in doc["profile"].items() if k in DEFAULT_PROFILE})
    return profile


def save_profile(user_id: str | None = None, **fields) -> bool:
    """Persist profile fields for the user. Returns False when storage is down."""
    user_id = user_id or get_active_user_id()
    clean = {k: v for k, v in fields.items() if k in DEFAULT_PROFILE}
    try:
        coll = _accounts_collection()
        result = coll.update_one(
            {"_id": user_id},
            {"$set": {"profile": clean}},
            upsert=False,
        )
    except Exception:
        return False
    if result.matched_count == 0:
        return False  # no account document (e.g. guest) — nothing saved
    st.session_state["user_profile"] = clean
    return True


def profile_prefill(key: str, default):
    """Return a stored profile value for prefilling forms, else the default."""
    profile = st.session_state.get("user_profile")
    if profile is None:
        profile = get_profile()
        st.session_state["user_profile"] = profile
    value = profile.get(key)
    if value in (None, ""):
        return default
    return value
