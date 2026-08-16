"""
Shared utilities for the AI Gym app.
"""

from __future__ import annotations

import os

from google import genai
import numpy as np
import pandas as pd
import streamlit as st

from constants import (
    BMI_CATEGORIES,
    CALORIE_MULTIPLIERS,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_REQUEST_TIMEOUT_S,
    NUTRITION_DATASET_PATH,
    WORKOUT_DATASET_PATH,
)


@st.cache_resource(show_spinner=False)
def _cached_gemini_client(api_key: str) -> genai.Client:
    """Create and cache a Gemini Client instance."""
    return genai.Client(api_key=api_key)


def initialize_gemini() -> genai.Client | None:
    """Return a cached Gemini Client if the API key is configured."""
    key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY)
    if not key or key == "YOUR_GEMINI_API_KEY_HERE":
        st.warning(
            "Gemini API key not found. Please enter your key in the sidebar Settings panel.",
            icon="🔑",
        )
        return None
    return _cached_gemini_client(key)


def get_gemini_response(prompt: str, client: genai.Client | None = None) -> str:
    """Send a prompt to Gemini and return plain text, safely catching API errors."""
    
    import sys
    import os
    
    # 1. TEMPORARILY ADD DIAGNOSTIC LOGGING
    print("\n" + "="*50)
    print("[Gemini Debug] Request started")
    print(f"[Gemini Debug] Python Executable: {sys.executable}")
    
    try:
        import google.genai as genai_module
        print(f"[Gemini Debug] SDK: google-genai (Location: {genai_module.__file__})")
    except Exception as e:
        print(f"[Gemini Debug] SDK Error: {e}")
    
    try:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE":
            print("[Gemini Debug] API key present: False")
            return "Please enter a valid Gemini API key in Settings."
            
        api_key = api_key.strip()
        print(f"[Gemini Debug] API key present: True")
        print(f"[Gemini Debug] API key length: {len(api_key)}")
        print(f"[Gemini Debug] Model: {GEMINI_MODEL}")
        
        if client is None:
            client = genai.Client(api_key=api_key)
            
        # Minimal diagnostic test FIRST
        print("[Gemini Debug] Running minimal diagnostic test...")
        test_response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents="Reply with exactly: GEMINI_TEST_OK"
        )
        print(f"[Gemini Debug] Minimal test response: {test_response.text.strip()}")
        
        print("[Gemini Debug] Running actual diet request...")
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        
        print(f"[Gemini Debug] Response received: True")
        print("[Gemini Debug] SUCCESS")
        print("="*50 + "\n")
        
        if not response or not response.text:
            print("[Gemini Debug] Warning: response or response.text is empty.")
            return "Gemini is temporarily unavailable. Please try again in a moment."
            
        return response.text.strip()
    except Exception as e:
        print(f"[Gemini Debug] Response received: False")
        print(f"[Gemini Debug] Exception Type: {type(e).__name__}")
        print(f"[Gemini Debug] Exact Exception Message: {e}")
        
        err_str = str(e).lower()
        if "404" in err_str or "not found" in err_str:
            print("[Gemini Debug] 404 MODEL_NOT_FOUND")
            print(f"[Gemini Debug] Model {GEMINI_MODEL} may be unavailable for this key.")
            print("[Gemini Debug] Attempting auto-recovery: searching for available models...")
            try:
                working_model = None
                for m in client.models.list():
                    methods = getattr(m, "supported_generation_methods", [])
                    if "generateContent" in methods:
                        name = m.name
                        if name.startswith("models/"):
                            name = name.split("/", 1)[1]
                        if "flash" in name or "pro" in name or "gemini" in name:
                            working_model = name
                            break
                if working_model:
                    print(f"[Gemini Debug] Found working model: {working_model}. Updating constants.py...")
                    with open("constants.py", "r", encoding="utf-8") as cf:
                        c_content = cf.read()
                    import re
                    c_content = re.sub(r'GEMINI_MODEL\s*=\s*os\.getenv\("GEMINI_MODEL",\s*"[^"]+"\)', f'GEMINI_MODEL    = os.getenv("GEMINI_MODEL", "{working_model}")', c_content)
                    with open("constants.py", "w", encoding="utf-8") as cf:
                        cf.write(c_content)
                        
                    print(f"[Gemini Debug] Retrying with {working_model}...")
                    response = client.models.generate_content(
                        model=working_model,
                        contents=prompt,
                    )
                    print("[Gemini Debug] Auto-recovery SUCCESS")
                    print("="*50 + "\n")
                    return response.text.strip()
                else:
                    print("[Gemini Debug] Auto-recovery FAILED: No valid models found.")
            except Exception as e2:
                print(f"[Gemini Debug] Auto-recovery Exception: {e2}")
                
        elif "401" in err_str or "403" in err_str or "unauthenticated" in err_str or "api key not valid" in err_str:
            print("[Gemini Debug] 401 INVALID_API_KEY or 403 PERMISSION_DENIED")
            
        print("="*50 + "\n")
        
        if "401" in err_str or "403" in err_str or "unauthenticated" in err_str or "api key not valid" in err_str:
            return "Gemini API authentication failed. Please check your API key."
        elif "404" in err_str or "not found" in err_str:
            return "The configured Gemini model is unavailable for this API key. Check the terminal for the exact model/API response."
        else:
            return "Gemini is temporarily unavailable. Please try again in a moment."

def calculate_bmi(weight_kg: float, height_cm: float) -> tuple[float, str]:
    """Return (bmi_value, bmi_category)."""
    if height_cm <= 0:
        return 0.0, "Invalid"
    height_m = height_cm / 100.0
    bmi = weight_kg / (height_m**2)
    category = "Unknown"
    for cat, (low, high) in BMI_CATEGORIES.items():
        if low <= bmi < high:
            category = cat
            break
    return round(bmi, 2), category


def calculate_tdee(
    weight_kg: float,
    height_cm: float,
    age: int,
    gender: str,
    activity_level: str,
) -> int:
    """Return total daily energy expenditure in kcal."""
    if gender == "Male":
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    multiplier = CALORIE_MULTIPLIERS.get(activity_level, 1.55)
    return round(bmr * multiplier)


def macro_split(calories: int, goal: str, weight_kg: float) -> dict[str, int]:
    """Return recommended macro grams based on weight, goal, and remaining calories."""
    # Determine protein and fat multipliers based on goal (g per kg of bodyweight)
    if goal == "Weight Loss":
        p_mult, f_mult = 2.2, 0.8
    elif goal == "Muscle Building":
        p_mult, f_mult = 2.0, 1.0
    elif goal == "Weight Gain":
        p_mult, f_mult = 1.8, 1.2
    elif goal == "Athletic Performance":
        p_mult, f_mult = 1.8, 1.0
    else:  # Maintenance and others
        p_mult, f_mult = 1.6, 1.0

    protein_g = int(weight_kg * p_mult)
    fat_g = int(weight_kg * f_mult)
    
    # Calculate calories taken by protein and fat
    pf_cals = (protein_g * 4) + (fat_g * 9)
    
    # Remaining calories for carbs
    remaining_cals = calories - pf_cals
    carbs_g = max(0, int(remaining_cals / 4))
    
    # Safety fallback for extreme low calories: proportional split if carbs < 0
    if remaining_cals < 0:
        return {
            "Protein (g)": round((calories * 0.4) / 4),
            "Carbs (g)": round((calories * 0.3) / 4),
            "Fat (g)": round((calories * 0.3) / 9),
        }

    return {
        "Protein (g)": protein_g,
        "Carbs (g)": carbs_g,
        "Fat (g)": fat_g,
    }


def calculate_angle(a: list, b: list, c: list) -> float:
    """Calculate the angle at point B from three 2-D points."""
    a_arr = np.array(a, dtype=float)
    b_arr = np.array(b, dtype=float)
    c_arr = np.array(c, dtype=float)
    radians = (
        np.arctan2(c_arr[1] - b_arr[1], c_arr[0] - b_arr[0])
        - np.arctan2(a_arr[1] - b_arr[1], a_arr[0] - b_arr[0])
    )
    angle = np.abs(radians * 180.0 / np.pi)
    if angle > 180.0:
        angle = 360.0 - angle
    return round(angle, 2)


def get_landmark_coords(landmarks, landmark_name: str, image_shape: tuple) -> list[float]:
    """Extract pixel coordinates for a named MediaPipe landmark."""
    import mediapipe as mp

    landmark_enum = getattr(mp.solutions.pose.PoseLandmark, landmark_name)
    landmark = landmarks[landmark_enum.value]
    height, width = image_shape[:2]
    return [landmark.x * width, landmark.y * height]


_SAMPLE_EXERCISES = pd.DataFrame(
    {
        "Title": [
            "Bench Press",
            "Squat",
            "Deadlift",
            "Pull Up",
            "Push Up",
            "Overhead Press",
            "Barbell Row",
            "Dumbbell Curl",
            "Tricep Dip",
            "Leg Press",
        ],
        "Desc": [
            "Lie on bench, lower bar to chest and press up.",
            "Stand with bar on traps, squat until thighs parallel.",
            "Pull bar from floor to hip level with neutral spine.",
            "Hang from bar, pull until chin clears the bar.",
            "Arms shoulder-width, lower chest to floor and press up.",
            "Press bar overhead from shoulder height to full extension.",
            "Hinge forward, row bar to lower chest.",
            "Curl dumbbells from hip to shoulder height.",
            "Lower body between bars until upper arm is parallel.",
            "Sit in machine and press platform away with legs.",
        ],
        "Type": ["Strength"] * 10,
        "BodyPart": [
            "Chest",
            "Legs",
            "Back",
            "Back",
            "Chest",
            "Shoulders",
            "Back",
            "Arms",
            "Triceps",
            "Legs",
        ],
        "Equipment": [
            "Barbell",
            "Barbell",
            "Barbell",
            "Pull-up Bar",
            "None",
            "Barbell",
            "Barbell",
            "Dumbbells",
            "Parallel Bars",
            "Machine",
        ],
        "Level": [
            "Beginner",
            "Beginner",
            "Intermediate",
            "Intermediate",
            "Beginner",
            "Intermediate",
            "Intermediate",
            "Beginner",
            "Intermediate",
            "Beginner",
        ],
    }
)

_SAMPLE_NUTRITION = pd.DataFrame(
    {
        "name": [
            "Chicken Breast (100g)",
            "Brown Rice (100g)",
            "Broccoli (100g)",
            "Salmon (100g)",
            "Whole Eggs (100g)",
            "Greek Yogurt (100g)",
            "Banana (100g)",
            "Sweet Potato (100g)",
            "Oats (100g)",
            "Almonds (100g)",
        ],
        "calories": [165, 216, 55, 208, 155, 59, 89, 86, 389, 579],
        "protein": [31.0, 4.5, 3.7, 20.0, 13.0, 10.0, 1.1, 1.6, 16.9, 21.2],
        "carbohydrate": [0.0, 45.0, 11.0, 0.0, 1.1, 3.6, 23.0, 20.0, 66.0, 21.6],
        "total_fat": [3.6, 1.8, 0.6, 13.0, 11.0, 0.4, 0.3, 0.1, 6.9, 49.9],
        "fiber": [0.0, 1.8, 2.6, 0.0, 0.0, 0.0, 2.6, 3.0, 10.6, 12.5],
    }
)


def load_exercise_data() -> pd.DataFrame:
    """Load exercise data or fall back to bundled sample rows."""
    try:
        if os.path.exists(WORKOUT_DATASET_PATH):
            return pd.read_csv(WORKOUT_DATASET_PATH)
    except Exception as exc:
        st.warning(f"Could not load exercise CSV: {exc}. Using sample data.")
    return _SAMPLE_EXERCISES.copy()


def load_nutrition_data() -> pd.DataFrame:
    """Load nutrition data or fall back to bundled sample rows."""
    try:
        if os.path.exists(NUTRITION_DATASET_PATH):
            return pd.read_csv(NUTRITION_DATASET_PATH)
    except Exception as exc:
        st.warning(f"Could not load nutrition CSV: {exc}. Using sample data.")
    return _SAMPLE_NUTRITION.copy()


def search_nutrition_db(query: str, df: pd.DataFrame) -> pd.DataFrame:
    """Return up to 15 case-insensitive matches for a nutrition query."""
    if df.empty:
        return df
    name_col = next(
        (column for column in df.columns if column.lower() in {"name", "food", "item", "ingredient"}),
        df.columns[0],
    )
    mask = df[name_col].astype(str).str.lower().str.contains(query.lower(), na=False)
    return df[mask].head(15)


def inject_custom_css() -> None:
    """Inject the shared CSS used across all pages."""
    st.markdown(
        """
        <style>
        html, body, [class*="css"] { font-family: 'Segoe UI', sans-serif; }

        [data-testid="metric-container"] {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            border: 1px solid #0f3460;
            border-radius: 12px;
            padding: 1rem;
        }

        .feature-card {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            border: 1px solid #0f3460;
            border-radius: 12px;
            padding: 1.4rem;
            margin-bottom: 1rem;
            height: 100%;
        }

        .feature-card h3 { color: #00D4FF; }

        .gradient-title {
            font-size: 2.6rem;
            font-weight: 800;
            background: linear-gradient(90deg, #FF6B35, #00D4FF);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-align: center;
            margin-bottom: 0.2rem;
        }

        [data-testid="stChatMessage"] {
            border-radius: 12px;
            margin-bottom: 0.5rem;
        }

        .stButton > button {
            border-radius: 8px;
            font-weight: 600;
            transition: all 0.2s ease;
        }

        .stButton > button:hover { transform: translateY(-1px); }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(icon: str, title: str, subtitle: str = "") -> None:
    """Render a consistent page header."""
    st.markdown(f"## {icon} {title}")
    if subtitle:
        st.markdown(f"*{subtitle}*")
    st.markdown("---")


def show_metrics_row(metrics: dict) -> None:
    """Render a horizontal row of Streamlit metric cards."""
    cols = st.columns(len(metrics))
    for col, (label, value) in zip(cols, metrics.items()):
        if isinstance(value, tuple):
            col.metric(label, value[0], value[1])
        else:
            col.metric(label, value)
