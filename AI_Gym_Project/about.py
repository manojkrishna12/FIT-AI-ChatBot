"""
About page — what FitAI is, how it works, and the tech behind it.
Includes the attribution required by the RepDB free-tier license
(see docs/LICENSES.md).
"""

from __future__ import annotations

import streamlit as st


def render_about_page() -> None:
    """Render the About page."""
    st.markdown(
        """
        <div class="stub-card">
          <div class="stub-title">FitAI — AI Fitness Platform</div>
          <div class="stub-desc">
            FitAI is an AI-powered fitness platform: real-time exercise coaching with
            MediaPipe pose analysis, an AI nutritionist powered by Google Gemini, and a
            companion that keeps you consistent.
          </div>
          <div class="stub-list">
            <div>•&nbsp; Built with Streamlit · MediaPipe BlazePose · Google Gemini · MongoDB</div>
            <div>•&nbsp; Rep counting uses a joint-angle state machine over 33 pose landmarks</div>
            <div>•&nbsp; Diet plans are validated for allergies and macro targets, with a deterministic fallback engine</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("")
    st.markdown("### Credits & licenses")
    st.markdown(
        "Exercise data by [RepDB (repdb.co)](https://repdb.co/) — used under the "
        "RepDB free-tier license. See [docs/LICENSES.md](https://github.com/manojkrishna12/FIT-AI-ChatBot/blob/develop/docs/LICENSES.md) "
        "for the full license text and compliance notes."
    )
    st.caption("Version 2.0 — development build")
