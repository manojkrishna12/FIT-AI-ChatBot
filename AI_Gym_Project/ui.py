"""
Shared presentation-layer components for the FIT-AI light design system.

This module is UI-only: no business logic, database, Gemini, authentication
or fitness calculations belong here. Pages should prefer these helpers over
hand-rolled markup so the visual language stays consistent.

Design language (assets/styles.css tokens): typography-first headers, dark
text on white, gray secondary text, one restrained green accent, no emoji in
chrome, no gradients, no glow.
"""

from __future__ import annotations

import streamlit as st


# ── Headers ────────────────────────────────────────────────────────────────────

def page_header(title: str, subtitle: str | None = None) -> None:
    """Typography-first page title with optional one-line gray subtitle."""
    subtitle_html = f'<div class="page-head-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f'<div class="page-head"><div class="page-head-title">{title}</div>{subtitle_html}</div>',
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str | None = None) -> None:
    """Smaller section heading for content grouped inside a page."""
    subtitle_html = f'<div class="section-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f'<div class="section-title">{title}</div>{subtitle_html}',
        unsafe_allow_html=True,
    )


# ── Actions ────────────────────────────────────────────────────────────────────

def action_buttons(
    actions: list[tuple[str, callable, bool]],
    *,
    key_prefix: str = "action",
) -> None:
    """Render a row of action buttons.

    actions: list of (label, on_click_callback, is_primary) tuples.
    Primary buttons use the accent fill; secondary are quiet bordered buttons.
    """
    if not actions:
        return
    cols = st.columns(len(actions), gap="small")
    for i, (label, on_click, is_primary) in enumerate(actions):
        with cols[i]:
            if st.button(
                label,
                key=f"{key_prefix}_{i}",
                type="primary" if is_primary else "secondary",
                use_container_width=True,
            ):
                on_click()


# ── Data display ───────────────────────────────────────────────────────────────

def stat_card(label: str, value: str, hint: str | None = None) -> str:
    """Return HTML for a bordered stat block (use inside st.columns)."""
    hint_html = f'<div class="stat-hint">{hint}</div>' if hint else ""
    return (
        '<div class="stat-card">'
        f'<div class="stat-label">{label}</div>'
        f'<div class="stat-value">{value}</div>'
        f"{hint_html}"
        "</div>"
    )


def stat_row(stats: list[dict]) -> None:
    """Render a responsive row of stat cards from {label, value, hint?} dicts."""
    if not stats:
        return
    cols = st.columns(len(stats), gap="medium")
    for col, stat in zip(cols, stats):
        with col:
            st.markdown(
                stat_card(stat.get("label", ""), stat.get("value", ""), stat.get("hint")),
                unsafe_allow_html=True,
            )


def card(content: str, *, key: str | None = None) -> None:
    """Render a simple bordered container with inner HTML content."""
    attrs = f' id="{key}"' if key else ""
    st.markdown(f'<div class="ui-card"{attrs}>{content}</div>', unsafe_allow_html=True)


def empty_state(title: str, description: str, action_label: str | None = None,
                on_action: callable | None = None) -> None:
    """Quiet bordered placeholder for empty lists/sections."""
    st.markdown(
        '<div class="empty-state">'
        f'<div class="empty-title">{title}</div>'
        f'<div class="empty-desc">{description}</div>'
        "</div>",
        unsafe_allow_html=True,
    )
    if action_label and on_action and st.button(action_label, type="secondary"):
        on_action()


# ── Navigation component (reuse only — wiring comes in a later step) ──────────

def section_tabs(
    options: list[str],
    *,
    key: str,
    default: str | None = None,
    label: str = "Section",
) -> str:
    """Segmented-control switcher for the features inside one section.

    Selection persists in st.session_state[key]; returns the active option.
    Not wired into the app's navigation yet — provided as the reusable
    component for the upcoming navigation step.
    """
    state_key = f"section_tabs_{key}"
    if state_key not in st.session_state:
        st.session_state[state_key] = default if default in options else (options[0] if options else None)
    try:
        return st.segmented_control(
            label,
            options,
            selection_mode="single",
            key=state_key,
            label_visibility="collapsed",
        ) or st.session_state[state_key]
    except Exception:
        # Older Streamlit fallback: quiet radio row.
        return st.radio(label, options, key=state_key, horizontal=True,
                        label_visibility="collapsed")
