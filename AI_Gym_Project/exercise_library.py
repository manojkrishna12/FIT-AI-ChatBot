"""
Exercise Library page — Phase 1 placeholder.
Phase 2 fills this page with the licensed exercise catalog (RepDB free tier,
curated subset) including images, filters and detail views.
"""

from __future__ import annotations

import streamlit as st

from m import render_placeholder_page


def render_exercise_library_page() -> None:
    """Render the Exercise Library placeholder page."""
    render_placeholder_page(
        "📚",
        "Exercise Library",
        "Browse the curated exercise catalog with images, muscles and equipment.",
        "A curated library of ~350 exercises with reference images and clear instructions, "
        "built on properly licensed open data (RepDB free tier — attribution in About).",
        [
            "Search and filter by body part, equipment, difficulty and muscle",
            "Exercise detail views with start/peak reference images",
            "Sourced from the RepDB free-tier dataset — no scraped content",
        ],
    )
