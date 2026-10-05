"""
Dedicated authentication screen — the app's front gate.

Shown by app.py before any main-app content when no session exists (the
Campus Lost & Found pattern: unauthenticated visitors only ever see this
screen). Everything is reused from auth.py — credential checks, account
creation, session binding and the browser session cookie — so there is no
second auth system. No sidebar and no navigation render here.
"""

from __future__ import annotations

import streamlit as st

from auth import authenticate, normalize_username, register_user, start_session
from ui import page_header


def render_auth_screen() -> None:
    """Full-page Sign in / Create account gate; reruns into Home on success."""
    # The gate has no sidebar — hide Streamlit's empty one for this run only.
    st.markdown(
        "<style>section[data-testid='stSidebar']{display:none!important}</style>",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="brand"><span class="brand-name">FIT-AI</span></div>', unsafe_allow_html=True)
    page_header(
        "Welcome to FIT-AI",
        "Sign in to your account — or create one — to open your dashboard.",
    )

    tab_login, tab_register = st.tabs(["Sign in", "Create account"])

    with tab_login:
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", key="login_user")
            password = st.text_input("Password", type="password", key="login_pass")
            submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
        if submitted:
            ok, message = authenticate(username, password)
            if ok:
                start_session(normalize_username(username))
                st.toast(f"Welcome back, {normalize_username(username)}!")
                st.rerun()
            else:
                st.error(message)

    with tab_register:
        with st.form("register_form", clear_on_submit=False):
            new_user = st.text_input("Username", key="reg_user", help="Letters, numbers, dots, dashes or underscores.")
            display = st.text_input("Display name (optional)", key="reg_display")
            new_pass = st.text_input("Password (min 8 characters)", type="password", key="reg_pass")
            new_pass2 = st.text_input("Confirm password", type="password", key="reg_pass2")
            submitted = st.form_submit_button("Create account", type="primary", use_container_width=True)
        if submitted:
            if new_pass != new_pass2:
                st.error("Passwords do not match.")
            else:
                ok, message = register_user(new_user, new_pass, display)
                if ok:
                    start_session(normalize_username(new_user))
                    st.toast("Account created — you are signed in.")
                    st.rerun()
                else:
                    st.error(message)
