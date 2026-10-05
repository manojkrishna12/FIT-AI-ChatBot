"""
Profile page — the signed-in user's account details and the fitness profile
that personalizes AI plans. Sign-in/create-account live on the dedicated
auth screen (auth_screen.py); this page is reached only through the app's
authentication gate. Authentication and profile logic live in auth.py and
are untouched here.
"""

from __future__ import annotations

import streamlit as st

from auth import (
    change_password,
    end_session,
    get_profile,
    is_authenticated,
    save_profile,
)
from m import page_header, section_header


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
        end_session()  # revokes the browser session too — lands on the auth screen
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


def _effective_display_name(profile: dict, account_name: str = "", username: str = "") -> str:
    """Reuse the account identity as the profile name — never ask for it again."""
    for value in (profile.get("name"), account_name, username):
        text = str(value or "").strip()
        if text:
            return text[:60]
    return ""


def _render_profile_form() -> None:
    from auth import current_username, get_account_display_name

    profile = get_profile()
    account_name = (get_account_display_name() or "").strip()
    identity = account_name or (current_username() or "")
    # The display name lives on the account — the fitness profile only reuses it.
    effective_name = _effective_display_name(profile, account_name, current_username() or "")

    section_header(
        "Fitness profile",
        "These details prefill the AI Gym Trainer and Diet Coach forms so your plans stay consistent.",
    )
    st.caption(f"Display name: {identity or '—'} — from your account.")

    with st.form("profile_form"):
        c1, c2 = st.columns(2)
        with c1:
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
            name=effective_name,
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
            st.toast("Profile saved.")
            st.session_state["_navigate_to"] = "Home"
            st.rerun()
        else:
            st.warning("Could not save your profile — the database is unavailable. Try again later.")


def render_profile_page() -> None:
    """Entry point called by app.py for the Profile page."""
    page_header(
        "Profile",
        "Your account and the fitness details that personalize your AI plans",
    )

    # Defensive only — the app's authentication gate keeps guests out.
    if not is_authenticated():
        st.info("Please sign in to view your profile.")
        return

    _render_account_panel()
    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
    _render_profile_form()
