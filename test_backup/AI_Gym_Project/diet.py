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
from storage import save_current_user_state


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
        response_text = get_gemini_response(prompt, model)
        
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



def format_json_plan_to_markdown(plan_data: dict, target_cal: int, target_p: int, target_c: int, target_f: int) -> str:
    if not isinstance(plan_data, dict) or "days" not in plan_data:
        return str(plan_data)
        
    md = []
    for day in plan_data.get("days", []):
        md.append(f"## Day {day.get('day', 'Unknown')}")
        daily_cal = daily_p = daily_c = daily_f = 0
        for meal in day.get("meals", []):
            name = meal.get("name", meal.get("meal_name", "Meal"))
            items = ""
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
            
            md.append(f"#### {name}")
            md.append(f"- **Items**: {items}")
            md.append(f"- *Estimates: {cals} kcal | {p}g protein | {c}g carbs | {f}g fat*")
        
        md.append("\n**Target vs Planned**\n")
        
        md.append("Calories:")
        md.append(f"Target {target_cal}")
        md.append(f"Planned {daily_cal}")
        md.append(f"Difference {daily_cal - target_cal}\n")
        
        md.append("Protein:")
        md.append(f"Target {target_p} g")
        md.append(f"Planned {daily_p} g")
        md.append(f"Difference {daily_p - target_p} g\n")

        md.append("Carbs:")
        md.append(f"Target {target_c} g")
        md.append(f"Planned {daily_c} g")
        md.append(f"Difference {daily_c - target_c} g\n")

        md.append("Fat:")
        md.append(f"Target {target_f} g")
        md.append(f"Planned {daily_f} g")
        md.append(f"Difference {daily_f - target_f} g\n")
        md.append("---")
    
    return "\n".join(md)

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

            st.markdown("### Daily Target (Calculated)")
            st.markdown(f"**Calories**: {target_cal} kcal")
            st.markdown(f"**Protein**: {macros['Protein (g)']} g")
            st.markdown(f"**Carbs**: {macros['Carbs (g)']} g")
            st.markdown(f"**Fat**: {macros['Fat (g)']} g")
            st.caption("These are calculated targets used as constraints for the AI.")
            
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

            # Clear stale error session state
            if "diet_plan_error" in st.session_state:
                st.session_state.pop("diet_plan_error", None)

            with st.spinner("Building your personalised 7-day meal plan..."):
                plan_data = ai_diet_plan(user_data, model)
                
            if isinstance(plan_data, dict):
                if plan_data.get("source") == "PYTHON_FALLBACK":
                    st.info("Generated using the built-in nutrition engine because AI generation is temporarily unavailable.")
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

            st.success("Your personalised diet plan is ready.")
            st.markdown(plan_md)
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
            st.success(f"💡 Nutrition Tip: {tip}")

    with tab2:
        st.subheader("🍽️ AI Meal Analyser")
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
            save_current_user_state()

            if st.button("➕ Add to Today's Calorie Log"):
                st.session_state.setdefault("calorie_log", []).append(
                    {"meal": meal_input[:60] + "...", "analysis": analysis}
                )
                save_current_user_state()
                st.success("Added to your calorie log.")

    with tab3:
        st.subheader("🛒 Smart Grocery List Generator")
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
        st.session_state.setdefault("pending_analysis", None)

        meal_desc = st.text_area("Describe your meal or food", placeholder="e.g. 2 eggs and 2 cups of milk", height=80)
        
        if st.button("🔍 Analyze Meal", use_container_width=True):
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
            st.markdown("### Meal Analysis")
            st.markdown(f"🍽️ **{res.get('food', meal_desc)}**")
            
            # Display metrics nicely
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Calories", f"{res.get('calories', 0)} kcal")
            c2.metric("Protein", f"{res.get('protein', 0)} g")
            c3.metric("Carbs", f"{res.get('carbs', 0)} g")
            c4.metric("Fat", f"{res.get('fat', 0)} g")
            c5.metric("Fiber", f"{res.get('fiber', 0)} g")
            
            st.caption(f"*Estimated based on: {res.get('serving_assumption', 'Typical serving sizes')}*")
            if res.get('notes'):
                st.caption(f"*{res.get('notes')}*")
                
            st.caption("Nutrition values are estimates and can vary by brand, preparation method, and serving size.")
            
            if st.button("➕ Add to Today's Log", use_container_width=True):
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

        st.markdown("---")
        if st.session_state["tracker_entries"]:
            log_df = pd.DataFrame(st.session_state["tracker_entries"])
            total_cal = log_df["Calories"].sum()
            total_protein = log_df.get("Protein (g)", pd.Series(dtype=int)).sum()
            total_carbs = log_df.get("Carbs (g)", pd.Series(dtype=int)).sum()
            total_fat = log_df.get("Fat (g)", pd.Series(dtype=int)).sum()
            total_fiber = log_df.get("Fiber (g)", pd.Series(dtype=int)).sum()
            
            remaining = st.session_state["goal_cal_input"] - total_cal

            show_metrics_row(
                {
                    "🔥 Calories Consumed": total_cal,
                    "🎯 Calories Remaining": remaining,
                    "💪 Total Protein": f"{total_protein}g",
                }
            )
            
            # Show secondary macros
            sc1, sc2, sc3 = st.columns(3)
            sc1.metric("🍞 Total Carbs", f"{total_carbs}g")
            sc2.metric("🥑 Total Fat", f"{total_fat}g")
            sc3.metric("🥦 Total Fiber", f"{total_fiber}g")

            progress = min(total_cal / max(1, st.session_state["goal_cal_input"]), 1.0)
            st.progress(progress, text=f"{int(progress * 100)}% of daily goal reached")
            st.dataframe(log_df, use_container_width=True)

            if st.button("🗑️ Clear Log"):
                st.session_state["tracker_entries"] = []
                st.session_state["pending_analysis"] = None
                save_current_user_state()
                st.rerun()
        else:
            st.info("No entries yet. Analyze and log your meals above.")
