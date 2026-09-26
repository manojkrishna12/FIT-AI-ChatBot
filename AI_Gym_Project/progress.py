"""
Progress page — Phase 1 placeholder.
The progress feature ships in a later phase; this page reserves its slot
in the navigation with a styled explanation of what is coming.
"""

from __future__ import annotations

import streamlit as st

from m import render_placeholder_page


def render_render_progress_page() -> None:
    """Render the progress placeholder page."""
    render_placeholder_page(
        "📊",
        "Progress",
        "Workout history, trends and milestones over time.",
        "Progress turns your logged sessions into visible momentum — volume, streaks and personal records.",
        ['Workout history from logged sessions', 'Volume and streak trends (including your Gym Buddy check-in streak)', 'Body measurement tracking alongside your profile'],
    )
