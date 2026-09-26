"""Storage degradation: the app must work (read-only) without MongoDB."""

from __future__ import annotations

import storage


def test_normalize_user_id_basic():
    assert storage.normalize_user_id("Manoj Kumar 12") == "manoj-kumar-12"


def test_normalize_user_id_strips_and_collapses():
    assert storage.normalize_user_id("  --A__B--  ") == "a-b"
    assert storage.normalize_user_id("!!!") == "guest"


def test_default_user_state_shape():
    state = storage._default_user_state("someone")
    assert state["user_id"] == "someone"
    assert state["habit"]["streak_days"] == 0
    assert state["diet"]["calorie_goal"] == 2000
    assert state["gym"]["workout_plan_history"] == []


def test_merge_defaults_preserves_new_unknown_keys():
    defaults = {"a": 1, "nested": {"x": 1}}
    loaded = {"a": 2, "nested": {"y": 9}, "future_key": {"unseen": True}}
    merged = storage._merge_defaults(defaults, loaded)
    assert merged["a"] == 2
    assert merged["nested"] == {"x": 1, "y": 9}
    assert merged["future_key"] == {"unseen": True}


def test_routine_and_session_helpers_fail_soft_without_db(monkeypatch):
    monkeypatch.setattr(storage, "get_routines_collection", lambda: None)
    assert storage.list_routines("u") == []
    assert storage.save_routine("u", {"name": "X", "days": []}) is None
    assert storage.delete_routine("u", "000000000000000000000000") is False
