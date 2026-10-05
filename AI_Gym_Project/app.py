"""
Main Streamlit entrypoint for FIT-AI.

Phase 1: professional light UI — a minimal two-level navigation (eight main
sidebar sections; Training and Nutrition open a segmented sub-navigation in
the content area) and a clean home dashboard. All backend logic (Gemini,
MongoDB, auth, trainer, diet) is untouched; pages are dispatched from the
labels below via their canonical targets.
"""

from __future__ import annotations

from datetime import date, datetime

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from m import inject_custom_css
from storage import ensure_user_state_loaded
from ui import page_header, section_header, section_tabs, stat_row

st.set_page_config(
    page_title="FIT-AI",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Navigation model ──────────────────────────────────────────────────────────
# The sidebar shows eight main sections. Training and Nutrition open a
# segmented control with their feature pages; every other section is a direct
# page (Coach IS Gym Buddy — no submenu). ROUTES maps every visible label to
# its canonical dispatch target; internal target strings are stable.

PAGE_HOME = "Home"
PAGE_TRAINING = "Training"
PAGE_NUTRITION = "Nutrition"
PAGE_PROGRESS = "Progress"
PAGE_COACH = "Coach"
PAGE_PROFILE = "Profile"
PAGE_SETTINGS = "Settings"
PAGE_ABOUT = "About"

PAGE_WORKOUTS = "Workouts"  # displayed name; canonical route stays "routines"
PAGE_EXERCISE_LIBRARY = "Exercise Library"
PAGE_TRAINER = "AI Gym Trainer"

PAGE_DIET = "Diet Coach"
PAGE_MEAL_ANALYSER = "Meal Analyser"
PAGE_CALORIE_TRACKER = "Calorie Tracker"

MAIN_NAV: list[str] = [
    PAGE_HOME,
    PAGE_TRAINING,
    PAGE_NUTRITION,
    PAGE_PROGRESS,
    PAGE_COACH,
    PAGE_PROFILE,
    PAGE_SETTINGS,
    PAGE_ABOUT,
]

# Feature pages per section, rendered with the shared section_tabs component.
SECTION_PAGES: dict[str, list[str]] = {
    PAGE_TRAINING: [PAGE_WORKOUTS, PAGE_EXERCISE_LIBRARY, PAGE_TRAINER],
    PAGE_NUTRITION: [PAGE_DIET, PAGE_MEAL_ANALYSER, PAGE_CALORIE_TRACKER],
}

ROUTES: dict[str, str] = {
    PAGE_HOME: "home",
    PAGE_TRAINING: "training",
    PAGE_NUTRITION: "nutrition",
    PAGE_PROGRESS: "progress",
    PAGE_COACH: "buddy",  # direct page — selecting Coach opens Gym Buddy
    PAGE_PROFILE: "profile",
    PAGE_SETTINGS: "settings",
    PAGE_ABOUT: "about",
    PAGE_WORKOUTS: "routines",
    PAGE_EXERCISE_LIBRARY: "exercise_library",
    PAGE_TRAINER: "trainer",
    PAGE_DIET: "diet",
    PAGE_MEAL_ANALYSER: "meal_analyser",
    PAGE_CALORIE_TRACKER: "calorie_tracker",
}


def _navigate(page: str) -> None:
    """Request a page switch; consumed by the sidebar before widgets render."""
    st.session_state["_navigate_to"] = page
    st.rerun()


def _parent_section(label: str) -> str | None:
    """Return the main section that owns a subsection label, if any."""
    for section, pages in SECTION_PAGES.items():
        if label in pages:
            return section
    return None


# ── Home dashboard ────────────────────────────────────────────────────────────

def _greeting_name() -> str:
    """Display name for the greeting: account name, else the active user id."""
    try:
        from auth import get_account_display_name, is_authenticated

        if is_authenticated():
            name = (get_account_display_name() or "").strip()
            if name:
                return name
    except Exception:
        pass
    user_id = (st.session_state.get("active_user_id") or "").strip()
    return "" if user_id in ("", "guest") else user_id


def _workouts_this_week() -> int | None:
    """Count logged Progress sessions in the last 7 days (real data only)."""
    try:
        from progress import list_sessions

        user_id = st.session_state.get("active_user_id") or "guest"
        sessions = list_sessions(user_id)
    except Exception:
        return None
    today = date.today()
    count = 0
    for session in sessions:
        raw = str(session.get("date") or "")[:10]
        try:
            day = date.fromisoformat(raw)
        except ValueError:
            continue
        delta = (today - day).days
        if 0 <= delta <= 6:
            count += 1
    return count


def _calories_logged() -> float | None:
    """Sum the calorie tracker log for the active user (real data only)."""
    entries = st.session_state.get("tracker_entries") or []
    total = 0.0
    for entry in entries:
        try:
            total += float(entry.get("Calories") or 0)
        except (TypeError, ValueError):
            continue
    return total


def render_home() -> None:
    """Clean home dashboard: greeting, primary actions, real stats, quick access."""
    hour = datetime.now().hour
    part = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
    name = _greeting_name()
    page_header(f"Good {part}, {name}" if name else f"Good {part}")

    st.markdown('<div style="height:0.45rem"></div>', unsafe_allow_html=True)

    action_col, meal_col, _ = st.columns([1, 1, 2.4], gap="small")
    with action_col:
        if st.button("Start Workout", type="primary", use_container_width=True, key="home_start_workout"):
            _navigate(PAGE_WORKOUTS)
    with meal_col:
        if st.button("Log Meal", use_container_width=True, key="home_log_meal"):
            _navigate(PAGE_MEAL_ANALYSER)

    week = _workouts_this_week()
    calories = _calories_logged()
    goal = st.session_state.get("calorie_goal", 2000)
    streak = st.session_state.get("streak_days", 0)
    stat_row(
        [
            {"label": "Workouts this week", "value": str(week) if week is not None else "—"},
            {
                "label": "Calories logged",
                "value": f"{int(calories):,}" if calories is not None else "—",
                "hint": f"Goal {int(goal):,} kcal",
            },
            {"label": "Streak", "value": str(int(streak or 0)), "hint": "days"},
        ]
    )

    section_header("Quick access")
    quick_items = [
        (PAGE_TRAINER, "AI Gym Trainer"),
        (PAGE_EXERCISE_LIBRARY, "Exercise Library"),
        (PAGE_WORKOUTS, "Workouts"),
        (PAGE_DIET, "Diet Coach"),
        (PAGE_CALORIE_TRACKER, "Calorie Tracker"),
        (PAGE_COACH, "Gym Buddy"),
    ]
    for start in (0, 3):
        cols = st.columns(3, gap="small")
        for col, (page, label) in zip(cols, quick_items[start : start + 3]):
            with col:
                if st.button(label, key=f"home_qa_{page}", use_container_width=True):
                    _navigate(page)


# ── Sidebar ───────────────────────────────────────────────────────────────────

def build_sidebar() -> str:
    """Render the minimal sidebar and return the selected main section.

    Cross-page links request a destination via `_navigate`; subsection labels
    resolve to their parent section plus the matching sub-navigation state.
    Per-user identity lives in auth/Profile (and is displayed in Settings),
    so the navigation carries no user ID or status content.
    """
    with st.sidebar:
        st.markdown('<div class="brand"><span class="brand-name">FIT-AI</span></div>', unsafe_allow_html=True)

        pending = st.session_state.pop("_navigate_to", None)
        if pending:
            parent = _parent_section(pending)
            if parent:
                st.session_state["nav_page"] = parent
                st.session_state[f"section_tabs_{parent}"] = pending
            elif pending in MAIN_NAV:
                st.session_state["nav_page"] = pending

        # A stale selection (e.g. from an older label set) resolves to Home.
        if st.session_state.get("nav_page") not in MAIN_NAV:
            st.session_state["nav_page"] = PAGE_HOME

        page = st.radio(
            "Navigation",
            options=MAIN_NAV,
            key="nav_page",
            label_visibility="collapsed",
        )

    return page


# ── Dispatch ──────────────────────────────────────────────────────────────────

def _render_section(section: str) -> None:
    """Render a section's sub-navigation and dispatch the chosen feature page.

    Selection persists per section; an unknown/stale selection falls back to
    the section's first page (Training -> Workouts, Nutrition -> Diet Coach).
    """
    pages = SECTION_PAGES[section]
    state_key = f"section_tabs_{section}"
    if st.session_state.get(state_key) not in pages:
        st.session_state[state_key] = pages[0]
    subsection = section_tabs(pages, key=section, default=pages[0])
    _dispatch(ROUTES.get(subsection, "home"))


def _dispatch(target: str) -> None:
    """Render the page for a canonical target string."""
    if target == "trainer":
        from gym_trainer import render_gym_trainer_page

        render_gym_trainer_page()
    elif target == "diet":
        from diet import render_diet_page

        render_diet_page()
    elif target == "buddy":
        from habit_tracker import render_gym_buddy_page

        render_gym_buddy_page()
    elif target == "exercise_library":
        from exercise_library import render_exercise_library_page

        render_exercise_library_page()
    elif target == "routines":
        from routines import render_routines_page

        render_routines_page()
    elif target == "meal_analyser":
        from nutrition import render_meal_analyser_page

        render_meal_analyser_page()
    elif target == "calorie_tracker":
        from nutrition import render_calorie_tracker_page

        render_calorie_tracker_page()
    elif target == "progress":
        from progress import render_progress_page

        render_progress_page()
    elif target == "profile":
        from profile_page import render_profile_page

        render_profile_page()
    elif target == "settings":
        from settings_page import render_settings_page

        render_settings_page()
    elif target == "about":
        from about import render_about_page

        render_about_page()


def main() -> None:
    """Run the application."""
    inject_custom_css()

    # Authentication gate — nothing from the main app (sidebar, Home,
    # features) renders before a session exists. A valid browser session
    # cookie restores the previous sign-in after a page reload.
    from auth import is_authenticated, restore_session
    from auth_screen import render_auth_screen

    if not is_authenticated():
        restore_session()
    if not is_authenticated():
        render_auth_screen()
        return

    page = build_sidebar()
    ensure_user_state_loaded()

    target = ROUTES.get(page, "home")
    if target == "home":
        render_home()
    elif target == "training":
        _render_section(PAGE_TRAINING)
    elif target == "nutrition":
        _render_section(PAGE_NUTRITION)
    else:
        _dispatch(target)


if __name__ == "__main__":
    main()
