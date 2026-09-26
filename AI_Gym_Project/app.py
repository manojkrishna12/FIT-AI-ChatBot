"""
Main Streamlit app entrypoint for the AI Gym project.
(UI-only redesign v2: premium fitness product UI — all backend logic preserved.)
"""

from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv
import os
load_dotenv()

from m import inject_custom_css, render_top_header
from storage import ensure_user_state_loaded, get_storage_status, normalize_user_id


st.set_page_config(
    page_title="AI Gym & Fitness Assistant",
    page_icon="💪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Navigation constants & routes (target information architecture) ──
# Labels are the exact sidebar entries; ROUTES maps each label to a dispatch
# target consumed by main(). Keep all three in sync.
PAGE_HOME = "🏠 Home"

PAGE_TRAINER = "🏋️ AI Gym Trainer"
PAGE_EXERCISE_LIBRARY = "📚 Exercise Library"
PAGE_ROUTINES = "🗓️ Routines"

PAGE_DIET = "🥗 Diet Coach"
PAGE_MEAL_ANALYSER = "🍽️ Meal Analyser"
PAGE_GROCERY = "🛒 Grocery List"
PAGE_CALORIE_TRACKER = "📈 Calorie Tracker"

PAGE_BUDDY = "🤝 Gym Buddy"

PAGE_PROGRESS = "📊 Progress"
PAGE_PROFILE = "👤 Profile"
PAGE_SETTINGS = "⚙️ Settings"
PAGE_ABOUT = "ℹ️ About"

# Ordered sidebar structure: (group label, [page labels]); None = no header.
# Grouping is rendered as flat nav for now (single-radio, lowest-risk);
# visual grouping can layer on top without changing ROUTES.
NAV_GROUPS: list[tuple[str | None, list[str]]] = [
    (None, [PAGE_HOME]),
    ("Training", [PAGE_TRAINER, PAGE_EXERCISE_LIBRARY, PAGE_ROUTINES]),
    ("Nutrition", [PAGE_DIET, PAGE_MEAL_ANALYSER, PAGE_GROCERY, PAGE_CALORIE_TRACKER]),
    ("Coach", [PAGE_BUDDY]),
    (None, [PAGE_PROGRESS, PAGE_PROFILE, PAGE_SETTINGS, PAGE_ABOUT]),
]
PAGE_OPTIONS: list[str] = [label for _, labels in NAV_GROUPS for label in labels]

ROUTES: dict[str, str] = {
    PAGE_HOME: "home",
    PAGE_TRAINER: "trainer",
    PAGE_EXERCISE_LIBRARY: "exercise_library",
    PAGE_ROUTINES: "routines",
    PAGE_DIET: "diet",
    PAGE_MEAL_ANALYSER: "meal_analyser",
    PAGE_GROCERY: "grocery_list",
    PAGE_CALORIE_TRACKER: "calorie_tracker",
    PAGE_BUDDY: "buddy",
    PAGE_PROGRESS: "progress",
    PAGE_PROFILE: "profile",
    PAGE_SETTINGS: "settings",
    PAGE_ABOUT: "about",
}

_ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

BRAND_HTML = """
<div class="brand">
  <svg width="42" height="42" viewBox="0 0 44 44" fill="none">
    <circle cx="18" cy="17" r="11" fill="#ff6a3d" opacity="0.9"/>
    <circle cx="27" cy="16" r="11" fill="#9d5cff" opacity="0.9"/>
    <circle cx="22" cy="27" r="11" fill="#ff2e63" opacity="0.9"/>
  </svg>
  <div>
    <div class="brand-name">FitAI Hub</div>
    <div class="brand-sub">Your AI Fitness Assistant</div>
  </div>
</div>
"""

MOTIVATIONAL_HTML = """
<div class="mcard">
  <div class="mcard-text"><span class="mcard-accent">Discipline today,</span> strength tomorrow.</div>
  <div class="mcard-icon">💪</div>
</div>
"""

HERO_TEXT_HTML = """
<div class="hero-badge">⚡ AI-POWERED FITNESS</div>
<div class="hero-title">Train Smarter.<br/>Eat Better.<br/><span class="hero-title-accent">Live Stronger.</span></div>
<div class="hero-sub">Your personal AI assistant for workouts, nutrition and everyday fitness guidance.</div>
"""

EXPLORE_HEADING_HTML = """
<div id="explore" class="section-head"><div class="section-icon">✦</div><div class="section-title">Explore</div></div>
<div class="section-sub">Everything you need for your fitness journey.</div>
"""

TOOLS_HEADING_HTML = """
<div class="section-head"><div class="section-icon green">🧰</div><div class="section-title">Fitness Tools</div></div>
<div class="section-sub">Quick nutrition and tracking tools.</div>
"""

QUICK_START_HTML = """
<div class="qs-wrap">
  <div class="section-head"><div class="section-icon">🚀</div><div class="qs-title">Quick Start</div></div>
  <div class="qs-sub">Your path to a stronger, healthier you.</div>
  <div class="qs-steps">
    <div class="qs-step"><div class="qs-num">1</div><div class="qs-name">Choose a module</div><div class="qs-desc">Training, Nutrition or Coach</div></div>
    <div class="qs-arrow">▸</div>
    <div class="qs-step"><div class="qs-num">2</div><div class="qs-name">Follow the instructions</div><div class="qs-desc">Get AI-powered assistance</div></div>
    <div class="qs-arrow">▸</div>
    <div class="qs-step"><div class="qs-num">3</div><div class="qs-name">Stay consistent</div><div class="qs-desc">Small steps, big results</div></div>
    <div class="qs-arrow">▸</div>
    <div class="qs-step"><div class="qs-num">4</div><div class="qs-name">Achieve your goals</div><div class="qs-desc">You've got this!</div></div>
  </div>
</div>
"""

HOME_FOOTER_HTML = '<div class="home-footer">BUILT WITH STREAMLIT · MEDIAPIPE · GEMINI AI</div>'


@st.cache_data(show_spinner=False)
def _media_data_uri(image_name: str) -> str | None:
    """Return a compressed base64 data URI for a local asset (cached)."""
    path = os.path.join(_ASSET_DIR, image_name)
    if not (os.path.exists(path) and os.path.getsize(path) > 5000):
        return None
    try:
        from PIL import Image
        import io
        import base64

        im = Image.open(path)
        im.thumbnail((1200, 1200))
        if im.mode != "RGB":
            im = im.convert("RGB")
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=72, optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return None


def _media_html(image_name: str, fallback_emoji: str) -> str:
    """HTML <img> for a local asset, with a gradient fallback if missing."""
    uri = _media_data_uri(image_name)
    if uri:
        return f'<img src="{uri}" alt="" loading="lazy"/>'
    return f'<div class="media-fallback">{fallback_emoji}</div>'


def _navigate(page: str) -> None:
    """Request a page switch; consumed before the nav radio is instantiated."""
    st.session_state["_navigate_to"] = page
    st.rerun()


def _scroll_to(anchor: str) -> None:
    st.session_state["_scroll_to"] = anchor
    st.rerun()


def render_home() -> None:
    """Render the landing page (hero, explore cards, tools, quick start)."""
    # ── Hero ──────────────────────────────────────────────────────────
    # Built via string concatenation (no leading indentation) so the
    # injected multi-line HTML never trips markdown's code-block rule.
    hero_html = (
        '<div class="hero-card"><div class="hero-grid"><div>'
        + HERO_TEXT_HTML
        + '</div><div class="hero-media">'
        + _media_html("hero.jpg", "🏋️")
        + '</div></div></div>'
    )
    st.markdown(hero_html, unsafe_allow_html=True)
    b1, b2, _spacer = st.columns([1, 1, 2.6], gap="small")
    with b1:
        if st.button("Get Started →", key="hero_start", type="primary", use_container_width=True):
            _navigate(PAGE_TRAINER)
    with b2:
        if st.button("Explore Features", key="hero_explore", use_container_width=True):
            _scroll_to("explore")

    # ── Explore: three primary feature cards ─────────────────────────
    st.markdown(EXPLORE_HEADING_HTML, unsafe_allow_html=True)
    cards = [
        ("AI Gym Trainer", "trainer.jpg", "🏋️",
         "Real-time exercise guidance, pose analysis and rep counting.",
         "Open Trainer →", "open_trainer", PAGE_TRAINER),
        ("Diet Coach", "diet.jpg", "🥗",
         "Personalized diet plans, meal analysis, grocery planning and calorie tracking.",
         "Open Diet Coach →", "open_diet", PAGE_DIET),
        ("Gym Buddy", "buddy.jpg", "🤖",
         "Your AI fitness companion for motivation, workout advice and fitness guidance.",
         "Open Gym Buddy →", "open_buddy", PAGE_BUDDY),
    ]
    cols = st.columns(3, gap="medium")
    for col, (title, img, emoji, desc, label, key, target) in zip(cols, cards):
        with col:
            st.markdown(
                f"""
                <div class="fcard">
                  <div class="fcard-media">{_media_html(img, emoji)}</div>
                  <div class="fcard-body">
                    <div class="fcard-title">{title}</div>
                    <div class="fcard-desc">{desc}</div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(label, key=key, use_container_width=True):
                _navigate(target)

    # ── Fitness Tools: existing Diet Coach tools (small cards) ───────
    st.markdown(TOOLS_HEADING_HTML, unsafe_allow_html=True)
    tools = [
        ("🥗", "Diet Coach", "Personalized 7-day meal plans", "open_nutrition", PAGE_DIET),
        ("🍽️", "Meal Analyser", "Instant nutritional breakdown", "open_analyser", PAGE_MEAL_ANALYSER),
        ("📈", "Calorie Tracker", "Log meals, track macros", "open_calories", PAGE_CALORIE_TRACKER),
        ("🛒", "Grocery List", "Weekly shopping lists", "open_grocery", PAGE_GROCERY),
    ]
    tcols = st.columns(4, gap="medium")
    for col, (icon, name, desc, key, target_page) in zip(tcols, tools):
        with col:
            st.markdown(
                f"""
                <div class="tool-card">
                  <div class="tool-icon">{icon}</div>
                  <div class="tool-name">{name}</div>
                  <div class="tool-desc">{desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Open →", key=key, use_container_width=True):
                _navigate(target_page)

    # ── Quick Start ──────────────────────────────────────────────────
    st.markdown(QUICK_START_HTML, unsafe_allow_html=True)
    st.markdown(HOME_FOOTER_HTML, unsafe_allow_html=True)

    # Honor a pending "scroll to explore" request.
    if st.session_state.pop("_scroll_to", None) == "explore":
        st.components.v1.html(
            "<script>parent.document.getElementById('explore')?.scrollIntoView({behavior:'smooth'});</script>",
            height=0,
        )


def build_sidebar() -> str:
    """Render the app navigation sidebar and return the selected page.

    Functional logic is fully preserved: the per-user ID handling and the
    Gemini/MongoDB availability checks still run here; only their technical
    status messages are no longer shown in the UI (User ID lives in Settings).
    """
    with st.sidebar:
        st.markdown(BRAND_HTML, unsafe_allow_html=True)

        st.markdown('<div class="nav-label">Main</div>', unsafe_allow_html=True)
        # Apply any pending navigation request before the radio widget renders.
        pending = st.session_state.pop("_navigate_to", None)
        if pending in PAGE_OPTIONS:
            st.session_state["nav_page"] = pending
        page = st.radio(
            "Navigation",
            options=PAGE_OPTIONS,
            key="nav_page",
            label_visibility="collapsed",
        )

        st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

        # ── Settings ───────────────────────────────────────────────────
        with st.expander("⚙️ Settings", expanded=False):
            st.markdown('<div class="set-label">User ID</div>', unsafe_allow_html=True)
            user_input = st.text_input(
                "User ID",
                value=st.session_state.get("active_user_id", ""),
                placeholder="e.g. manoj123",
                label_visibility="collapsed",
                help="Each user id gets their own saved chat, diet, and workout history.",
            )
            user_id = normalize_user_id(user_input)
            if st.session_state.get("active_user_id") != user_id:
                st.session_state["active_user_id"] = user_id
                st.session_state["_loaded_user_id"] = None

            # Underlying checks are still performed (behavior unchanged),
            # but their technical status is not displayed in the UI.
            os.environ.get("GEMINI_API_KEY", "").strip()
            get_storage_status()

            st.markdown('<div class="set-divider"></div>', unsafe_allow_html=True)
            st.markdown("**Appearance** — Dark theme")
            st.markdown("**AI Provider** — Google Gemini")
            st.markdown("**Storage** — Local session")

        # ── About ──────────────────────────────────────────────────────
        with st.expander("ℹ️ About", expanded=False):
            st.markdown("**FitAI Hub** — AI Gym & Fitness Assistant")
            st.caption("Your personal AI fitness assistant, powered by Streamlit, MediaPipe and Google Gemini.")
            st.caption("Version 1.0 — stable")

        st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
        st.markdown(MOTIVATIONAL_HTML, unsafe_allow_html=True)

    return page


def main() -> None:
    """Run the application."""
    inject_custom_css()
    page = build_sidebar()
    ensure_user_state_loaded()
    render_top_header()

    target = ROUTES.get(page, "home")

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
        from library import render_exercise_library_page

        render_exercise_library_page()
    elif target == "routines":
        from routines import render_routines_page

        render_routines_page()
    elif target == "meal_analyser":
        from nutrition import render_meal_analyser_page

        render_meal_analyser_page()
    elif target == "grocery_list":
        from nutrition import render_grocery_list_page

        render_grocery_list_page()
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


if __name__ == "__main__":
    main()