"""
Shared helpers for the FIT-AI test suite.

Tests run without a Streamlit server: the app modules import cleanly in bare
mode (no ScriptRunContext), and Mongo-touching paths are either not exercised
or given a fake session_state.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parent.parent / "AI_Gym_Project"
sys.path.insert(0, str(APP_DIR))


@pytest.fixture()
def session_state(monkeypatch):
    """Provide a dict-backed stand-in for st.session_state."""
    import streamlit as st

    store: dict = {}  # dict.get already matches the session_state API

    class _SS:
        def __getattr__(self, name):
            try:
                return store[name]
            except KeyError:
                raise AttributeError(name)

        def __setattr__(self, name, value):
            store[name] = value

        def __getitem__(self, name):
            return store[name]

        def __setitem__(self, name, value):
            store[name] = value

        def get(self, name, default=None):
            return store.get(name, default)

        def setdefault(self, name, default=None):
            return store.setdefault(name, default)

        def pop(self, name, *default):
            return store.pop(name, *default)

        def __contains__(self, name):
            return name in store

        def __delitem__(self, name):
            del store[name]

    st.session_state = _SS()
    yield store
