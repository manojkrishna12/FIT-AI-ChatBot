"""
Settings page — session, integration and data overview. Mirrors the sidebar
essentials and adds environment status plus clear pointers to data controls.
"""

from __future__ import annotations

import os

import streamlit as st

from auth import current_username, is_authenticated
from constants import GEMINI_MODEL, MONGODB_DB_NAME
from m import page_header, section_header
from storage import get_storage_status
from ui import stat_row


def render_settings_page() -> None:
    """Entry point called by app.py for the Settings page."""
    page_header(
        "Settings",
        "Session, integrations and data overview",
    )

    section_header("Session")
    if is_authenticated():
        st.markdown(
            f"Signed in as **{current_username()}**. Manage sign-out, password and your "
            "fitness profile on the **Profile** page."
        )
    else:
        st.markdown(
            "Browsing as **guest** — sign in on the welcome screen to persist your data."
        )
    user_id = st.session_state.get("active_user_id", "guest")
    st.caption(f"Active user id: {user_id} — keys your saved plans, chat and routines.")

    section_header("Integrations")
    gemini_ok = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    mongo_ok, mongo_msg = get_storage_status()
    try:
        from rag import knowledge_base_status

        kb = knowledge_base_status()
    except Exception:
        kb = {"available": False, "embedded": 0}
    stat_row(
        [
            {
                "label": "AI provider",
                "value": "Gemini",
                "hint": f"{GEMINI_MODEL} — configured" if gemini_ok else "GEMINI_API_KEY not set in .env",
            },
            {
                "label": "Storage",
                "value": "MongoDB" if mongo_ok else "Unavailable",
                "hint": mongo_msg,
            },
            {
                "label": "Gym Buddy knowledge",
                "value": f"{kb.get('embedded', 0)} exercises" if kb.get("available") else "Unavailable",
                "hint": f"{kb.get('model')}" if kb.get("available") else "Gym Buddy answers without exercise grounding",
            },
        ]
    )
    if not mongo_ok:
        st.warning(
            "MongoDB is unavailable. The app keeps working in-session, but plans, "
            "routines and profiles cannot be saved until it is reachable."
        )

    section_header("Data")
    st.markdown(
        "- Saved plans, chat history and routines are stored per user id in MongoDB.\n"
        "- Clearing the chat lives on the **Gym Buddy** page; routine deletion on the **Workouts** page.\n"
        "- Signing out returns you to the welcome (sign-in) screen."
    )
    st.caption("Version 2.0 — development build")
