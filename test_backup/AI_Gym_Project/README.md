# 💪 AI Gym & Fitness Assistant

> An all-in-one AI-powered fitness ecosystem built with **Streamlit**, **MediaPipe**, and **Gemini AI**.

---

## 🏗️ Project Structure

```
AI_Gym_Project/
│
├── app.py               ← 🚀 Main Streamlit app (entry point + router)
├── m.py                 ← 🔧 Shared utilities (sub-module of app.py)
├── gym_trainer.py       ← 🏋️  Module 1: AI Gym Trainer
├── diet.py              ← 🥗  Module 2: AI Dietician & Calorie Coach
├── habit_tracker.py     ← 🤝  Module 3: Virtual Gym Buddy (FitBot)
│
├── constants.py         ← ⚙️  All configuration, constants & exercise configs
├── models.txt           ← 📋  AI model & dataset reference sheet
├── requirements.txt     ← 📦  Python dependencies
├── .env.example         ← 🔑  Environment variable template
│
├── Data/
│   ├── exercises.csv    ← 🗂️  Kaggle Exercise Dataset (place here)
│   └── nutrition.csv    ← 🥦  Kaggle Nutrition Dataset (place here)
│
└── README.md
```

---

## 🎯 Use Cases Implemented

| # | Module | Description |
|---|--------|-------------|
| 1 | 🏋️ AI Gym Trainer | Upload image/video → MediaPipe pose detection, rep counting, form feedback, AI workout plans |
| 2 | 🥗 AI Dietician | BMI/TDEE calculator, 7-day AI meal plans, grocery lists, meal analyser, calorie tracker |
| 5 | 🤝 Virtual Gym Buddy | AI chat companion (FitBot) with full session memory, sentiment analysis, mood boosts |

---

## ⚡ Quick Setup

### 1. Clone & create virtual environment
```bash
git clone <your-repo-url>
cd AI_Gym_Project
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Mac/Linux)
source venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up Gemini API key
```bash
# Option A: Copy .env.example → .env and add your key
cp .env.example .env
# Then edit .env and paste your key

# Option B: Enter the key directly in the app sidebar Settings panel
```

Get your **free** Gemini API key at: https://makersuite.google.com/app/apikey

### 4. Download Kaggle Datasets *(optional but recommended)*

**Exercise Dataset**
- URL: https://www.kaggle.com/datasets/niharika41298/gym-exercise-dataset
- Download → rename to `exercises.csv` → place in `Data/`

**Nutrition Dataset**
- URL: https://www.kaggle.com/datasets/trolukovich/nutritional-values-for-common-foods-and-products
- Download → rename to `nutrition.csv` → place in `Data/`

> ✅ The app works without these CSVs — it will use built-in sample data as fallback.

### 5. Run the app
```bash
streamlit run app.py
```

The app will open at **http://localhost:8501**

---

## 🏋️ Module 1 — AI Gym Trainer

| Tab | Feature |
|-----|---------|
| 📸 Image Analysis | Upload a photo → MediaPipe detects pose, calculates joint angle, gives form feedback |
| 🎬 Video & Rep Counter | Upload a video → counts reps, tracks joint angle across frames, shows angle chart |
| 📋 Workout Plan Generator | Fill in your profile → Gemini generates a full 7-day personalised plan |
| 🗂️ Exercise Database | Search & filter the Kaggle exercise dataset by body part / equipment |

**Supported exercises for pose detection:**
Squat · Bicep Curl · Push-up · Shoulder Press · Lunge · Deadlift · Plank

---

## 🥗 Module 2 — AI Dietician & Calorie Coach

| Tab | Feature |
|-----|---------|
| 📋 My Diet Plan | BMI/TDEE calculation + Gemini 7-day meal plan tailored to your goal |
| 🍽️ Meal Analyser | Describe any meal in plain English → AI returns calorie + macro breakdown |
| 🛒 Grocery List | Auto-generate a weekly grocery list from your meal plan |
| 🔍 Food Database | Search the Kaggle nutrition database (8 000+ food items) |
| 📈 Calorie Tracker | Manually log meals and track daily calorie / protein intake |

**Supported dietary styles:** No Restriction · Vegetarian · Vegan · Keto · Mediterranean · Paleo · Gluten-Free · Dairy-Free

---

## 🤝 Module 3 — Virtual Gym Buddy (FitBot)

| Feature | Description |
|---------|-------------|
| 💬 Chat | Full conversational AI with session-long memory (last 14 messages as context) |
| 🧠 Sentiment | Keyword-based mood detection → FitBot responds with empathy when you're feeling low |
| 💪 Daily Challenge | AI generates a fresh equipment-free micro-challenge each time |
| 🚀 Mood Boost | Select your current mood → personalised motivational response |
| 💡 Quick Tips | Expert tips on recovery, sleep, hydration, nutrition, motivation, and more |
| ✅ Streak Tracker | Check-in when you complete a workout → tracks your consecutive day streak |

---

## 🛠️ Technology Stack

| Component | Technology |
|-----------|-----------|
| Frontend UI | Streamlit 1.32 |
| AI Responses | Google Gemini 1.5 Flash (free tier) |
| Pose Detection | MediaPipe BlazePose (33 landmarks) |
| Image/Video Processing | OpenCV 4.9 |
| Data Processing | Pandas 2.2, NumPy 1.26 |
| Nutrition Calculations | Mifflin-St Jeor (BMR/TDEE), custom macro splits |
| Sentiment Analysis | Rule-based keyword matching (no API needed) |
| Datasets | Kaggle (exercise + nutrition CSVs) |

---

## 📐 How Rep Counting Works

1. MediaPipe detects 33 pose landmarks on each video frame
2. Three landmarks form a joint angle (e.g. hip→knee→ankle for squats)
3. A **state machine** tracks `UP` / `DOWN` transitions:
   - Angle crosses `up_angle` threshold → stage = `"up"`
   - Angle crosses `down_angle` threshold AND was `"up"` → **+1 rep**
4. Angles are plotted as a line chart so you can visually inspect your reps

---

## 🔧 Configuration

All settings are centralised in `constants.py`:

- `GEMINI_API_KEY` / `GEMINI_MODEL` — AI model config
- `EXERCISE_CONFIG` — add new exercises or adjust angle thresholds
- `CALORIE_MULTIPLIERS` — TDEE activity level multipliers
- `BMI_CATEGORIES` — BMI range definitions

---

## 🚀 Future Enhancements

- [ ] Real-time webcam pose detection (browser WebRTC)
- [ ] User authentication + cloud data persistence
- [ ] Progress photos comparison
- [ ] Wearable device integration (heart rate, steps)
- [ ] Voice interface for hands-free coaching
- [ ] Multi-language support

---

## 📄 License

This project is for educational purposes as part of an academic major project.

---

*Built with ❤️ using Streamlit · MediaPipe · Gemini AI*
