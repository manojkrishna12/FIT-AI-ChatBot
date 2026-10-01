"""
Progress — log workout sessions and see history, streaks and volume.

Sessions live in the `workout_sessions` collection, user-scoped. Logged
exercises can come from a saved Routine or be entered freely. Charts show
rolling streaks and per-session volume trends.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd
import streamlit as st

from m import page_header, section_header
from storage import (
    delete_routine,
    get_active_user_id,
    get_routine,
    get_routines_collection,
    list_routines,
)
from ui import empty_state, stat_row


# ────────────────────────────────────────────────────────────────────────────
# Session persistence (sessions collection)
# ────────────────────────────────────────────────────────────────────────────


def _sessions_collection():
    from constants import WORKOUT_SESSIONS_COLLECTION
    from storage import _get_collection

    try:
        return _get_collection(WORKOUT_SESSIONS_COLLECTION)
    except Exception:
        return None


def save_session(user_id: str, session: dict) -> str | None:
    coll = _sessions_collection()
    if coll is None:
        return None
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "user_id": user_id,
        "date": session.get("date") or date.today().isoformat(),
        "name": (session.get("name") or "Workout").strip()[:80],
        "routine_id": session.get("routine_id"),
        "exercises": session.get("exercises") or [],
        "notes": (session.get("notes") or "").strip()[:500],
        "created_at": now,
    }
    result = coll.insert_one(doc)
    return str(result.inserted_id)


def list_sessions(user_id: str, limit: int = 120) -> list[dict]:
    coll = _sessions_collection()
    if coll is None:
        return []
    try:
        return list(coll.find({"user_id": user_id}).sort("date", -1).limit(limit))
    except Exception:
        return []


def delete_session(user_id: str, session_id) -> bool:
    coll = _sessions_collection()
    if coll is None:
        return False
    from bson import ObjectId

    try:
        oid = ObjectId(str(session_id))
    except Exception:
        return False
    return coll.delete_one({"_id": oid, "user_id": user_id}).deleted_count > 0


def _parse_weight(value) -> float:
    """Best-effort numeric weight (kg); anything non-positive/invalid is 0."""
    try:
        weight = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return weight if weight > 0 else 0.0


def _session_volume(session: dict) -> float:
    """Sum training load per session.

    Per exercise: sets × reps, multiplied by recorded weight (kg) when the
    exercise carries one. Exercises without weight (bodyweight or unspecified
    — the legacy shape) count sets × reps only.
    """
    total = 0.0
    for exercise in session.get("exercises") or []:
        sets = float(exercise.get("sets") or 0)
        reps_raw = str(exercise.get("reps") or "0").split("-")[0]
        try:
            reps = float(reps_raw)
        except ValueError:
            reps = 0.0
        volume = sets * reps
        weight = _parse_weight(exercise.get("weight"))
        if weight > 0:
            volume *= weight
        total += volume
    return total


# ────────────────────────────────────────────────────────────────────────────
# Page sections
# ────────────────────────────────────────────────────────────────────────────


def _session_editor(default_name: str = "", preset: dict | None = None, key_prefix: str = "custom") -> dict | None:
    """Collect one workout session; returns the payload when submitted.

    ``key_prefix`` scopes the per-exercise widget keys to the logging mode
    (and routine), so switching modes or routines re-instantiates the rows
    with the new preset values instead of retaining stale widget state.
    """
    preset = preset or {"exercises": []}
    with st.form("log_session_form"):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Workout name", value=default_name or preset.get("name", ""))
            day = st.date_input("Date", value=date.today())
        with c2:
            notes = st.text_input("Notes (optional)", value=preset.get("notes", ""))

        exercises = preset.get("exercises") or [{"exercise_name": "", "sets": 3, "reps": "8-10", "rest": "90s"}]
        edited: list[dict] = []
        st.markdown("**Exercises**")
        for idx, exercise in enumerate(exercises):
            row = st.columns([4, 1, 1, 1, 1])
            with row[0]:
                ename = st.text_input("Exercise", value=exercise.get("exercise_name", ""), key=f"se_name_{key_prefix}_{idx}", label_visibility="collapsed")
            with row[1]:
                sets = st.number_input("Sets", 1, 30, int(exercise.get("sets") or 3), key=f"se_sets_{key_prefix}_{idx}", label_visibility="collapsed")
            with row[2]:
                reps = st.text_input("Reps", value=str(exercise.get("reps") or "8-10"), key=f"se_reps_{key_prefix}_{idx}", label_visibility="collapsed")
            with row[3]:
                rest = st.text_input("Rest", value=str(exercise.get("rest") or ""), key=f"se_rest_{key_prefix}_{idx}", label_visibility="collapsed")
            with row[4]:
                weight = st.number_input(
                    "Weight (kg)", 0.0, 1000.0,
                    value=float(_parse_weight(exercise.get("weight"))), step=2.5,
                    key=f"se_weight_{key_prefix}_{idx}", label_visibility="collapsed",
                )
            entry = {"exercise_name": ename.strip()[:80], "sets": int(sets), "reps": reps.strip()[:20], "rest": rest.strip()[:20]}
            if weight > 0:
                entry["weight"] = round(float(weight), 1)
            edited.append(entry)

        submitted = st.form_submit_button("Log workout", type="primary", use_container_width=True)

    if not submitted:
        return None
    clean = [e for e in edited if e["exercise_name"]]
    if not clean:
        st.warning("Add at least one exercise with a name.")
        return None
    return {"name": name, "date": day.isoformat(), "notes": notes, "exercises": clean}


def _render_logging() -> None:
    user_id = get_active_user_id()
    routines = list_routines(user_id)

    if not routines:
        session = _session_editor()
        if session:
            _save_and_toast(user_id, session)
        return

    mode = st.radio("Log from", ["Custom workout", "From a routine"], horizontal=True, key="log_mode")
    if mode == "From a routine":
        routine = st.selectbox(
            "Routine",
            routines,
            format_func=lambda r: r.get("name", "Untitled"),
            key="log_routine",
        )
        exercises = [
            {
                "exercise_id": ex.get("exercise_id"),
                "exercise_name": ex.get("exercise_name"),
                "sets": ex.get("sets"),
                "reps": ex.get("reps"),
                "rest": ex.get("rest"),
                "weight": ex.get("weight"),
            }
            for ex in (routine.get("days") or [{}])[0].get("exercises") or []
        ]
        if not exercises:
            st.info("That routine's Day 1 has no exercises — pick another routine or log a custom workout.")
        session = _session_editor(
            default_name=routine.get("name", ""),
            preset={"exercises": exercises},
            key_prefix=str(routine["_id"]),
        )
        if session:
            session["routine_id"] = str(routine["_id"])
            _save_and_toast(user_id, session)
    else:
        session = _session_editor()
        if session:
            _save_and_toast(user_id, session)


def _save_and_toast(user_id: str, session: dict) -> None:
    if save_session(user_id, session):
        st.toast("Workout logged.")
        st.rerun()
    else:
        st.error("Storage unavailable — the workout could not be logged. Check MongoDB.")


def _render_history(sessions: list[dict]) -> None:
    user_id = get_active_user_id()
    section_header("History")
    if not sessions:
        empty_state(
            "No workouts logged yet",
            "Log your first session above — history, volume and streaks build from here.",
        )
        return
    for session in sessions[:20]:
        date_str = session.get("date", "?")
        n_ex = len(session.get("exercises") or [])
        volume = _session_volume(session)
        with st.container(border=True):
            row = st.columns([4, 1.4, 1])
            with row[0]:
                st.markdown(f"**{session.get('name', 'Workout')}**")
                names = ", ".join(e.get("exercise_name", "?") for e in (session.get("exercises") or [])[:4])
                more = " …" if n_ex > 4 else ""
                st.caption(f"{date_str} · {n_ex} exercise{'s' if n_ex != 1 else ''} · {names}{more}")
            with row[1]:
                st.markdown(
                    f"<div class='stat-inline'><span class='stat-inline-label'>Volume</span>"
                    f"<span class='stat-inline-value'>{volume:.0f}</span></div>",
                    unsafe_allow_html=True,
                )
            with row[2]:
                if st.button("Delete", key=f"del_sess_{session['_id']}", use_container_width=True):
                    delete_session(user_id, session["_id"])
                    st.rerun()


def _render_charts(sessions: list[dict]) -> None:
    if not sessions:
        return

    # Summary block — real data only, rendered even for a single session.
    dates = sorted({s.get("date") for s in sessions if s.get("date")})
    best = current = 0
    prev = None
    from datetime import timedelta

    for d in dates:
        day = date.fromisoformat(d)
        current = current + 1 if (prev and (day - prev).days == 1) else 1
        best = max(best, current)
        prev = day
    today = date.today()
    last = date.fromisoformat(dates[-1]) if dates else None
    active = bool(last and 0 <= (today - last).days <= 1)
    total_volume = sum(_session_volume(s) for s in sessions)
    stat_row([
        {"label": "Sessions logged", "value": str(len(sessions))},
        {"label": "Current streak", "value": f"{current if active else 0}", "hint": "consecutive days"},
        {"label": "Longest streak", "value": f"{best}", "hint": "consecutive days"},
        {"label": "Total volume", "value": f"{total_volume:,.0f}", "hint": "sets × reps × load"},
    ])

    if len(sessions) < 2:
        return

    section_header("Trends")
    frame = pd.DataFrame(
        [
            {"date": s.get("date", ""), "volume": _session_volume(s), "exercises": len(s.get("exercises") or [])}
            for s in sessions
        ]
    ).sort_values("date")

    c1, c2 = st.columns(2)
    with c1:
        st.bar_chart(frame.set_index("date")["volume"], height=220)
        st.caption("Volume per session (sets × reps × load)")
    with c2:
        st.line_chart(frame.set_index("date")["exercises"], height=220)
        st.caption("Exercises per session")


def render_progress_page() -> None:
    """Entry point called by app.py for the Progress page."""
    page_header(
        "Progress",
        "Workout history, consistency and training volume",
    )

    user_id = get_active_user_id()
    sessions = list_sessions(user_id)
    _render_charts(sessions)

    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
    section_header("Log a workout")
    _render_logging()

    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
    _render_history(sessions)
