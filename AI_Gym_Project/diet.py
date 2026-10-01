"""
Diet Coach page with per-user saved plans, analyses, and tracker state.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from constants import BMI_COLORS, CALORIE_MULTIPLIERS
from m import (
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

def ai_grocery_list(meal_plan: str, model=None) -> str:
    """Generate a grocery list from a meal plan."""
    prompt = f"""
Based on this 7-day meal plan, generate a weekly grocery list for one person.

Meal plan:
{meal_plan[:3000]}

CRITICAL:
1. Group items logically exactly into these categories: Produce, Protein, Grains/Carbohydrates, Dairy, Other.
2. Avoid duplicate items. Combine quantities if necessary.
3. End with 2 practical shopping tips.
"""
    try:
        resp = get_gemini_response(prompt)
        if "Add a Gemini API key" in resp or "Error" in resp:
            # Deterministic fallback if API fails
            fallback = ["**Fallback Grocery List (Generated from items)**"]
            return "\\n".join(fallback) + "\\n\\nPlease configure API key for intelligent grouping."
        return resp
    except Exception as e:
        print(f"[Dietician] Grocery List Error: {e}")
        return "AI service is temporarily unavailable. Please try again in a moment."


def ai_meal_analysis_structured(meal_description: str, model=None) -> dict | None:
    """Generate a nutrition breakdown for a meal; structured dict, None if unavailable."""
    prompt = f"""Analyze this meal and return ONLY a valid JSON object (no markdown formatting, no extra text).
Meal: {meal_description}

Return exactly this JSON structure:
{{
  "calories": 350,
  "protein": 25,
  "carbs": 40,
  "fat": 10,
  "fiber": 5,
  "serving_assumption": "1 standard serving",
  "notes": "brief health note"
}}
Use realistic estimated values. All numeric fields must be integers.
"""
    try:
        resp = get_gemini_response(prompt)

        if not resp or resp.startswith("Error:") or "unavailable" in resp.lower() or "failed" in resp.lower() or "api key" in resp.lower():
            return None

        data = extract_and_parse_json(resp)
        if not isinstance(data, dict) or "calories" not in data:
            return None
        data.setdefault("protein", 0)
        data.setdefault("carbs", 0)
        data.setdefault("fat", 0)
        data.setdefault("fiber", 0)
        data.setdefault("serving_assumption", "1 standard serving")
        data.setdefault("notes", "")
        return data
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



def ai_macro_tracker(meal_description: str, model=None) -> dict | None:
    """Analyze a meal and return structured macros as a dict."""
    prompt = f"""Analyze this meal and return ONLY a valid JSON object (no markdown, no extra text):
Meal: {meal_description}

Return exactly this JSON structure:
{{
  "food": "brief meal name",
  "calories": 350,
  "protein": 25,
  "carbs": 40,
  "fat": 10,
  "fiber": 5,
  "serving_assumption": "1 standard serving",
  "notes": "brief health note"
}}

Use realistic estimated values. All numeric fields must be integers."""
    try:
        resp = get_gemini_response(prompt)
        # Try to parse JSON from response
        import json, re
        text = resp.strip()
        if "```" in text:
            text = text.split("```")[1].split("```")[0]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text.strip())
        # Validate required fields
        for field in ["calories", "protein", "carbs", "fat"]:
            if field not in result:
                result[field] = 0
        result.setdefault("fiber", 0)
        result.setdefault("food", meal_description[:50])
        result.setdefault("serving_assumption", "1 standard serving")
        result.setdefault("notes", "")
        return result
    except Exception:
        # Deterministic fallback: return rough estimate
        words = meal_description.lower().split()
        base_cal = 300
        if any(w in words for w in ["chicken", "fish", "meat", "beef", "pork"]):
            return {"food": meal_description[:50], "calories": 400, "protein": 35,
                    "carbs": 20, "fat": 15, "fiber": 3,
                    "serving_assumption": "1 standard serving",
                    "notes": "Estimated — AI unavailable"}
        elif any(w in words for w in ["rice", "pasta", "bread", "roti", "chapati"]):
            return {"food": meal_description[:50], "calories": 350, "protein": 10,
                    "carbs": 65, "fat": 5, "fiber": 4,
                    "serving_assumption": "1 standard serving",
                    "notes": "Estimated — AI unavailable"}
        else:
            return {"food": meal_description[:50], "calories": base_cal, "protein": 15,
                    "carbs": 40, "fat": 10, "fiber": 5,
                    "serving_assumption": "1 standard serving",
                    "notes": "Estimated — AI unavailable"}


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
        cal_offset = {
            "Weight Loss": -500,
            "Weight Gain": 400,
            "Muscle Building": 300,
            "Weight Maintenance": 0,
            "Athletic Performance": 0,
        }
        target_cal = tdee + cal_offset.get(goal, 0)
        
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
    """Meal analyser tool (page body)."""
    model = None  # Gemini client; helpers create their own when None
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
            save_current_user_state()
        else:
            st.session_state.pop("pending_meal_analysis", None)

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

        if st.button("Add to today's log", key="add_meal_to_log"):
            st.session_state.setdefault("calorie_log", []).append(
                {"meal": meal_input[:60] + "...", "analysis": "meal analysis"}
            )
            st.session_state.setdefault("tracker_entries", []).append({
                "Meal": meal_input[:60] + "...",
                "Calories": int(result.get("calories", 0) or 0),
                "Protein (g)": int(result.get("protein", 0) or 0),
                "Carbs (g)": int(result.get("carbs", 0) or 0),
                "Fat (g)": int(result.get("fat", 0) or 0),
                "Fiber (g)": int(result.get("fiber", 0) or 0),
            })
            st.session_state.pop("pending_meal_analysis", None)
            save_current_user_state()
            st.toast("Added to today's log.")
            st.rerun()


def _tab3_grocery_list() -> None:
    """Grocery list tool (page body)."""
    model = None  # Gemini client; helpers create their own when None
    section_header("Grocery list", "A weekly shopping list from your meal plan")
    if st.session_state.get("diet_plan"):
        with st.expander("Your latest meal plan", expanded=False):
            st.markdown(st.session_state["diet_plan"][:1000] + " …")
        plan_text = st.session_state["diet_plan"]
    else:
        st.info("Generate a diet plan first, or paste one below.")
        plan_text = st.text_area("Paste meal plan here", height=200, key="manual_plan")

    if st.button("Generate grocery list", type="primary", use_container_width=True, key="grocery_btn"):
        if plan_text:
            with st.spinner("Building your weekly grocery list..."):
                groceries = ai_grocery_list(plan_text, model)
            section_header("Your weekly grocery list")
            st.markdown('<div class="plan-output">' + groceries + "</div>", unsafe_allow_html=True)
            save_current_user_state()
            st.download_button(
                "Download grocery list",
                groceries,
                file_name="grocery_list.txt",
                mime="text/plain",
            )
        else:
            st.warning("Please generate or paste a meal plan first.")


def _tab4_calorie_tracker() -> None:
    """Calorie tracker tool (page body)."""
    section_header("Calorie tracker", "What you've eaten today and what remains")
    goal_cal = st.session_state.get("calorie_goal", 2000)
    st.number_input(
        "Daily Calorie Goal (kcal)",
        800,
        5000,
        goal_cal,
        key="goal_cal_input",
        help="Auto-filled from your diet plan, or set manually.",
    )

    st.session_state.setdefault("tracker_entries", [])
    st.session_state.setdefault("pending_analysis", None)

    meal_desc = st.text_area("Describe your meal or food", placeholder="e.g. 2 eggs and 2 cups of milk", height=80)

    if st.button("Analyze meal", use_container_width=True):
        if not meal_desc.strip():
            st.warning("Please enter a meal description.")
        else:
            with st.spinner("Analyzing nutrition..."):
                result = ai_macro_tracker(meal_desc, model)
                if result:
                    st.session_state["pending_analysis"] = result
                else:
                    st.error("Unable to analyze this meal right now. Please try again.")
                    st.session_state["pending_analysis"] = None

    if st.session_state.get("pending_analysis"):
        res = st.session_state["pending_analysis"]
        section_header("Meal analysis")
        st.markdown(f"**{res.get('food', meal_desc)}**")

        stat_row([
            {"label": "Calories", "value": f"{res.get('calories', 0)}"},
            {"label": "Protein", "value": f"{res.get('protein', 0)} g"},
            {"label": "Carbs", "value": f"{res.get('carbs', 0)} g"},
            {"label": "Fat", "value": f"{res.get('fat', 0)} g"},
            {"label": "Fiber", "value": f"{res.get('fiber', 0)} g"},
        ])

        st.caption(f"Estimated based on: {res.get('serving_assumption', 'typical serving sizes')}")
        if res.get('notes'):
            st.caption(res['notes'])

        st.caption("Nutrition values are estimates and can vary by brand, preparation method, and serving size.")

        if st.button("Add to today's log", type="primary", use_container_width=True, key="tracker_add_btn"):
            st.session_state["tracker_entries"].append({
                "Meal": res.get("food", meal_desc),
                "Calories": res.get("calories", 0),
                "Protein (g)": res.get("protein", 0),
                "Carbs (g)": res.get("carbs", 0),
                "Fat (g)": res.get("fat", 0),
                "Fiber (g)": res.get("fiber", 0),
            })
            st.session_state["pending_analysis"] = None
            save_current_user_state()
            st.success("Meal added to today's log!")
            st.rerun()

    section_header("Today's log")
    if st.session_state["tracker_entries"]:
        log_df = pd.DataFrame(st.session_state["tracker_entries"])
        total_cal = log_df["Calories"].sum()
        total_protein = log_df.get("Protein (g)", pd.Series(dtype=int)).sum()
        total_carbs = log_df.get("Carbs (g)", pd.Series(dtype=int)).sum()
        total_fat = log_df.get("Fat (g)", pd.Series(dtype=int)).sum()
        total_fiber = log_df.get("Fiber (g)", pd.Series(dtype=int)).sum()

        remaining = st.session_state["goal_cal_input"] - total_cal

        stat_row([
            {"label": "Calories", "value": f"{int(total_cal):,}", "hint": f"goal {int(st.session_state['goal_cal_input']):,}"},
            {"label": "Remaining", "value": f"{int(remaining):,}"},
            {"label": "Protein", "value": f"{int(total_protein)} g"},
            {"label": "Carbs", "value": f"{int(total_carbs)} g"},
            {"label": "Fat", "value": f"{int(total_fat)} g"},
            {"label": "Fiber", "value": f"{int(total_fiber)} g"},
        ])

        progress = min(total_cal / max(1, st.session_state["goal_cal_input"]), 1.0)
        st.progress(progress, text=f"{int(progress * 100)}% of daily goal")
        st.dataframe(log_df, use_container_width=True)

        if st.button("Clear log", key="tracker_clear_btn"):
            st.session_state["tracker_entries"] = []
            st.session_state["pending_analysis"] = None
            save_current_user_state()
            st.rerun()
    else:
        empty_state(
            "Nothing logged yet",
            "Analyze a meal above and add it to build today's log.",
        )


def render_diet_page() -> None:
    """Render the combined Diet Coach page (all four tools in sequence)."""
    _page_intro()
    _tab1_diet_plan()
    st.markdown("---")
    _tab2_meal_analyser()
    st.markdown("---")
    _tab3_grocery_list()
    st.markdown("---")
    _tab4_calorie_tracker()


# ── Cross-page navigation between the Nutrition tools ──────────────────
# NOTE: labels must mirror the PAGE_* constants in app.py exactly;
# tests/test_nav_labels.py (Phase 7) asserts they stay in sync.


_NUTRITION_PAGE_LABELS = {
    "diet": "Diet Coach",
    "meal_analyser": "Meal Analyser",
    "grocery_list": "Grocery List",
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


def render_grocery_list_page() -> None:
    """Standalone Grocery List page (Diet Coach tool 3)."""
    _page_intro()
    _tab3_grocery_list()
    _nutrition_footer("grocery_list")


def render_calorie_tracker_page() -> None:
    """Standalone Calorie Tracker page (Diet Coach tool 4)."""
    _page_intro()
    _tab4_calorie_tracker()
    _nutrition_footer("calorie_tracker")
