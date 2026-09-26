"""
Profile page — Phase 1 placeholder.
The profile feature ships in a later phase; this page reserves its slot
in the navigation with a styled explanation of what is coming.
"""

from __future__ import annotations

import streamlit as st

from m import render_placeholder_page


def render_render_profile_page_page() -> None:
    """Render the profile placeholder page."""
    render_placeholder_page(
        "👤",
        "Profile",
        "Your measurements, goals and account settings in one place.",
        "Your profile feeds the AI: body metrics personalize both workout plans and diet plans.",
        ['Body metrics — height, weight, age, activity level', 'Goals — primary goal, target weight, dietary preference', 'Account — password protection arrives with the accounts phase'],
    )
