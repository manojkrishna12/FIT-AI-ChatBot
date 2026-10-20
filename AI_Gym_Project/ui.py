"""
Shared presentation-layer components for the FIT-AI light design system.

This module is UI-only: no business logic, database, Gemini, authentication
or fitness calculations belong here. Pages should prefer these helpers over
hand-rolled markup so the visual language stays consistent.

Design language (assets/styles.css tokens): typography-first headers, dark
text on white, gray secondary text, one restrained green accent, no emoji in
chrome, no gradients, no glow.

Icon set: simple, consistent line icons (24×24 grid, stroke-based). Rendered
inline as SVG so they inherit `currentColor` and stay crisp at any size.
"""

from __future__ import annotations

import streamlit as st


# ── Icons ──────────────────────────────────────────────────────────────────────
# A small, consistent line-icon set. Keys are stable identifiers; values are
# the inner SVG markup (paths drawn on a 24×24 grid).

_ICONS: dict[str, str] = {
    # Brand
    "dumbbell": (
        '<path d="M6.5 6.5v11M17.5 6.5v11"/>'
        '<path d="M4 9.5v5M20 9.5v5"/>'
        '<path d="M6.5 12h11"/>'
    ),
    # Navigation
    "home": (
        '<path d="M3 10.5 12 3l9 7.5"/>'
        '<path d="M5.5 9.5V20a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1V9.5"/>'
        '<path d="M9.75 21v-6h4.5v6"/>'
    ),
    "workout": (
        '<path d="M6.5 6.5v11M17.5 6.5v11"/>'
        '<path d="M4 9.5v5M20 9.5v5"/>'
        '<path d="M6.5 12h11"/>'
    ),
    "library": (
        '<path d="M12 6.5C10.5 5 8.5 4.5 4 4.5v13c4.5 0 6.5.5 8 2 1.5-1.5 3.5-2 8-2v-13c-4.5 0-6.5.5-8 2z"/>'
        '<path d="M12 6.5v13"/>'
    ),
    "trainer": (
        '<rect x="6" y="6" width="12" height="12" rx="2"/>'
        '<rect x="9.5" y="9.5" width="5" height="5" rx="1"/>'
        '<path d="M9 3v3M15 3v3M9 18v3M15 18v3M3 9h3M3 15h3M18 9h3M18 15h3"/>'
    ),
    "diet": (
        '<path d="M6 3v4M9 3v4M12 3v4"/>'
        '<path d="M6 7a3 3 0 0 0 6 0"/>'
        '<path d="M9 10v11"/>'
        '<path d="M17.5 3v18"/>'
        '<path d="M17.5 3c-1.8 1.8-2.5 4-2.5 6 0 1.4.8 2.2 2.5 2.4"/>'
    ),
    "meal": (
        '<path d="M9 4.5H7.5A1.5 1.5 0 0 0 6 6v13a1.5 1.5 0 0 0 1.5 1.5h9A1.5 1.5 0 0 0 18 19V6a1.5 1.5 0 0 0-1.5-1.5H15"/>'
        '<rect x="9" y="2.5" width="6" height="4" rx="1.2"/>'
        '<path d="M9 11h6M9 15h4"/>'
    ),
    "calories": (
        '<path d="M12 21.5c3.6 0 6-2.4 6-5.5 0-4-4-5-4-9 0 0-1.2 1-1.8 2.8C11 8.4 10.4 7 10.4 5.5 8 7.6 6 10.2 6 14c0 3.6 2.4 7.5 6 7.5z"/>'
    ),
    "progress": (
        '<path d="M3 17l6-6 4 4 8-8"/>'
        '<path d="M15 7h6v6"/>'
    ),
    "buddy": (
        '<path d="M4.5 7A2.5 2.5 0 0 1 7 4.5h10A2.5 2.5 0 0 1 19.5 7v6A2.5 2.5 0 0 1 17 15.5H10l-4 4v-4H7A2.5 2.5 0 0 1 4.5 13z"/>'
    ),
    "profile": (
        '<circle cx="12" cy="8" r="3.5"/>'
        '<path d="M4.5 20.5c0-3.6 3.4-5.5 7.5-5.5s7.5 1.9 7.5 5.5"/>'
    ),
    "settings": (
        '<path d="M10.3 3.2a1.8 1.8 0 0 1 3.4 0l.3 1.4a7 7 0 0 1 1.9.8l1.3-.6a1.8 1.8 0 0 1 2.4 2.4l-.6 1.3c.3.6.6 1.2.8 1.9l1.4.3a1.8 1.8 0 0 1 0 3.4l-1.4.3a7 7 0 0 1-.8 1.9l.6 1.3a1.8 1.8 0 0 1-2.4 2.4l-1.3-.6a7 7 0 0 1-1.9.8l-.3 1.4a1.8 1.8 0 0 1-3.4 0l-.3-1.4a7 7 0 0 1-1.9-.8l-1.3.6a1.8 1.8 0 0 1-2.4-2.4l.6-1.3a7 7 0 0 1-.8-1.9l-1.4-.3a1.8 1.8 0 0 1 0-3.4l1.4-.3a7 7 0 0 1 .8-1.9l-.6-1.3a1.8 1.8 0 0 1 2.4-2.4l1.3.6a7 7 0 0 1 1.9-.8z"/>'
        '<circle cx="12" cy="12" r="3"/>'
    ),
    "about": (
        '<circle cx="12" cy="12" r="9"/>'
        '<path d="M12 11v5.5"/>'
        '<path d="M12 7.6h.01"/>'
    ),
    # Actions & chrome
    "play": '<path d="M8 5.5 18.5 12 8 18.5z"/>',
    "arrow-right": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "chevron-right": '<path d="M9.5 5.5 16 12l-6.5 6.5"/>',
    "chevron-down": '<path d="M6 9.5l6 6 6-6"/>',
    "calendar": (
        '<rect x="5" y="6.5" width="14" height="14" rx="1.8"/>'
        '<path d="M5 10.5h14M9 3v4M15 3v4"/>'
    ),
    "clock": (
        '<circle cx="12" cy="12" r="8.5"/>'
        '<path d="M12 7.5V12l3.2 2"/>'
    ),
    "flame": (
        '<path d="M12 21.5c3.6 0 6-2.4 6-5.5 0-4-4-5-4-9 0 0-1.2 1-1.8 2.8C11 8.4 10.4 7 10.4 5.5 8 7.6 6 10.2 6 14c0 3.6 2.4 7.5 6 7.5z"/>'
    ),
    "target": (
        '<circle cx="12" cy="12" r="8.5"/>'
        '<circle cx="12" cy="12" r="4.8"/>'
        '<circle cx="12" cy="12" r="1.4"/>'
    ),
    "check": '<path d="M5 12.5 10 17.5 19 7"/>',
    "circle": '<circle cx="12" cy="12" r="8.2"/><circle cx="12" cy="12" r="3.2"/>',
    "bell": (
        '<path d="M18 15.5V10a6 6 0 1 0-12 0v5.5L4.5 18.5h15z"/>'
        '<path d="M9.6 18.5a2.6 2.6 0 0 0 4.8 0"/>'
    ),
    "trend": (
        '<path d="M3 17l6-6 4 4 8-8"/>'
        '<path d="M15 7h6v6"/>'
    ),
}


def icon(name: str, *, size: int | None = None, cls: str = "") -> str:
    """Return an inline SVG for a named line icon.

    Icons inherit `currentColor`, so the surrounding element's text color
    controls the stroke. `size` overrides the CSS-driven width/height.
    """
    body = _ICONS.get(name)
    if body is None:
        return ""
    style = f' style="width:{size}px;height:{size}px"' if size else ""
    klass = f' class="{cls}"' if cls else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
        f'stroke-linejoin="round"{style}{klass} aria-hidden="true" focusable="false">'
        f"{body}</svg>"
    )


def gap(height: float = 0.85) -> None:
    """Render a standalone spacer block (tight, even vertical rhythm)."""
    st.markdown(f'<div class="app-gap" style="height:{height}rem"></div>', unsafe_allow_html=True)


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


def link_action(label: str, on_click: callable, *, key: str) -> None:
    """Render a quiet text-link action (e.g. 'View history →')."""
    st.markdown('<div class="link-btn"></div>', unsafe_allow_html=True)
    if st.button(label, key=key, type="tertiary", on_click=on_click):
        pass


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


# ── Dashboard pieces (Home) ───────────────────────────────────────────────────

def brand_block() -> None:
    """FIT-AI brand treatment: small fitness icon + wordmark."""
    st.markdown(
        f'<div class="brand"><div class="brand-mark">{icon("dumbbell")}</div>'
        '<span class="brand-name">FIT-AI</span></div>',
        unsafe_allow_html=True,
    )


def nav_group_label(text: str) -> None:
    """Small uppercase navigation group label (HOME / TRAINING / …)."""
    st.markdown(f'<div class="nav-group-label">{text}</div>', unsafe_allow_html=True)


def nav_group_separator() -> None:
    """Hairline separating the main navigation from the account group."""
    st.markdown('<hr class="nav-group-sep"/>', unsafe_allow_html=True)


def greeting_header(greeting: str, subline: str, date_label: str, quote: str = "Keep going! Small steps make big results.") -> None:
    """Dashboard greeting: headline + subline left, current date + quote right."""
    st.markdown(
        '<div class="greeting-row">'
        f'<div><div class="page-head-title">{greeting}</div>'
        f'<div class="page-head-sub">{subline}</div></div>'
        f'<div class="greeting-right">'
        f'<div class="greeting-date">{icon("calendar")}<span>{date_label}</span></div>'
        f'<div class="greeting-quote">{quote}</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def action_card(
    title: str,
    subtitle: str,
    icon_name: str,
    *,
    variant: str,
    key: str,
    on_click: callable,
) -> None:
    """One primary/secondary dashboard action card (fully clickable)."""
    st.markdown(
        f'<div class="action-card-wrapper">'
        f'<div class="action-card action-card--{variant}">'
        f'<div class="action-ico">{icon(icon_name)}</div>'
        f'<div class="action-card-text">'
        f'<div class="action-title">{title}</div>'
        f'<div class="action-sub">{subtitle}</div>'
        '</div></div></div>',
        unsafe_allow_html=True,
    )
    st.button(title, key=key, on_click=on_click)


def stat_strip(tiles: list[dict]) -> None:
    """Compact horizontal statistics bar.

    Each tile: {label, value, hint?, icon?, tone?, progress?} where progress
    is a 0–1 fraction for the calorie-style bar.
    """
    cells = []
    for tile in tiles:
        tone = tile.get("tone", "green")
        icon_html = (
            f'<div class="stat-tile-ico stat-tile-ico--{tone}">{icon(tile.get("icon", "trend"))}</div>'
            if tile.get("icon")
            else ""
        )
        hint_html = f'<div class="stat-tile-hint">{tile["hint"]}</div>' if tile.get("hint") else ""
        bar = ""
        if tile.get("progress") is not None:
            pct = max(0, min(100, round(float(tile["progress"]) * 100)))
            bar = f'<div class="stat-bar"><div style="width:{pct}%"></div></div>'
        cells.append(
            f'<div class="stat-tile">{icon_html}'
            f'<div class="stat-tile-body">'
            f'<div class="stat-tile-label">{tile.get("label", "")}</div>'
            f'<div class="stat-tile-value">{tile.get("value", "")}</div>'
            f"{hint_html}{bar}</div></div>"
        )
    st.markdown(f'<div class="stat-strip">{"".join(cells)}</div>', unsafe_allow_html=True)


def panel_header(title: str, subtitle: str | None = None,
                 action_label: str | None = None, action_key: str | None = None,
                 on_action: callable | None = None) -> None:
    """Panel heading with optional supporting line and right-aligned action."""
    head = st.columns([2.7, 1.5], gap="small")
    with head[0]:
        sub_html = f'<div class="panel-sub">{subtitle}</div>' if subtitle else ""
        st.markdown(f'<div><div class="panel-title">{title}</div>{sub_html}</div>', unsafe_allow_html=True)
    with head[1]:
        if action_label and action_key and on_action:
            link_action(action_label, on_action, key=action_key)


def quick_tile(
    title: str,
    subtitle: str,
    icon_name: str,
    *,
    tone: str = "green",
    key: str,
    on_click: callable,
) -> None:
    """One Quick Access tile (fully clickable)."""
    st.markdown(
        f'<div class="quick-tile-wrapper">'
        f'<div class="quick-tile">'
        f'<div class="quick-ico quick-ico--{tone}">{icon(icon_name)}</div>'
        f'<div class="quick-body"><div class="quick-title">{title}</div>'
        f'<div class="quick-sub">{subtitle}</div></div>'
        f'<div class="quick-chevron">{icon("chevron-right")}</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )
    st.button(title, key=key, on_click=on_click)


def activity_list(rows: list[dict], empty_title: str, empty_desc: str) -> None:
    """Recent activity rows: {title, sub, icon?, tone?} newest first."""
    if not rows:
        empty_state(empty_title, empty_desc)
        return
    cells = []
    for row in rows:
        tone = row.get("tone", "green")
        cells.append(
            f'<div class="activity-row">'
            f'<div class="activity-ico quick-ico--{tone}">{icon(row.get("icon", "clock"))}</div>'
            f'<div class="activity-body"><div class="activity-title">{row.get("title", "")}</div>'
            f'<div class="activity-sub">{row.get("sub", "")}</div></div>'
            f'<div class="activity-chevron">{icon("chevron-right")}</div>'
            "</div>"
        )
    st.markdown(f'<div class="activity-list">{"".join(cells)}</div>', unsafe_allow_html=True)


def goal_list(rows: list[dict], empty_title: str, empty_desc: str) -> None:
    """Goal rows: {label, value, hint?, icon?, tone?, progress?}."""
    if not rows:
        empty_state(empty_title, empty_desc)
        return
    cells = []
    for row in rows:
        tone = row.get("tone", "green")
        bar = ""
        if row.get("progress") is not None:
            pct = max(0, min(100, round(float(row["progress"]) * 100)))
            bar = f'<div class="stat-bar"><div style="width:{pct}%"></div></div>'
        hint_html = f'<div class="goal-hint">{row["hint"]}</div>' if row.get("hint") else ""
        cells.append(
            f'<div class="goal-row"><div class="goal-head">'
            f'<div class="goal-ico quick-ico--{tone}">{icon(row.get("icon", "target"))}</div>'
            f'<div class="goal-label">{row.get("label", "")}</div>'
            f'<div class="goal-value">{row.get("value", "")}</div></div>'
            f"{bar}{hint_html}</div>"
        )
    st.markdown(f'<div class="goal-list">{"".join(cells)}</div>', unsafe_allow_html=True)


def home_hero(greeting: str, subline: str, quote: str, image_path: str = "assets/hero.jpg") -> None:
    """Premium welcome hero for Home: soft green gradient card, photo on the
    right with a fade, quote chip. Action buttons are rendered separately
    directly below inside the same visual card."""
    import base64
    from pathlib import Path

    path = Path(__file__).resolve().parent / image_path
    try:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        photo = f'<img src="data:image/jpeg;base64,{encoded}" alt="" class="home-hero-photo"/>'
    except OSError:
        photo = ""
    st.markdown(
        '<div class="home-hero">'
        '<div class="home-hero-eyebrow">Welcome back</div>'
        f'<div class="home-hero-title">{greeting}</div>'
        f'<div class="home-hero-sub">{subline}</div>'
        f'{photo}'
        f'<div class="home-hero-quote">&ldquo;{quote}&rdquo;</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def home_today(date_label: str, rows: list[dict]) -> None:
    """Today checklist card: date header plus real status rows.

    rows: {label, done, hint?} — done states come from stored data only.
    """
    cells = []
    for row in rows:
        done = bool(row.get("done"))
        state_cls = "home-today-ico--done" if done else "home-today-ico--todo"
        hint = f'<span class="home-today-hint">{row["hint"]}</span>' if row.get("hint") else ""
        cells.append(
            '<div class="home-today-row">'
            f'<div class="home-today-ico {state_cls}">{icon("check" if done else "circle")}</div>'
            f'<div class="home-today-label">{row.get("label", "")}</div>'
            f'{hint}</div>'
        )
    st.markdown(
        '<div class="home-today">'
        f'<div class="home-today-head">{icon("calendar")}<span class="home-today-title">Today</span>'
        f'<span class="home-today-date">{date_label}</span></div>'
        f'{"".join(cells)}</div>',
        unsafe_allow_html=True,
    )


def feature_tile(
    title: str,
    subtitle: str,
    icon_name: str,
    *,
    tone: str = "green",
    key: str,
    on_click: callable,
    meta: str = "",
) -> None:
    """One journey/nutrition shortcut tile (fully clickable, optional meta)."""
    meta_html = f'<div class="feature-meta">{meta}</div>' if meta else ""
    st.markdown(
        f'<div class="feature-tile-wrapper">'
        f'<div class="feature-tile feature-tile--{tone}">'
        f'<div class="feature-ico feature-ico--{tone}">{icon(icon_name)}</div>'
        f'<div class="feature-body"><div class="feature-title">{title}</div>'
        f'<div class="feature-sub">{subtitle}</div>{meta_html}</div>'
        f'<div class="feature-arrow">{icon("chevron-right")}</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )
    st.button(title, key=key, on_click=on_click)


def motivation_banner(title: str, subtitle: str, quote: str, image_path: str = "assets/hero.jpg") -> None:
    """Restrained fitness banner using an existing local asset."""
    import base64
    from pathlib import Path

    path = Path(__file__).resolve().parent / image_path
    try:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        image = f'<img src="data:image/jpeg;base64,{encoded}" alt="" class="motivation-img"/>'
    except OSError:
        image = ""
    st.markdown(
        f'<div class="motivation-banner">'
        f'{image}'
        f'<div class="motivation-overlay"></div>'
        f'<div class="motivation-inner">'
        f'<div class="motivation-left">'
        f'<div class="motivation-accent-bar"></div>'
        f'<div>'
        f'<div class="motivation-title">{title}</div>'
        f'<div class="motivation-sub">{subtitle}</div>'
        '</div>'
        '</div>'
        f'<div class="motivation-quote-box">&ldquo;{quote}&rdquo;</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )


def sidebar_user_profile(name: str, on_view_profile: callable) -> None:
    """Professional profile section at the bottom of the sidebar."""
    initials = (name[:2].upper() if name else "M")
    st.markdown(
        f'<div class="sidebar-user">'
        f'<div class="sidebar-avatar">{initials}</div>'
        f'<div class="sidebar-user-info">'
        f'<div class="sidebar-user-name">{name or "Manu"}</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )
    if st.button("View profile →", key="sidebar_view_profile", type="tertiary"):
        on_view_profile()
