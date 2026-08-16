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
    print("\n" + "="*50)
    print("[Gemini] Request started")

    try:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE":
            print("[Gemini] API key missing")
            return "Please enter a valid Gemini API key in Settings."

        print(f"[Gemini] API key present: True, length: {len(api_key)}")
        print(f"[Gemini] Model: {GEMINI_MODEL}")

        if client is None:
            client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )

        if not response or not response.text:
            print("[Gemini] Empty response received")
            return "Gemini returned an empty response. Please try again."

        print("[Gemini] SUCCESS")
        print("="*50 + "\n")
        return response.text.strip()

    except Exception as e:
        err_str = str(e).lower()
        print(f"[Gemini] FAILED — {type(e).__name__}: {e}")

        # Try to auto-recover by listing available models on 404
        if ("404" in err_str or "not found" in err_str) and client is not None:
            print("[Gemini] 404: attempting model auto-recovery...")
            try:
                working_model = None
                for m in client.models.list():
                    methods = getattr(m, "supported_generation_methods", [])
                    if "generateContent" in methods:
                        name = m.name
                        if name.startswith("models/"):
                            name = name.split("/", 1)[1]
                        if "flash" in name or "pro" in name:
                            working_model = name
                            break
                if working_model:
                    print(f"[Gemini] Retrying with {working_model}")
                    response = client.models.generate_content(
                        model=working_model,
                        contents=prompt,
                    )
                    print("[Gemini] Auto-recovery SUCCESS")
                    return response.text.strip()
            except Exception as e2:
                print(f"[Gemini] Auto-recovery failed: {e2}")

        print("="*50 + "\n")

        if "401" in err_str or "403" in err_str or "unauthenticated" in err_str or "api key not valid" in err_str:
            return "Gemini API authentication failed. Please check your API key."
        elif "404" in err_str or "not found" in err_str:
            return "Gemini model unavailable. The app will use the built-in fallback."
        elif "429" in err_str or "quota" in err_str or "rate" in err_str:
            return "Gemini rate limit reached. The app will use the built-in fallback."
        else:
            return f"Gemini is temporarily unavailable. The app will use the built-in fallback."


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
def load_workout_data() -> pd.DataFrame:
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

def page_header(icon: str, title: str, subtitle: str = "") -> None:
    """Render a consistent page header."""
    st.markdown(
        f"""
        <div style="padding: 0.5rem 0 0.2rem 0;">
          <span style="font-size:2rem;">{icon}</span>
          <span style="font-size:1.8rem; font-weight:800; margin-left:0.4rem;">{title}</span>
        </div>
        {"<p style='color:#aaa;margin-top:0;'>" + subtitle + "</p>" if subtitle else ""}
        """,
        unsafe_allow_html=True,
    )
    st.markdown("---")


def show_metrics_row(metrics: dict) -> None:
    """Render a row of st.metric cards from a {label: value} dict."""
    cols = st.columns(len(metrics))
    for col, (label, value) in zip(cols, metrics.items()):
        col.metric(label, value)


# ── CSS injection ───────────────────────────────────────────────────────────────

def inject_custom_css() -> None:
    """Inject shared custom CSS."""
    st.markdown(
        """
        <style>
        .feature-card {
            background: linear-gradient(135deg, #1e1e2e 0%, #2a2a3e 100%);
            border: 1px solid #3a3a5e;
            border-radius: 12px;
            padding: 1.2rem 1.4rem;
            height: 100%;
        }
        .feature-card h3 { color: #FF6B35; margin-bottom: 0.4rem; }
        .feature-card ul { color: #ccc; padding-left: 1.2rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )
