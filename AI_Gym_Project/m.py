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

# Shared presentation components live in ui.py (design-system helpers only).
# Re-exported here so the established `from m import page_header` imports
# across pages keep working unchanged.
from ui import (  # noqa: F401  (re-exports)
    card,
    empty_state,
    page_header,
    section_header,
    section_tabs,
    stat_card,
    stat_row,
)


@st.cache_resource(show_spinner=False)
def _cached_gemini_client(api_key: str) -> genai.Client:
    """Create and cache a Gemini Client instance."""
    return genai.Client(api_key=api_key)


def initialize_gemini() -> genai.Client | None:
    """Return a cached Gemini Client if the API key is configured."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    return _cached_gemini_client(key)


def get_gemini_response(prompt: str, client: genai.Client | None = None) -> str:
    """Send a prompt to Gemini and return plain text, safely catching API errors."""
    print("\n" + "="*50)
    print("[Gemini] Request started")

    try:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        print(f"[Gemini] API key configured: {bool(api_key)}")
        print(f"[Gemini] Model: {GEMINI_MODEL}")
        
        if not api_key:
            print("[Gemini] Request failed")
            return "Gemini API key is not configured. Add GEMINI_API_KEY to the .env file."

        if client is None:
            client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )

        if not response or not response.text:
            print("[Gemini] Request failed")
            return "Gemini returned an empty response. Please try again."

        print("[Gemini] Request successful")
        print("="*50 + "\n")
        return response.text.strip()

    except Exception as e:
        err_str = str(e).lower()
        print(f"[Gemini] Request failed: {e}")
        print("="*50 + "\n")
        if "400" in err_str or "401" in err_str or "403" in err_str or "api key not valid" in err_str or "unauthenticated" in err_str or "invalid api key" in err_str or "projects/" in err_str:
            return f"Error: The Gemini API key in your .env file is invalid. Make sure it starts with 'AIza' and is not a Project ID. Details: {e}"
        return "Gemini is temporarily unavailable. Please try again in a moment."

# ── BMI / TDEE helpers ─────────────────────────────────────────────────────────

def calculate_bmi(weight_kg: float, height_cm: float) -> tuple[float, str]:
    """Return (bmi_value, category_string)."""
    if height_cm <= 0:
        return 0.0, "Unknown"
    bmi = weight_kg / (height_cm / 100) ** 2
    for cat, (lo, hi) in BMI_CATEGORIES.items():
        if lo <= bmi < hi:
            return round(bmi, 1), cat
    return round(bmi, 1), "Unknown"


def calculate_tdee(
    weight_kg: float,
    height_cm: float,
    age: int,
    gender: str,
    activity: str,
) -> int:
    """Mifflin-St Jeor TDEE."""
    if gender == "Male":
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    multiplier = CALORIE_MULTIPLIERS.get(activity, 1.55)
    return int(bmr * multiplier)


def macro_split(calories: int, goal: str, weight_kg: float) -> dict[str, int]:
    """Return protein/carbs/fat in grams for a given calorie target and goal."""
    if goal in ("Muscle Building", "Athletic Performance"):
        protein_g = int(weight_kg * 2.0)
    elif goal == "Weight Loss":
        protein_g = int(weight_kg * 1.8)
    else:
        protein_g = int(weight_kg * 1.6)

    protein_cal = protein_g * 4
    fat_g = int(calories * 0.25 / 9)
    fat_cal = fat_g * 9
    carb_cal = calories - protein_cal - fat_cal
    carb_g = max(0, int(carb_cal / 4))

    return {
        "Protein (g)": protein_g,
        "Carbs (g)": carb_g,
        "Fat (g)": fat_g,
    }


# ── Dataset loaders ─────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_nutrition_data() -> pd.DataFrame:
    """Load the nutrition CSV, returning an empty DataFrame on failure."""
    try:
        df = pd.read_csv(NUTRITION_DATASET_PATH)
        df.columns = [c.strip() for c in df.columns]
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_exercise_data() -> pd.DataFrame:
    """Load the workout/exercise CSV, returning an empty DataFrame on failure."""
    try:
        df = pd.read_csv(WORKOUT_DATASET_PATH)
        df.columns = [c.strip() for c in df.columns]
        return df
    except Exception:
        return pd.DataFrame()


def search_nutrition_db(query: str, df: pd.DataFrame) -> pd.DataFrame:
    """Return rows from the nutrition DataFrame matching the query."""
    if df.empty or not query:
        return pd.DataFrame()
    name_col = next(
        (c for c in df.columns if "name" in c.lower() or "food" in c.lower()),
        df.columns[0],
    )
    mask = df[name_col].astype(str).str.lower().str.contains(query.lower(), na=False)
    return df[mask].head(20)


# ── UI helpers ──────────────────────────────────────────────────────────────────

# page_header is provided by ui.py (typography-first: title + optional
# subtitle, no icon chip) and re-exported above.


def render_top_header() -> None:
    """Legacy hook kept for app.main() compatibility.

    The app-wide avatar/greeting bar was removed as part of the light design
    system (chrome de-cluttering); a proper greeting lives on the Home
    dashboard instead. Callers stay untouched.
    """
    return None


def show_metrics_row(metrics: dict) -> None:
    """Render a row of st.metric cards from a {label: value} dict.

    Retained: actively used by the diet and trainer pages. New surfaces
    should prefer ui.stat_row for the quieter bordered stat blocks.
    """
    cols = st.columns(len(metrics))
    for col, (label, value) in zip(cols, metrics.items()):
        col.metric(label, value)


# ── CSS injection ───────────────────────────────────────────────────────────────

_STYLES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "styles.css")


@st.cache_data(show_spinner=False)
def _load_stylesheet() -> str:
    """Load the FitAI design system stylesheet from assets/styles.css."""
    with open(_STYLES_PATH, encoding="utf-8") as fh:
        return fh.read()


def inject_custom_css() -> None:
    """Inject the shared FitAI design system (dark, premium, unified accent)."""
    st.markdown(f"<style>{_load_stylesheet()}</style>", unsafe_allow_html=True)





# ── Computer Vision helpers ─────────────────────────────────────────────────────

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
