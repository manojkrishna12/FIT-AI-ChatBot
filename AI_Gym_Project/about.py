"""
About page — what FitAI is, how it works, and the tech behind it.
Includes the attribution required by the RepDB free-tier license
(see docs/LICENSES.md).
"""

from __future__ import annotations

import streamlit as st

from m import page_header, section_header


_TECH_FACTS = [
    "Built with Streamlit · MediaPipe BlazePose · Google Gemini · MongoDB",
    "Rep counting uses a joint-angle state machine over 33 pose landmarks",
    "Diet plans are validated for allergies and macro targets, with a deterministic fallback engine",
]


def render_about_page() -> None:
    """Render the About page."""
    page_header(
        "About",
        "What FitAI is and how it works",
    )

    st.markdown(
        """
        <div class="about-lede">
          FitAI is an AI fitness platform: real-time exercise coaching with MediaPipe
          pose analysis, an AI nutritionist powered by Google Gemini, and a companion
          that keeps you consistent.
        </div>
        """,
        unsafe_allow_html=True,
    )

    section_header("Technology")
    for fact in _TECH_FACTS:
        st.markdown(f"- {fact}")

    section_header("Credits & licenses")
    st.markdown(
        "Exercise data by [RepDB (repdb.co)](https://repdb.co/) — used under the "
        "RepDB free-tier license. See [docs/LICENSES.md]"
        "(https://github.com/manojkrishna12/FIT-AI-ChatBot/blob/develop/docs/LICENSES.md) "
        "for the full license text and compliance notes."
    )
    st.caption("Version 2.0 — development build")
