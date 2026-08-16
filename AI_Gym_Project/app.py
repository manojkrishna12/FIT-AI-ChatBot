"""
Main Streamlit app entrypoint for the AI Gym project.
"""

from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv
import os
load_dotenv()

from m import inject_custom_css
from storage import ensure_user_state_loaded, get_storage_status, normalize_user_id


st.set_page_config(
    page_title="AI Gym & Fitness Assistant",
    page_icon="💪",
    layout="wide",
    initial_sidebar_state="expanded",
)


def render_home() -> None:
    """Render the landing page."""
    st.markdown(
        """
        <div style="text-align:center; padding: 1rem 0 0.5rem 0;">
          <span style="font-size:3.2rem; font-weight:900;
                background:linear-gradient(90deg,#FF6B35,#FF3CAC,#00D4FF);
                -webkit-background-clip:text; -webkit-text-fill-color:transparent;">
            💪 AI Gym & Fitness Assistant
          </span>
          <p style="font-size:1.1rem; color:#aaa; margin-top:0.4rem;">
            Your all-in-one AI-powered fitness companion.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("---")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            """
            <div class="feature-card">
              <h3>🏋️ AI Gym Trainer</h3>
              <p>Pose analysis, rep counting, form feedback, and workout plans.</p>
              <ul>
                <li>7 exercise pose detectors</li>
                <li>Angle-based rep counter</li>
                <li>AI workout planner</li>
                <li>Exercise database</li>
              </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            """
            <div class="feature-card">
              <h3>🥗 Diet Coach</h3>
              <p>Meal plans, calorie tracking, meal analysis, and grocery support.</p>
              <ul>
                <li>BMI and TDEE calculator</li>
                <li>7-day AI diet plans</li>
                <li>Meal analyser</li>
                <li>Nutrition database</li>
              </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            """
            <div class="feature-card">
              <h3>🤝 Gym Buddy</h3>
              <p>Persistent AI chat, mood boosts, tips, and streak tracking.</p>
              <ul>
                <li>Per-user chat history</li>
                <li>Mood-aware replies</li>
                <li>Daily challenge support</li>
                <li>Workout streak tracker</li>
              </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("### Getting Started")
    left, right = st.columns([2, 1])
    with left:
        st.info(
            """
            1. Enter a `User ID` in the sidebar so the app can load your own saved history.
            2. Add your Gemini API key in the sidebar.
            3. Configure `MONGODB_URI` in `.env` if you want a custom MongoDB instance.
            4. Open any module from the sidebar and continue where that user left off.
            """
        )
    with right:
        st.markdown("#### Stack")
        st.markdown(
            """
            | Layer | Tool |
            |---|---|
            | UI | Streamlit |
            | AI | Gemini 1.5 Flash |
            | Database | MongoDB |
            | CV | MediaPipe + OpenCV |
            """
        )


def build_sidebar() -> str:
    """Render the sidebar and return the selected page."""
    with st.sidebar:
        st.markdown("<h2 style='text-align:center;'>💪 FitAI Hub</h2>", unsafe_allow_html=True)
        st.markdown("---")

        page = st.radio(
            "Navigation",
            options=[
                "🏠 Home",
                "🏋️ AI Gym Trainer",
                "🥗 Diet Coach",
                "🤝 Gym Buddy",
            ],
            label_visibility="collapsed",
        )

        st.markdown("---")
        st.markdown("### Settings")

        user_input = st.text_input(
            "👤 User ID",
            value=st.session_state.get("active_user_id", ""),
            placeholder="e.g. manoj123",
            help="Each user id gets their own saved chat, diet, and workout history.",
        )
        user_id = normalize_user_id(user_input)
        if st.session_state.get("active_user_id") != user_id:
            st.session_state["active_user_id"] = user_id
            st.session_state["_loaded_user_id"] = None

        if user_input.strip():
            st.success(f"Saving data for user: `{user_id}`")
        else:
            st.caption("Using the shared `guest` profile until you enter a user id.")

        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        if not gemini_key:
            st.error("Gemini API key is not configured. Add GEMINI_API_KEY to the .env file.")
        else:
            st.success("Gemini API connected.")

        mongo_ok, mongo_msg = get_storage_status()
        if mongo_ok:
            st.success(mongo_msg)
        else:
            st.warning(mongo_msg)

        st.markdown("---")
        st.caption("Built with Streamlit, MongoDB, MediaPipe, and Gemini AI.")

    return page


def main() -> None:
    """Run the application."""
    inject_custom_css()
    page = build_sidebar()
    ensure_user_state_loaded()

    if page == "🏠 Home":
        render_home()
    elif page == "🏋️ AI Gym Trainer":
        from gym_trainer import render_gym_trainer_page

        render_gym_trainer_page()
    elif page == "🥗 Diet Coach":
        from diet import render_diet_page

        render_diet_page()
    elif page == "🤝 Gym Buddy":
        from habit_tracker import render_gym_buddy_page

        render_gym_buddy_page()


if __name__ == "__main__":
    main()
