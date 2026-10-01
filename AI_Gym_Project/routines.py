"""
Routines — build and manage multi-day workout routines.

Exercises are picked from the Exercise Library catalog (RepDB free tier,
seeded into MongoDB). Routines are stored per user in the `routines`
collection via the storage layer. Persistence logic is unchanged; this
module only presents it.
"""

from __future__ import annotations

import copy

import streamlit as st

from m import page_header, section_header
from storage import (
    delete_routine,
    get_active_user_id,
    get_exercises_collection,
    list_routines,
    save_routine,
)
from ui import empty_state


def _display(label: str) -> str:
    return (label or "").replace("_", " ").title()


def _empty_day(index: int) -> dict:
    return {"day_name": f"Day {index + 1}", "exercises": []}


def _clean_exercise(ex: dict) -> dict | None:
    """Normalize one builder exercise row into its saved shape.

    Weight (kg) is optional: empty, zero or invalid values are omitted so
    pre-weight routines keep their exact document shape, and bodyweight
    exercises stay unweighted by leaving the field at 0.
    """
    if not ex.get("exercise_id"):
        return None
    clean = {
        "exercise_id": ex.get("exercise_id"),
        "exercise_name": ex.get("exercise_name"),
        "sets": int(ex.get("sets") or 3),
        "reps": str(ex.get("reps") or "").strip()[:20],
        "rest": str(ex.get("rest") or "").strip()[:20],
    }
    try:
        weight = float(ex.get("weight") or 0)
    except (TypeError, ValueError):
        weight = 0.0
    if weight > 0:
        clean["weight"] = round(min(weight, 1000.0), 1)
    return clean


def _blank_builder() -> dict:
    return {"_id": None, "name": "", "notes": "", "days": [_empty_day(0)], "_ver": 0}


def _load_catalog() -> list[dict]:
    coll = get_exercises_collection()
    if coll is None:
        return []
    try:
        docs = list(
            coll.find(
                {},
                {"_id": 1, "name_en": 1, "body_part": 1, "equipment": 1},
            )
        )
    except Exception:
        return []
    docs.sort(key=lambda d: d.get("name_en", ""))
    return docs


def _picker_label(doc: dict) -> str:
    name = doc.get("name_en", doc.get("_id", ""))
    bp = _display(doc.get("body_part", ""))
    return f"{name} ({bp})" if bp else name


def _open_builder(routine: dict | None) -> None:
    """Seed the builder — a blank routine, or an existing one for editing."""
    ver = (st.session_state.get("routine_builder") or {}).get("_ver", 0) + 1
    if routine is None:
        builder = _blank_builder()
    else:
        builder = {
            "_id": routine.get("_id"),
            "name": routine.get("name", ""),
            "notes": routine.get("notes", ""),
            "days": copy.deepcopy(routine.get("days") or [_empty_day(0)]),
        }
        if not builder["days"]:
            builder["days"] = [_empty_day(0)]
    builder["_ver"] = ver
    st.session_state["routine_builder"] = builder
    st.rerun()


def _render_saved_list() -> None:
    user_id = get_active_user_id()
    routines = list_routines(user_id)

    list_head = st.columns([3, 1])
    with list_head[0]:
        section_header("Your workouts")
    with list_head[1]:
        if st.button("Create workout", type="primary", use_container_width=True, key="create_routine"):
            _open_builder(None)

    if not routines:
        empty_state(
            "No workouts yet",
            "Create a workout routine from the Exercise Library — structure training days,"
            " pick exercises and set sets, reps, rest and weight.",
        )
        return

    for routine in routines:
        n_days = len(routine.get("days") or [])
        n_ex = sum(len(day.get("exercises") or []) for day in routine.get("days") or [])
        updated = (routine.get("updated_at") or "")[:10]
        with st.container(border=True):
            top = st.columns([4, 1, 1])
            with top[0]:
                st.markdown(f"**{routine.get('name', 'Untitled routine')}**")
                meta = [f"{n_days} day{'s' if n_days != 1 else ''}", f"{n_ex} exercise{'s' if n_ex != 1 else ''}"]
                if updated:
                    meta.append(f"updated {updated}")
                st.caption(" · ".join(meta))
            with top[1]:
                if st.button("Edit", key=f"edit_{routine['_id']}", use_container_width=True):
                    _open_builder(routine)
            with top[2]:
                if st.button("Delete", key=f"del_{routine['_id']}", use_container_width=True):
                    delete_routine(user_id, routine["_id"])
                    st.toast("Routine deleted.")
                    st.rerun()


def _render_builder(catalog: list[dict]) -> None:
    builder = st.session_state["routine_builder"]
    ver = builder.get("_ver", 0)

    section_header("Routine builder")

    if not catalog:
        st.warning(
            "The exercise catalog is empty — seed the Exercise Library first "
            "(`python scripts/seed_exercises.py --source <dataset-dir>`). "
            "You can still structure days, but exercises cannot be picked."
        )

    c1, c2 = st.columns([1, 2])
    with c1:
        builder["name"] = st.text_input(
            "Routine name", value=builder.get("name", ""), placeholder="e.g. Upper/Lower 4-day",
            key=f"rb_name_{ver}",
        )
    with c2:
        builder["notes"] = st.text_input(
            "Notes (optional)", value=builder.get("notes", ""), placeholder="Progression notes, tempo…",
            key=f"rb_notes_{ver}",
        )

    days = builder.setdefault("days", [])
    for day_idx, day in enumerate(days):
        with st.container(border=True):
            head = st.columns([4, 1])
            with head[0]:
                day["day_name"] = st.text_input(
                    "Day name",
                    value=day.get("day_name", f"Day {day_idx + 1}"),
                    key=f"day_name_{ver}_{day_idx}",
                    label_visibility="collapsed",
                )
            with head[1]:
                if st.button("Remove day", key=f"day_del_{ver}_{day_idx}", disabled=len(days) <= 1, use_container_width=True):
                    days.pop(day_idx)
                    st.rerun()

            exercises = day.setdefault("exercises", [])
            if not exercises:
                st.caption("No exercises yet — add one below.")
            for ex_idx, exercise in enumerate(exercises):
                row = st.columns([4, 1, 1, 1, 1, 0.7])
                with row[0]:
                    labels = {d["_id"]: _picker_label(d) for d in catalog}
                    current_id = exercise.get("exercise_id")
                    options = [""] + list(labels.keys())
                    chosen = st.selectbox(
                        "Exercise",
                        options,
                        format_func=lambda oid: labels.get(oid, "— choose an exercise —"),
                        index=options.index(current_id) if current_id in options else 0,
                        key=f"ex_pick_{ver}_{day_idx}_{ex_idx}",
                        label_visibility="collapsed",
                    )
                    exercise["exercise_id"] = chosen or None
                    exercise["exercise_name"] = labels.get(chosen, exercise.get("exercise_name", ""))
                with row[1]:
                    exercise["sets"] = st.number_input(
                        "Sets", 1, 20,
                        value=int(exercise.get("sets") or 3),
                        key=f"ex_sets_{ver}_{day_idx}_{ex_idx}",
                        label_visibility="collapsed",
                    )
                with row[2]:
                    exercise["reps"] = st.text_input(
                        "Reps", value=str(exercise.get("reps") or "8-10"),
                        key=f"ex_reps_{ver}_{day_idx}_{ex_idx}",
                        label_visibility="collapsed",
                    )
                with row[3]:
                    exercise["rest"] = st.text_input(
                        "Rest", value=str(exercise.get("rest") or "90s"),
                        key=f"ex_rest_{ver}_{day_idx}_{ex_idx}",
                        label_visibility="collapsed",
                    )
                with row[4]:
                    exercise["weight"] = st.number_input(
                        "Weight (kg)", 0.0, 1000.0,
                        value=float(exercise.get("weight") or 0.0), step=2.5,
                        key=f"ex_weight_{ver}_{day_idx}_{ex_idx}",
                        label_visibility="collapsed",
                    )
                with row[5]:
                    if st.button("✕", key=f"ex_del_{ver}_{day_idx}_{ex_idx}", use_container_width=True):
                        exercises.pop(ex_idx)
                        st.rerun()

            bcol1, bcol2, _ = st.columns([1, 1, 2])
            with bcol1:
                if st.button("Add exercise", key=f"ex_add_{ver}_{day_idx}"):
                    exercises.append({"exercise_id": None, "exercise_name": "", "sets": 3, "reps": "8-10", "rest": "90s", "weight": 0.0})
                    st.rerun()
            with bcol2:
                if st.button("Add day", key=f"day_add_{ver}_{day_idx}"):
                    days.append(_empty_day(len(days)))
                    st.rerun()

    action = st.columns([1, 1, 2])
    with action[0]:
        if st.button("Save routine", type="primary", use_container_width=True, key=f"rb_save_{ver}"):
            clean_days = [
                {
                    "day_name": (day.get("day_name") or f"Day {i + 1}").strip()[:60],
                    "exercises": [
                        cleaned
                        for ex in day.get("exercises") or []
                        if (cleaned := _clean_exercise(ex)) is not None
                    ],
                }
                for i, day in enumerate(days)
            ]
            if not (builder.get("name") or "").strip():
                st.warning("Give your routine a name first.")
            elif not any(day["exercises"] for day in clean_days):
                st.warning("Add at least one exercise (with an exercise selected) before saving.")
            else:
                routine_id = save_routine(
                    get_active_user_id(),
                    {"_id": builder.get("_id"), "name": builder["name"], "notes": builder.get("notes", ""), "days": clean_days},
                )
                if routine_id:
                    st.session_state.pop("routine_builder", None)
                    st.toast("Routine saved.")
                    st.rerun()
                else:
                    st.error("Storage unavailable — the routine could not be saved. Check MongoDB.")
    with action[1]:
        if st.button("Cancel", use_container_width=True, key=f"rb_cancel_{ver}"):
            st.session_state.pop("routine_builder", None)
            st.rerun()


def render_routines_page() -> None:
    """Entry point called by app.py for the Workouts/Routines page."""
    page_header(
        "Workouts",
        "Build and manage multi-day workout routines",
    )

    _render_saved_list()
    if "routine_builder" in st.session_state:
        st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
        catalog = _load_catalog()
        _render_builder(catalog)
