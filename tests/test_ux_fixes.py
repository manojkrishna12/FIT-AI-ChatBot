"""Targeted tests for the consolidated UX fixes.

Covers: workout-logging freshness, routine per-set rows (creator + detail),
the AI Gym Trainer tab set, the Workout Planner's new home, the Grocery List
removal from Nutrition, and the profile display-name reuse.
"""

from __future__ import annotations

import inspect

import app  # noqa: E402  (path configured in conftest)
import diet  # noqa: E402
import exercise_library  # noqa: E402
import gym_trainer  # noqa: E402
import nutrition  # noqa: E402
import profile_page  # noqa: E402
import progress  # noqa: E402
import routines  # noqa: E402


# ── new workout logs start clean ──────────────────────────────────────────────

def test_log_attempt_starts_at_zero(session_state):
    assert progress._log_attempt() == 0


def test_saving_a_log_bumps_the_attempt(session_state):
    """Bumping the attempt re-keys every widget, so nothing is carried over."""
    progress._bump_log_attempt()
    progress._bump_log_attempt()
    assert progress._log_attempt() == 2


def test_log_widget_keys_include_the_attempt():
    source = inspect.getsource(progress._render_session_editor)
    assert "_log_attempt()" in source
    assert 'key=f"log_name_{tag}"' in source


# ── routine set rows ─────────────────────────────────────────────────────────

def test_new_exercise_card_starts_with_three_sets(session_state):
    exercise = routines._blank_exercise()
    assert exercise["exercise_id"] is None
    assert len(exercise["set_rows"]) == 3
    assert all("_rid" in row for row in exercise["set_rows"])


def test_set_rows_derive_sets_and_summary_fields():
    exercise = {
        "exercise_id": "squat",
        "exercise_name": "Back Squat",
        "rest": "2m",
        "set_rows": [
            {"weight": 20, "reps": "10"},
            {"weight": 20, "reps": "10"},
            {"weight": 22, "reps": "8"},
        ],
    }
    clean = routines._clean_exercise(exercise)
    assert clean["sets"] == 3
    assert clean["reps"] == "8"        # lowest numeric rep count, matching volume
    assert clean["weight"] == 20.0     # first positive set weight
    assert clean["set_rows"][2]["weight"] == 22.0
    assert "_rid" not in clean["set_rows"][0]


def test_set_rows_survive_as_an_additive_schema():
    """Legacy keys keep their names; per-set detail is additive only."""
    exercise = {
        "exercise_id": "curl",
        "exercise_name": "Curl",
        "rest": "60s",
        "set_rows": [{"weight": 12.5, "reps": "12"}, {"reps": "10"}],
        "note": "slow eccentric",
    }
    clean = routines._clean_exercise(exercise)
    assert clean["set_rows"][0] == {"weight": 12.5, "reps": "12"}
    assert clean["set_rows"][1] == {"reps": "10"}   # bodyweight set, no weight key
    assert clean["note"] == "slow eccentric"
    assert clean["sets"] == 2


def test_legacy_routine_expands_into_set_rows_for_display():
    legacy = {
        "exercise_id": "curl",
        "exercise_name": "Curl",
        "sets": 2,
        "reps": "8-10",
        "rest": "60s",
        "weight": 12.5,
    }
    rows = routines._set_rows_for(legacy)
    assert len(rows) == 2
    assert [row["reps"] for row in rows] == ["8-10", "8-10"]
    assert all(row["weight"] == 12.5 for row in rows)
    # Re-saving a legacy routine without touching it keeps its shape.
    assert routines._clean_exercise(legacy)["weight"] == 12.5


def test_legacy_bodyweight_routine_has_no_weight_rows():
    legacy = {"exercise_id": "pushup", "exercise_name": "Push-up", "sets": 3, "reps": "15", "rest": "45s"}
    rows = routines._set_rows_for(legacy)
    assert len(rows) == 3
    assert all(row.get("weight", 0) == 0 for row in rows)


def test_set_row_summary_drives_session_volume():
    """A routine built with per-set rows still feeds Progress volume."""
    clean = routines._clean_exercise({
        "exercise_id": "squat",
        "exercise_name": "Back Squat",
        "rest": "2m",
        "set_rows": [{"weight": 60, "reps": "8"}, {"weight": 60, "reps": "8"}, {"weight": 60, "reps": "8"}],
    })
    session = {"exercises": [
        {"sets": clean["sets"], "reps": clean["reps"], "weight": clean["weight"]},
    ]}
    assert progress._session_volume(session) == 3 * 8 * 60


def test_routine_detail_table_renders_sets():
    table = routines._sets_table([{"weight": 20, "reps": "10"}, {"reps": "8"}])
    assert "set-table" in table
    assert "20 kg" in table
    assert "10" in table and "8" in table
    assert "set-placeholder" in table  # bodyweight set shows a quiet dash


def test_picker_label_includes_body_part():
    assert routines.picker_label({"_id": "squat", "name_en": "Back Squat", "body_part": "upper_legs"}) == (
        "Back Squat (Upper Legs)"
    )


# ── AI Gym Trainer tabs + Workout Planner relocation ─────────────────────────

def test_trainer_tabs_are_exactly_the_three_analysis_modes():
    assert gym_trainer.TRAINER_TABS == ["Image Analysis", "Video Analysis", "Live Webcam"]
    source = inspect.getsource(gym_trainer.render_gym_trainer_page)
    assert "Exercise Database" not in source
    assert "Workout Plan" not in source


def test_video_analysis_keeps_its_rep_counting_body():
    source = inspect.getsource(gym_trainer.render_gym_trainer_page)
    assert 'mode == "Video Analysis"' in source
    assert "process_video" in source


def test_workout_planner_is_rendered_from_the_workouts_page():
    assert callable(gym_trainer.render_workout_planner)
    source = inspect.getsource(routines.render_routines_page)
    assert "_render_ai_planner" in source
    assert "render_workout_planner" in inspect.getsource(routines._render_ai_planner)


# ── Nutrition no longer offers Grocery List ──────────────────────────────────

def test_grocery_list_is_gone_from_nutrition():
    assert "Grocery List" not in app.ROUTES
    assert "grocery_list" not in app.ROUTES.values()
    assert not hasattr(nutrition, "render_grocery_list_page")
    assert "grocery_list" not in diet._NUTRITION_PAGE_LABELS


def test_meal_analyser_stays_text_only():
    source = inspect.getsource(diet._tab2_meal_analyser)
    assert "text_area" in source
    assert "file_uploader" not in source
    assert "camera" not in source.lower()


# ── Profile display name + save → Home ───────────────────────────────────────

def test_profile_reuses_stored_then_account_identity():
    assert profile_page._effective_display_name({"name": "Manoj"}, "Account", "user") == "Manoj"
    assert profile_page._effective_display_name({}, "Account Name", "user") == "Account Name"
    assert profile_page._effective_display_name({}, "", "user") == "user"
    assert profile_page._effective_display_name({}, "", "") == ""


def test_fitness_profile_no_longer_asks_for_a_display_name():
    source = inspect.getsource(profile_page._render_profile_form)
    assert "Display name" in source          # shown as account info only
    assert "text_input(\"Display name\"" not in source
    assert "save_profile(" in source
    assert '"_navigate_to"' in source and '"Home"' in source


# ── Exercise Library shared image helper ─────────────────────────────────────

def test_exercise_library_exposes_public_image_helper():
    assert exercise_library.image_html is exercise_library._image_html
    assert 'class="media-fallback"' in exercise_library.image_html(None)
