"""
Nutrition pages — the Diet Coach tools, split into focused pages.

The implementations live in diet.py (logic moved verbatim in Phase 6);
this module is the stable re-export surface used by app.py routing.
"""

from __future__ import annotations

from diet import (  # noqa: F401
    render_diet_page,
    render_meal_analyser_page,
    render_grocery_list_page,
    render_calorie_tracker_page,
)

