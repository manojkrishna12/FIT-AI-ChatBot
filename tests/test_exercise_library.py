"""Exercise Library helper logic (no MongoDB required)."""

from __future__ import annotations

import exercise_library as lib


def test_display_turns_slugs_into_labels():
    assert lib._display("pull_up_bar") == "Pull Up Bar"
    assert lib._display("bodyweight") == "Bodyweight"
    assert lib._display("") == ""


def test_facets_collect_sorted_unique_values():
    docs = [
        {"body_part": "chest", "equipment": "barbell", "difficulty": "beginner"},
        {"body_part": "back", "equipment": None, "difficulty": "advanced"},
        {"body_part": "chest", "equipment": "dumbbell", "difficulty": "beginner"},
    ]
    facets = lib._facets(docs)
    assert facets["body_part"] == ["back", "chest"]
    assert facets["equipment"] == ["barbell", "bodyweight", "dumbbell"]
    assert facets["difficulty"] == ["advanced", "beginner"]


def test_filters_combine():
    docs = [
        {"name_en": "Squat", "search_text": "squat quads", "body_part": "upper_legs", "equipment": "barbell", "difficulty": "intermediate"},
        {"name_en": "Push-up", "search_text": "push chest", "body_part": "chest", "equipment": "bodyweight", "difficulty": "beginner"},
        {"name_en": "Bench Press", "search_text": "bench chest", "body_part": "chest", "equipment": "barbell", "difficulty": "beginner"},
    ]
    assert len(lib._apply_filters(docs, "", "All", "All", "All")) == 3
    assert len(lib._apply_filters(docs, "chest", "All", "All", "All")) == 2
    chest = lib._apply_filters(docs, "", "chest", "All", "All")
    assert len(chest) == 2
    barbell_chest = lib._apply_filters(docs, "", "chest", "barbell", "All")
    assert [d["name_en"] for d in barbell_chest] == ["Bench Press"]
    beginner_chest = lib._apply_filters(docs, "", "chest", "All", "beginner")
    assert [d["name_en"] for d in beginner_chest] == ["Push-up", "Bench Press"]
    assert lib._apply_filters(docs, "zzz-no-match", "All", "All", "All") == []
