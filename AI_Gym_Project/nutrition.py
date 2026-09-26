"""
Nutrition Tools page — Phase 1 placeholder.
The nutrition tools feature ships in a later phase; this page reserves its slot
in the navigation with a styled explanation of what is coming.
"""

from __future__ import annotations

import streamlit as st

from m import render_placeholder_page


def render_render_nutrition_page() -> None:
    """Render the nutrition tools placeholder page."""
    render_placeholder_page(
        "🍽️",
        "Nutrition Tools",
        "Focused single-purpose pages for the nutrition workflow.",
        "The Diet Coach tools are being split into focused pages so each workflow gets full space.",
        ['Meal Analyser — instant nutritional breakdown of any meal', 'Grocery List — weekly shopping list from your meal plan', 'Calorie Tracker — log meals and track daily macros'],
    )
