"""
About FitAI page — Phase 1 placeholder.
The about fitai feature ships in a later phase; this page reserves its slot
in the navigation with a styled explanation of what is coming.
"""

from __future__ import annotations

import streamlit as st

from m import render_placeholder_page


def render_render_about_page() -> None:
    """Render the about fitai placeholder page."""
    render_placeholder_page(
        "ℹ️",
        "About FitAI",
        "What FitAI is, how it works, and the tech behind it.",
        "FitAI is an AI-powered fitness platform: real-time exercise coaching with MediaPipe, an AI nutritionist with Gemini, and a companion that keeps you consistent.",
        ['Built with Streamlit · MediaPipe BlazePose · Google Gemini · MongoDB', 'Rep counting uses a joint-angle state machine over 33 pose landmarks', 'Exercise data in the Exercise Library is credited to its dataset source'],
    )
