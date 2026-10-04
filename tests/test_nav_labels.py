"""Navigation model tests: main sections, subsections, and route coverage."""
from __future__ import annotations

import app  # noqa: E402  (path configured in conftest)
import diet  # noqa: E402


def test_main_navigation_labels():
    """The sidebar shows exactly the eight approved main sections."""
    assert app.MAIN_NAV == [
        "Home",
        "Training",
        "Nutrition",
        "Progress",
        "Coach",
        "Profile",
        "Settings",
        "About",
    ]
    assert len(set(app.MAIN_NAV)) == len(app.MAIN_NAV), "duplicate main labels"


def test_training_subsection_labels():
    assert app.SECTION_PAGES["Training"] == ["Workouts", "Exercise Library", "AI Gym Trainer"]


def test_nutrition_subsection_labels():
    """Nutrition is Diet Coach, Meal Analyser and Calorie Tracker only."""
    assert app.SECTION_PAGES["Nutrition"] == [
        "Diet Coach",
        "Meal Analyser",
        "Calorie Tracker",
    ]
    assert "Grocery List" not in app.ROUTES


def test_every_label_routes():
    """Every visible label (main + subsection) owns exactly one route."""
    labels = [*app.MAIN_NAV, *(p for pages in app.SECTION_PAGES.values() for p in pages)]
    assert set(labels) == set(app.ROUTES.keys()), "labels and ROUTES diverged"
    assert len(app.ROUTES) == len(labels), "duplicate route ownership"


def test_canonical_targets_unique():
    """No two labels dispatch to the same canonical target."""
    values = list(app.ROUTES.values())
    assert len(set(values)) == len(values), "a canonical target is owned by two labels"


def test_coach_opens_gym_buddy_directly():
    """Coach is a direct main page — no submenu, no second click."""
    assert app.ROUTES["Coach"] == "buddy"
    assert "Coach" not in app.SECTION_PAGES
    from habit_tracker import render_gym_buddy_page

    assert callable(render_gym_buddy_page)


def test_workouts_uses_existing_routines_implementation():
    """'Workouts' is the display name; the canonical routines route is intact."""
    assert app.ROUTES["Workouts"] == "routines"
    from routines import render_routines_page

    assert callable(render_routines_page)
    assert "Routines" not in app.ROUTES, "old display name still routed"


def test_all_destination_pages_importable():
    """Every canonical target resolves to an importable renderer."""
    targets = {
        "home": ("app", "render_home"),
        "trainer": ("gym_trainer", "render_gym_trainer_page"),
        "routines": ("routines", "render_routines_page"),
        "exercise_library": ("exercise_library", "render_exercise_library_page"),
        "diet": ("diet", "render_diet_page"),
        "meal_analyser": ("nutrition", "render_meal_analyser_page"),
        "calorie_tracker": ("nutrition", "render_calorie_tracker_page"),
        "buddy": ("habit_tracker", "render_gym_buddy_page"),
        "progress": ("progress", "render_progress_page"),
        "profile": ("profile_page", "render_profile_page"),
        "settings": ("settings_page", "render_settings_page"),
        "about": ("about", "render_about_page"),
    }
    for target, (module, function) in targets.items():
        mod = __import__(module)
        assert callable(getattr(mod, function)), f"{module}.{function} missing for target {target!r}"


def test_nutrition_footer_labels_match_sidebar():
    """The Diet page footer links must keep routing to the nutrition pages."""
    for target, label in diet._NUTRITION_PAGE_LABELS.items():
        assert app.ROUTES.get(label) == target, f"footer label {label!r} no longer routes to {target!r}"
