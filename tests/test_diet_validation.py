"""Diet validation helpers: JSON extraction, allergy and macro checks."""

from __future__ import annotations

import diet


def test_extract_plain_json():
    text = '{"days": [{"day": 1, "meals": []}]}'
    assert diet.extract_and_parse_json(text)["days"][0]["day"] == 1


def test_extract_json_in_markdown_fence():
    text = '```json\n{"calories": 500}\n```'
    assert diet.extract_and_parse_json(text) == {"calories": 500}


def test_extract_json_with_trailing_comma():
    text = '{"a": 1, "b": [1, 2,],}'
    assert diet.extract_and_parse_json(text) == {"a": 1, "b": [1, 2]}


def test_extract_invalid_returns_none():
    assert diet.extract_and_parse_json("not json at all") is None


def test_contains_allergy_detects_avoided_food():
    plan = {"days": [{"meals": [{"items": "Peanut butter sandwich"}]}]}
    assert diet.contains_allergy(plan, "peanut") is True
    assert diet.contains_allergy(plan, "shellfish") is False


def test_contains_allergy_ignores_none():
    assert diet.contains_allergy({"days": []}, "") is False
    assert diet.contains_allergy({"days": []}, "None") is False


def test_validate_nutrition_difference_flags_deviation():
    plan = {"days": [{"meals": [{"calories": 2000}]}]}
    # 2000 vs 1200 target = ~67% deviation → flagged
    assert diet.validate_nutrition_difference(plan, 1200, 100, 150, 40) is True
    # 2000 vs 1800 target = ~11% deviation → accepted
    assert diet.validate_nutrition_difference(plan, 1800, 100, 150, 40) is False
