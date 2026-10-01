"""
Profile page — account management and the fitness profile that personalizes
AI plans. Guests are offered sign-in/registration; the profile form is
available to signed-in users and feeds the trainer/diet form prefills.
Authentication and profile logic live in auth.py and are untouched here.
"""

from __future__ import annotations

import streamlit as st

from auth import (
    authenticate,
    change_password,
    get_profile,
    is_authenticated,
    normalize_username,
    register_user,
    save_profile,
    sign_in,
    sign_out,
)
from m import page_header, section_header


def _render_auth_panel() -> None:
    st.info(
        "You are browsing as a guest. Create an account so your routines, profile "
        "and saved plans stay tied to you."
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
                sign_in(username)
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
                    sign_in(normalize_username(new_user))
                    st.toast("Account created — you are signed in.")
                    st.rerun()
                else:
                    st.error(message)


def _render_account_panel() -> None:
    from auth import current_username, get_account_display_name

    username = current_username()
    display = get_account_display_name() or username
    st.markdown(
        f"""
        <div class="ui-card account-card">
          <div>
            <div class="account-name">{display}</div>
            <div class="account-username">{username}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Sign out", use_container_width=True):
        sign_out()
        st.rerun()

    with st.expander("Change password"):
        with st.form("password_form", clear_on_submit=True):
            current_pw = st.text_input("Current password", type="password", key="pw_cur")
            new_pw = st.text_input("New password (min 8 characters)", type="password", key="pw_new")
            new_pw2 = st.text_input("Confirm new password", type="password", key="pw_new2")
            submitted = st.form_submit_button("Update password", use_container_width=True)
        if submitted:
            if new_pw != new_pw2:
                st.error("New passwords do not match.")
            else:
                ok, message = change_password(username, current_pw, new_pw)
                if ok:
                    st.success(message)
                else:
                    st.error(message)


def _render_profile_form() -> None:
    profile = get_profile()

    section_header(
        "Fitness profile",
        "These details prefill the AI Gym Trainer and Diet Coach forms so your plans stay consistent.",
    )

    with st.form("profile_form"):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Display name", value=profile.get("name") or "")
            age = st.number_input("Age", 10, 100, int(profile.get("age") or 22))
            gender = st.selectbox("Gender", ["Male", "Female", "Other"], index=["Male", "Female", "Other"].index(profile.get("gender") or "Male"))
            weight = st.number_input("Weight (kg)", 30.0, 200.0, float(profile.get("weight_kg") or 68.0), step=0.5)
            height = st.number_input("Height (cm)", 100.0, 250.0, float(profile.get("height_cm") or 170.0), step=0.5)
        with c2:
            activity = st.selectbox("Activity level", ["Sedentary", "Lightly Active", "Moderately Active", "Very Active", "Extra Active"], index=max(0, ["Sedentary", "Lightly Active", "Moderately Active", "Very Active", "Extra Active"].index(profile.get("activity") or "Moderately Active")))
            goal = st.selectbox("Primary goal", ["Weight Loss", "Weight Gain", "Weight Maintenance", "Muscle Building", "Athletic Performance", "General Fitness"], index=max(0, ["Weight Loss", "Weight Gain", "Weight Maintenance", "Muscle Building", "Athletic Performance", "General Fitness"].index(profile.get("goal") or "General Fitness")))
            diet_type = st.selectbox("Dietary preference", ["No Restriction", "Vegetarian", "Vegan", "Eggitarian", "Keto", "Mediterranean", "Paleo", "Gluten-Free", "Dairy-Free"], index=max(0, ["No Restriction", "Vegetarian", "Vegan", "Eggitarian", "Keto", "Mediterranean", "Paleo", "Gluten-Free", "Dairy-Free"].index(profile.get("diet_type") or "No Restriction")))
            allergies = st.text_input("Allergies / foods to avoid", value=profile.get("allergies") or "None")

        submitted = st.form_submit_button("Save profile", type="primary", use_container_width=True)

    if submitted:
        ok = save_profile(
            name=name.strip()[:60],
            age=int(age),
            gender=gender,
            weight_kg=float(weight),
            height_cm=float(height),
            activity=activity,
            goal=goal,
            diet_type=diet_type,
            allergies=allergies.strip()[:120] or "None",
        )
        if ok:
            st.success("Profile saved — your AI forms will use these details.")
        else:
            st.warning("Could not save: profiles are tied to accounts. Sign in above and try again.")


def render_profile_page() -> None:
    """Entry point called by app.py for the Profile page."""
    page_header(
        "Profile",
        "Your account and the fitness details that personalize your AI plans",
    )

    if not is_authenticated():
        _render_auth_panel()
        st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
        st.caption("Sign in to edit your fitness profile — your details prefill every AI form.")
        return

    _render_account_panel()
    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
    _render_profile_form()
