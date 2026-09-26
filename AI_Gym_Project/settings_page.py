"""
Settings page — Phase 1 placeholder.
The settings feature ships in a later phase; this page reserves its slot
in the navigation with a styled explanation of what is coming.
"""

from __future__ import annotations

import streamlit as st

from m import render_placeholder_page


def render_render_settings_page_page() -> None:
    """Render the settings placeholder page."""
    render_placeholder_page(
        "⚙️",
        "Settings",
        "App preferences, connections and data controls.",
        "Settings centralizes what the sidebar used to hide: identity, integrations and data management.",
        ['User ID / account management', 'AI provider and storage status at a glance', 'Export or clear your saved plans and history'],
    )
