"""The sidebar labels used across modules must stay in exact sync."""

from __future__ import annotations

import app  # noqa: E402  (path configured in conftest)
import diet  # noqa: E402


def test_nav_groups_cover_all_routes():
    labels = [label for _, labels in app.NAV_GROUPS for label in labels]
    assert sorted(labels) == sorted(app.ROUTES.keys()), "NAV_GROUPS and ROUTES diverged"
    assert len(labels) == len(set(labels)), "duplicate sidebar labels"


def test_nutrition_footer_labels_match_sidebar():
    for target, label in diet._NUTRITION_PAGE_LABELS.items():
        assert app.ROUTES.get(label) == target, f"footer label {label!r} no longer routes to {target!r}"


def test_page_constants_are_unique():
    import app as a

    labels = [a.PAGE_HOME, a.PAGE_TRAINER, a.PAGE_DIET, a.PAGE_BUDDY, a.PAGE_PROGRESS, a.PAGE_PROFILE, a.PAGE_SETTINGS, a.PAGE_ABOUT]
    assert len(labels) == len(set(labels))
