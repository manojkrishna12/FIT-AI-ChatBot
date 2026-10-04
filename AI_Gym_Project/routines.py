"""
Workouts — build, review and log multi-day workout routines.

Exercises are picked from the Exercise Library catalog (RepDB free tier,
seeded into MongoDB). Routines are stored per user in the `routines`
collection via the storage layer; storage.py is unchanged. The AI workout
planner is surfaced here (Training → Workouts) and reuses the existing
Gemini prompt from gym_trainer.

Saved routine documents stay backward compatible: pre-weight documents only
carry sets/reps/rest/weight, while per-set detail is additive (`set_rows`,
`note`) and the legacy summary fields are derived from it on save.
"""

from __future__ import annotations

import copy

import streamlit as st

from exercise_library import image_html
from m import page_header, section_header
from storage import (
    delete_routine,
    get_active_user_id,
    get_exercises_collection,
    get_routine,
    list_routines,
    save_routine,
)
from ui import empty_state


# ── Small helpers ────────────────────────────────────────────────────────────

def _display(label: str) -> str:
    return (label or "").replace("_", " ").title()


def _empty_day(index: int) -> dict:
    return {"day_name": f"Day {index + 1}", "exercises": []}


def _next_row_id() -> int:
    rid = int(st.session_state.get("_routine_row_seq", 0)) + 1
    st.session_state["_routine_row_seq"] = rid
    return rid


def _ensure_row_id(row: dict) -> int:
    """Stable widget identity for a builder row (day, exercise or set).

    Widgets are keyed by these ids rather than list positions, so removing a
    row never shifts another row's typed values.
    """
    rid = row.get("_rid")
    if not isinstance(rid, int):
        rid = _next_row_id()
        row["_rid"] = rid
    return rid


def _blank_set_row(reps: str = "10", weight: float = 0.0) -> dict:
    return {"_rid": _next_row_id(), "weight": float(weight or 0.0), "reps": str(reps or "")}


def _blank_exercise() -> dict:
    """A new exercise card: three empty sets, weight and reps editable."""
    return {
        "exercise_id": None,
        "exercise_name": "",
        "note": "",
        "rest": "90s",
        "set_rows": [_blank_set_row() for _ in range(3)],
    }


# ── Exercise catalog ─────────────────────────────────────────────────────────

def load_catalog() -> list[dict]:
    """Return the exercise catalog sorted by name (empty when unreachable)."""
    coll = get_exercises_collection()
    if coll is None:
        return []
    try:
        docs = list(
            coll.find(
                {},
                {"_id": 1, "name_en": 1, "body_part": 1, "equipment": 1, "images": 1},
            )
        )
    except Exception:
        return []
    docs.sort(key=lambda d: d.get("name_en", ""))
    return docs


def picker_label(doc: dict) -> str:
    """Picker label for one catalog doc: 'Name (Body Part)'."""
    name = doc.get("name_en", doc.get("_id", ""))
    bp = _display(doc.get("body_part", ""))
    return f"{name} ({bp})" if bp else name


def catalog_names(catalog: list[dict]) -> dict[str, str]:
    """Map exercise id → picker label for the loaded catalog."""
    return {d["_id"]: picker_label(d) for d in catalog}


def _first_image(doc: dict | None) -> str | None:
    images = (doc or {}).get("images") or {}
    return images.get("start") or images.get("peak") or images.get("main")


def _exercise_image(doc: dict | None) -> str:
    """Thumbnail markup for one exercise (GridFS image, URL fallback, label)."""
    return f'<div class="ex-thumb">{image_html(_first_image(doc))}</div>'


# ── Set rows: cleaning, summary fields and legacy expansion ──────────────────

def _clean_set_rows(raw) -> list[dict]:
    """Normalize builder set rows into the saved `set_rows` shape."""
    if not isinstance(raw, list):
        return []
    rows: list[dict] = []
    for row in raw[:40]:
        if not isinstance(row, dict):
            continue
        clean = {"reps": str(row.get("reps") or "").strip()[:20]}
        try:
            weight = float(row.get("weight") or 0)
        except (TypeError, ValueError):
            weight = 0.0
        if weight > 0:
            clean["weight"] = round(min(weight, 1000.0), 1)
        rows.append(clean)
    return rows


def _summary_reps(rows: list[dict]) -> str:
    """Summary reps for the legacy field: the lowest numeric value, else text."""
    numbers: list[float] = []
    first = ""
    for row in rows:
        value = str(row.get("reps") or "").strip()
        if value and not first:
            first = value
        try:
            numbers.append(float(value.split("-")[0]))
        except (TypeError, ValueError):
            continue
    if numbers:
        low = min(numbers)
        return str(int(low)) if float(low).is_integer() else f"{low:g}"
    return first[:20]


def _summary_weight(rows: list[dict]) -> float:
    """Working weight for the legacy field: the first positive set weight."""
    for row in rows:
        try:
            weight = float(row.get("weight") or 0)
        except (TypeError, ValueError):
            continue
        if weight > 0:
            return round(min(weight, 1000.0), 1)
    return 0.0


def _set_rows_for(exercise: dict) -> list[dict]:
    """Set rows for an exercise: stored detail, else derived from legacy fields.

    Pre-weight routine documents only carry sets/reps/weight, so they expand
    into one identical row per set and keep rendering unchanged.
    """
    rows = exercise.get("set_rows")
    if isinstance(rows, list) and rows:
        return [row for row in rows if isinstance(row, dict)]
    try:
        count = int(exercise.get("sets") or 0)
    except (TypeError, ValueError):
        count = 0
    if count <= 0:
        return []
    try:
        weight = float(exercise.get("weight") or 0)
    except (TypeError, ValueError):
        weight = 0.0
    weight = round(min(weight, 1000.0), 1) if weight > 0 else 0.0
    reps = str(exercise.get("reps") or "")
    return [{"weight": weight, "reps": reps} for _ in range(min(count, 40))]


def _clean_exercise(ex: dict) -> dict | None:
    """Normalize one builder exercise into its saved shape.

    Weight (kg) is optional: empty, zero or invalid values are omitted so
    pre-weight routines keep their exact document shape, and bodyweight
    exercises stay unweighted. When the builder has per-set rows they are
    stored as `set_rows` and the legacy summary fields (sets, reps, weight)
    are derived from them, keeping the weight-tracking schema working.
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
    rows = _clean_set_rows(ex.get("set_rows"))
    if rows:
        clean["set_rows"] = rows
        clean["sets"] = len(rows)
        reps = _summary_reps(rows)
        if reps:
            clean["reps"] = reps
        weight = _summary_weight(rows)
        if weight > 0:
            clean["weight"] = weight
    else:
        try:
            weight = float(ex.get("weight") or 0)
        except (TypeError, ValueError):
            weight = 0.0
        if weight > 0:
            clean["weight"] = round(min(weight, 1000.0), 1)
    note = str(ex.get("note") or "").strip()[:200]
    if note:
        clean["note"] = note
    return clean


def _weight_text(value) -> str:
    try:
        weight = float(value or 0)
    except (TypeError, ValueError):
        weight = 0.0
    return f"{weight:g} kg" if weight > 0 else '<span class="set-placeholder">—</span>'


def _sets_table(rows: list[dict]) -> str:
    """Read-only SET | WEIGHT | REPS table for the routine detail view."""
    body = []
    for index, row in enumerate(rows, 1):
        reps = str(row.get("reps") or "").strip() or '<span class="set-placeholder">—</span>'
        body.append(
            f'<tr><td class="set-index">{index}</td>'
            f"<td>{_weight_text(row.get('weight'))}</td><td>{reps}</td></tr>"
        )
    return (
        '<table class="set-table"><thead><tr>'
        '<th class="set-index">Set</th><th>Weight</th><th>Reps</th>'
        "</tr></thead><tbody>" + "".join(body) + "</tbody></table>"
    )


# ── Builder state ────────────────────────────────────────────────────────────

def _blank_builder() -> dict:
    return {"_id": None, "name": "", "notes": "", "days": [_empty_day(0)], "_ver": 0}


def _open_builder(routine: dict | None) -> None:
    """Seed the builder — a blank routine, or an existing one for editing."""
    ver = (st.session_state.get("routine_builder") or {}).get("_ver", 0) + 1
    if routine is None:
        builder = _blank_builder()
    else:
        days = copy.deepcopy(routine.get("days") or [_empty_day(0)]) or [_empty_day(0)]
        builder = {
            "_id": routine.get("_id"),
            "name": routine.get("name", ""),
            "notes": routine.get("notes", ""),
            "days": days,
        }
    builder["_ver"] = ver
    st.session_state["routine_builder"] = builder
    st.rerun()


def _open_detail(routine_id) -> None:
    st.session_state["routine_view_id"] = str(routine_id)
    st.session_state.pop("routine_builder", None)
    st.rerun()


def _close_builder() -> None:
    st.session_state.pop("routine_builder", None)
    st.rerun()


# ── Saved routines list ──────────────────────────────────────────────────────

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
            " pick exercises and set weight and reps for every set.",
        )
        return

    for routine in routines:
        n_days = len(routine.get("days") or [])
        n_ex = sum(len(day.get("exercises") or []) for day in routine.get("days") or [])
        updated = (routine.get("updated_at") or "")[:10]
        with st.container(border=True):
            top = st.columns([4, 1, 1, 1])
            with top[0]:
                st.markdown(f"**{routine.get('name', 'Untitled routine')}**")
                meta = [
                    f"{n_days} day{'s' if n_days != 1 else ''}",
                    f"{n_ex} exercise{'s' if n_ex != 1 else ''}",
                ]
                if updated:
                    meta.append(f"updated {updated}")
                st.caption(" · ".join(meta))
            with top[1]:
                if st.button("Open", type="primary", key=f"open_{routine['_id']}", use_container_width=True):
                    _open_detail(routine["_id"])
            with top[2]:
                if st.button("Edit", key=f"edit_{routine['_id']}", use_container_width=True):
                    _open_builder(routine)
            with top[3]:
                if st.button("Delete", key=f"del_{routine['_id']}", use_container_width=True):
                    delete_routine(user_id, routine["_id"])
                    st.toast("Routine deleted.")
                    st.rerun()


# ── Routine detail ───────────────────────────────────────────────────────────

def _render_exercise_detail(exercise: dict, doc: dict | None) -> None:
    rows = _set_rows_for(exercise)
    name = exercise.get("exercise_name") or (doc or {}).get("name_en") or "Exercise"
    with st.container(border=True):
        head = st.columns([0.7, 4])
        with head[0]:
            st.markdown(_exercise_image(doc), unsafe_allow_html=True)
        with head[1]:
            st.markdown(f"**{name}**")
            meta = []
            body_part = _display((doc or {}).get("body_part", ""))
            if body_part:
                meta.append(body_part)
            meta.append(f"{len(rows)} set{'s' if len(rows) != 1 else ''}")
            if exercise.get("rest"):
                meta.append(f"rest {exercise['rest']}")
            st.caption(" · ".join(meta))
            if exercise.get("note"):
                st.caption(f"Note: {exercise['note']}")
        if rows:
            st.markdown(_sets_table(rows), unsafe_allow_html=True)


def _render_detail(routine: dict, catalog_by_id: dict[str, dict]) -> None:
    user_id = get_active_user_id()
    st.button("← All workouts", key="routine_back", on_click=lambda: st.session_state.pop("routine_view_id", None))

    name = routine.get("name", "Untitled routine")
    notes = (routine.get("notes") or "").strip()
    section_header(name, notes or None)

    days = routine.get("days") or []
    n_ex = sum(len(day.get("exercises") or []) for day in days)
    updated = (routine.get("updated_at") or "")[:10]
    meta = [
        f"{len(days)} day{'s' if len(days) != 1 else ''}",
        f"{n_ex} exercise{'s' if n_ex != 1 else ''}",
    ]
    if updated:
        meta.append(f"updated {updated}")
    st.caption(" · ".join(meta))

    actions = st.columns([1, 1, 1, 3])
    with actions[0]:
        if st.button("Edit routine", type="primary", use_container_width=True, key="detail_edit"):
            _open_builder(routine)
    with actions[1]:
        if st.button("Log day 1", use_container_width=True, key="detail_log_first"):
            _start_logging(routine, 0)
    with actions[2]:
        if st.button("Delete", use_container_width=True, key="detail_delete"):
            delete_routine(user_id, routine["_id"])
            st.session_state.pop("routine_view_id", None)
            st.toast("Routine deleted.")
            st.rerun()

    if not days:
        empty_state("No training days", "Edit this routine to add exercises and sets.")
        return

    for day_index, day in enumerate(days):
        day_exercises = day.get("exercises") or []
        head = st.columns([4, 1])
        with head[0]:
            section_header(day.get("day_name") or f"Day {day_index + 1}")
        with head[1]:
            if st.button("Log this day", key=f"detail_log_{day_index}", use_container_width=True):
                _start_logging(routine, day_index)
        if not day_exercises:
            st.caption("No exercises on this day yet.")
            continue
        for exercise in day_exercises:
            doc = catalog_by_id.get(exercise.get("exercise_id"))
            _render_exercise_detail(exercise, doc)


def _start_logging(routine: dict, day_index: int) -> None:
    """Hand the routine day to the Progress logger and open it."""
    st.session_state["_log_routine_id"] = str(routine.get("_id"))
    st.session_state["_log_routine_day"] = int(day_index)
    st.session_state["_navigate_to"] = "Progress"
    st.rerun()


# ── Routine builder (Hevy-style exercise cards) ──────────────────────────────

def _render_exercise_card(
    exercise: dict,
    catalog_by_id: dict[str, dict],
    labels: dict[str, str],
    options: list[str],
    ver: int,
) -> bool:
    """Render one exercise card. Returns True when the user removed it."""
    ex_rid = _ensure_row_id(exercise)
    removed = False

    with st.container(border=True):
        head = st.columns([0.8, 3.6, 1])
        with head[0]:
            st.markdown(
                _exercise_image(catalog_by_id.get(exercise.get("exercise_id"))),
                unsafe_allow_html=True,
            )
        with head[1]:
            current_id = exercise.get("exercise_id")
            chosen = st.selectbox(
                "Exercise",
                options,
                format_func=lambda oid: labels.get(oid, "— choose an exercise —"),
                index=options.index(current_id) if current_id in options else 0,
                key=f"ex_pick_{ver}_{ex_rid}",
                label_visibility="collapsed",
            )
            exercise["exercise_id"] = chosen or None
            exercise["exercise_name"] = labels.get(chosen, "")
        with head[2]:
            if st.button("Remove", key=f"ex_del_{ver}_{ex_rid}", use_container_width=True):
                removed = True

        note_cols = st.columns([3, 1])
        with note_cols[0]:
            exercise["note"] = st.text_input(
                "Note (optional)",
                value=str(exercise.get("note") or ""),
                placeholder="e.g. pause at the bottom, slow eccentric",
                key=f"ex_note_{ver}_{ex_rid}",
            )
        with note_cols[1]:
            exercise["rest"] = st.text_input(
                "Rest between sets",
                value=str(exercise.get("rest") or ""),
                placeholder="90s",
                key=f"ex_rest_{ver}_{ex_rid}",
            )

        rows = exercise.get("set_rows")
        if not isinstance(rows, list) or not rows:
            rows = _set_rows_for(exercise)
            exercise["set_rows"] = rows
        if not rows:
            rows.append(_blank_set_row())

        head_row = st.columns([0.55, 1.6, 1.6, 0.55])
        for col, title in zip(head_row, ("Set", "Weight (kg)", "Reps", "")):
            col.markdown(f'<div class="set-col-head">{title}</div>', unsafe_allow_html=True)

        for set_index, row in enumerate(rows):
            row_rid = _ensure_row_id(row)
            cells = st.columns([0.55, 1.6, 1.6, 0.55])
            with cells[0]:
                st.markdown(f'<div class="set-index">{set_index + 1}</div>', unsafe_allow_html=True)
            with cells[1]:
                row["weight"] = st.number_input(
                    "Weight (kg)",
                    0.0,
                    1000.0,
                    value=float(row.get("weight") or 0.0),
                    step=2.5,
                    key=f"set_w_{ver}_{row_rid}",
                    label_visibility="collapsed",
                )
            with cells[2]:
                row["reps"] = st.text_input(
                    "Reps",
                    value=str(row.get("reps") or ""),
                    placeholder="10",
                    key=f"set_r_{ver}_{row_rid}",
                    label_visibility="collapsed",
                )
            with cells[3]:
                if st.button("✕", key=f"set_del_{ver}_{row_rid}", use_container_width=True):
                    rows.pop(set_index)
                    st.rerun()

        add_col, _ = st.columns([1, 3])
        with add_col:
            if st.button("+ Add Set", key=f"set_add_{ver}_{ex_rid}", use_container_width=True):
                last = rows[-1] if rows else {"weight": 0.0, "reps": "10"}
                rows.append(
                    _blank_set_row(
                        reps=str(last.get("reps") or "10"),
                        weight=float(last.get("weight") or 0.0),
                    )
                )
                st.rerun()

    return removed


def _render_builder(catalog: list[dict]) -> None:
    builder = st.session_state["routine_builder"]
    ver = builder.get("_ver", 0)

    st.button("← All workouts", key=f"rb_back_{ver}", on_click=_close_builder)
    section_header(
        "Routine builder",
        "Pick exercises from the library, then set weight and reps for every set.",
    )

    if not catalog:
        st.warning(
            "The exercise catalog is empty — seed the Exercise Library first "
            "(`python scripts/seed_exercises.py --source <dataset-dir>`). "
            "Routines cannot be built until the catalog is available."
        )
        return

    catalog_by_id = {d["_id"]: d for d in catalog}
    labels = catalog_names(catalog)
    options = [""] + list(labels.keys())

    c1, c2 = st.columns([1, 2])
    with c1:
        builder["name"] = st.text_input(
            "Routine name",
            value=builder.get("name", ""),
            placeholder="e.g. Push / Pull / Legs",
            key=f"rb_name_{ver}",
        )
    with c2:
        builder["notes"] = st.text_input(
            "Notes (optional)",
            value=builder.get("notes", ""),
            placeholder="Progression notes, tempo…",
            key=f"rb_notes_{ver}",
        )

    days = builder.setdefault("days", [])
    for day_index, day in enumerate(days):
        day_rid = _ensure_row_id(day)
        with st.container(border=True):
            head = st.columns([4, 1])
            with head[0]:
                day["day_name"] = st.text_input(
                    "Day name",
                    value=day.get("day_name", f"Day {day_index + 1}"),
                    key=f"day_name_{ver}_{day_rid}",
                    label_visibility="collapsed",
                )
            with head[1]:
                if st.button(
                    "Remove day",
                    key=f"day_del_{ver}_{day_rid}",
                    disabled=len(days) <= 1,
                    use_container_width=True,
                ):
                    days.pop(day_index)
                    st.rerun()

            exercises = day.setdefault("exercises", [])
            if not exercises:
                st.caption("No exercises yet — add one below.")

            for ex_index, exercise in enumerate(exercises):
                if _render_exercise_card(exercise, catalog_by_id, labels, options, ver):
                    exercises.pop(ex_index)
                    st.rerun()

            add_col, _ = st.columns([1, 3])
            with add_col:
                if st.button("Add exercise", key=f"ex_add_{ver}_{day_rid}", use_container_width=True):
                    exercises.append(_blank_exercise())
                    st.rerun()

    add_day_col, _ = st.columns([1, 3])
    with add_day_col:
        if st.button("Add day", key=f"day_add_{ver}", use_container_width=True):
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
                    {
                        "_id": builder.get("_id"),
                        "name": builder["name"],
                        "notes": builder.get("notes", ""),
                        "days": clean_days,
                    },
                )
                if routine_id:
                    st.session_state.pop("routine_builder", None)
                    st.session_state["routine_view_id"] = str(routine_id)
                    st.toast("Routine saved.")
                    st.rerun()
                else:
                    st.error("Storage unavailable — the routine could not be saved. Check MongoDB.")
    with action[1]:
        if st.button("Cancel", use_container_width=True, key=f"rb_cancel_{ver}"):
            _close_builder()


# ── AI workout planner (moved here from the AI Gym Trainer) ──────────────────

def _render_ai_planner() -> None:
    section_header(
        "AI Workout Planner",
        "Generate a workout plan based on goals, fitness level, equipment and training preferences.",
    )
    if not st.session_state.get("ai_planner_open"):
        create_col, _ = st.columns([1, 3])
        with create_col:
            if st.button("Create with AI", use_container_width=True, key="ai_planner_open_btn"):
                st.session_state["ai_planner_open"] = True
                st.rerun()
        return

    from gym_trainer import render_workout_planner  # lazy: keeps the pose stack out of this page

    render_workout_planner()


# ── Page entry point ─────────────────────────────────────────────────────────

def render_routines_page() -> None:
    """Entry point called by app.py for the Workouts page."""
    page_header(
        "Workouts",
        "Build, review and log your workout routines",
    )

    if "routine_builder" in st.session_state:
        _render_builder(load_catalog())
        return

    view_id = st.session_state.get("routine_view_id")
    if view_id:
        routine = get_routine(get_active_user_id(), view_id)
        if routine is not None:
            _render_detail(routine, {d["_id"]: d for d in load_catalog()})
            return
        st.session_state.pop("routine_view_id", None)

    _render_saved_list()
    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
    _render_ai_planner()
