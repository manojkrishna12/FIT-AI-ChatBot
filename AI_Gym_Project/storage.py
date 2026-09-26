"""
Mongo-backed per-user state helpers.

This module keeps user-specific data in a single MongoDB document so the app
can restore chat history and saved plans across reruns and browser sessions.
"""

from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
from typing import Any

import streamlit as st

from constants import (
DEFAULT_USER_ID,
EXERCISE_DB_COLLECTION,
EXERCISE_IMAGES_BUCKET,
MONGODB_DB_NAME,
MONGODB_SERVER_SELECTION_TIMEOUT_MS,
MONGODB_URI,
MONGODB_USERS_COLLECTION,
ROUTINES_COLLECTION,
)
try:
    from gridfs import GridFS
except ImportError:
    GridFS = None

try:
    from pymongo import MongoClient
except ImportError:
    MongoClient = None


def normalize_user_id(raw_value: str) -> str:
    """Create a stable, URL-safe user id."""
    cleaned = []
    for char in (raw_value or "").strip().lower():
        cleaned.append(char if char.isalnum() else "-")
    normalized = "-".join(part for part in "".join(cleaned).split("-") if part)
    return normalized or DEFAULT_USER_ID


def get_active_user_id() -> str:
    """Return the active user id from Streamlit session state."""
    return normalize_user_id(st.session_state.get("active_user_id", DEFAULT_USER_ID))


@lru_cache(maxsize=1)
def _get_users_collection():
    """Return the MongoDB collection used for user profiles."""
    if MongoClient is None:
        raise RuntimeError("`pymongo` is not installed.")
    if not MONGODB_URI:
        raise RuntimeError("`MONGODB_URI` is not configured.")

    client = MongoClient(
        MONGODB_URI,
        serverSelectionTimeoutMS=MONGODB_SERVER_SELECTION_TIMEOUT_MS,
        connectTimeoutMS=MONGODB_SERVER_SELECTION_TIMEOUT_MS,
        socketTimeoutMS=max(5000, MONGODB_SERVER_SELECTION_TIMEOUT_MS),
    )
    client.admin.command("ping")
    collection = client[MONGODB_DB_NAME][MONGODB_USERS_COLLECTION]
    collection.create_index("updated_at")
    return collection


def get_storage_status() -> tuple[bool, str]:
    """Report whether MongoDB persistence is currently available."""
    try:
        _get_users_collection()
        return True, f"MongoDB connected: `{MONGODB_DB_NAME}.{MONGODB_USERS_COLLECTION}`"
    except Exception as exc:
        return False, f"MongoDB unavailable: {exc}"


def _default_user_state(user_id: str) -> dict[str, Any]:
    """Return the default persisted shape for a new user."""
    return {
        "user_id": user_id,
        "habit": {
            "streak_days": 0,
            "last_checkin_date": None,
            "checkin_done_today": False,
        },
        "diet": {
            "diet_plan": "",
            "calorie_goal": 2000,
            "calorie_log": [],
            "tracker_entries": [],
            "meal_history": [],
            "diet_plan_history": [],
            "grocery_history": [],
        },
        "gym": {
            "workout_plan_history": [],
        },
    }


def _merge_defaults(defaults: dict[str, Any], loaded: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge a loaded MongoDB document into default values."""
    merged = dict(defaults)
    for key, value in loaded.items():
        if key == "_id":
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_defaults(merged[key], value)
        else:
            merged[key] = value
    return merged


def _parse_optional_date(value: Any) -> date | None:
    """Convert an ISO string back into a date when possible."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def load_user_state(user_id: str) -> dict[str, Any]:
    """Load a user's persisted state, or return defaults if unavailable."""
    defaults = _default_user_state(user_id)
    try:
        doc = _get_users_collection().find_one({"_id": user_id})
    except Exception:
        doc = None

    state = _merge_defaults(defaults, doc or {})
    state["habit"]["last_checkin_date"] = _parse_optional_date(
        state["habit"].get("last_checkin_date")
    )
    state["habit"]["checkin_done_today"] = (
        state["habit"]["last_checkin_date"] == date.today()
    )
    return state


def append_session_history(key: str, item: dict[str, Any], limit: int = 12) -> None:
    """Append an item to a session-state history list and trim it."""
    history = list(st.session_state.get(key, []))
    history.insert(0, item)
    st.session_state[key] = history[:limit]


def ensure_user_state_loaded() -> None:
    """Load the active user's saved state into Streamlit session state."""
    user_id = get_active_user_id()
    if st.session_state.get("_loaded_user_id") == user_id:
        return

    state = load_user_state(user_id)
    st.session_state["active_user_id"] = user_id
    st.session_state["streak_days"] = state["habit"]["streak_days"]
    st.session_state["last_checkin_date"] = state["habit"]["last_checkin_date"]
    st.session_state["checkin_done_today"] = state["habit"]["checkin_done_today"]
    st.session_state["diet_plan"] = state["diet"]["diet_plan"]
    st.session_state["calorie_goal"] = state["diet"]["calorie_goal"]
    st.session_state["calorie_log"] = list(state["diet"]["calorie_log"])
    st.session_state["tracker_entries"] = list(state["diet"]["tracker_entries"])
    st.session_state["meal_history"] = list(state["diet"]["meal_history"])
    st.session_state["diet_plan_history"] = list(state["diet"]["diet_plan_history"])
    st.session_state["grocery_history"] = list(state["diet"]["grocery_history"])
    st.session_state["workout_plan_history"] = list(state["gym"]["workout_plan_history"])
    st.session_state["_loaded_user_id"] = user_id


def save_current_user_state() -> bool:
    """Persist the current Streamlit session state for the active user."""
    try:
        collection = _get_users_collection()
    except Exception:
        return False

    user_id = get_active_user_id()
    now = datetime.utcnow().isoformat()
    last_checkin = st.session_state.get("last_checkin_date")
    if isinstance(last_checkin, date):
        last_checkin = last_checkin.isoformat()

    payload = {
        "user_id": user_id,
        "habit": {
            "streak_days": int(st.session_state.get("streak_days", 0)),
            "last_checkin_date": last_checkin,
            "checkin_done_today": bool(st.session_state.get("checkin_done_today", False)),
        },
        "diet": {
            "diet_plan": st.session_state.get("diet_plan", ""),
            "calorie_goal": int(st.session_state.get("calorie_goal", 2000)),
            "calorie_log": list(st.session_state.get("calorie_log", []))[-30:],
            "tracker_entries": list(st.session_state.get("tracker_entries", []))[-100:],
            "meal_history": list(st.session_state.get("meal_history", []))[:12],
            "diet_plan_history": list(st.session_state.get("diet_plan_history", []))[:12],
            "grocery_history": list(st.session_state.get("grocery_history", []))[:12],
        },
        "gym": {
            "workout_plan_history": list(st.session_state.get("workout_plan_history", []))[:12],
        },
        "updated_at": now,
    }

    collection.update_one(
        {"_id": user_id},
        {"$set": payload, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return True


# ════════════════════════════════════════════════════════════════════
# Generic collection accessor (Phase 2+) — additive layer; the legacy
# single-document user state above is unchanged.
# ════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=4)
def _get_collection(collection_name: str):
    """Return a MongoDB collection handle by name (shared client)."""
    return _get_users_collection().database[collection_name]


def get_exercises_collection():
    """Return the shared exercise catalog collection (empty if unreachable)."""
    try:
        return _get_collection(EXERCISE_DB_COLLECTION)
    except Exception:
        return None


def get_exercise_images_bucket():
    """Return the GridFS bucket for exercise images (None if unreachable)."""
    try:
        client = _get_users_collection().database.client
        return GridFS(client[MONGODB_DB_NAME], collection=EXERCISE_IMAGES_BUCKET)
    except Exception:
        return None


def get_routines_collection():
    """Return the user routines collection (None if unreachable)."""
    try:
        return _get_collection(ROUTINES_COLLECTION)
    except Exception:
        return None


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def list_routines(user_id: str) -> list[dict]:
    """Return the user's routines, newest first."""
    coll = get_routines_collection()
    if coll is None:
        return []
    try:
        return list(coll.find({"user_id": user_id}).sort("updated_at", -1))
    except Exception:
        return []


def save_routine(user_id: str, routine: dict) -> str | None:
    """Create or update a routine; returns its id, or None if storage is down."""
    coll = get_routines_collection()
    if coll is None:
        return None
    now = _now_iso()
    doc = {
        "user_id": user_id,
        "name": (routine.get("name") or "Untitled routine").strip()[:80],
        "notes": (routine.get("notes") or "").strip()[:500],
        "days": routine.get("days") or [],
        "updated_at": now,
    }
    routine_id = routine.get("_id")
    if routine_id:
        result = coll.update_one(
            {"_id": routine_id, "user_id": user_id},
            {"$set": doc},
        )
        if result.matched_count == 0:
            return None
        return str(routine_id)
    doc["created_at"] = now
    result = coll.insert_one(doc)
    return str(result.inserted_id)


def delete_routine(user_id: str, routine_id) -> bool:
    """Delete one of the user's routines by id."""
    coll = get_routines_collection()
    if coll is None:
        return False
    from bson import ObjectId

    try:
        oid = ObjectId(str(routine_id))
    except Exception:
        return False
    result = coll.delete_one({"_id": oid, "user_id": user_id})
    return result.deleted_count > 0


def get_routine(user_id: str, routine_id):
    """Fetch one of the user's routines by id, or None."""
    coll = get_routines_collection()
    if coll is None:
        return None
    from bson import ObjectId

    try:
        oid = ObjectId(str(routine_id))
    except Exception:
        return None
    return coll.find_one({"_id": oid, "user_id": user_id})
