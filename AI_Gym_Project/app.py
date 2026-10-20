"""
Main Streamlit entrypoint for FIT-AI.

Reference-driven dashboard: a grouped navigation sidebar (HOME / TRAINING /
NUTRITION / PROGRESS / COACH + account pages) and a Home dashboard rebuilt to
the approved layout — greeting, two primary actions, a compact statistics bar,
a two-column main/side grid, and a restrained banner. All backend logic
(Gemini, MongoDB, auth, trainer, diet, RAG) is untouched; pages are
dispatched from the labels below via their canonical targets.
"""

from __future__ import annotations

from datetime import date, datetime

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from m import inject_custom_css
from storage import ensure_user_state_loaded
from ui import (
    activity_list,
    brand_block,
    feature_tile,
    gap,
    goal_list,
    home_hero,
    home_today,
    icon,
    nav_group_label,
    nav_group_separator,
    panel_header,
    sidebar_user_profile,
    stat_strip,
)

st.set_page_config(
    page_title="FIT-AI",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Navigation model ──────────────────────────────────────────────────────────
# One flat, grouped nav list. Every visible label owns exactly one canonical
# dispatch target; the group headings are presentation only.

PAGE_HOME = "Home"
PAGE_WORKOUTS = "Workouts"
PAGE_EXERCISE_LIBRARY = "Exercise Library"
PAGE_TRAINER = "AI Gym Trainer"
PAGE_DIET = "Diet Coach"
PAGE_MEAL_ANALYSER = "Meal Analyser"
PAGE_CALORIE_TRACKER = "Calorie Tracker"
PAGE_PROGRESS = "Progress"
PAGE_COACH = "Gym Buddy"
PAGE_PROFILE = "Profile"
PAGE_SETTINGS = "Settings"
PAGE_ABOUT = "About"

# (group label, items) — group labels are shown as small uppercase captions.
NAV_GROUPS: list[tuple[str, list[str]]] = [
    ("Home", [PAGE_HOME]),
    ("Training", [PAGE_WORKOUTS, PAGE_EXERCISE_LIBRARY, PAGE_TRAINER]),
    ("Nutrition", [PAGE_DIET, PAGE_MEAL_ANALYSER, PAGE_CALORIE_TRACKER]),
    ("Progress", [PAGE_PROGRESS]),
    ("Coach", [PAGE_COACH]),
]

# Account pages sit at the bottom, below a hairline, with no group label.
NAV_ACCOUNT: list[str] = [PAGE_PROFILE, PAGE_SETTINGS, PAGE_ABOUT]

# Every visible label (main + account) in display order.
MAIN_NAV: list[str] = [page for _, pages in NAV_GROUPS for page in pages]
ALL_NAV: list[str] = MAIN_NAV + NAV_ACCOUNT

ROUTES: dict[str, str] = {
    PAGE_HOME: "home",
    PAGE_WORKOUTS: "routines",
    PAGE_EXERCISE_LIBRARY: "exercise_library",
    PAGE_TRAINER: "trainer",
    PAGE_DIET: "diet",
    PAGE_MEAL_ANALYSER: "meal_analyser",
    PAGE_CALORIE_TRACKER: "calorie_tracker",
    PAGE_PROGRESS: "progress",
    PAGE_COACH: "buddy",
    PAGE_PROFILE: "profile",
    PAGE_SETTINGS: "settings",
    PAGE_ABOUT: "about",
}


def _navigate(page: str) -> None:
    """Request a page switch; consumed by the sidebar before widgets render."""
    st.session_state["_navigate_to"] = page
    st.rerun()


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


def _workout_sessions() -> list[dict]:
    """Logged Progress sessions for the active user (real data only)."""
    try:
        from progress import list_sessions

        user_id = st.session_state.get("active_user_id") or "guest"
        return list_sessions(user_id)
    except Exception:
        return []


def _workouts_this_week(sessions: list[dict] | None = None) -> int:
    """Count logged sessions in the last 7 days (real data only)."""
    sessions = _workout_sessions() if sessions is None else sessions
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


def _workouts_last_week(sessions: list[dict] | None = None) -> int:
    """Count logged sessions in the previous 7-day window (days 7–13 ago)."""
    sessions = _workout_sessions() if sessions is None else sessions
    today = date.today()
    count = 0
    for session in sessions:
        raw = str(session.get("date") or "")[:10]
        try:
            day = date.fromisoformat(raw)
        except ValueError:
            continue
        delta = (today - day).days
        if 7 <= delta <= 13:
            count += 1
    return count


def _workout_delta_hint(this_week: int, last_week: int) -> str:
    """Honest week-over-week wording — no invented numbers."""
    if this_week == 0 and last_week == 0:
        return "last 7 days"
    if last_week == 0:
        return f"↗ +{this_week} vs last week"
    diff = this_week - last_week
    if diff > 0:
        return f"↗ +{diff} vs last week"
    if diff < 0:
        return f"↘ −{abs(diff)} vs last week"
    return "→ same as last week"


@st.cache_data(ttl=300, show_spinner=False)
def _exercise_count() -> int:
    """Real size of the Exercise Library catalog (0 when unavailable)."""
    try:
        from storage import get_exercises_collection

        coll = get_exercises_collection()
        return int(coll.count_documents({})) if coll is not None else 0
    except Exception:
        return 0


def _today_checklist() -> list[dict]:
    """Today's status rows derived strictly from stored/derived state."""
    today_iso = date.today().isoformat()
    workout_done = any(str(s.get("date") or "")[:10] == today_iso for s in _workout_sessions())
    meals_done = any(
        (e.get("date") in (None, "", today_iso))
        for e in (st.session_state.get("tracker_entries") or [])
    )
    checkin_done = bool(st.session_state.get("checkin_done_today"))
    goal_set = bool(st.session_state.get("calorie_goal_manual")) or bool(
        st.session_state.get("calorie_goal_auto")
    )
    streak = int(st.session_state.get("streak_days") or 0)
    return [
        {"label": "Complete today's workout", "done": workout_done},
        {"label": "Log your meals", "done": meals_done},
        {"label": "Daily check-in", "done": checkin_done},
        {
            "label": "Set your calorie goal",
            "done": goal_set,
            "hint": f"{streak}-day streak" if streak else "",
        },
    ]


def _calories_logged() -> float:
    """Sum today's calorie tracker log for the active user (real data only).

    Day-separated like the tracker page: entries from other days don't
    count toward today's total; undated legacy entries still do.
    """
    entries = st.session_state.get("tracker_entries") or []
    today_iso = date.today().isoformat()
    total = 0.0
    for entry in entries:
        if entry.get("date") not in (None, "", today_iso):
            continue
        try:
            total += float(entry.get("Calories") or 0)
        except (TypeError, ValueError):
            continue
    return total


def _relative_day(iso_text: str) -> str:
    """'2 days ago' style label from an ISO date/datetime string."""
    raw = (iso_text or "")[:10]
    try:
        day = date.fromisoformat(raw)
    except ValueError:
        return ""
    delta = (date.today() - day).days
    if delta <= 0:
        return "today"
    if delta == 1:
        return "yesterday"
    if delta < 7:
        return f"{delta} days ago"
    if delta < 14:
        return "last week"
    if delta < 60:
        return f"{delta // 7} weeks ago"
    return f"{delta // 30} months ago"


def _recent_activity(limit: int = 5) -> list[dict]:
    """Recent activity built only from real, stored records."""
    items: list[tuple[str, dict]] = []  # (sortable timestamp, row)

    for session in _workout_sessions()[:6]:
        stamp = str(session.get("date") or session.get("created_at") or "")
        name = (session.get("name") or "Workout").strip()
        exercises = session.get("exercises") or []
        detail = f"{len(exercises)} exercise{'s' if len(exercises) != 1 else ''}"
        items.append((stamp, {
            "title": name,
            "sub": f"{_relative_day(stamp).capitalize() or 'Logged'} · {detail}",
            "icon": "workout",
        }))

    for entry in reversed(list(st.session_state.get("tracker_entries") or [])[:4]):
        meal = (entry.get("Meal") or "Meal").strip()
        calories = entry.get("Calories")
        detail = f"{int(calories):,} kcal" if str(calories or "").strip() else "logged"
        items.append((datetime.now().isoformat(), {
            "title": meal,
            "sub": f"Logged meal · {detail}",
            "icon": "diet",
        }))

    for plan in list(st.session_state.get("workout_plan_history") or [])[:3]:
        stamp = str(plan.get("created_at") or "")
        goal = (plan.get("goal") or "Workout plan").strip()
        items.append((stamp, {
            "title": f"{goal} plan",
            "sub": f"Generated with AI · {_relative_day(stamp) or 'recent'}",
            "icon": "trainer",
        }))

    items.sort(key=lambda pair: pair[0], reverse=True)
    return [row for _, row in items[:limit]]


def _current_plan() -> dict | None:
    """The user's most recently updated saved routine, plus last-trained info."""
    try:
        from storage import get_active_user_id, list_routines

        routines = list_routines(get_active_user_id())
    except Exception:
        return None
    if not routines:
        return None

    routine = routines[0]
    days = routine.get("days") or []
    exercises = sum(len(day.get("exercises") or []) for day in days)

    # Last trained date for this routine's logged sessions (real data only).
    trained = ""
    for session in _workout_sessions():
        if str(session.get("routine_id") or "") == str(routine.get("_id") or ""):
            trained = str(session.get("date") or "")
            break

    # Extract target muscles for a concise subtitle (e.g. Chest • Shoulders • Triceps)
    muscles: list[str] = []
    try:
        from routines import load_catalog
        catalog = {doc["_id"]: doc for doc in load_catalog()}
        for day in days:
            for ex in day.get("exercises") or []:
                doc = catalog.get(ex.get("exercise_id"))
                if doc and doc.get("target_muscle"):
                    m = str(doc["target_muscle"]).strip().capitalize()
                    if m and m not in muscles:
                        muscles.append(m)
    except Exception:
        pass
    muscle_line = " • ".join(muscles[:3]) if muscles else "Full Body"

    return {
        "name": routine.get("name") or "Untitled routine",
        "days": len(days),
        "exercises": exercises,
        "muscles": muscle_line,
        "updated": routine.get("updated_at") or "",
        "trained": trained,
        "routine_id": str(routine.get("_id") or ""),
    }


def _plan_image_html(plan: dict) -> str:
    """Thumbnail for the current plan's first exercise (own library data)."""
    try:
        from exercise_library import image_html
        from routines import _first_image, load_catalog

        catalog = {doc["_id"]: doc for doc in load_catalog()}
        from storage import get_active_user_id, get_routine

        routine = get_routine(get_active_user_id(), plan.get("routine_id"))
        for day in (routine or {}).get("days") or []:
            for exercise in day.get("exercises") or []:
                doc = catalog.get(exercise.get("exercise_id"))
                media = _first_image(doc)
                if media:
                    return image_html(media)
    except Exception:
        pass
    return '<div class="media-fallback">No image</div>'


def _render_user_chip(display_name: str) -> None:
    """Topbar account chip (avatar initial + name) -> Profile. Fully clickable."""
    initial = (display_name[:1] or "U").upper()
    st.markdown(
        '<div class="topbar-user-wrapper"><div class="topbar-user">'
        f'<div class="topbar-avatar">{initial}</div>'
        f'<div class="topbar-user-name">{display_name}</div>'
        f'<div class="topbar-chevron">{icon("chevron-down")}</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )
    st.button(display_name or "Profile", key="home_user_chip", on_click=lambda: _navigate(PAGE_PROFILE))


def render_home() -> None:
    """Home dashboard: hero, real stats, shortcuts, today, activity, goals."""
    hour = datetime.now().hour
    part = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
    name = _greeting_name()
    greeting = f"Good {part},{f' {name}' if name else ''}"

    # Top bar: search left, notifications + account chip right
    bar = st.columns([2.6, 0.16, 0.95], gap="small")
    with bar[0]:
        st.markdown('<div class="search-wrap">', unsafe_allow_html=True)
        st.text_input(
            "Search",
            key="home_search",
            label_visibility="collapsed",
            placeholder="Search workouts, exercises, meals, or ask anything…",
        )
        st.markdown('</div>', unsafe_allow_html=True)
    with bar[1]:
        _notifications()
    with bar[2]:
        _render_user_chip(name or "Profile")

    # Hero welcome card with primary quick actions
    with st.container(border=True):
        home_hero(
            greeting,
            "Consistency today builds a stronger tomorrow.",
            "Small steps every day make big results.",
        )
        hero_cols = st.columns([1, 1, 2.4], gap="small")
        with hero_cols[0]:
            st.button(
                "Start Workout",
                key="home_start_workout",
                type="primary",
                use_container_width=True,
                on_click=lambda: _navigate(PAGE_WORKOUTS),
            )
        with hero_cols[1]:
            st.button(
                "View Plan",
                key="home_view_plan",
                use_container_width=True,
                on_click=lambda: _navigate(PAGE_WORKOUTS),
            )

    # Statistics row (real data only)
    sessions = _workout_sessions()
    week = _workouts_this_week(sessions)
    last_week = _workouts_last_week(sessions)
    calories = _calories_logged()
    goal = int(st.session_state.get("calorie_goal") or 2000)
    streak = int(st.session_state.get("streak_days") or 0)
    stat_strip([
        {
            "label": "Workouts this week",
            "value": str(week),
            "icon": "workout",
            "tone": "green",
            "hint": _workout_delta_hint(week, last_week),
        },
        {
            "label": "Calories logged",
            "value": f"{int(calories):,}",
            "icon": "flame",
            "tone": "amber",
            "hint": f"Goal {goal:,} kcal",
            "progress": (calories / goal) if goal > 0 else 0,
        },
        {
            "label": "Current streak",
            "value": f"{streak}",
            "icon": "target",
            "tone": "blue",
            "hint": "days",
        },
        {
            "label": "Avg. workout time",
            "value": "—",
            "icon": "trend",
            "tone": "green",
            "hint": "minutes",
        },
    ])

    # Main grid: shortcuts left / side panels right
    st.markdown('<div class="dash-grid"></div>', unsafe_allow_html=True)
    grid = st.columns([0.67, 0.33], gap="large")

    with grid[0]:
        panel_header(
            "Your journey",
            action_label="View all →",
            action_key="home_journey_all",
            on_action=lambda: _navigate(PAGE_WORKOUTS),
        )
        journey = st.columns(3, gap="medium")
        with journey[0]:
            feature_tile(
                "Workouts",
                "Start or continue your training session.",
                "workout",
                tone="green",
                key="home_journey_workouts",
                on_click=lambda: _navigate(PAGE_WORKOUTS),
            )
        with journey[1]:
            count = _exercise_count()
            feature_tile(
                "Exercise Library",
                "Browse and search every exercise.",
                "library",
                tone="blue",
                key="home_journey_library",
                on_click=lambda: _navigate(PAGE_EXERCISE_LIBRARY),
                meta=f"{count} exercises" if count else "",
            )
        with journey[2]:
            feature_tile(
                "AI Gym Trainer",
                "Get personalised workout guidance.",
                "trainer",
                tone="violet",
                key="home_journey_trainer",
                on_click=lambda: _navigate(PAGE_TRAINER),
            )

        gap(0.9)
        panel_header(
            "Nutrition tools",
            action_label="View all →",
            action_key="home_nutrition_all",
            on_action=lambda: _navigate(PAGE_DIET),
        )
        nutrition = st.columns(3, gap="medium")
        with nutrition[0]:
            feature_tile(
                "Diet Coach",
                "Get personalised diet plans and advice.",
                "diet",
                tone="amber",
                key="home_nutrition_diet",
                on_click=lambda: _navigate(PAGE_DIET),
            )
        with nutrition[1]:
            feature_tile(
                "Meal Analyser",
                "Analyse any meal and see its nutrition.",
                "meal",
                tone="rose",
                key="home_nutrition_meal",
                on_click=lambda: _navigate(PAGE_MEAL_ANALYSER),
            )
        with nutrition[2]:
            feature_tile(
                "Calorie Tracker",
                "Track your daily intake and what's left.",
                "calories",
                tone="teal",
                key="home_nutrition_tracker",
                on_click=lambda: _navigate(PAGE_CALORIE_TRACKER),
                meta=f"{int(calories):,} / {goal:,} kcal today",
            )

        # Current plan panel only when a routine actually exists.
        if _current_plan():
            gap(0.9)
            _render_current_plan()

    with grid[1]:
        with st.container(border=True):
            home_today(date.today().strftime("%A, %d %b %Y"), _today_checklist())
        gap(1.1)
        _render_recent_activity()
        gap(1.1)
        _render_goals()


def _notifications() -> None:
    """Bell popover summarising real, derived daily state."""
    try:
        with st.popover("", icon=":material/notifications:", help="Notifications", key="home_notifications"):
            week = _workouts_this_week()
            calories = _calories_logged()
            goal = int(st.session_state.get("calorie_goal") or 2000)
            streak = int(st.session_state.get("streak_days") or 0)
            st.markdown("**Today at a glance**")
            st.caption(f"Workouts this week — {week}")
            st.caption(f"Calories logged — {int(calories):,} of {goal:,} kcal")
            st.caption(f"Current streak — {streak} day{'s' if streak != 1 else ''}")
            if not week and not calories and not streak:
                st.caption("Nothing new yet — log a workout or a meal to see updates here.")
    except Exception:
        pass


def _render_current_plan() -> None:
    """Current plan panel — rendered only when a saved routine exists."""
    plan = _current_plan()
    if not plan:
        return

    panel_header(
        "Your current plan",
        action_label="View all routines →",
        action_key="home_view_routines",
        on_action=lambda: _navigate(PAGE_WORKOUTS),
    )

    with st.container(border=True):
        media_col, body_col, act_col = st.columns([1.1, 2.2, 1.4], gap="medium")
        with media_col:
            st.markdown(
                f'<div class="plan-media">{_plan_image_html(plan)}</div>',
                unsafe_allow_html=True,
            )
        with body_col:
            muscles = plan.get("muscles", "Chest • Shoulders • Triceps")
            st.markdown(
                f'<div class="plan-chip">Today&rsquo;s Focus</div>'
                f'<div class="plan-name">{plan["name"]}</div>'
                f'<div class="plan-muscles">{muscles}</div>'
                f'<div class="plan-meta">'
                f'<span>{icon("workout")} {plan["exercises"]} exercises</span>'
                f'<span>{icon("clock")} ~ 60 min</span>'
                '</div>',
                unsafe_allow_html=True,
            )
        with act_col:
            st.button(
                "Continue Workout",
                key="home_continue_workout",
                type="primary",
                use_container_width=True,
                on_click=lambda: _navigate(PAGE_WORKOUTS),
            )
            trained = (
                f"Last trained {_relative_day(plan['trained'])}"
                if plan.get("trained")
                else "Not trained yet"
            )
            st.markdown(f'<div class="plan-last-trained">{trained}</div>', unsafe_allow_html=True)


def _render_quick_access() -> None:
    """Quick Access: six core feature links in a 3×2 tile grid."""
    panel_header("Quick access")
    quick_items = [
        (PAGE_WORKOUTS, "Workouts", "Track your workouts and build routines", "workout", "green"),
        (PAGE_EXERCISE_LIBRARY, "Exercise Library", "Browse and search exercises", "library", "blue"),
        (PAGE_TRAINER, "AI Gym Trainer", "Get form feedback and training guidance", "trainer", "violet"),
        (PAGE_DIET, "Diet Coach", "Get personalised nutrition plans", "diet", "amber"),
        (PAGE_MEAL_ANALYSER, "Meal Analyser", "Analyse your meals with AI", "meal", "rose"),
        (PAGE_CALORIE_TRACKER, "Calorie Tracker", "Track your daily nutrition intake", "calories", "teal"),
    ]
    for start in (0, 3):
        st.markdown('<div class="pos-row"></div>', unsafe_allow_html=True)
        cols = st.columns(3, gap="medium")
        for col, (page, label, sub, icon_name, tone) in zip(cols, quick_items[start : start + 3]):
            with col:
                quick_tile(
                    label,
                    sub,
                    icon_name,
                    tone=tone,
                    key=f"home_qa_{page}",
                    on_click=lambda p=page: _navigate(p),
                )


def _render_recent_activity() -> None:
    """Recent activity panel from real stored records."""
    panel_header(
        "Recent activity",
        action_label="View history →",
        action_key="home_view_history",
        on_action=lambda: _navigate(PAGE_PROGRESS),
    )
    rows = _recent_activity()
    with st.container(border=True):
        activity_list(
            rows,
            "No activity yet",
            "Log a workout or a meal and it will appear here.",
        )


def _render_goals() -> None:
    """Your goals panel, driven by real user data only."""
    panel_header(
        "Your goals",
        action_label="Edit goals →",
        action_key="home_edit_goals",
        on_action=lambda: _navigate(PAGE_CALORIE_TRACKER),
    )
    calories = _calories_logged()
    goal = int(st.session_state.get("calorie_goal") or 2000)
    streak = int(st.session_state.get("streak_days") or 0)
    week = _workouts_this_week()
    workout_goal = 4
    streak_goal = 7
    rows = [
        {
            "label": "Daily calories",
            "value": f"{int(calories):,} / {goal:,} kcal",
            "icon": "flame",
            "tone": "amber",
            "progress": (calories / goal) if goal > 0 else 0,
        },
        {
            "label": "Workouts per week",
            "value": f"{week} / {workout_goal}",
            "icon": "workout",
            "tone": "green",
            "progress": (week / workout_goal) if workout_goal > 0 else 0,
        },
        {
            "label": "Streak",
            "value": f"{streak} / {streak_goal} days",
            "icon": "target",
            "tone": "blue",
            "progress": (streak / streak_goal) if streak_goal > 0 else 0,
        },
    ]
    with st.container(border=True):
        goal_list(rows, "No goals yet", "Set a calorie goal on the Calorie Tracker to get started.")


# ── Sidebar ───────────────────────────────────────────────────────────────────

NAV_ICONS: dict[str, str] = {
    PAGE_HOME: ":material/home:",
    PAGE_WORKOUTS: ":material/fitness_center:",
    PAGE_EXERCISE_LIBRARY: ":material/menu_book:",
    PAGE_TRAINER: ":material/psychology:",
    PAGE_DIET: ":material/restaurant:",
    PAGE_MEAL_ANALYSER: ":material/center_focus_strong:",
    PAGE_CALORIE_TRACKER: ":material/bar_chart:",
    PAGE_PROGRESS: ":material/trending_up:",
    PAGE_COACH: ":material/chat_bubble:",
    PAGE_PROFILE: ":material/person:",
    PAGE_SETTINGS: ":material/settings:",
    PAGE_ABOUT: ":material/info:",
}


def _render_sidebar_nav_item(label: str, current: str) -> None:
    """One navigation item rendered as a clean sidebar button with icon."""
    is_active = (current == label)
    icon_str = NAV_ICONS.get(label, ":material/circle:")
    if st.sidebar.button(
        label,
        key=f"nav_btn_{label}",
        type="primary" if is_active else "secondary",
        icon=icon_str,
        use_container_width=True,
    ):
        if not is_active:
            _navigate(label)


def build_sidebar() -> str:
    """Render the grouped navigation sidebar and return the selected page."""
    with st.sidebar:
        brand_block()

        # A cross-page link requested a destination; apply it before widgets.
        pending = st.session_state.pop("_navigate_to", None)
        if pending in ALL_NAV:
            st.session_state["nav_page"] = pending

        if st.session_state.get("nav_page") not in ALL_NAV:
            st.session_state["nav_page"] = PAGE_HOME
        current = st.session_state["nav_page"]

        for group_label, pages in NAV_GROUPS:
            if group_label != NAV_GROUPS[0][0]:
                nav_group_separator()
            nav_group_label(group_label)
            for page in pages:
                _render_sidebar_nav_item(page, current)

        nav_group_separator()
        for page in NAV_ACCOUNT:
            _render_sidebar_nav_item(page, current)

        nav_group_separator()
        sidebar_user_profile(_greeting_name(), on_view_profile=lambda: _navigate(PAGE_PROFILE))

    return current


# ── Dispatch ──────────────────────────────────────────────────────────────────

def _dispatch(target: str) -> None:
    """Render the page for a canonical target string."""
    if target == "home":
        render_home()
    elif target == "trainer":
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

    _dispatch(ROUTES.get(page, "home"))


if __name__ == "__main__":
    main()
