"""Pure CV logic: angle math and the rep-counting state machine."""

from __future__ import annotations

import m
from gym_trainer import RepCounter


def test_calculate_angle_right_angle():
    a, b, c = [0, 10], [0, 0], [10, 0]
    assert m.calculate_angle(a, b, c) == 90.0


def test_calculate_angle_straight_line():
    assert m.calculate_angle([0, 0], [5, 0], [10, 0]) == 180.0


def test_calculate_angle_reflex_folds_to_interior():
    # The helper maps reflex angles onto their interior equivalent.
    assert m.calculate_angle([0, 0], [5, 0], [0, -5]) == 45.0


def test_rep_counter_counts_full_cycle_only():
    counter = RepCounter("Squat")
    cfg = counter.cfg
    assert counter.process_angle(cfg["up_angle"] + 5) == (0, "up")
    assert counter.process_angle((cfg["up_angle"] + cfg["down_angle"]) / 2) == (0, "up")
    assert counter.process_angle(cfg["down_angle"] - 5) == (1, "down")
    # Mid-range oscillation without crossing thresholds adds no reps.
    assert counter.process_angle((cfg["up_angle"] + cfg["down_angle"]) / 2) == (1, "down")
    assert counter.process_angle(cfg["up_angle"] + 5) == (1, "up")
    assert counter.process_angle(cfg["down_angle"] - 5) == (2, "down")


def test_rep_counter_partial_range_does_not_count():
    counter = RepCounter("Bicep Curl")
    counter.process_angle(120)  # below up threshold, above down threshold
    assert counter.rep_count == 0
