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

def page_header(icon: str, title: str, subtitle: str = "") -> None:
    """Render a consistent styled page header used across all modules."""
    subtitle_html = f'<div class="page-head-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div class="page-head">
          <div class="page-head-icon">{icon}</div>
          <div>
            <div class="page-head-title">{title}</div>
            {subtitle_html}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_top_header() -> None:
    """Render the app-wide top header (welcome message + profile chip)."""
    raw = st.session_state.get("active_user_id", "") or ""
    display = "Guest"
    if raw and raw.strip() and raw.strip().lower() != "guest":
        display = raw.strip().replace("-", " ").title()
    initial = display[0].upper()
    st.markdown(
        f"""
        <div class="topbar">
          <div>
            <div class="topbar-title">Welcome, {display} 👋</div>
            <div class="topbar-sub">Your personal AI fitness assistant.</div>
          </div>
          <div class="topbar-right">
            <div class="topbar-avatar">{initial}</div>
            <div>
              <div class="topbar-name">{display}</div>
              <div class="topbar-role">Member</div>
            </div>
          </div>
        </div>
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
    """Inject the shared FitAI design system (dark, premium, unified accent)."""
    css = """
    <style>
    /* ── Fonts & base ─────────────────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, .stApp, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }
    .stApp {
        background:
            radial-gradient(1100px 520px at 88% -12%, rgba(157, 92, 255, 0.10), transparent 60%),
            radial-gradient(900px 480px at -10% 112%, rgba(255, 46, 99, 0.08), transparent 55%),
            #0b0f19;
        color: #eef1f7;
    }
    html { color-scheme: dark; }

    /* ── Hide default Streamlit chrome ────────────────────────────── */
    [data-testid="stHeader"], .stAppHeader, [data-testid="stToolbar"],
    [data-testid="stDecoration"], #MainMenu, footer { display: none !important; }

    .block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1280px; margin: 0 auto; }

    /* ── Scrollbar ────────────────────────────────────────────────── */
    .stApp ::-webkit-scrollbar { width: 9px; height: 9px; }
    .stApp ::-webkit-scrollbar-track { background: transparent; }
    .stApp ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.12); border-radius: 8px; }
    .stApp ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.22); }

    /* ── Sidebar ──────────────────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background: #0d1220;
        border-right: 1px solid rgba(255,255,255,0.06);
        width: 268px; min-width: 268px;
    }
    .set-label { font-size: 0.72rem; font-weight: 600; color: #8b93a5; margin-bottom: 0.3rem; }
    .set-divider { height: 1px; background: rgba(255,255,255,0.07); margin: 0.75rem 0; }
    section[data-testid="stSidebar"] [data-testid="stSidebarContent"] { padding: 1.15rem 0.9rem 1.5rem; }

    .brand { display: flex; align-items: center; gap: 0.7rem; padding: 0.15rem 0.35rem 0.9rem; }
    .brand-name { font-size: 1.22rem; font-weight: 800; letter-spacing: -0.02em; color: #fff; line-height: 1.1; }
    .brand-sub { font-size: 0.72rem; color: #8b93a5; margin-top: 0.15rem; }

    .nav-label { font-size: 0.66rem; font-weight: 700; letter-spacing: 0.12em; color: #5d6577;
                 text-transform: uppercase; margin: 0.9rem 0.45rem 0.4rem; }
    .sidebar-divider { height: 1px; background: rgba(255,255,255,0.07); margin: 0.55rem 0.35rem; }

    /* Navigation radio → nav pills */
    section[data-testid="stSidebar"] [role="radiogroup"] { gap: 3px; display: flex; flex-direction: column; }
    section[data-testid="stSidebar"] [role="radiogroup"] label {
        display: flex; align-items: center; gap: 0.65rem;
        padding: 0.52rem 0.85rem; margin: 0;
        border-radius: 12px; cursor: pointer;
        color: #a8b0c0; font-weight: 500; font-size: 0.95rem;
        transition: background 0.15s ease, color 0.15s ease;
    }
    section[data-testid="stSidebar"] [role="radiogroup"] label:hover { background: rgba(255,255,255,0.05); color: #fff; }
    section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
        background: linear-gradient(135deg, rgba(255,75,43,0.92), rgba(139,92,246,0.92));
        color: #fff; font-weight: 600;
        box-shadow: 0 8px 22px rgba(255,75,43,0.22);
    }
    section[data-testid="stSidebar"] [role="radiogroup"] input { position: absolute; opacity: 0; pointer-events: none; }
    section[data-testid="stSidebar"] [role="radiogroup"] label > div:first-child { display: none !important; }
    section[data-testid="stSidebar"] [role="radiogroup"] [data-testid="stMarkdownContainer"] { width: 100%; }

    /* Sidebar inputs / expanders / captions */
    section[data-testid="stSidebar"] [data-testid="stTextInput"] input {
        background: #121826; border: 1px solid rgba(255,255,255,0.09); border-radius: 10px; color: #eef1f7;
    }
    section[data-testid="stSidebar"] [data-testid="stTextInput"] input:focus { border-color: rgba(255,105,80,0.7); }
    section[data-testid="stSidebar"] [data-testid="stExpander"] { border: none; background: transparent; }
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary {
        padding: 0.45rem 0.7rem; border-radius: 10px; color: #a8b0c0; font-weight: 500; font-size: 0.93rem;
    }
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover { background: rgba(255,255,255,0.05); color: #fff; }
    section[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stCaptionContainer"] { color: #7e8799; }
    section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] .stMarkdown p { color: #a8b0c0; font-size: 0.86rem; }

    /* Motivational card */
    .mcard {
        margin-top: 1rem; padding: 1rem 1.05rem;
        background: linear-gradient(150deg, #151d30, #10162a);
        border: 1px solid rgba(255,255,255,0.08); border-radius: 16px;
        display: flex; align-items: center; justify-content: space-between; gap: 0.6rem;
    }
    .mcard-text { font-size: 0.85rem; font-weight: 600; color: #e8ecf4; line-height: 1.45; }
    .mcard-accent { color: #ff6a5b; }
    .mcard-icon { font-size: 1.7rem; opacity: 0.9; }

    /* ── Top header ───────────────────────────────────────────────── */
    .topbar {
        display: flex; align-items: center; justify-content: space-between; gap: 1rem;
        padding: 0.2rem 0 1.15rem;
    }
    .topbar-title { font-size: 1.5rem; font-weight: 800; letter-spacing: -0.02em; color: #fff; }
    .topbar-sub { font-size: 0.9rem; color: #8b93a5; margin-top: 0.2rem; }
    .topbar-right { display: flex; align-items: center; gap: 0.7rem; }
    .topbar-avatar {
        width: 40px; height: 40px; border-radius: 50%;
        background: linear-gradient(135deg, #ff6a3d, #ff2e63, #9d5cff);
        color: #fff; font-weight: 700; font-size: 1.02rem;
        display: flex; align-items: center; justify-content: center;
        box-shadow: 0 6px 18px rgba(255, 46, 99, 0.30);
    }
    .topbar-name { font-size: 0.92rem; font-weight: 600; color: #eef1f7; }
    .topbar-role { font-size: 0.72rem; color: #8b93a5; }

    /* ── Page headers (all modules) ───────────────────────────────── */
    .page-head { display: flex; align-items: center; gap: 0.9rem; padding: 0.4rem 0 0.2rem; }
    .page-head-icon {
        width: 52px; height: 52px; border-radius: 15px; font-size: 1.6rem;
        background: linear-gradient(135deg, rgba(255,75,43,0.22), rgba(139,92,246,0.22));
        border: 1px solid rgba(255,255,255,0.1);
        display: flex; align-items: center; justify-content: center;
    }
    .page-head-title { font-size: 1.5rem; font-weight: 800; letter-spacing: -0.02em; color: #fff; }
    .page-head-sub { font-size: 0.88rem; color: #8b93a5; margin-top: 0.15rem; }

    /* ── Typography ───────────────────────────────────────────────── */
    h1, h2, h3, h4 { color: #f2f4f8 !important; letter-spacing: -0.01em; }
    .stMarkdown a { color: #ff8a75; }
    .stMarkdown code, code {
        background: rgba(255,255,255,0.08); color: #ffd9d2;
        border-radius: 6px; padding: 0.1em 0.4em;
    }
    pre {
        background: #131a2a !important; border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px !important; color: #dbe0ea;
    }
    .stCaptionContainer p, [data-testid="stCaptionContainer"] { color: #7e8799; }

    /* ── Buttons ──────────────────────────────────────────────────── */
    [data-testid="stBaseButton-secondary"], [data-testid="stDownloadButton"] button {
        background: #161e30; border: 1px solid rgba(255,255,255,0.12); color: #e8ebf2;
        border-radius: 12px; padding: 0.55rem 1.05rem; font-weight: 600;
        transition: all 0.15s ease;
    }
    [data-testid="stBaseButton-secondary"]:hover, [data-testid="stDownloadButton"] button:hover {
        background: #1f2a42; border-color: rgba(255,106,61,0.45); color: #fff;
    }
    [data-testid="stBaseButton-primary"] {
        background: linear-gradient(135deg, #ff6a3d, #ff2e63, #9d5cff);
        border: none; color: #fff; font-weight: 700;
        border-radius: 12px; padding: 0.62rem 1.25rem;
        box-shadow: 0 10px 26px rgba(255, 46, 99, 0.30);
        transition: all 0.15s ease;
    }
    [data-testid="stBaseButton-primary"]:hover { filter: brightness(1.1); box-shadow: 0 12px 30px rgba(255, 46, 99, 0.38); }
    .stFormSubmitButton button { width: 100%; }

    /* ── Inputs ───────────────────────────────────────────────────── */
    [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
    [data-testid="stTextArea"] textarea {
        background: #121826; border: 1px solid rgba(255,255,255,0.09);
        border-radius: 10px; color: #eef1f7; caret-color: #ff8a75;
    }
    [data-testid="stTextInput"] input:focus, [data-testid="stNumberInput"] input:focus,
    [data-testid="stTextArea"] textarea:focus { border-color: rgba(255,105,80,0.7); box-shadow: 0 0 0 2px rgba(255,105,80,0.12); }
    [data-testid="stTextInput"] label, [data-testid="stTextArea"] label,
    [data-testid="stSelectbox"] label, [data-testid="stMultiSelect"] label,
    [data-testid="stNumberInput"] label, [data-testid="stSlider"] label { color: #a8b0c0; }
    [data-baseweb="select"] > div, [data-testid="stMultiSelect"] [data-baseweb="select"] {
        background: #121826 !important; border: 1px solid rgba(255,255,255,0.09) !important;
        border-radius: 10px !important; color: #eef1f7 !important;
    }
    [data-testid="stNumberInput"] button { background: #171f31 !important; border-color: rgba(255,255,255,0.09) !important; }
    [data-baseweb="popover"] { background: #141d30 !important; border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; }
    [data-baseweb="popover"] li, [data-baseweb="popover"] [role="option"] { color: #dbe0ea !important; }
    [data-baseweb="popover"] li:hover, [data-baseweb="popover"] [role="option"]:hover { background: rgba(255,255,255,0.07) !important; }
    [data-testid="stSlider"] [role="slider"] { background: #ff4b2b !important; border-color: #ff4b2b !important; }
    [data-testid="stCheckbox"] { color: #a8b0c0; }

    /* ── File uploader ────────────────────────────────────────────── */
    [data-testid="stFileUploader"] {
        background: #111827; border: 1px dashed rgba(255,255,255,0.18);
        border-radius: 14px; padding: 0.2rem;
    }
    [data-testid="stFileUploader"] button { background: #171f31; border: 1px solid rgba(255,255,255,0.12); border-radius: 10px; color: #eef1f7; }
    [data-testid="stFileUploader"] button:hover { background: #212c44; }

    /* ── Tabs ─────────────────────────────────────────────────────── */
    [data-testid="stTabs"] { gap: 0.35rem; }
    [data-testid="stTabs"] button[role="tab"] {
        background: transparent; border: none; color: #8b93a5;
        font-weight: 600; font-size: 0.92rem;
        padding: 0.6rem 0.95rem; border-radius: 10px;
        transition: all 0.15s ease;
    }
    [data-testid="stTabs"] button[role="tab"]:hover { background: rgba(255,255,255,0.05); color: #fff; }
    [data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
        background: rgba(255,75,43,0.13); color: #ff8a75;
        box-shadow: inset 0 -2px 0 #ff4b2b;
    }

    /* ── Forms & expanders & metrics ──────────────────────────────── */
    [data-testid="stForm"] {
        background: #111827; border: 1px solid rgba(255,255,255,0.07);
        border-radius: 18px; padding: 1.15rem 1.25rem;
    }
    [data-testid="stExpander"] {
        background: #111827; border: 1px solid rgba(255,255,255,0.07); border-radius: 14px;
        overflow: hidden;
    }
    [data-testid="stExpander"] summary { color: #e6e9ef; font-weight: 600; padding: 0.65rem 1rem; }
    [data-testid="stMetric"] {
        background: #121a2b; border: 1px solid rgba(255,255,255,0.07);
        border-radius: 14px; padding: 0.85rem 1rem;
    }
    [data-testid="stMetricLabel"] { color: #8b93a5; }
    [data-testid="stMetricValue"] { color: #fff; font-weight: 700; }
    [data-testid="stProgress"] > div { background: linear-gradient(90deg, #ff4b2b, #8b5cf6); }

    /* ── Alerts (muted, elegant) ──────────────────────────────────── */
    [data-testid="stAlert"] {
        background: rgba(255,255,255,0.045);
        border: 1px solid rgba(255,255,255,0.08);
        border-left: 3px solid #8b5cf6;
        border-radius: 12px; color: #dbe0ea;
    }

    /* ── Data & charts ────────────────────────────────────────────── */
    [data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; border: 1px solid rgba(255,255,255,0.07); }
    [data-testid="stVegaLiteChart"] {
        background: #111827; border: 1px solid rgba(255,255,255,0.07);
        border-radius: 14px; padding: 0.5rem;
    }
    .stImage img { border-radius: 14px; }

    /* ── Chat ─────────────────────────────────────────────────────── */
    [data-testid="stChatMessage"] {
        background: #111827; border: 1px solid rgba(255,255,255,0.06);
        border-radius: 16px; padding: 0.85rem 1rem; margin-bottom: 0.55rem;
    }
    [data-testid="stChatInput"] { border-radius: 14px; }
    [data-testid="stChatInput"] textarea {
        background: #121826; border: 1px solid rgba(255,255,255,0.1); border-radius: 14px; color: #eef1f7;
    }

    /* ── WebRTC component ─────────────────────────────────────────── */
    [data-testid="stCustomComponentV1"] iframe {
        border-radius: 16px; border: 1px solid rgba(255,255,255,0.08);
        background: #0e1424;
    }

    /* ── Spinner ──────────────────────────────────────────────────── */
    [data-testid="stSpinner"] { color: #ff8a75; }

    /* ── Home: hero ───────────────────────────────────────────────── */
    .hero-card {
        position: relative; overflow: hidden;
        background:
            radial-gradient(120% 170% at 88% -8%, rgba(157, 92, 255, 0.20), transparent 55%),
            radial-gradient(120% 170% at 2% 115%, rgba(255, 46, 99, 0.14), transparent 55%),
            linear-gradient(135deg, #121a2e, #0e1424);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 22px;
        padding: 2.2rem 2.3rem 1.9rem;
        margin-bottom: 0.9rem;
    }
    .hero-grid {
        display: grid; grid-template-columns: 1.35fr 1fr;
        gap: 2.2rem; align-items: center;
    }
    .hero-badge {
        display: inline-flex; align-items: center; gap: 0.4rem;
        font-size: 0.7rem; font-weight: 700; letter-spacing: 0.16em;
        color: #ffb199; text-transform: uppercase;
        background: rgba(255, 46, 99, 0.14); border: 1px solid rgba(255, 46, 99, 0.35);
        border-radius: 999px; padding: 0.3rem 0.8rem; margin-bottom: 1.05rem;
    }
    .hero-title { font-size: 2.6rem; font-weight: 800; line-height: 1.14; letter-spacing: -0.03em; color: #fff; }
    .hero-title-accent {
        background: linear-gradient(92deg, #ff6a3d, #ff2e63, #9d5cff);
        -webkit-background-clip: text; background-clip: text;
        -webkit-text-fill-color: transparent; color: transparent;
    }
    .hero-sub { font-size: 0.99rem; color: #9aa4b8; margin-top: 0.9rem; max-width: 33rem; line-height: 1.6; }
    .hero-media {
        position: relative; border-radius: 18px; overflow: hidden;
        border: 1px solid rgba(255,255,255,0.1);
        min-height: 320px; height: 100%;
    }
    .hero-media img { width: 100%; height: 320px; object-fit: cover; display: block; }
    .hero-media::before {
        content: ""; position: absolute; inset: 0; z-index: 1;
        background: linear-gradient(115deg, rgba(14, 20, 36, 0.55) 0%, rgba(14, 20, 36, 0.05) 45%, rgba(14, 20, 36, 0.2) 100%);
        pointer-events: none;
    }
    .hero-media::after {
        content: ""; position: absolute; inset: 0;
        background: linear-gradient(115deg, rgba(14, 20, 36, 0.75) 0%, rgba(14, 20, 36, 0.05) 45%, rgba(14, 20, 36, 0.25) 100%);
    }
    .hero-media .media-fallback {
        min-height: 320px; display: flex; align-items: center; justify-content: center;
        font-size: 4rem; background: linear-gradient(150deg, #1a2440, #101828);
    }

    /* ── Home: section headings ───────────────────────────────────── */
    .section-head { display: flex; align-items: center; gap: 0.55rem; margin-top: 1.7rem; }
    .section-icon {
        width: 30px; height: 30px; border-radius: 9px; font-size: 0.95rem;
        background: linear-gradient(135deg, rgba(255, 106, 61, 0.25), rgba(157, 92, 255, 0.25));
        border: 1px solid rgba(255,255,255,0.1);
        display: flex; align-items: center; justify-content: center;
    }
    .section-icon.green { background: linear-gradient(135deg, rgba(34, 197, 94, 0.22), rgba(34, 197, 94, 0.10)); }
    .section-title { font-size: 1.32rem; font-weight: 800; letter-spacing: -0.02em; color: #fff; }
    .section-sub { font-size: 0.88rem; color: #8b93a5; margin: 0.3rem 0 1rem; }

    /* ── Home: feature cards ──────────────────────────────────────── */
    .fcard {
        background: linear-gradient(165deg, #141d31, #0f1626);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 18px; overflow: hidden;
        height: 100%; display: flex; flex-direction: column;
        transition: transform 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease;
        box-shadow: 0 10px 30px rgba(0,0,0,0.25);
    }
    .fcard:hover { transform: translateY(-4px); border-color: rgba(255,255,255,0.16); box-shadow: 0 16px 40px rgba(0,0,0,0.35); }
    .fcard-media { position: relative; height: 150px; overflow: hidden; background: #101828; }
    .fcard-media img { width: 100%; height: 150px; object-fit: cover; display: block; transition: transform 0.4s ease; }
    .fcard:hover .fcard-media img { transform: scale(1.05); }
    .fcard-media::after {
        content: ""; position: absolute; inset: 0;
        background: linear-gradient(180deg, rgba(15, 22, 38, 0) 55%, rgba(15, 22, 38, 0.55) 100%);
    }
    .fcard-media .media-fallback {
        height: 150px; display: flex; align-items: center; justify-content: center;
        font-size: 3.4rem;
        background: linear-gradient(150deg, rgba(255, 46, 99, 0.18), rgba(157, 92, 255, 0.18));
    }
    .fcard-actions { padding: 0.9rem 1.1rem 1.1rem; }
    .fcard + div, .fcard + [data-testid="stButton"] { margin-top: 0.15rem; }
    .fcard-body { padding: 1rem 1.1rem 0.2rem; flex-grow: 1; }
    .fcard-title { font-size: 1.08rem; font-weight: 700; color: #fff; margin-bottom: 0.4rem; }
    .fcard-desc { font-size: 0.85rem; color: #9aa4b8; line-height: 1.55; }
    .fcard-actions { padding: 0.9rem 1.1rem 1.1rem; }
    .tool-actions { width: 100%; margin-top: 0.55rem; }
    .tool-actions [data-testid="stBaseButton-secondary"] {
        background: rgba(34, 197, 94, 0.10); border-color: rgba(34, 197, 94, 0.25); color: #7ee2a0;
    }
    .tool-actions [data-testid="stBaseButton-secondary"]:hover {
        background: rgba(34, 197, 94, 0.18); border-color: rgba(34, 197, 94, 0.45); color: #fff;
    }

    /* ── Home: fitness tools ──────────────────────────────────────── */
    .tool-card {
        background: linear-gradient(165deg, #121b2d, #0f1626);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 16px; padding: 1rem 1.05rem;
        height: 100%; display: flex; flex-direction: column; align-items: flex-start; gap: 0.65rem;
        transition: transform 0.15s ease, border-color 0.15s ease;
    }
    .tool-card:hover { transform: translateY(-3px); border-color: rgba(34, 197, 94, 0.4); }
    .tool-icon {
        width: 40px; height: 40px; border-radius: 12px; font-size: 1.15rem;
        background: linear-gradient(135deg, rgba(34, 197, 94, 0.28), rgba(34, 197, 94, 0.12));
        border: 1px solid rgba(34, 197, 94, 0.25);
        display: flex; align-items: center; justify-content: center;
    }
    .tool-name { font-size: 0.95rem; font-weight: 700; color: #fff; }
    .tool-desc { font-size: 0.76rem; color: #8b93a5; line-height: 1.45; }

    /* ── Home: quick start ────────────────────────────────────────── */
    .qs-wrap { margin-top: 2rem; }
    .qs-head { display: flex; align-items: center; gap: 0.55rem; }
    .qs-title { font-size: 1.32rem; font-weight: 800; letter-spacing: -0.02em; color: #fff; }
    .qs-sub { font-size: 0.88rem; color: #8b93a5; margin: 0.3rem 0 1rem; }
    .qs-steps {
        display: grid; grid-template-columns: 1fr auto 1fr auto 1fr auto 1fr;
        align-items: center; gap: 0.5rem;
    }
    .qs-step {
        background: #111827; border: 1px solid rgba(255,255,255,0.07);
        border-radius: 16px; padding: 1rem 0.9rem; text-align: center;
    }
    .qs-num {
        width: 30px; height: 30px; border-radius: 50%; margin: 0 auto 0.55rem;
        color: #fff; font-weight: 700; font-size: 0.9rem;
        display: flex; align-items: center; justify-content: center;
        background: linear-gradient(135deg, #ff6a3d, #ff2e63, #9d5cff);
    }
    .qs-name { font-size: 0.92rem; font-weight: 700; color: #fff; }
    .qs-desc { font-size: 0.76rem; color: #8b93a5; margin-top: 0.2rem; }
    .qs-arrow { color: #5d6577; font-size: 1rem; }

    .home-footer {
        text-align: center; color: #5d6577; font-size: 0.78rem;
        margin-top: 2.8rem; letter-spacing: 0.04em;
    }

    /* ── Responsive ───────────────────────────────────────────────── */
    @media (max-width: 1100px) {
        .hero-title { font-size: 2.05rem; }
        .hero-media, .hero-media img { min-height: 260px; height: 260px; }
        .qs-steps { grid-template-columns: 1fr 1fr; gap: 0.7rem; }
        .qs-arrow { display: none; }
    }
    @media (max-width: 860px) {
        section[data-testid="stSidebar"] { width: 240px; min-width: 240px; }
        .hero-card { padding: 1.5rem 1.4rem; }
        .hero-grid { grid-template-columns: 1fr; gap: 1.4rem; }
        .topbar-title { font-size: 1.25rem; }
        .topbar-sub { font-size: 0.8rem; }
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


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
