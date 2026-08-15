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
    load_nutrition_data,
    macro_split,
    page_header,
    search_nutrition_db,
    show_metrics_row,
)
from storage import append_session_history, save_current_user_state


import json
import re

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
        text = re.sub(r',\\s*([}\\]])', r'\\1', text)
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

def ai_diet_plan(user_data: dict, model=None, is_retry=False) -> dict | str | None:
    """Generate a 7-day diet plan using JSON structure, with 1 retry on failure."""
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
2. If Cuisine/Notes suggests Indian food (or if left broad and user is in India), include common Indian foods (Roti, Dal, Paneer, Idli, etc.) while respecting the Dietary style.
3. You must provide exactly {user_data['meals_per_day']} meals per day.

Respond ONLY with a valid JSON object in the following format (do not include markdown codeblocks, just the raw JSON):
{{
  "days": [
    {{
      "day": 1,
      "meals": [
        {{
          "meal_name": "Breakfast",
          "items": "2 scrambled eggs, 1 toast",
          "serving_size": "2 eggs, 1 slice",
          "calories": 300,
          "protein": 14,
          "carbohydrates": 15,
          "fat": 10
        }}
      ]
    }}
  ]
}}
Do not calculate daily totals in the JSON, the application will do that.
"""
    if is_retry:
        prompt += "\\n\\nPREVIOUS ATTEMPT FAILED (Allergy included or invalid JSON). You MUST STRICTLY OMIT ALLERGIES AND OUTPUT VALID JSON."

    try:
        response_text = get_gemini_response(prompt, model)
        plan_data = extract_and_parse_json(response_text)
        
        if plan_data is None:
            if not is_retry:
                return ai_diet_plan(user_data, model, is_retry=True)
            return None
            
        if contains_allergy(plan_data, user_data['allergies']):
            if not is_retry:
                return ai_diet_plan(user_data, model, is_retry=True)
            return None
            
        return plan_data
    except Exception as e:
        print(f"[Dietician] AI Error: {e}")
        return None


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
        resp = get_gemini_response(prompt, model)
        if "Add a Gemini API key" in resp or "Error" in resp:
            # Deterministic fallback if API fails
            fallback = ["**Fallback Grocery List (Generated from items)**"]
            return "\\n".join(fallback) + "\\n\\nPlease configure API key for intelligent grouping."
        return resp
    except Exception as e:
        print(f"[Dietician] Grocery List Error: {e}")
        return "AI service is temporarily unavailable. Please try again in a moment."


def ai_meal_analysis(meal_description: str, model=None) -> str:
    """Generate a nutrition breakdown for a meal."""
    prompt = f"""
Analyze this meal:
{meal_description}

Return a structured markdown response with:
- **Estimated Calories**: ...
- **Protein**: ...
- **Carbs**: ...
- **Fat**: ...
- **Health Rating**: .../10
- **What's Good**: ...
- **What to Watch**: ...
- **How to Improve**: ...

CRITICAL: Clearly state at the beginning that these are AI-estimated values and may not be 100% accurate.
"""
    try:
        resp = get_gemini_response(prompt, model)
        if "Add a Gemini API key" in resp or "Error" in resp:
            return resp
        return resp
    except Exception as e:
        print(f"[Dietician] Meal Analysis Error: {e}")
        return "AI service is temporarily unavailable. Please try again in a moment."


def ai_nutrition_tip(goal: str, model=None) -> str:
    """Return one short nutrition tip."""
    try:
        prompt = f"Give one practical nutrition tip for someone focused on {goal}. Keep it under 60 words."
        return get_gemini_response(prompt, model)
    except Exception:
        return "Stay hydrated and eat balanced meals!"


def _history_expander(title: str, items: list[dict], preview_key: str) -> None:
    """Render a compact saved-history expander."""
    if not items:
        return
    with st.expander(title):
        for item in items[:5]:
            st.markdown(f"**{item['created_at']}**")
            st.caption(str(item.get(preview_key, ""))[:320] + "...")

def format_json_plan_to_markdown(plan_data: dict, target_cal: int, target_p: int, target_c: int, target_f: int) -> str:
    if not isinstance(plan_data, dict) or "days" not in plan_data:
        return str(plan_data)
        
    md = []
    for day in plan_data.get("days", []):
        md.append(f"## Day {day.get('day', 'Unknown')}")
        daily_cal = daily_p = daily_c = daily_f = 0
        for meal in day.get("meals", []):
            name = meal.get("meal_name", "Meal")
            items = meal.get("items", "")
            serving = meal.get("serving_size", "")
            cals = int(meal.get("calories", 0))
            p = int(meal.get("protein", 0))
            c = int(meal.get("carbohydrates", 0))
            f = int(meal.get("fat", 0))
            
            daily_cal += cals
            daily_p += p
            daily_c += c
            daily_f += f
            
            md.append(f"#### {name}")
            if serving:
                md.append(f"- **Items**: {items} ({serving})")
            else:
                md.append(f"- **Items**: {items}")
            md.append(f"- *Estimates: {cals} kcal | {p}g protein | {c}g carbs | {f}g fat*")
        
        md.append("---")
        md.append(f"**Daily Totals (Calculated by App from AI estimates)**:")
        md.append(f"- **Target Calories**: {target_cal} kcal | **Planned**: {daily_cal} kcal | **Difference**: {daily_cal - target_cal} kcal")
        md.append(f"- **Target Protein**: {target_p} g | **Planned Protein**: {daily_p} g | **Difference**: {daily_p - target_p} g")
        md.append(f"- **Target Carbs**: {target_c} g | **Planned Carbs**: {daily_c} g | **Difference**: {daily_c - target_c} g")
        md.append(f"- **Target Fat**: {target_f} g | **Planned Fat**: {daily_f} g | **Difference**: {daily_f - target_f} g")
        md.append("---")
    
    return "\\n".join(md)


def render_diet_page() -> None:
    """Render the Diet Coach page."""
    page_header(
        "🥗",
        "AI Dietician & Calorie Coach",
        "Your personal nutritionist — meal plans, calorie tracking, and food insights",
    )
    st.warning("🩺 **Medical Disclaimer:** The AI Dietician provides general nutrition guidance and is NOT a substitute for professional medical advice, diagnosis, or treatment. Always consult with a qualified healthcare provider with any questions you may have regarding a medical condition, pregnancy, eating disorder, or specialized diet.")

    model = None
    nutrition_df = load_nutrition_data()

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "📋 My Diet Plan",
            "🍽️ Meal Analyser",
            "🛒 Grocery List",
            "🔍 Food Database",
            "📈 Calorie Tracker",
        ]
    )

    with tab1:
        st.subheader("Generate Your Personalised 7-Day Meal Plan")
        _history_expander("Saved Diet Plan History", st.session_state.get("diet_plan_history", []), "plan")

        with st.form("diet_form"):
            left, right = st.columns(2)
            with left:
                name = st.text_input("Your Name", "User")
                age = st.number_input("Age", 10, 100, 22)
                gender = st.selectbox("Gender", ["Male", "Female", "Other"])
                weight = st.number_input("Weight (kg)", 30.0, 200.0, 65.0, step=0.5)
                height = st.number_input("Height (cm)", 100.0, 250.0, 168.0, step=0.5)
            with right:
                goal = st.selectbox(
                    "Primary Goal",
                    [
                        "Weight Loss",
                        "Weight Gain",
                        "Weight Maintenance",
                        "Muscle Building",
                        "Athletic Performance",
                    ],
                )
                activity = st.selectbox("Activity Level", list(CALORIE_MULTIPLIERS.keys()))
                diet_type = st.selectbox(
                    "Dietary Preference",
                    [
                        "No Restriction",
                        "Vegetarian",
                        "Vegan",
                        "Eggitarian",
                        "Keto",
                        "Mediterranean",
                        "Paleo",
                        "Gluten-Free",
                        "Dairy-Free",
                    ],
                )
                allergies = st.text_input("Allergies / Foods to avoid", "None")
                meals_per_day = st.number_input("Meals per day", 2, 6, 4)
                cuisine = st.text_input("Cuisine preference / Notes (optional)", "Any")
            submitted = st.form_submit_button("🍽️ Generate My Diet Plan", use_container_width=True)

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

            st.markdown("### Your Stats")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("BMI", f"{bmi}", bmi_cat)
            c2.metric("Maintenance kcal", f"{tdee}", "TDEE")
            c3.metric("Target Calories", f"{target_cal}", "kcal/day")
            c4.metric("Protein Target", f"{macros['Protein (g)']}g", "daily")

            bmi_icon = BMI_COLORS.get(bmi_cat, "⚪")
            st.info(
                f"{bmi_icon} BMI **{bmi}** — *{bmi_cat}* | "
                f"Daily target: **{target_cal} kcal** | "
                f"Protein: **{macros['Protein (g)']}g** "
                f"Carbs: **{macros['Carbs (g)']}g** "
                f"Fat: **{macros['Fat (g)']}g**"
            )

            macro_df = pd.DataFrame(
                {"Macronutrient": list(macros.keys()), "Grams": list(macros.values())}
            )
            st.bar_chart(macro_df.set_index("Macronutrient"))

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
                "allergies": allergies,
                "meals_per_day": meals_per_day,
                "cuisine": cuisine,
            }

            with st.spinner("Building your personalised 7-day meal plan..."):
                plan_data = ai_diet_plan(user_data, model)
                
            if plan_data is None:
                st.error("AI response could not be processed. Please try again in a moment.")
                st.stop()
                
            if isinstance(plan_data, dict):
                plan_md = format_json_plan_to_markdown(
                    plan_data, 
                    target_cal, 
                    macros['Protein (g)'], 
                    macros['Carbs (g)'], 
                    macros['Fat (g)']
                )
            else:
                plan_md = str(plan_data)

            st.success("Your personalised diet plan is ready.")
            st.markdown(plan_md)
            st.session_state["diet_plan"] = plan_md
            st.session_state["calorie_goal"] = target_cal
            append_session_history(
                "diet_plan_history",
                {
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "goal": goal,
                    "plan": plan_md,
                },
            )
            save_current_user_state()

            st.download_button(
                "📥 Download Diet Plan",
                plan_md,
                file_name=f"{name}_diet_plan.txt",
                mime="text/plain",
            )

            with st.spinner("Generating a personalised tip..."):
                tip = ai_nutrition_tip(goal, model)
            st.success(f"💡 Nutrition Tip: {tip}")

    with tab2:
        st.subheader("🍽️ AI Meal Analyser")
        _history_expander("Saved Meal Analysis History", st.session_state.get("meal_history", []), "analysis")
        st.write("Describe any meal and get an instant nutritional breakdown.")

        meal_input = st.text_area(
            "Describe your meal",
            placeholder=(
                "e.g. 2 scrambled eggs with whole wheat toast, butter, and a glass of orange juice"
            ),
            height=110,
        )

        left, right = st.columns([1, 2])
        with left:
            analyse_btn = st.button("🔬 Analyse This Meal", use_container_width=True)
        with right:
            if st.button("🎲 Analyse a Random Example", use_container_width=True):
                meal_input = (
                    "Grilled chicken breast 150g, brown rice 1 cup cooked, steamed broccoli, "
                    "and a drizzle of olive oil"
                )
                st.info(f"Analysing: *{meal_input}*")
                analyse_btn = True

        if analyse_btn and meal_input:
            with st.spinner("Analysing nutritional content..."):
                analysis = ai_meal_analysis(meal_input, model)
            st.subheader("Nutritional Analysis")
            st.markdown(analysis)
            append_session_history(
                "meal_history",
                {
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "meal": meal_input[:120],
                    "analysis": analysis,
                },
            )
            save_current_user_state()

            if st.button("➕ Add to Today's Calorie Log"):
                st.session_state.setdefault("calorie_log", []).append(
                    {"meal": meal_input[:60] + "...", "analysis": analysis}
                )
                save_current_user_state()
                st.success("Added to your calorie log.")

    with tab3:
        st.subheader("🛒 Smart Grocery List Generator")
        _history_expander("Saved Grocery Lists", st.session_state.get("grocery_history", []), "content")

        if st.session_state.get("diet_plan"):
            st.success("Using your latest generated diet plan.")
            plan_text = st.session_state["diet_plan"]
            st.expander("Your meal plan preview").write(plan_text[:1000] + " ...")
        else:
            st.info("Generate a diet plan first, or paste a plan below.")
            plan_text = st.text_area("Paste meal plan here", height=200, key="manual_plan")

        if st.button("🛒 Generate Grocery List", use_container_width=True, key="grocery_btn"):
            if plan_text:
                with st.spinner("Building your weekly grocery list..."):
                    groceries = ai_grocery_list(plan_text, model)
                st.subheader("Your Weekly Grocery List")
                st.markdown(groceries)
                append_session_history(
                    "grocery_history",
                    {
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "content": groceries,
                    },
                )
                save_current_user_state()
                st.download_button(
                    "📥 Download Grocery List",
                    groceries,
                    file_name="grocery_list.txt",
                    mime="text/plain",
                )
            else:
                st.warning("Please generate or paste a meal plan first.")

    with tab4:
        st.subheader("🔍 Nutrition Database Search")
        search_q = st.text_input("Search food item", placeholder="e.g. oats, salmon, banana")
        if search_q:
            results = search_nutrition_db(search_q, nutrition_df)
            if results.empty:
                st.info("No results found. Try the Meal Analyser for AI lookup.")
            else:
                st.dataframe(results, use_container_width=True)
                st.caption(f"Found {len(results)} item(s) matching '{search_q}'")

        if not nutrition_df.empty:
            with st.expander("Database Overview"):
                c1, c2 = st.columns(2)
                c1.metric("Total Food Items", f"{len(nutrition_df):,}")
                c2.metric("Data Columns", len(nutrition_df.columns))
                st.dataframe(nutrition_df.head(20), use_container_width=True)

    with tab5:
        st.subheader("📈 Today's Calorie & Macro Tracker")
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

        with st.form("tracker_form"):
            c1, c2, c3 = st.columns(3)
            meal_name = c1.text_input("Meal / Food", placeholder="e.g. Oatmeal")
            cal_entry = c2.number_input("Calories (kcal)", 0, 5000, 300)
            protein_entry = c3.number_input("Protein (g)", 0, 200, 10)
            add_entry = st.form_submit_button("➕ Add to Log", use_container_width=True)

        if add_entry and meal_name:
            st.session_state["tracker_entries"].append(
                {
                    "Meal": meal_name,
                    "Calories": cal_entry,
                    "Protein (g)": protein_entry,
                }
            )
            save_current_user_state()
            st.success(f"'{meal_name}' logged.")

        if st.session_state["tracker_entries"]:
            log_df = pd.DataFrame(st.session_state["tracker_entries"])
            total_cal = log_df["Calories"].sum()
            total_protein = log_df["Protein (g)"].sum()
            remaining = st.session_state["goal_cal_input"] - total_cal

            show_metrics_row(
                {
                    "🔥 Calories Consumed": total_cal,
                    "🎯 Calories Remaining": remaining,
                    "💪 Protein Consumed": f"{total_protein}g",
                }
            )

            progress = min(total_cal / st.session_state["goal_cal_input"], 1.0)
            st.progress(progress, text=f"{int(progress * 100)}% of daily goal reached")
            st.dataframe(log_df, use_container_width=True)

            if st.button("🗑️ Clear Log"):
                st.session_state["tracker_entries"] = []
                save_current_user_state()
                st.rerun()
        else:
            st.info("No entries yet. Log your meals above.")
