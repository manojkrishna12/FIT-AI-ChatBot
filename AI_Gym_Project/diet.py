"""
Diet Coach page with per-user saved plans, analyses, and tracker state.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from constants import BMI_COLORS, CALORIE_MULTIPLIERS
from m import (
    _TRANSIENT_MARKERS,
    calculate_bmi,
    calculate_tdee,
    get_gemini_response,
    macro_split,
    page_header,
    section_header,
    stat_row,
)
from storage import save_current_user_state
from auth import profile_prefill
from ui import empty_state


import json
import re


def compute_daily_targets(profile: dict) -> tuple[int, dict[str, int]]:
    """Estimate daily calorie and macro targets from a saved profile.

    Uses the app's existing Mifflin-St Jeor TDEE (m.calculate_tdee), applies
    the goal calorie offset shared with the Diet Coach, and derives macros
    with the shared macro_split(). The same helper backs the Diet Coach form
    and the Calorie Tracker's auto goal, so both always agree.

    Returns (0, {}) when the profile lacks needed values — callers must then
    ask the user to complete their profile instead of inventing defaults.
    """
    try:
        weight = float(profile.get("weight_kg") or profile.get("weight") or 0)
        height = float(profile.get("height_cm") or profile.get("height") or 0)
        age = int(profile.get("age") or 0)
    except (TypeError, ValueError):
        return 0, {}
    gender = (profile.get("gender") or "").strip()
    activity = (profile.get("activity") or "").strip()
    goal = (profile.get("goal") or "").strip()

    if weight <= 0 or height <= 0 or age <= 0 or not gender or not activity:
        return 0, {}

    tdee = calculate_tdee(weight, height, age, gender, activity)
    target_cal = tdee + CALORIE_OFFSETS.get(goal, 0)
    if target_cal < 1200:
        target_cal = 1200
    elif target_cal > 4000:
        target_cal = 4000
    return target_cal, macro_split(target_cal, goal or "General Fitness", weight)


# Calorie offset per goal, shared by the Diet Coach form and
# compute_daily_targets ("General Fitness" and unknown goals get no offset).
CALORIE_OFFSETS = {
    "Weight Loss": -500,
    "Weight Gain": 400,
    "Muscle Building": 300,
    "Weight Maintenance": 0,
    "Athletic Performance": 0,
    "General Fitness": 0,
}

DIET_GOALS = [
    "Weight Loss",
    "Weight Gain",
    "Weight Maintenance",
    "Muscle Building",
    "Athletic Performance",
    "General Fitness",
]

DIET_TYPES = [
    "No Restriction",
    "Vegetarian",
    "Vegan",
    "Eggitarian",
    "Keto",
    "Mediterranean",
    "Paleo",
    "Gluten-Free",
    "Dairy-Free",
]


def _safe_index(options: list, value, default: int = 0) -> int:
    """Return options.index(value) or default when the value is unknown."""
    try:
        return options.index(value)
    except ValueError:
        return default


def extract_and_parse_json(text: str):
    """Robustly extract and parse JSON from a response, handling markdown fences."""
    text = text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        # Fallback for common trailing comma issue
        text = re.sub(r',\s*([}\]])', r'\1', text)
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            return None

def contains_allergy(plan_data: dict, allergies: str) -> bool:
    """Check if any generated meal items contain the user's avoided foods."""
    if not allergies or allergies.lower() == "none" or not plan_data:
        return False
    avoid_list = [a.strip().lower() for a in allergies.split(",") if a.strip()]
    
    for day in plan_data.get("days", []):
        for meal in day.get("meals", []):
            items_str = meal.get("items", "").lower()
            for avoid in avoid_list:
                if avoid in items_str:
                    return True
    return False

def validate_nutrition_difference(plan_data: dict, target_cal: int, target_p: int, target_c: int, target_f: int) -> bool:
    """Return True if plan is significantly outside targets."""
    try:
        days = plan_data.get("days", [])
        if not days: return False
        
        total_cals = 0
        for day in days:
            daily_cals = sum(int(m.get("calories", 0)) for m in day.get("meals", []))
            total_cals += daily_cals
            
        avg_cals = total_cals / len(days)
        diff = abs(avg_cals - target_cal)
        if diff > (target_cal * 0.25): # >25% deviation
            return True
        return False
    except Exception:
        return False

def ai_diet_plan(user_data: dict, model=None, is_retry=False) -> dict:
    """Generate a 7-day diet plan using JSON structure, with fallback to deterministic engine."""
    import diet_fallback
    print("[DIET] Starting generation")
    
    target_macros = {
        "calories": user_data['calories'],
        "protein": user_data['macros']['Protein (g)'],
        "carbs": user_data['macros']['Carbs (g)'],
        "fat": user_data['macros']['Fat (g)']
    }
    
    prompt = f"""
You are a certified nutritionist.
Create a practical 7-day meal plan for:
Name: {user_data['name']}
Age: {user_data['age']}
Gender: {user_data['gender']}
Weight: {user_data['weight']} kg
Height: {user_data['height']} cm
Activity: {user_data['activity']}
Goal: {user_data['goal']}
Calories target: {user_data['calories']} kcal
Protein target: {user_data['macros']['Protein (g)']} g
Carbs target: {user_data['macros']['Carbs (g)']} g
Fat target: {user_data['macros']['Fat (g)']} g
Dietary style: {user_data['diet_type']}
Allergies/Avoid: {user_data['allergies']}
Meals per day: {user_data['meals_per_day']}
Cuisine/Notes: {user_data['cuisine']}

CRITICAL CONSTRAINTS:
1. NEVER include items from "Allergies/Avoid".
2. If Cuisine/Notes suggests Indian food, include practical Indian foods.
3. You must provide exactly {user_data['meals_per_day']} meals per day, for exactly 7 days.
4. Total calories and macros per day MUST closely match the targets provided above.

Respond ONLY with a valid JSON object in the following format (NO markdown blocks, just raw JSON):
{{
  "days": [
    {{
      "day": 1,
      "meals": [
        {{
          "name": "Breakfast",
          "foods": [
            {{"item": "Oats", "quantity": "60 g"}}
          ],
          "calories": 500,
          "protein": 25,
          "carbs": 65,
          "fat": 15
        }}
      ]
    }}
  ]
}}
"""
    if is_retry:
        prompt += "\n\nPREVIOUS ATTEMPT FAILED. You MUST STRICTLY OMIT ALLERGIES AND MATCH MACROS ACCURATELY."

    def get_fallback():
        print("[DIET] Falling back to Python engine")
        try:
            fallback_plan = diet_fallback.generate_fallback_diet_plan(user_data, target_macros)
            fallback_plan["source"] = "PYTHON_FALLBACK"
            print("[DIET] Fallback generated: SUCCESS")
            print("[DIET] Final plan source: PYTHON_FALLBACK")
            return fallback_plan
        except Exception as fe:
            print(f"[DIET] Fallback generated: FAILURE ({fe})")
            return {"days": [], "source": "PYTHON_FALLBACK_FAILED"}

    print("[DIET] Gemini attempt started")
    try:
        response_text = get_gemini_response(prompt)
        
        # Check if the response is actually an error message from our helper
        if not response_text or "unavailable" in response_text.lower() or "failed" in response_text.lower() or "api key" in response_text.lower():
            print("[DIET] Gemini success/failure: FAILURE")
            return get_fallback()
            
        plan_data = extract_and_parse_json(response_text)
        
        if plan_data is None:
            print("[DIET] Gemini success/failure: FAILURE (JSON Parse Error)")
            if not is_retry:
                return ai_diet_plan(user_data, model, is_retry=True)
            return get_fallback()
            
        if contains_allergy(plan_data, user_data['allergies']):
            print("[DIET] Gemini success/failure: FAILURE (Allergy Violation)")
            if not is_retry:
                return ai_diet_plan(user_data, model, is_retry=True)
            return get_fallback()
            
        if validate_nutrition_difference(plan_data, user_data['calories'], user_data['macros']['Protein (g)'], user_data['macros']['Carbs (g)'], user_data['macros']['Fat (g)']):
            print("[DIET] Gemini success/failure: FAILURE (Nutrition Deviation)")
            if not is_retry:
                return ai_diet_plan(user_data, model, is_retry=True)
            return get_fallback()
            
        print("[DIET] Gemini success/failure: SUCCESS")
        print("[DIET] Final plan source: GEMINI")
        plan_data["source"] = "GEMINI"
        return plan_data
        
    except Exception as e:
        print(f"[DIET] Gemini success/failure: FAILURE (Exception: {e})")
        return get_fallback()

def normalize_meal_analysis(data) -> dict | None:
    """Coerce a raw meal-analysis payload into a validated, consistent shape.

    Accepts dicts (or JSON strings) as returned by Gemini. Numbers come back
    as non-negative ints/floats inside safe bounds; a missing or absurd
    "calories" makes the whole result invalid (None) so callers can refuse
    to guess. Returns a dict with the keys: food, calories, protein, carbs,
    fat, fiber, serving_assumption, notes, estimate (always True when the
    values came from an AI estimate rather than a packaged/label measurement).
    """
    if isinstance(data, str):
        data = extract_and_parse_json(data)
    if not isinstance(data, dict):
        return None

    def _num(key, default=0.0, lo=0.0, hi=5000.0):
        value = data.get(key, default)
        try:
            value = float(value)
        except (TypeError, ValueError):
            return default
        if value != value or value < lo:  # NaN / negative
            return default
        return round(min(value, hi), 1)

    calories = _num("calories", 0.0, lo=0.0, hi=8000.0)
    if calories <= 0:
        return None  # no calorie estimate at all → refuse to fabricate one

    food = str(data.get("food") or data.get("meal") or "").strip()[:80]
    return {
        "food": food,
        "calories": calories,
        "protein": _num("protein"),
        "carbs": _num("carbs"),
        "fat": _num("fat"),
        "fiber": _num("fiber"),
        "serving_assumption": str(data.get("serving_assumption") or "typical serving size").strip()[:120],
        "notes": str(data.get("notes") or "").strip()[:200],
        # AI-parsed nutrition is an estimate, never a lab measurement.
        "estimate": bool(data.get("estimate", True)),
    }


def ai_meal_analysis_structured(meal_description: str, model=None) -> dict | None:
    """Generate a nutrition breakdown for a meal; structured dict, None if unavailable.

    Multi-item natural-language meals are split so every item gets a
    recognized quantity; results are summed into one total. Output goes
    through normalize_meal_analysis; AI/API failures return None (callers
    show their own message instead of printing model text).
    """
    meal_description = (meal_description or "").strip()
    if not meal_description:
        return None

    prompt = f"""Analyze this meal and return ONLY a valid JSON object (no markdown formatting, no extra text).
Meal: {meal_description}

Return exactly this JSON structure:
{{
  "food": "short meal name",
  "calories": 350,
  "protein": 25,
  "carbs": 40,
  "fat": 10,
  "fiber": 5,
  "serving_assumption": "describe assumed portion, e.g. '2 large boiled eggs'",
  "notes": "one short sentence stating your assumptions or low confidence"
}}
Use standard USDA-style reference values for real food. All numeric fields must be plain numbers in grams/kcal (no units inside them). If a quantity is ambiguous, state the assumption in serving_assumption. If you are unsure of a value, still give your best realistic estimate and flag it in notes.
"""
    try:
        resp = get_gemini_response(prompt)

        if not resp or any(marker in resp.lower() for marker in _TRANSIENT_MARKERS):
            return None
        if resp.startswith("Error:") or "unavailable" in resp.lower() or "api key" in resp.lower():
            return None
        if resp.startswith("The Gemini API rejected") or resp.startswith("The configured Gemini model"):
            return None  # config problem: shown to the user by the caller
        normalized = normalize_meal_analysis(resp)
        if normalized is None:
            return None
        if not normalized.get("food"):
            normalized["food"] = meal_description[:80]
        return normalized
    except Exception:
        return None


def ai_meal_analysis(meal_description: str, model=None) -> str:
    """Legacy plain-text meal analysis (kept for compatibility)."""
    data = ai_meal_analysis_structured(meal_description, model)
    if data is None:
        return "Meal analysis is temporarily unavailable. Please try again."
    return (
        f"**Estimated Calories**: {data.get('calories', 0)} kcal\n\n"
        f"**Protein**: {data.get('protein', 0)} g\n\n"
        f"**Carbs**: {data.get('carbs', 0)} g\n\n"
        f"**Fat**: {data.get('fat', 0)} g\n\n"
        f"**Fiber**: {data.get('fiber', 0)} g\n\n"
        f"*Serving Assumption*: {data.get('serving_assumption', 'Typical serving size')}\n\n"
        f"*Note*: {data.get('notes', '')}"
    )


def ai_nutrition_tip(goal: str, model=None) -> str:
    """Return one short nutrition tip."""
    try:
        prompt = f"Give one practical nutrition tip for someone focused on {goal}. Keep it under 60 words."
        return get_gemini_response(prompt)
    except Exception:
        return "Stay hydrated and eat balanced meals!"


def format_json_plan_to_markdown(plan_data: dict, target_cal: int, target_p: int, target_c: int, target_f: int) -> str:
    """Render a structured 7-day plan as clean markdown with daily target checks."""
    if not isinstance(plan_data, dict) or "days" not in plan_data:
        return str(plan_data)

    md = []
    for day in plan_data.get("days", []):
        daily_cal = daily_p = daily_c = daily_f = 0
        meals_md = []
        for meal in day.get("meals", []):
            name = meal.get("name", meal.get("meal_name", "Meal"))
            if "foods" in meal:
                items = ", ".join([f"{f.get('item', '')} ({f.get('quantity', '')})" for f in meal.get("foods", [])])
            else:
                items = meal.get("items", "")
                serving = meal.get("serving_size", "")
                if serving:
                    items += f" ({serving})"

            cals = int(meal.get("calories", 0))
            p = int(meal.get("protein", 0))
            c = int(meal.get("carbs", meal.get("carbohydrates", 0)))
            f = int(meal.get("fat", 0))

            daily_cal += cals
            daily_p += p
            daily_c += c
            daily_f += f

            meals_md.append(
                f"**{name}** — {items}  \n"
                f"<span class='meal-macros'>{cals} kcal · {p} g protein · {c} g carbs · {f} g fat</span>"
            )

        md.append(f"### Day {day.get('day', '?')}")
        md.extend(m for m in meals_md)
        md.append("")
        md.append(
            f"<span class='day-total'>Day total: {daily_cal} kcal · {daily_p} g protein · "
            f"{daily_c} g carbs · {daily_f} g fat — target {target_cal} kcal · {target_p} g · "
            f"{target_c} g · {target_f} g (Δ kcal {daily_cal - target_cal:+d})</span>"
        )
        md.append("")

    return "\n".join(md)

def _page_intro() -> None:
    """Shared page header and medical disclaimer."""
    page_header(
        "Diet Coach",
        "Meal plans, calorie tracking, and food insights",
    )
    st.warning(
        "**Medical disclaimer:** This tool provides general nutrition guidance only and is not "
        "medical advice. Consult a qualified healthcare provider about any medical condition "
        "or specialized diet."
    )


def _tab1_diet_plan() -> None:
    """Diet plan tool (page body)."""
    model = None  # Gemini client; helpers create their own when None
    section_header("Your 7-day meal plan", "Personalised targets and a full week of meals")
    with st.form("diet_form"):
        left, right = st.columns(2)
        with left:
            name = st.text_input("Your Name", str(profile_prefill("name", "User")))
            age = st.number_input("Age", 10, 100, int(profile_prefill("age", 22)))
            gender = st.selectbox("Gender", ["Male", "Female", "Other"], index=_safe_index(["Male", "Female", "Other"], profile_prefill("gender", "Male")))
            weight = st.number_input("Weight (kg)", 30.0, 200.0, float(profile_prefill("weight_kg", 65.0)), step=0.5)
            height = st.number_input("Height (cm)", 100.0, 250.0, float(profile_prefill("height_cm", 168.0)), step=0.5)
        with right:
            goal = st.selectbox(
                "Primary Goal",
                DIET_GOALS,
                index=_safe_index(DIET_GOALS, profile_prefill("goal", "Weight Loss")),
            )
            activity = st.selectbox("Activity Level", list(CALORIE_MULTIPLIERS.keys()), index=_safe_index(list(CALORIE_MULTIPLIERS.keys()), profile_prefill("activity", "Moderately Active")))
            diet_type = st.selectbox(
                "Dietary Preference",
                DIET_TYPES,
                index=_safe_index(DIET_TYPES, profile_prefill("diet_type", "No Restriction")),
            )
            allergies = st.text_input("Allergies / Foods to avoid", str(profile_prefill("allergies", "None")))
            meals_per_day = st.number_input("Meals per day", 2, 6, 4)
            cuisine = st.text_input("Cuisine preference / Notes (optional)", "Any")
        submitted = st.form_submit_button("Generate diet plan", use_container_width=True)

    if submitted:
        if weight <= 0 or height <= 0 or age <= 0:
            st.error("Please enter valid positive numbers for Age, Weight, and Height.")
            st.stop()
        bmi, bmi_cat = calculate_bmi(weight, height)
        tdee = calculate_tdee(weight, height, age, gender, activity)
        target_cal = tdee + CALORIE_OFFSETS.get(goal, 0)
        
        if target_cal < 1200:
            st.warning("⚠️ **Warning**: Your calculated calorie target is unusually low (below 1200 kcal). We strongly recommend consulting a qualified healthcare professional before starting an extreme calorie-restriction diet. We have adjusted your target to a safer minimum of 1200 kcal for this plan.")
            target_cal = 1200
        elif target_cal > 4000:
            st.warning("⚠️ **Warning**: Your calculated calorie target is very high. Please consult a professional to ensure this is appropriate for you.")

        macros = macro_split(target_cal, goal, weight)

        section_header("Daily target")
        st.markdown(
            f"<span class='meal-macros'>{target_cal} kcal · {macros['Protein (g)']} g protein · "
            f"{macros['Carbs (g)']} g carbs · {macros['Fat (g)']} g fat</span> — calculated targets "
            "used as constraints for the plan.",
            unsafe_allow_html=True,
        )
        
        user_data = {
            "name": name,
            "age": age,
            "gender": gender,
            "weight": weight,
            "height": height,
            "bmi": bmi,
            "bmi_cat": bmi_cat,
            "activity": activity,
            "goal": goal,
            "calories": target_cal,
            "macros": macros,
            "diet_type": diet_type,
            "dietary_preference": diet_type,  # FIX: diet_fallback.filter_db() uses this key
            "allergies": allergies,
            "meals_per_day": meals_per_day,
            "cuisine": cuisine,
        }

        # Clear stale error session state
        if "diet_plan_error" in st.session_state:
            st.session_state.pop("diet_plan_error", None)

        with st.spinner("Building your personalised 7-day meal plan..."):
            plan_data = ai_diet_plan(user_data, model)
            
        if isinstance(plan_data, dict):
            if plan_data.get("source") == "PYTHON_FALLBACK":
                st.info("Generated with the built-in nutrition engine because AI generation is temporarily unavailable.")
            elif plan_data.get("source") == "PYTHON_FALLBACK_FAILED":
                st.error("Failed to generate diet plan. Please check your inputs and try again.")
                st.stop()

            plan_md = format_json_plan_to_markdown(
                plan_data,
                target_cal,
                macros['Protein (g)'],
                macros['Carbs (g)'],
                macros['Fat (g)']
            )
        else:
            plan_md = str(plan_data)

        with st.container(border=True):
            st.markdown('<div class="plan-output">' + plan_md + "</div>", unsafe_allow_html=True)
        st.session_state["diet_plan"] = plan_md
        st.session_state["calorie_goal"] = target_cal
        save_current_user_state()

        st.download_button(
            "📥 Download Diet Plan",
            plan_md,
            file_name=f"{name}_diet_plan.txt",
            mime="text/plain",
        )

        with st.spinner("Generating a personalised tip..."):
            tip = ai_nutrition_tip(goal, model)
        st.info(f"**Nutrition tip:** {tip}")


_EXAMPLE_MEAL = (
    "Grilled chicken breast 150g, brown rice 1 cup cooked, steamed broccoli, "
    "and a drizzle of olive oil"
)


def _fill_meal_example() -> None:
    """on_click callback: seeds the meal box before widgets instantiate."""
    st.session_state["meal_input"] = _EXAMPLE_MEAL
    st.session_state["meal_analyser_autorun"] = True


def _tab2_meal_analyser() -> None:
    """Meal analyser tool (page body) — the only meal-entry page."""
    model = None  # Gemini client; helpers create their own when None
    saved_meal = st.session_state.pop("meal_log_success", None)
    if saved_meal:
        st.success(
            f"✅ **{saved_meal}** added to today's log — open the Calorie "
            "Tracker to see today's totals."
        )
    section_header("Meal analyser", "Describe a meal and get its nutritional breakdown")

    meal_input = st.text_area(
        "Describe your meal",
        placeholder=(
            "e.g. 2 scrambled eggs with whole wheat toast, butter, and a glass of orange juice"
        ),
        height=110,
        key="meal_input",
    )

    left, right = st.columns([1, 2])
    with left:
        analyse_btn = st.button("Analyse meal", type="primary", use_container_width=True, key="analyse_meal_btn")
    with right:
        st.button("Analyse an example", use_container_width=True, key="random_meal_btn", on_click=_fill_meal_example)

    if st.session_state.pop("meal_analyser_autorun", False) and st.session_state.get("meal_input"):
        analyse_btn = True

    if analyse_btn and meal_input:
        with st.spinner("Analysing nutritional content..."):
            result = ai_meal_analysis_structured(meal_input, model)
        if result is not None:
            st.session_state["pending_meal_analysis"] = result
        else:
            st.session_state.pop("pending_meal_analysis", None)
            st.error(
                "Unable to analyse this meal right now. Try rephrasing it "
                "with quantities (e.g. '2 boiled eggs', '150 g grilled chicken') "
                "— or try again in a moment."
            )

    result = st.session_state.get("pending_meal_analysis")
    if result is not None:
        section_header("Nutritional analysis")
        stat_row([
            {"label": "Calories", "value": f"{result.get('calories', 0)}"},
            {"label": "Protein", "value": f"{result.get('protein', 0)} g"},
            {"label": "Carbs", "value": f"{result.get('carbs', 0)} g"},
            {"label": "Fat", "value": f"{result.get('fat', 0)} g"},
            {"label": "Fiber", "value": f"{result.get('fiber', 0)} g"},
        ])
        st.caption(
            f"Serving assumption: {result.get('serving_assumption', 'typical serving size')}"
            + (f" · {result['notes']}" if result.get("notes") else "")
        )
        st.caption("Nutrition values are estimates and can vary by brand, preparation and serving size.")

        # Pop-before-append: a repeated click or rerun finds no pending
        # analysis and cannot add the same meal twice.
        if st.button("Add to today's log", key="add_meal_to_log"):
            from datetime import date as _date

            confirmed = st.session_state.pop("pending_meal_analysis", None)
            if confirmed is not None:
                today_iso = _date.today().isoformat()
                entry = build_tracker_entry(confirmed, meal_input, today_iso)
                st.session_state.setdefault("tracker_entries", []).append(entry)
                st.session_state.setdefault("calorie_log", []).append(
                    {"date": today_iso, "meal": entry["Meal"], "analysis": "meal analysis"}
                )
                save_current_user_state()
                # Shown as a success banner on the next run (a toast would
                # be discarded by this rerun).
                st.session_state["meal_log_success"] = entry["Meal"]
            st.rerun()


def today_log_entries(entries: list[dict], today_iso: str) -> list[dict]:
    """Entries belonging to today's log.

    Entries saved before per-day dating (legacy, no "date" key) keep
    counting on the day they are encountered; everything saved after
    carries an explicit date and is strictly day-separated.
    """
    return [e for e in (entries or []) if not e.get("date") or e.get("date") == today_iso]


def summarize_log(entries: list[dict]) -> dict[str, float]:
    """Total calories/macros over log entries; malformed values count as 0."""
    totals = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0, "fiber": 0.0}
    for e in entries or []:
        for src, dst in (
            ("Calories", "calories"),
            ("Protein (g)", "protein"),
            ("Carbs (g)", "carbs"),
            ("Fat (g)", "fat"),
            ("Fiber (g)", "fiber"),
        ):
            try:
                totals[dst] += float(e.get(src) or 0)
            except (TypeError, ValueError):
                continue
    return totals


def remaining_calories_text(goal: int, consumed: float) -> str:
    """User-facing summary of the calories still available today.

    Never renders a negative "remaining" number: over-goal consumption is
    reported as an exceedance instead.
    """
    remaining = int(round(goal - consumed))
    if remaining > 0:
        return f"{remaining:,} kcal remaining"
    if remaining == 0:
        return "Daily calorie goal reached"
    return f"Goal exceeded by {abs(remaining):,} kcal today"


def build_tracker_entry(analysis: dict, meal_description: str, today_iso: str) -> dict:
    """One dated log entry from a confirmed (not merely analyzed) meal."""
    def _int(key: str) -> int:
        try:
            return int(float(analysis.get(key) or 0))
        except (TypeError, ValueError):
            return 0

    return {
        "Meal": str(analysis.get("food") or meal_description or "Meal")[:80],
        "Calories": _int("calories"),
        "Protein (g)": _int("protein"),
        "Carbs (g)": _int("carbs"),
        "Fat (g)": _int("fat"),
        "Fiber (g)": _int("fiber"),
        "date": today_iso,
        "logged_at": datetime.now().isoformat(),
    }


def drop_entries_for_day(entries: list[dict], today_iso: str) -> list[dict]:
    """Entries kept when a single day's log is cleared: exactly the
    complement of today_log_entries. Undated legacy entries count as
    today for totals, so they clear with today's log as well."""
    return [e for e in (entries or []) if e.get("date") and e.get("date") != today_iso]


def _tracker_goal_state() -> tuple[int, str]:
    """Resolve the tracker's daily calorie goal: (goal, source).

    source is one of 'manual' (explicitly saved by the user — always
    respected, never overwritten), 'auto' (computed from the signed-in
    user's saved profile via compute_daily_targets), or 'default'.
    """
    manual = st.session_state.get("calorie_goal_manual")
    if isinstance(manual, (int, float)) and 800 <= int(manual) <= 5000:
        return int(manual), "manual"

    profile = {
        "weight_kg": profile_prefill("weight_kg", 0),
        "height_cm": profile_prefill("height_cm", 0),
        "age": profile_prefill("age", 0),
        "gender": profile_prefill("gender", ""),
        "activity": profile_prefill("activity", ""),
        "goal": profile_prefill("goal", ""),
    }
    target, _macros = compute_daily_targets(profile)
    if target:
        st.session_state["calorie_goal_auto"] = target
        return target, "auto"

    return int(st.session_state.get("calorie_goal") or 2000), "default"


def _tab4_calorie_tracker() -> None:
    """Read-only daily nutrition dashboard.

    Meal entry lives exclusively on the Meal Analyser page; this page only
    reads the shared `tracker_entries` log.
    """
    section_header("Calorie tracker", "What you've eaten today and what remains")

    goal_cal, goal_source = _tracker_goal_state()
    st.number_input(
        "Daily Calorie Goal (kcal)",
        800,
        5000,
        goal_cal,
        key="goal_cal_input",
        help=(
            "Auto-computed from your profile. Change it here to save a "
            "manual goal that is never overwritten."
        ),
    )
    if goal_source == "auto":
        st.caption(f"✓ Based on your saved profile (weight, height, age, activity, goal).")
    elif goal_source == "manual":
        st.caption("Manual goal saved — not recalculated from your profile.")

    # Persist explicit edits when the value changes.
    widget_value = st.session_state.get("goal_cal_input", goal_cal)
    if int(widget_value) != goal_cal:
        st.session_state["calorie_goal_manual"] = int(widget_value)
        st.session_state["calorie_goal"] = int(widget_value)
        save_current_user_state()
        goal_cal = int(widget_value)

    from datetime import date as _date

    today_iso = _date.today().isoformat()
    st.session_state.setdefault("tracker_entries", [])

    # ── Daily summary (always shown, from saved entries only) ──
    today_entries = today_log_entries(st.session_state["tracker_entries"], today_iso)
    totals = summarize_log(today_entries)
    consumed = int(totals["calories"])
    remaining_text = remaining_calories_text(goal_cal, consumed)

    stat_row([
        {"label": "Daily goal", "value": f"{goal_cal:,} kcal"},
        {"label": "Consumed", "value": f"{consumed:,} kcal"},
        {"label": "Remaining", "value": remaining_text},
    ])
    progress = min(consumed / max(1, goal_cal), 1.0)
    pct = round(consumed / max(1, goal_cal) * 100)
    bar_text = f"{consumed:,} of {goal_cal:,} kcal ({pct}%)"
    if consumed > goal_cal:
        bar_text += f" — goal exceeded by {consumed - goal_cal:,} kcal"
    st.progress(progress, text=bar_text)

    # ── Today's log (read-only list of confirmed entries) ──
    section_header("Today's log")
    # Re-read saved entries so the list always reflects what was persisted,
    # never text still sitting in an input box.
    today_entries = today_log_entries(st.session_state["tracker_entries"], today_iso)
    if today_entries:
        log_df = pd.DataFrame(today_entries)
        display_cols = ["Meal", "Calories", "Protein (g)", "Carbs (g)", "Fat (g)", "Fiber (g)"]
        log_df = log_df[[c for c in display_cols if c in log_df.columns]]
        st.dataframe(log_df, use_container_width=True)

        # Two-step confirmation so a stray click cannot wipe the day's log.
        if st.session_state.get("tracker_confirm_clear"):
            confirm_col, cancel_col = st.columns(2)
            with confirm_col:
                if st.button("Yes, clear today's log", type="primary", key="tracker_clear_yes"):
                    st.session_state["tracker_entries"] = drop_entries_for_day(
                        st.session_state["tracker_entries"], today_iso
                    )
                    st.session_state["tracker_confirm_clear"] = False
                    save_current_user_state()
                    st.rerun()
            with cancel_col:
                if st.button("Cancel", key="tracker_clear_cancel"):
                    st.session_state["tracker_confirm_clear"] = False
                    st.rerun()
        else:
            if st.button("Clear today's log", key="tracker_clear_btn"):
                st.session_state["tracker_confirm_clear"] = True
                st.rerun()
    else:
        empty_state(
            "Nothing logged yet today",
            "Analyse a meal on the Meal Analyser page and add it to today's "
            "log — it will show up here.",
            action_label="Go to Meal Analyser",
            on_action=_go_to_meal_analyser,
        )


def _go_to_meal_analyser() -> None:
    """Navigate to the Meal Analyser page (the only meal-entry page)."""
    st.session_state["_navigate_to"] = _NUTRITION_PAGE_LABELS["meal_analyser"]
    st.rerun()


def render_diet_page() -> None:
    """Render the combined Diet Coach page as three native tabs.

    Tabs keep the (often long) generated plan from pushing the Meal
    Analyser and Calorie Tracker down a single scrolling page.
    """
    _page_intro()
    tab_plan, tab_meals, tab_tracker = st.tabs(
        ["Diet Plan", "Meal Analyser", "Calorie Tracker"]
    )
    with tab_plan:
        _tab1_diet_plan()
    with tab_meals:
        _tab2_meal_analyser()
    with tab_tracker:
        _tab4_calorie_tracker()


# ── Cross-page navigation between the Nutrition tools ──────────────────
# NOTE: labels must mirror the PAGE_* constants in app.py exactly;
# tests/test_nav_labels.py (Phase 7) asserts they stay in sync.


_NUTRITION_PAGE_LABELS = {
    "diet": "Diet Coach",
    "meal_analyser": "Meal Analyser",
    "calorie_tracker": "Calorie Tracker",
}


def _nutrition_footer(current: str) -> None:
    """Small link bar to move between the standalone nutrition pages."""
    buttons = st.columns(len(_NUTRITION_PAGE_LABELS))
    for col, (target, label) in zip(buttons, _NUTRITION_PAGE_LABELS.items()):
        with col:
            if target != current:
                if st.button(label, key=f"nav_foot_{target}", use_container_width=True):
                    st.session_state["_navigate_to"] = label
                    st.rerun()
            else:
                st.button(label, disabled=True, use_container_width=True)



def render_meal_analyser_page() -> None:
    """Standalone Meal Analyser page (Diet Coach tool 2)."""
    _page_intro()
    _tab2_meal_analyser()
    _nutrition_footer("meal_analyser")


def render_calorie_tracker_page() -> None:
    """Standalone Calorie Tracker page (Diet Coach tool 4)."""
    _page_intro()
    _tab4_calorie_tracker()
    _nutrition_footer("calorie_tracker")
