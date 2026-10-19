"""Diet tools: compute_daily_targets, meal normalization, and tracker goal logic.

All Gemini calls are mocked; MongoDB is not required.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "AI_Gym_Project"))

import diet  # noqa: E402


# ── compute_daily_targets (Issue 3) ─────────────────────────────────────

PROFILE = {
    "age": 25,
    "gender": "Male",
    "weight_kg": 70.0,
    "height_cm": 175.0,
    "activity": "Moderately Active",
    "goal": "Weight Loss",
}


def test_targets_are_personal_not_hardcoded():
    calories, macros = diet.compute_daily_targets(PROFILE)
    # Mifflin-St Jeor for this profile: BMR = 10*70 + 6.25*175 - 5*25 + 5 = 1648.75
    # TDEE = 1648.75 * 1.55 = 2594 (app formula); Weight Loss offset -500 → 2094
    assert calories == 2094
    assert calories != 2000  # must be personal, not the hardcoded default
    assert macros["Protein (g)"] == 126  # 1.8 g/kg for weight loss
    assert macros["Fat (g)"] == int(2094 * 0.25 / 9)


def test_female_profile_differs_from_male():
    female = dict(PROFILE, gender="Female")
    cal_m, _ = diet.compute_daily_targets(PROFILE)
    cal_f, _ = diet.compute_daily_targets(female)
    assert cal_f < cal_m  # female BMR subtracts 161 instead of adding 5


def test_goal_changes_offset():
    cal_loss, _ = diet.compute_daily_targets(PROFILE)
    cal_gain, _ = diet.compute_daily_targets(dict(PROFILE, goal="Weight Gain"))
    assert cal_gain == cal_loss + 900  # +400 vs -500


def test_missing_profile_values_return_zero_not_defaults():
    for key in ("age", "weight_kg", "height_cm", "gender", "activity"):
        profile = dict(PROFILE)
        profile[key] = "" if key in ("gender", "activity") else 0
        calories, macros = diet.compute_daily_targets(profile)
        assert calories == 0 and macros == {}, f"expected refusal for missing {key}"


def test_no_invented_values_for_partial_profile():
    profile = dict(PROFILE, age=0)
    calories, macros = diet.compute_daily_targets(profile)
    assert calories == 0 and macros == {}


def test_targets_clamped_to_safe_range():
    tiny = dict(PROFILE, weight_kg=35.0, height_cm=110.0, age=60, activity="Sedentary", goal="Weight Loss")
    calories, _ = diet.compute_daily_targets(tiny)
    assert calories == 1200  # safety floor
    huge = dict(PROFILE, weight_kg=199.0, height_cm=110.0, activity="Extra Active", goal="Weight Gain")
    calories, _ = diet.compute_daily_targets(huge)
    assert calories == 4000  # safety ceiling


# ── normalize_meal_analysis (Issue 5) ───────────────────────────────────

def test_normalize_two_eggs_example():
    raw = (
        '{"food": "2 boiled eggs", "calories": 156, "protein": 12.6, "carbs": 1.1,'
        ' "fat": 10.6, "fiber": 0, "serving_assumption": "2 large eggs",'
        ' "notes": "assumes large eggs, boiled"}'
    )
    result = diet.normalize_meal_analysis(raw)
    assert result is not None
    assert 12 <= result["protein"] <= 13  # spec: ~12–13 g protein for 2 eggs
    assert 140 <= result["calories"] <= 165
    assert result["estimate"] is True
    assert result["serving_assumption"] == "2 large eggs"


def test_normalize_rejects_zero_calories():
    assert diet.normalize_meal_analysis({"calories": 0, "protein": 5}) is None
    assert diet.normalize_meal_analysis({"protein": 5}) is None


def test_normalize_rejects_non_dict_and_garbage():
    assert diet.normalize_meal_analysis(None) is None
    assert diet.normalize_meal_analysis("this is not json") is None
    assert diet.normalize_meal_analysis(["calories", 100]) is None


def test_normalize_clamps_absurd_values():
    result = diet.normalize_meal_analysis(
        {"calories": 999999, "protein": -5, "carbs": "abc", "fat": None}
    )
    assert result is not None
    assert result["calories"] == 8000.0  # ceiling applied
    assert result["protein"] == 0.0      # negative → default 0
    assert result["carbs"] == 0.0        # non-numeric → default 0


def test_normalize_passes_numbers_through():
    result = diet.normalize_meal_analysis(
        {"calories": 350, "protein": 25, "carbs": 40, "fat": 10, "fiber": 5}
    )
    assert result == {
        "food": "",
        "calories": 350.0,
        "protein": 25.0,
        "carbs": 40.0,
        "fat": 10.0,
        "fiber": 5.0,
        "serving_assumption": "typical serving size",
        "notes": "",
        "estimate": True,
    }


# ── ai_meal_analysis_structured (mocked Gemini) ─────────────────────────

def test_structured_analysis_uses_normalizer(monkeypatch):
    monkeypatch.setattr(
        diet,
        "get_gemini_response",
        lambda prompt: '{"calories": 156, "protein": 12.6, "carbs": 1.1, "fat": 10.6, "fiber": 0}',
    )
    result = diet.ai_meal_analysis_structured("2 boiled eggs")
    assert result is not None
    assert result["calories"] == 156.0
    assert result["food"] == "2 boiled eggs"  # falls back to the meal text


def test_structured_analysis_returns_none_on_api_failure(monkeypatch):
    monkeypatch.setattr(
        diet, "get_gemini_response", lambda prompt: "Gemini is still busy after 3 attempts."
    )
    assert diet.ai_meal_analysis_structured("2 boiled eggs") is None


def test_structured_analysis_returns_none_on_bad_json(monkeypatch):
    monkeypatch.setattr(diet, "get_gemini_response", lambda prompt: "a paragraph of prose, no JSON")
    assert diet.ai_meal_analysis_structured("2 boiled eggs") is None


def test_structured_analysis_rejects_empty_input():
    assert diet.ai_meal_analysis_structured("   ") is None


# ── Calorie tracker: day separation, totals, remaining (Issue: tracker) ──

def test_today_log_entries_separates_days():
    today, yesterday = "2026-10-17", "2026-10-16"
    entries = [
        {"Meal": "A", "Calories": 100, "date": today},
        {"Meal": "B", "Calories": 200, "date": yesterday},
        {"Meal": "legacy", "Calories": 50},  # saved before per-day dating
    ]
    assert [e["Meal"] for e in diet.today_log_entries(entries, today)] == ["A", "legacy"]
    assert [e["Meal"] for e in diet.today_log_entries(entries, yesterday)] == ["B", "legacy"]


def test_summarize_log_sums_and_tolerates_garbage():
    entries = [
        {"Calories": 650, "Protein (g)": 30, "Carbs (g)": 60, "Fat (g)": 20, "Fiber (g)": 6},
        {"Calories": "abc", "Protein (g)": None, "Carbs (g)": "40", "Fat (g)": True, "Fiber (g)": []},
    ]
    totals = diet.summarize_log(entries)
    assert totals["calories"] == 650
    assert totals["protein"] == 30
    assert totals["carbs"] == 100
    assert totals["fat"] == 21
    assert totals["fiber"] == 6


def test_remaining_calories_positive_zero_exceeded():
    assert diet.remaining_calories_text(2786, 650) == "2,136 kcal remaining"
    assert diet.remaining_calories_text(2000, 2000) == "Daily calorie goal reached"
    assert diet.remaining_calories_text(2786, 3000) == "Goal exceeded by 214 kcal today"
    # a negative remaining must never surface as a number
    assert "-" not in diet.remaining_calories_text(1000, 5000)


def test_build_tracker_entry_stamps_date_and_coerces():
    entry = diet.build_tracker_entry(
        {"food": "Eggs & toast", "calories": 340.7, "protein": "19.6", "carbs": None, "fat": True, "fiber": "x"},
        "2 boiled eggs and 2 slices of bread",
        "2026-10-17",
    )
    assert entry["date"] == "2026-10-17"
    assert entry["Calories"] == 340
    assert entry["Protein (g)"] == 19
    assert entry["Carbs (g)"] == 0
    assert entry["Fat (g)"] == 1
    assert entry["Fiber (g)"] == 0
    assert entry["logged_at"]


def test_build_tracker_entry_falls_back_to_meal_description():
    assert diet.build_tracker_entry({"calories": 100}, "", "2026-10-17")["Meal"] == "Meal"
    assert diet.build_tracker_entry({"calories": 100}, "protein shake", "2026-10-17")["Meal"] == "protein shake"


def test_multiple_meals_totals_and_remaining():
    today = "2026-10-17"
    meals = [
        diet.build_tracker_entry({"food": "Breakfast", "calories": 650, "protein": 30, "carbs": 60, "fat": 20, "fiber": 6}, "", today),
        diet.build_tracker_entry({"food": "Lunch bowl", "calories": 800, "protein": 40, "carbs": 90, "fat": 25, "fiber": 9}, "", today),
        diet.build_tracker_entry({"food": "Yesterday's dinner", "calories": 900, "protein": 40, "carbs": 80, "fat": 30, "fiber": 5}, "", "2026-10-16"),
    ]
    totals = diet.summarize_log(diet.today_log_entries(meals, today))
    assert totals["calories"] == 1450  # yesterday excluded
    assert diet.remaining_calories_text(2786, totals["calories"]) == "1,336 kcal remaining"


# ── Page-level workflow (Streamlit mocked) ──────────────────────────────
# Meal Analyser is the only meal-entry page; Calorie Tracker is read-only
# and reads the same shared `tracker_entries` log.

class _NoOpCtx:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _mock_common_st(monkeypatch):
    import streamlit as st

    for name in (
        "caption", "error", "warning", "markdown", "progress", "toast",
        "dataframe", "rerun", "success", "number_input", "info",
    ):
        monkeypatch.setattr(st, name, lambda *a, **k: None)
    monkeypatch.setattr(st, "spinner", lambda *a, **k: _NoOpCtx())

    def fake_columns(spec, *a, **k):
        n = spec if isinstance(spec, int) else len(spec)
        return [_NoOpCtx() for _ in range(n)]

    monkeypatch.setattr(st, "columns", fake_columns)


def _mock_tracker_readonly(monkeypatch, clicks, stats_calls):
    import streamlit as st

    _mock_common_st(monkeypatch)

    def fake_button(label, *a, **k):
        return clicks.get(label, False)

    monkeypatch.setattr(st, "button", fake_button)

    def _no_textarea(*a, **k):
        raise AssertionError("Calorie Tracker must not render a meal text area")

    monkeypatch.setattr(st, "text_area", _no_textarea)
    monkeypatch.setattr(diet, "section_header", lambda *a, **k: None)
    monkeypatch.setattr(diet, "empty_state", lambda *a, **k: None)
    monkeypatch.setattr(diet, "stat_row", lambda stats, *a, **k: stats_calls.append(stats))
    monkeypatch.setattr(diet, "_tracker_goal_state", lambda: (2786, "auto"))
    monkeypatch.setattr(diet, "save_current_user_state", lambda: True)


def _mock_analyser(monkeypatch, clicks, analysis):
    import streamlit as st

    _mock_common_st(monkeypatch)

    def fake_button(label, *a, **k):
        return clicks.get(label, False)

    monkeypatch.setattr(st, "button", fake_button)
    monkeypatch.setattr(st, "text_area", lambda *a, **k: "2 eggs and 2 cups of milk")
    monkeypatch.setattr(diet, "section_header", lambda *a, **k: None)
    monkeypatch.setattr(diet, "stat_row", lambda *a, **k: None)
    monkeypatch.setattr(diet, "save_current_user_state", lambda: True)
    monkeypatch.setattr(diet, "ai_meal_analysis_structured", lambda desc, model=None: analysis)


ANALYSIS = {"food": "Eggs & Milk", "calories": 440, "protein": 27, "carbs": 24, "fat": 26, "fiber": 0}


def test_tracker_page_is_read_only():
    import inspect

    tracker_src = inspect.getsource(diet._tab4_calorie_tracker)
    assert "text_area" not in tracker_src
    assert "Analyze meal" not in tracker_src and "Analyse meal" not in tracker_src
    assert "ai_meal_analysis_structured" not in tracker_src
    assert "Add to today's log" not in tracker_src

    analyser_src = inspect.getsource(diet._tab2_meal_analyser)
    assert "ai_meal_analysis_structured" in analyser_src
    assert "Add to today's log" in analyser_src


def test_tracker_reads_shared_log_and_summarizes(monkeypatch, session_state):
    from datetime import date

    today = date.today().isoformat()
    session_state["tracker_entries"] = [
        {"Meal": "Eggs & Milk", "Calories": 440, "Protein (g)": 27, "Carbs (g)": 24,
         "Fat (g)": 26, "Fiber (g)": 0, "date": today},
        {"Meal": "Yesterday dinner", "Calories": 900, "Protein (g)": 40, "Carbs (g)": 80,
         "Fat (g)": 30, "Fiber (g)": 5, "date": "2026-10-16"},
    ]
    stats_calls: list = []
    _mock_tracker_readonly(monkeypatch, {}, stats_calls)

    diet._tab4_calorie_tracker()

    by_label = {s["label"]: s["value"] for s in stats_calls[0]}
    assert by_label["Daily goal"] == "2,786 kcal"
    assert by_label["Consumed"] == "440 kcal"  # yesterday's 900 excluded
    assert by_label["Remaining"] == "2,346 kcal remaining"


def test_drop_entries_for_day_preserves_history():
    entries = [
        {"Meal": "A", "date": "2026-10-17"},
        {"Meal": "B", "date": "2026-10-16"},
        {"Meal": "legacy"},  # undated counts as today → clears with today
    ]
    kept = diet.drop_entries_for_day(entries, "2026-10-17")
    assert [e["Meal"] for e in kept] == ["B"]
    # kept + cleared must exactly partition the entry list
    cleared = diet.today_log_entries(entries, "2026-10-17")
    assert len(kept) + len(cleared) == len(entries)


def test_tracker_clear_removes_only_today(monkeypatch, session_state):
    from datetime import date

    today = date.today().isoformat()
    session_state["tracker_entries"] = [
        {"Meal": "A", "Calories": 440, "date": today},
        {"Meal": "Old", "Calories": 900, "date": "2026-10-16"},
        {"Meal": "legacy", "Calories": 50},
    ]
    stats_calls: list = []

    # Step 1: "Clear today's log" only arms the confirmation.
    _mock_tracker_readonly(monkeypatch, {"Clear today's log": True}, stats_calls)
    diet._tab4_calorie_tracker()
    assert session_state["tracker_confirm_clear"] is True
    assert len(session_state["tracker_entries"]) == 3

    # Step 2: explicit confirm removes today's dated entry and the undated
    # legacy entry (it counts as today); other days survive.
    _mock_tracker_readonly(monkeypatch, {"Yes, clear today's log": True}, stats_calls)
    diet._tab4_calorie_tracker()
    assert [e["Meal"] for e in session_state["tracker_entries"]] == ["Old"]
    assert session_state["tracker_confirm_clear"] is False


def test_analysed_meal_not_counted_until_confirmed(monkeypatch, session_state):
    _mock_analyser(monkeypatch, {"Analyse meal": True}, ANALYSIS)

    diet._tab2_meal_analyser()

    assert session_state.get("pending_meal_analysis") == ANALYSIS
    assert session_state.get("tracker_entries", []) == []


def test_add_to_log_saves_once_and_shows_success(monkeypatch, session_state):
    from datetime import date

    today = date.today().isoformat()
    clicks = {"Add to today's log": True}
    _mock_analyser(monkeypatch, clicks, ANALYSIS)
    session_state["pending_meal_analysis"] = dict(ANALYSIS)

    diet._tab2_meal_analyser()

    entries = session_state["tracker_entries"]
    assert len(entries) == 1
    assert entries[0]["date"] == today
    assert entries[0]["Calories"] == 440
    assert session_state["meal_log_success"] == "Eggs & Milk"
    assert session_state.get("pending_meal_analysis") is None

    # Rerun without the click: no duplicate; the success banner is consumed.
    _mock_analyser(monkeypatch, {}, ANALYSIS)
    diet._tab2_meal_analyser()
    assert len(session_state["tracker_entries"]) == 1
    assert "meal_log_success" not in session_state


def test_analysis_failure_keeps_log_clean(monkeypatch, session_state):
    _mock_analyser(monkeypatch, {"Analyse meal": True}, None)

    diet._tab2_meal_analyser()

    assert session_state.get("pending_meal_analysis") is None
    assert session_state.get("tracker_entries", []) == []
