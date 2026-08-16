"""
constants.py
============
Central configuration file for AI Gym & Fitness Assistant.
All shared constants, settings, and configurations live here.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# 🔑 API CONFIGURATION
# ─────────────────────────────────────────────
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
GEMINI_MODEL    = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
GEMINI_REQUEST_TIMEOUT_S = int(os.getenv("GEMINI_REQUEST_TIMEOUT_S", "20"))
CHAT_CONTEXT_TURNS = int(os.getenv("CHAT_CONTEXT_TURNS", "8"))

# Per-user app profile used when no identifier is provided in the sidebar.
DEFAULT_USER_ID = os.getenv("DEFAULT_USER_ID", "guest")

# MongoDB persistence
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "ai_gym_assistant")
MONGODB_USERS_COLLECTION = os.getenv("MONGODB_USERS_COLLECTION", "user_profiles")
MONGODB_SERVER_SELECTION_TIMEOUT_MS = int(
    os.getenv("MONGODB_SERVER_SELECTION_TIMEOUT_MS", "1500")
)

# ─────────────────────────────────────────────
# 📁 DATASET PATHS  (Kaggle CSVs go in Data/)
# ─────────────────────────────────────────────
DATA_DIR              = "Data"
WORKOUT_DATASET_PATH  = f"{DATA_DIR}/exercises.csv"       # Kaggle: gym-exercise-dataset
NUTRITION_DATASET_PATH = f"{DATA_DIR}/nutrition.csv"      # Kaggle: nutritional-values-for-common-foods

# ─────────────────────────────────────────────
# 🎥 MEDIAPIPE CONFIGURATION
# ─────────────────────────────────────────────
MIN_DETECTION_CONFIDENCE = 0.70
MIN_TRACKING_CONFIDENCE  = 0.50
MAX_VIDEO_FRAMES         = 150     # Max frames to process per video upload

# ─────────────────────────────────────────────
# 🏃 EXERCISE CONFIGURATIONS  (for rep counting)
# Each entry maps an exercise to:
#   landmarks : 3 MediaPipe joint names forming the angle
#   up_angle  : angle (°) considered "top/rest" position
#   down_angle: angle (°) considered "bottom/peak" position
#   description: quick coaching cue
# ─────────────────────────────────────────────
EXERCISE_CONFIG = {
    "Squat": {
        "landmarks"  : ["LEFT_HIP", "LEFT_KNEE", "LEFT_ANKLE"],
        "up_angle"   : 170,
        "down_angle" : 90,
        "description": "Keep back straight, chest up, knees track over toes.",
        "muscle"     : "Quadriceps, Glutes, Hamstrings",
    },
    "Bicep Curl": {
        "landmarks"  : ["LEFT_SHOULDER", "LEFT_ELBOW", "LEFT_WRIST"],
        "up_angle"   : 160,
        "down_angle" : 30,
        "description": "Keep elbows pinned to your sides, full range of motion.",
        "muscle"     : "Biceps, Forearms",
    },
    "Push-up": {
        "landmarks"  : ["LEFT_SHOULDER", "LEFT_ELBOW", "LEFT_WRIST"],
        "up_angle"   : 160,
        "down_angle" : 70,
        "description": "Body in a straight line from head to heels, elbows at 45°.",
        "muscle"     : "Chest, Triceps, Shoulders",
    },
    "Shoulder Press": {
        "landmarks"  : ["LEFT_ELBOW", "LEFT_SHOULDER", "LEFT_HIP"],
        "up_angle"   : 160,
        "down_angle" : 80,
        "description": "Don't lock elbows at the top; control the descent.",
        "muscle"     : "Deltoids, Trapezius, Triceps",
    },
    "Lunge": {
        "landmarks"  : ["LEFT_HIP", "LEFT_KNEE", "LEFT_ANKLE"],
        "up_angle"   : 170,
        "down_angle" : 85,
        "description": "Front knee stays above ankle; torso upright.",
        "muscle"     : "Quadriceps, Glutes, Calves",
    },
    "Deadlift": {
        "landmarks"  : ["LEFT_SHOULDER", "LEFT_HIP", "LEFT_KNEE"],
        "up_angle"   : 170,
        "down_angle" : 100,
        "description": "Neutral spine throughout; drive through heels.",
        "muscle"     : "Hamstrings, Glutes, Lower Back",
    },
    "Plank": {
        "landmarks"  : ["LEFT_SHOULDER", "LEFT_HIP", "LEFT_ANKLE"],
        "up_angle"   : 175,
        "down_angle" : 155,
        "description": "Straight line from head to heels; engage your core.",
        "muscle"     : "Core, Shoulders, Glutes",
    },
}

# ─────────────────────────────────────────────
# 📊 BMI CATEGORIES
# ─────────────────────────────────────────────
BMI_CATEGORIES = {
    "Underweight" : (0,    18.5),
    "Normal"      : (18.5, 25.0),
    "Overweight"  : (25.0, 30.0),
    "Obese"       : (30.0, float("inf")),
}

BMI_COLORS = {
    "Underweight" : "🟡",
    "Normal"      : "🟢",
    "Overweight"  : "🟠",
    "Obese"       : "🔴",
}

# ─────────────────────────────────────────────
# 🔥 CALORIE MULTIPLIERS  (Mifflin-St Jeor TDEE)
# ─────────────────────────────────────────────
CALORIE_MULTIPLIERS = {
    "Sedentary"          : 1.200,
    "Lightly Active"     : 1.375,
    "Moderately Active"  : 1.550,
    "Very Active"        : 1.725,
    "Extra Active"       : 1.900,
}

# ─────────────────────────────────────────────
# 💬 MOTIVATIONAL QUOTES
# ─────────────────────────────────────────────
MOTIVATIONAL_QUOTES = [
    "The only bad workout is the one that didn't happen! 💪",
    "Push yourself because no one else is going to do it for you! 🔥",
    "Your body can stand almost anything. It's your mind you have to convince. 🧠",
    "Success starts with self-discipline. Keep going! ⚡",
    "Every rep brings you closer to your goal! 🎯",
    "Sore today, stronger tomorrow. 🏆",
    "You didn't come this far to only come this far. 🚀",
    "Believe in yourself and all that you are. 🌟",
    "Champions are made in the moments they want to quit and don't. 👊",
    "Your future self is watching you right now — make them proud. 🙌",
]

# ─────────────────────────────────────────────
# 🎨 UI THEME
# ─────────────────────────────────────────────
PRIMARY_COLOR   = "#FF6B35"
SECONDARY_COLOR = "#1E1E2E"
ACCENT_COLOR    = "#00D4FF"
SUCCESS_COLOR   = "#00C851"
WARNING_COLOR   = "#FFBB33"
