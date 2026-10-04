"""
Progress — log workout sessions and see history, streaks and volume.

Sessions live in the `workout_sessions` collection, user-scoped. Logged
exercises are picked from the Exercise Library catalog (or a saved routine's
day). Charts show rolling streaks and per-session volume trends.
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


_LOG_ATTEMPT_KEY = "_workout_log_attempt"


def _log_attempt() -> int:
    """Current logging-form generation, bumped after every saved workout.

    Widget keys are namespaced by this value, so a new log always starts from
    its own defaults — the previous workout's name and exercise values are
    never carried over.
    """
    return int(st.session_state.get(_LOG_ATTEMPT_KEY, 0))


def _bump_log_attempt() -> None:
    st.session_state[_LOG_ATTEMPT_KEY] = _log_attempt() + 1


def _preset_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _routine_exercises(routine: dict, day_index: int = 0) -> list[dict]:
    """One routine day's exercises, mapped to the session preset shape."""
    days = routine.get("days") or []
    if not days:
        return []
    day_index = min(max(day_index, 0), len(days) - 1)
    return [
        {
            "exercise_id": ex.get("exercise_id"),
            "exercise_name": ex.get("exercise_name"),
            "sets": ex.get("sets"),
            "reps": ex.get("reps"),
            "rest": ex.get("rest"),
            "weight": ex.get("weight"),
        }
        for ex in days[day_index].get("exercises") or []
    ]


def _render_session_editor(
    *,
    default_name: str = "",
    preset_exercises: list[dict] | None = None,
    key_prefix: str = "custom",
    catalog: list[dict] | None = None,
    routine_id: str | None = None,
) -> None:
    """Log one workout: pick exercises from the library, then sets/reps/rest/weight.

    Every widget key is namespaced by the current logging attempt, so a fresh
    log starts clean (no previous workout name, no carried exercise values).
    """
    preset_exercises = preset_exercises or []
    catalog = catalog or []
    tag = f"{key_prefix}_{_log_attempt()}"

    labels: dict[str, str] = {}
    body_parts: dict[str, str] = {}
    option_ids: list[str] = []
    for doc in catalog:
        oid = doc.get("_id")
        labels[oid] = doc.get("name_en", oid)
        body_parts[oid] = (doc.get("body_part") or "").replace("_", " ").title()
        option_ids.append(oid)
    preset_by_id = {ex.get("exercise_id"): ex for ex in preset_exercises if ex.get("exercise_id")}
    for oid, ex in preset_by_id.items():
        if oid not in labels:
            # Routine references an exercise that is no longer in the catalog.
            labels[oid] = ex.get("exercise_name") or oid
            option_ids.append(oid)

    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input(
            "Workout name",
            value=default_name,
            placeholder="e.g. Push day",
            key=f"log_name_{tag}",
        )
    with c2:
        day = st.date_input("Date", value=date.today(), key=f"log_date_{tag}")
    notes = st.text_input(
        "Notes (optional)",
        value="",
        placeholder="How did it feel?",
        key=f"log_notes_{tag}",
    )

    ids_key = f"log_ids_{tag}"
    if ids_key not in st.session_state:
        st.session_state[ids_key] = list(preset_by_id.keys())

    if catalog:
        chosen_ids = st.multiselect(
            "Exercises",
            option_ids,
            format_func=lambda oid: labels.get(oid, oid),
            key=ids_key,
            placeholder="Search the exercise library — e.g. squat, curl, bench",
            help="Pick what you did today, then set sets, reps, rest and weight below.",
        )
    else:
        chosen_ids = list(st.session_state[ids_key])
        st.warning(
            "The exercise library is unavailable (check MongoDB) — exercises cannot be picked right now."
        )

    edited: list[dict] = []
    for oid in chosen_ids:
        preset = preset_by_id.get(oid, {})
        with st.container(border=True):
            head = st.columns([4, 1])
            with head[0]:
                st.markdown(f"**{labels.get(oid, oid)}**")
                if body_parts.get(oid):
                    st.caption(body_parts[oid])
            with head[1]:
                if st.button("Remove", key=f"log_del_{tag}_{oid}", use_container_width=True):
                    st.session_state[ids_key] = [x for x in st.session_state[ids_key] if x != oid]
                    st.rerun()

            cells = st.columns(4)
            with cells[0]:
                sets = st.number_input(
                    "Sets", 1, 30, _preset_int(preset.get("sets"), 3), key=f"log_sets_{tag}_{oid}"
                )
            with cells[1]:
                reps = st.text_input(
                    "Reps", value=str(preset.get("reps") or "10"), key=f"log_reps_{tag}_{oid}"
                )
            with cells[2]:
                rest = st.text_input(
                    "Rest", value=str(preset.get("rest") or "90s"), key=f"log_rest_{tag}_{oid}"
                )
            with cells[3]:
                weight = st.number_input(
                    "Weight (kg)",
                    0.0,
                    1000.0,
                    value=_parse_weight(preset.get("weight")),
                    step=2.5,
                    key=f"log_weight_{tag}_{oid}",
                )

        entry = {
            "exercise_id": oid,
            "exercise_name": labels.get(oid, oid),
            "sets": int(sets),
            "reps": reps.strip()[:20],
            "rest": rest.strip()[:20],
        }
        if weight > 0:
            entry["weight"] = round(float(weight), 1)
        edited.append(entry)

    if not chosen_ids:
        st.caption("No exercises selected yet — pick from the library above.")

    log_col, _ = st.columns([1, 3])
    with log_col:
        submitted = st.button(
            "Log workout", type="primary", use_container_width=True, key=f"log_submit_{tag}"
        )
    if not submitted:
        return

    clean = [entry for entry in edited if entry["exercise_name"]]
    if not clean:
        st.warning("Pick at least one exercise before logging.")
        return
    session = {"name": name, "date": day.isoformat(), "notes": notes, "exercises": clean}
    if routine_id:
        session["routine_id"] = routine_id
    _save_and_toast(get_active_user_id(), session)


def _render_logging() -> None:
    """Log a workout: a saved routine's day, or a custom session."""
    from routines import load_catalog

    user_id = get_active_user_id()
    routines = list_routines(user_id)
    catalog = load_catalog()

    pending_id = st.session_state.pop("_log_routine_id", None)
    pending_day = st.session_state.pop("_log_routine_day", None)
    if pending_id and routines:
        st.session_state["log_mode"] = "From a routine"

    if routines:
        mode = st.radio(
            "Log from", ["Custom workout", "From a routine"], horizontal=True, key="log_mode"
        )
    else:
        mode = "Custom workout"

    if mode == "From a routine" and routines:
        default_index = 0
        if pending_id:
            default_index = next(
                (i for i, r in enumerate(routines) if str(r.get("_id")) == str(pending_id)),
                0,
            )
            st.session_state.pop("log_routine", None)
        routine = st.selectbox(
            "Routine",
            routines,
            index=default_index,
            format_func=lambda r: r.get("name", "Untitled"),
            key="log_routine",
        )
        day_index = _preset_int(pending_day, 0) if pending_id else 0
        exercises = _routine_exercises(routine, day_index)
        if not exercises:
            st.info(
                "That routine day has no exercises — add some in Workouts, or log a custom workout."
            )
        _render_session_editor(
            default_name=routine.get("name", ""),
            preset_exercises=exercises,
            key_prefix=f"routine-{routine.get('_id')}",
            catalog=catalog,
            routine_id=str(routine.get("_id")),
        )
        return

    _render_session_editor(key_prefix="custom", catalog=catalog)


def _save_and_toast(user_id: str, session: dict) -> None:
    if save_session(user_id, session):
        _bump_log_attempt()  # the next log starts from a clean form
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
