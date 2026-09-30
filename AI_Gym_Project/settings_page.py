"""
Settings page — session, integration and data overview. Mirrors the sidebar
essentials and adds environment status plus clear pointers to data controls.
"""

from __future__ import annotations

import os

import streamlit as st

from auth import current_username, is_authenticated
from constants import GEMINI_MODEL, MONGODB_DB_NAME
from m import page_header
from storage import get_storage_status


def render_settings_page() -> None:
    """Entry point called by app.py for the Settings page."""
    page_header(
        "Settings",
        "Session, integrations and data overview",
    )

    st.subheader("Session")
    if is_authenticated():
        st.markdown(f"- **Account:** `{current_username()}`")
        st.markdown("- Manage sign-out, password and your fitness profile on the **Profile** page.")
    else:
        st.markdown("- **Identity:** guest (browse freely; sign in from the **Profile** page to persist your data)")
    user_id = st.session_state.get("active_user_id", "guest")
    st.markdown(f"- **Active user id:** `{user_id}` — keys your saved plans, chat and routines.")

    st.markdown("---")
    st.subheader("Integrations")
    gemini_ok = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    mongo_ok, mongo_msg = get_storage_status()
    st.markdown(
        f"- **AI provider:** Google Gemini (`{GEMINI_MODEL}`) — {'✅ configured' if gemini_ok else '⚠️ not configured (add GEMINI_API_KEY to .env)'}"
    )
    st.markdown(f"- **Storage:** {mongo_msg}")

    st.markdown("---")
    st.subheader("Data")
    st.markdown(
        "- Saved plans, chat history and routines are stored per user id in MongoDB.\n"
        "- Clearing the chat lives on the **Gym Buddy** page; routine deletion on the **Routines** page.\n"
        "- Signing out returns the session to the shared guest identity."
    )
    st.caption("Version 2.0 — development build")
