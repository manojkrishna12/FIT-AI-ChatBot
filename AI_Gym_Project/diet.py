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


def ai_diet_plan(user_data: dict, model=None) -> str:
    """Generate a 7-day diet plan."""
    prompt = f"""
You are a certified nutritionist.

Create a practical 7-day meal plan for:
Name: {user_data['name']}
Age: {user_data['age']}
Gender: {user_data['gender']}
Weight: {user_data['weight']} kg
Height: {user_data['height']} cm
BMI: {user_data['bmi']} ({user_data['bmi_cat']})
Activity: {user_data['activity']}
Goal: {user_data['goal']}
Calories: {user_data['calories']} kcal
Protein: {user_data['macros']['Protein (g)']} g
Carbs: {user_data['macros']['Carbs (g)']} g
Fat: {user_data['macros']['Fat (g)']} g
Dietary style: {user_data['diet_type']}
Allergies: {user_data['allergies']}
Cuisine: {user_data['cuisine']}

Format each day with breakfast, lunch, dinner, snacks, hydration, and daily total.
End with 5 tips and one motivating note.
"""
    return get_gemini_response(prompt, model)


def ai_grocery_list(meal_plan: str, model=None) -> str:
    """Generate a grocery list from a meal plan."""
    prompt = f"""
Based on this 7-day meal plan, generate a weekly grocery list for one person.

Meal plan:
{meal_plan[:3000]}

Organize it by category and keep quantities specific.
End with 2 practical shopping tips.
"""
    return get_gemini_response(prompt, model)


def ai_meal_analysis(meal_description: str, model=None) -> str:
    """Generate a nutrition breakdown for a meal."""
    prompt = f"""
Analyze this meal:
{meal_description}

Return:
- Estimated calories
- Protein
- Carbs
- Fat
- Health rating out of 10
- What's good
- What to watch
- How to make it healthier
"""
    return get_gemini_response(prompt, model)


def ai_nutrition_tip(goal: str, model=None) -> str:
    """Return one short nutrition tip."""
    prompt = f"Give one practical nutrition tip for someone focused on {goal}. Keep it under 60 words."
    return get_gemini_response(prompt, model)


def _history_expander(title: str, items: list[dict], preview_key: str) -> None:
    """Render a compact saved-history expander."""
    if not items:
        return
    with st.expander(title):
        for item in items[:5]:
            st.markdown(f"**{item['created_at']}**")
            st.caption(item.get(preview_key, "")[:320] + "...")


def render_diet_page() -> None:
    """Render the Diet Coach page."""
    page_header(
        "🥗",
        "AI Dietician & Calorie Coach",
        "Your personal nutritionist — meal plans, calorie tracking, and food insights",
    )

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
                        "Keto",
                        "Mediterranean",
                        "Paleo",
                        "Gluten-Free",
                        "Dairy-Free",
                    ],
                )
                allergies = st.text_input("Allergies / Foods to avoid", "None")
                cuisine = st.text_input("Cuisine preference (optional)", "Any")
            submitted = st.form_submit_button("🍽️ Generate My Diet Plan", use_container_width=True)

        if submitted:
            bmi, bmi_cat = calculate_bmi(weight, height)
            tdee = calculate_tdee(weight, height, age, gender, activity)
            cal_offset = {
                "Weight Loss": -500,
                "Weight Gain": 400,
                "Muscle Building": 300,
                "Weight Maintenance": 0,
                "Athletic Performance": 0,
            }
            target_cal = max(1200, tdee + cal_offset.get(goal, 0))
            macros = macro_split(target_cal, goal)

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
                "cuisine": cuisine,
            }

            with st.spinner("Building your personalised 7-day meal plan..."):
                plan = ai_diet_plan(user_data, model)

            st.success("Your personalised diet plan is ready.")
            st.markdown(plan)
            st.session_state["diet_plan"] = plan
            st.session_state["calorie_goal"] = target_cal
            append_session_history(
                "diet_plan_history",
                {
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "goal": goal,
                    "plan": plan,
                },
            )
            save_current_user_state()

            st.download_button(
                "📥 Download Diet Plan",
                plan,
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
