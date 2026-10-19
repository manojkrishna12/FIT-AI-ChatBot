"""
Shared utilities for the AI Gym app.
"""

from __future__ import annotations

import os
import time

from google import genai
import numpy as np
import pandas as pd
import streamlit as st

from constants import (
    BMI_CATEGORIES,
    CALORIE_MULTIPLIERS,
    GEMINI_MAX_ATTEMPTS,
    GEMINI_MODEL,
    GEMINI_REQUEST_TIMEOUT_S,
    GEMINI_RETRY_BASE_DELAY_S,
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
    """Create and cache a Gemini Client instance (with a request timeout)."""
    http_timeout_ms = GEMINI_REQUEST_TIMEOUT_S * 1000
    return genai.Client(
        api_key=api_key,
        http_options={"timeout": http_timeout_ms},
    )


def initialize_gemini() -> genai.Client | None:
    """Return a cached Gemini Client if the API key is configured."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    return _cached_gemini_client(key)


def _safe_cached_client(api_key: str) -> genai.Client:
    """Return the cached client, or None when the resource cache is unavailable
    (bare/test mode without Streamlit runtime)."""
    try:
        return _cached_gemini_client(api_key)
    except Exception:
        return None


# Error categories returned by _classify_gemini_error. Callers (diet parsing,
# chat UI) can sniff _TRANSIENT_MARKERS in the visible text to distinguish a
# retryable outage from a configuration problem.
_TRANSIENT_MARKERS = (
    "temporarily unavailable",  # legacy message, may still be in saved state
    "still busy after",
)
_CONFIG_MARKERS = (
    "API key is not configured",
    "Gemini API key",
    "no content for this request",
)


def _classify_gemini_error(err: Exception) -> str:
    """Map a Gemini SDK exception to a classification.

    Returns one of:
      'auth'        — permanent key/permission problem, do not retry
      'transient'   — network / 429 / 5xx / timeout, worth retrying
      anything else — a ready-to-show user-facing message for a permanent
                      misconfiguration (e.g. unknown model), not retried
    """
    status = getattr(err, "code", None)  # google.genai.errors.APIError carries .code
    text = str(err).lower()

    if status in (401, 403):
        return "auth"
    if status == 400 and "api key" in text:
        return "auth"
    if status == 400:
        return ("The Gemini request was rejected (400). The configured model "
                "name may not exist for this API key — check GEMINI_MODEL "
                "in the .env file.")
    if status == 404:
        return "The configured Gemini model was not found (404). Check GEMINI_MODEL in the .env file."
    if "api key" in text or "unauthenticated" in text or "permission denied" in text:
        return "auth"
    return "transient"


def get_gemini_response(prompt: str, client: genai.Client | None = None) -> str:
    """Send a prompt to Gemini and return plain text.

    Transient failures (network, rate limits, 5xx) are retried with backoff;
    permanent ones (bad key, unknown model) fail fast. User-facing messages
    explain what went wrong and what to do; internal/API details stay in the
    server log and are never echoed to the UI.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return "Gemini API key is not configured. Add GEMINI_API_KEY to the .env file."

    if client is None:
        client = _safe_cached_client(api_key)
    if client is None:
        client = genai.Client(api_key=api_key, http_options={"timeout": GEMINI_REQUEST_TIMEOUT_S * 1000})

    attempts = GEMINI_MAX_ATTEMPTS
    last_detail = ""
    for attempt in range(1, attempts + 1):
        try:
            start = time.monotonic()
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
            elapsed = time.monotonic() - start
            if not response or not response.text:
                # An empty completion usually means the prompt was blocked;
                # retrying rarely changes that, so surface the expected state.
                print("[Gemini] Empty response (possibly content-blocked)")
                return "The model returned no content for this request — try rephrasing."
            print(f"[Gemini] OK in {elapsed:.1f}s (attempt {attempt})")
            return response.text.strip()
        except Exception as e:
            last_detail = str(e)
            print(f"[Gemini] Attempt {attempt}/{attempts} failed: {type(e).__name__}: {last_detail[:200]}")
            category = _classify_gemini_error(e)
            if category == "auth":
                print("[Gemini] Auth/config error — not retrying")
                return (
                    "The Gemini API rejected the request. The configured API key "
                    "may be invalid or lacks access. Update GEMINI_API_KEY (or "
                    "GEMINI_MODEL) in the .env file and restart."
                )
            if category != "transient":
                # A ready-made message for a permanent misconfiguration.
                return category
            if attempt < attempts:
                time.sleep(GEMINI_RETRY_BASE_DELAY_S * attempt)

    return (
        f"Gemini is still busy after {attempts} attempts. Please try again "
        "in a moment. (Transient service/network error — no details exposed.)"
    )

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
