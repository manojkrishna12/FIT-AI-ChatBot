"""
Exercise Library — browse the curated exercise catalog.

Data source: RepDB free tier (see docs/LICENSES.md), seeded into MongoDB by
scripts/seed_exercises.py. All displayed content comes verbatim from the
dataset; nothing is fabricated here.
"""

from __future__ import annotations

import io

import streamlit as st

from constants import (
    EXERCISE_DB_COLLECTION,
    REPDB_IMAGES_BASE_URL,
    REPDB_ATTRIBUTION,
)
from m import page_header
from storage import get_exercise_images_bucket

_PAGE_SIZE = 24


def _display(label: str) -> str:
    """Turn dataset slugs like 'pull_up_bar' into 'Pull Up Bar'."""
    return (label or "").replace("_", " ").title()


@st.cache_data(ttl=3600, show_spinner=False)
def _image_data_uri(filename: str) -> str | None:
    """Load an exercise image from GridFS and return a data URI (cached)."""
    bucket = get_exercise_images_bucket()
    if bucket is None:
        return None
    try:
        data = bucket.get_last_version(filename).read()
    except Exception:
        return None
    try:
        from PIL import Image

        im = Image.open(io.BytesIO(data))
        im.thumbnail((512, 512))
        buf = io.BytesIO()
        im.save(buf, format="WEBP", quality=80)
        return "data:image/webp;base64," + __import__("base64").b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return None


def _image_html(filename: str | None) -> str:
    """Return an <img> tag for a GridFS image, with a URL fallback for missing ones."""
    if filename:
        uri = _image_data_uri(filename)
        if uri:
            return f'<img src="{uri}" alt="" loading="lazy"/>'
        if filename:
            url = REPDB_IMAGES_BASE_URL + filename
            return (
                f'<img src="{url}" alt="" loading="lazy" '
                f'onerror="this.style.display=\'none\'" style="background:#101828"/>'
            )
    return '<div class="media-fallback">🏋️</div>'


def _load_catalog() -> list[dict]:
    from storage import get_exercises_collection

    coll = get_exercises_collection()
    if coll is None:
        return []
    try:
        docs = list(
            coll.find(
                {},
                {
                    "_id": 1,
                    "name_en": 1,
                    "category": 1,
                    "difficulty": 1,
                    "equipment": 1,
                    "body_part": 1,
                    "primary_muscles": 1,
                    "force_type": 1,
                    "mechanic": 1,
                    "met": 1,
                    "images": 1,
                    "search_text": 1,
                },
            )
        )
    except Exception:
        return []
    docs.sort(key=lambda d: d.get("name_en", ""))
    return docs


def _facets(docs: list[dict]) -> dict[str, list[str]]:
    """Collect sorted facet values from the catalog."""
    facets: dict[str, set[str]] = {"body_part": set(), "equipment": set(), "difficulty": set()}
    for d in docs:
        if d.get("body_part"):
            facets["body_part"].add(d["body_part"])
        facets["equipment"].add(d.get("equipment") or "bodyweight")
        if d.get("difficulty"):
            facets["difficulty"].add(d["difficulty"])
    return {k: sorted(v) for k, v in facets.items()}


def _apply_filters(docs, query, body_part, equipment, difficulty):
    out = docs
    if query:
        q = query.lower().strip()
        out = [d for d in out if q in d.get("search_text", "") or q in d.get("name_en", "").lower()]
    if body_part != "All":
        out = [d for d in out if d.get("body_part") == body_part]
    if equipment != "All":
        out = [d for d in out if (d.get("equipment") or "bodyweight") == equipment]
    if difficulty != "All":
        out = [d for d in out if d.get("difficulty") == difficulty]
    return out


def _render_card(doc: dict) -> None:
    images = doc.get("images") or {}
    first = images.get("start") or images.get("peak") or images.get("main")
    st.markdown(
        f"""
        <div class="ex-card">
          <div class="ex-media">{_image_html(first)}</div>
          <div class="ex-name">{doc.get('name_en', doc.get('_id', ''))}</div>
          <div class="ex-meta">{_display(doc.get('body_part', ''))} · {_display(doc.get('equipment') or 'bodyweight')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Details →", key=f"ex_{doc['_id']}", use_container_width=True):
        st.session_state["exlib_selected"] = doc["_id"]
        st.rerun()


def _render_detail(doc: dict) -> None:
    st.button("← Back to library", key="exlib_back", on_click=lambda: st.session_state.pop("exlib_selected", None))
    images = doc.get("images") or {}
    start = images.get("start")
    peak = images.get("peak")
    main = images.get("main")

    media = _image_html(start or main)
    if peak:
        media += _image_html(peak)
    st.markdown(
        f"""
        <div class="ex-detail-media">{media}</div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader(doc.get("name_en", doc.get("_id", "")))
    meta_bits = [
        _display(doc.get("body_part", "")),
        _display(doc.get("equipment") or "bodyweight"),
        _display(doc.get("difficulty") or ""),
        _display(doc.get("force_type") or ""),
    ]
    st.caption(" · ".join(b for b in meta_bits if b))

    muscles = (doc.get("primary_muscles") or []) + (doc.get("secondary_muscles") or [])
    if muscles:
        st.markdown("**Muscles:** " + ", ".join(_display(m) for m in muscles))
    if doc.get("met"):
        st.caption(f"MET ≈ {doc['met']} (intensity reference from the dataset)")

    desc = doc.get("description_en")
    if desc:
        st.markdown(desc)

    steps = doc.get("instructions_en") or []
    if steps:
        st.markdown("### Instructions")
        for i, step in enumerate(steps, 1):
            st.markdown(f"{i}. {step}")

    tips = doc.get("tips_en") or []
    if tips:
        st.markdown("### Tips")
        for tip in tips:
            st.markdown(f"- {tip}")

    st.caption(f"Source: {REPDB_ATTRIBUTION}. Content shown verbatim from the licensed dataset.")


def render_exercise_library_page() -> None:
    """Entry point called by app.py for the Exercise Library page."""
    page_header(
        "Exercise Library",
        "Curated catalog with images, muscles and equipment — licensed open data",
    )

    docs = _load_catalog()

    if not docs:
        st.info(
            "The exercise catalog is empty. Seed it once with "
            "`python scripts/seed_exercises.py --source <dataset-dir>` "
            "(see docs/LICENSES.md). Browsing requires a running MongoDB."
        )
        return

    st.success(f"{len(docs)} curated exercises · {REPDB_ATTRIBUTION}")
    facets = _facets(docs)

    c1, c2 = st.columns([2, 1])
    with c1:
        query = st.text_input("🔍 Search", placeholder="e.g. squat, curl, hip …", key="exlib_search")
    with c2:
        sort_by = st.selectbox(
            "Sort by",
            ["Name (A–Z)", "Name (Z–A)"],
            key="exlib_sort",
        )

    f1, f2, f3, f4 = st.columns(4)
    with f1:
        body_part = st.selectbox(
            "Body part",
            ["All"] + facets["body_part"],
            format_func=_display,
            key="exlib_bp",
        )
    with f2:
        equipment = st.selectbox(
            "Equipment",
            ["All"] + facets["equipment"],
            format_func=_display,
            key="exlib_eq",
        )
    with f3:
        difficulty = st.selectbox(
            "Difficulty",
            ["All"] + facets["difficulty"],
            format_func=_display,
            key="exlib_diff",
        )
    with f4:
        category = st.selectbox(
            "Category",
            ["All"] + sorted({d.get("category", "") for d in docs if d.get("category")}),
            format_func=_display,
            key="exlib_cat",
        )

    filtered = _apply_filters(docs, query, body_part, equipment, difficulty)
    if category != "All":
        filtered = [d for d in filtered if d.get("category") == category]

    filtered.sort(key=lambda d: d.get("name_en", ""), reverse=(sort_by == "Name (Z–A)"))

    if st.session_state.get("exlib_selected"):
        from storage import get_exercises_collection

        coll = get_exercises_collection()
        selected = coll.find_one({"_id": st.session_state["exlib_selected"]}) if coll is not None else None
        if selected:
            _render_detail(selected)
            return
        st.session_state.pop("exlib_selected", None)

    st.markdown(f"Showing **{len(filtered)}** exercises")
    if not filtered:
        st.info("No exercises match these filters.")
        return

    page = st.session_state.get("exlib_page", 0)
    total_pages = max(1, (len(filtered) + _PAGE_SIZE - 1) // _PAGE_SIZE)
    page = min(page, total_pages - 1)
    start_idx = page * _PAGE_SIZE
    chunk = filtered[start_idx : start_idx + _PAGE_SIZE]

    cols = st.columns(4)
    for i, doc in enumerate(chunk):
        with cols[i % 4]:
            _render_card(doc)

    nav1, nav2, nav3 = st.columns([1, 2, 1])
    with nav1:
        if st.button("← Prev", disabled=page == 0, use_container_width=True):
            st.session_state["exlib_page"] = page - 1
            st.rerun()
    with nav2:
        st.caption(f"Page {page + 1} of {total_pages}")
    with nav3:
        if st.button("Next →", disabled=page >= total_pages - 1, use_container_width=True):
            st.session_state["exlib_page"] = page + 1
            st.rerun()
