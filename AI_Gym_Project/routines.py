"""
Routines page — Phase 1 placeholder.
The routines feature ships in a later phase; this page reserves its slot
in the navigation with a styled explanation of what is coming.
"""

from __future__ import annotations

import streamlit as st

from m import render_placeholder_page


def render_render_routines_page() -> None:
    """Render the routines placeholder page."""
    render_placeholder_page(
        "🗓️",
        "Routines",
        "Build multi-day workout routines from the Exercise Library.",
        "Routines let you compose training days from the Exercise Library, save them, and reuse them across weeks.",
        ['Routine builder — pick exercises, sets, reps and rest per day', 'Routine templates for common splits (push/pull/legs, full body)', "One-click 'start session' bridge to the AI Gym Trainer"],
    )
