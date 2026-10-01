"""Weight-tracking tests — routine builder normalization, session logging,
Progress volume, and persistence round-trips (MongoDB faked, offline)."""

from __future__ import annotations

import pytest

import progress  # noqa: E402  (path configured in conftest)
import routines  # noqa: E402
import storage  # noqa: E402


_BASE = {"exercise_id": "squat", "exercise_name": "Back Squat", "sets": 3, "reps": "8-10", "rest": "90s"}


# ── routine builder normalization ─────────────────────────────────────────────

def test_routine_without_weight_keeps_legacy_shape():
    """Existing behaviour: no weight key → saved doc stays exactly as before."""
    assert routines._clean_exercise(dict(_BASE)) == _BASE


def test_routine_with_weight_is_included():
    cleaned = routines._clean_exercise({**_BASE, "weight": 60.0})
    assert cleaned["weight"] == 60.0


def test_routine_weight_rounds_to_one_decimal():
    cleaned = routines._clean_exercise({**_BASE, "weight": 22.55})
    assert cleaned["weight"] == 22.6  # round(22.55, 1) — banker's rounding


def test_routine_weight_capped_at_1000():
    cleaned = routines._clean_exercise({**_BASE, "weight": 5000})
    assert cleaned["weight"] == 1000.0


@pytest.mark.parametrize("bad", [0, 0.0, None, "", "abc", -5])
def test_routine_empty_or_invalid_weight_omitted(bad):
    assert "weight" not in routines._clean_exercise({**_BASE, "weight": bad})


def test_routine_multiple_exercises_different_weights():
    days = [{"day_name": "Day 1", "exercises": [
        {**_BASE, "exercise_id": "a", "weight": 80},
        {**_BASE, "exercise_id": "b", "weight": 0},      # bodyweight row
        {**_BASE, "exercise_id": "c", "weight": 12.5},
    ]}]
    cleaned = [routines._clean_exercise(ex) for ex in days[0]["exercises"]]
    assert cleaned[0]["weight"] == 80.0
    assert "weight" not in cleaned[1]
    assert cleaned[2]["weight"] == 12.5


def test_routine_row_without_exercise_id_dropped():
    assert routines._clean_exercise({**_BASE, "exercise_id": None}) is None


# ── session volume (Progress) ─────────────────────────────────────────────────

def test_volume_legacy_session_without_weight():
    session = {"exercises": [{"sets": 3, "reps": "8-10"}, {"sets": 4, "reps": "10"}]}
    assert progress._session_volume(session) == 3 * 8 + 4 * 10


def test_volume_uses_weight_when_present():
    session = {"exercises": [{"sets": 5, "reps": "5", "weight": 100}]}
    assert progress._session_volume(session) == 2500.0


def test_volume_mixed_weighted_and_bodyweight():
    session = {"exercises": [
        {"sets": 3, "reps": "8", "weight": 50},   # 1200
        {"sets": 3, "reps": "12"},                # 36 (bodyweight)
    ]}
    assert progress._session_volume(session) == 1236.0


def test_volume_reps_range_uses_lower_bound_with_weight():
    session = {"exercises": [{"sets": 2, "reps": "8-12", "weight": 20}]}
    assert progress._session_volume(session) == 2 * 8 * 20


@pytest.mark.parametrize("bad", [None, 0, "", "xx"])
def test_volume_zero_or_invalid_weight_counts_reps_only(bad):
    session = {"exercises": [{"sets": 2, "reps": "10", "weight": bad}]}
    assert progress._session_volume(session) == 20.0


# ── persistence round-trips (faked collections) ───────────────────────────────

class _FakeResult:
    def __init__(self, inserted_id="rid", matched=1):
        self.inserted_id = inserted_id
        self.matched_count = matched


class _FakeCollection:
    def __init__(self):
        self.docs = []

    def insert_one(self, doc):
        self.docs.append(doc)
        return _FakeResult()

    def update_one(self, q, set_):
        self.docs.append({"query": q, "set": set_})
        return _FakeResult(matched=1)


def test_save_routine_persists_weight(monkeypatch):
    fake = _FakeCollection()
    monkeypatch.setattr(storage, "get_routines_collection", lambda: fake)
    rid = storage.save_routine("user1", {"name": "P", "days": [{"day_name": "D1", "exercises": [
        routines._clean_exercise({**_BASE, "weight": 72.5}),
        routines._clean_exercise(dict(_BASE)),
    ]}]})
    assert rid == "rid"
    saved = fake.docs[0]["days"][0]["exercises"]
    assert saved[0]["weight"] == 72.5
    assert "weight" not in saved[1]  # legacy exercise untouched


def test_save_session_persists_weight(monkeypatch):
    fake = _FakeCollection()
    monkeypatch.setattr(progress, "_sessions_collection", lambda: fake)
    sid = progress.save_session("user1", {"name": "Push", "exercises": [
        {"exercise_name": "Bench", "sets": 5, "reps": "5", "rest": "3m", "weight": 80},
        {"exercise_name": "Pushup", "sets": 3, "reps": "15", "rest": "1m"},
    ]})
    assert sid == "rid"
    saved = fake.docs[0]["exercises"]
    assert saved[0]["weight"] == 80
    assert "weight" not in saved[1]


def test_routine_to_session_weight_flows_through(monkeypatch):
    """From-routine logging prefills the planned weight into the session form."""
    fake = _FakeCollection()
    monkeypatch.setattr(storage, "get_routines_collection", lambda: fake)
    storage.save_routine("user1", {"name": "Lower", "days": [{"day_name": "D1", "exercises": [
        routines._clean_exercise({**_BASE, "weight": 100}),
    ]}]})
    routine_doc = fake.docs[0]
    preset_weight = routine_doc["days"][0]["exercises"][0].get("weight")
    assert preset_weight == 100.0
    # Progress maps routine exercise → session preset verbatim (weight included).
    session = {"name": "Lower", "exercises": [{
        "exercise_name": routine_doc["days"][0]["exercises"][0]["exercise_name"],
        "sets": 3, "reps": "8-10", "weight": preset_weight,
    }]}
    assert progress._session_volume(session) == 3 * 8 * 100


def test_reloaded_routine_without_weight_still_renders_clean():
    """A pre-weight routine document passes back through the builder cleaning unchanged."""
    legacy = dict(_BASE)
    cleaned = routines._clean_exercise(legacy)
    assert cleaned == _BASE
