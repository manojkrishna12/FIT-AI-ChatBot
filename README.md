# 💪 FIT-AI — AI Fitness Platform

An AI-powered fitness platform built with Python and Streamlit: real-time
exercise coaching with MediaPipe pose analysis, an AI nutritionist powered by
Google Gemini, and a companion that keeps you consistent.

## ✨ Features

**Training**
- 🏋️ AI Gym Trainer — image/video pose analysis, live webcam rep counting and form feedback (MediaPipe BlazePose, 7 exercises)
- 📚 Exercise Library — 379 curated exercises with reference images, muscles and equipment (licensed data, see below)
- 🗓️ Routines — build multi-day workout routines from the library

**Nutrition**
- 🥗 Diet Coach — BMI/TDEE targets and personalized 7-day meal plans (validated JSON + deterministic fallback)
- 🍽️ Meal Analyser — instant nutritional breakdown of any meal
- 🛒 Grocery List — weekly shopping list from your meal plan
- 📈 Calorie Tracker — log meals and track daily calories and macros

**Coach, Progress & Accounts**
- 🤝 Gym Buddy (FitBot) — conversational AI coach with sentiment awareness, streak check-ins and daily challenges
- 📊 Progress — log workout sessions (from routines or custom) with streak and volume trends
- 👤 Accounts & Profile — password sign-up/sign-in (bcrypt-hashed), fitness profile that prefills AI forms
- 🗄️ MongoDB persistence — per-user saved plans, chat, routines and sessions

## 🛠️ Tech Stack

Python 3.12 · Streamlit · Google Gemini (`google-genai`) · MediaPipe BlazePose ·
OpenCV · streamlit-webrtc · MongoDB (PyMongo + GridFS) · Pandas · bcrypt

## 🚀 Run Locally

```bash
git clone https://github.com/manojkrishna12/FIT-AI-ChatBot.git
cd FIT-AI-ChatBot

python -m venv .venv
.venv\Scripts\activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r AI_Gym_Project/requirements.txt

copy AI_Gym_Project\.env.example AI_Gym_Project\.env   # then add your GEMINI_API_KEY
```

Start MongoDB (local or Atlas) and set `MONGODB_URI` in `.env` if it is not the
default `mongodb://127.0.0.1:27017`. Then:

```bash
cd AI_Gym_Project
..\.venv\Scripts\python -m streamlit run app.py
```

Open http://localhost:8501.

### Optional: seed the Exercise Library

The Exercise Library is backed by the [RepDB free-tier dataset](https://github.com/RepDB/exercise-dataset).
Per its license the data is **not committed** to this repository — download it
once and seed it into MongoDB:

```bash
python scripts/seed_exercises.py --source <path-to-exercise-dataset-main>
```

**Exercise data by RepDB (repdb.co)** — see [docs/LICENSES.md](docs/LICENSES.md)
for the full license text and compliance notes.

## 🧪 Tests & CI

```bash
pip install pytest
python -m pytest tests/ -q
```

GitHub Actions runs the suite on every push/PR (`.github/workflows/ci.yml`).

## 🐳 Docker

```bash
docker build -t fit-ai .
docker run -p 8501:8501 --env-file AI_Gym_Project/.env fit-ai
```

## 📁 Project Structure

```
AI_Gym_Project/
├── app.py                 # entry point: router + Home page + sidebar nav
├── m.py                   # shared utilities (Gemini, BMI/TDEE, CV helpers, CSS loader)
├── assets/styles.css      # FitAI design system
├── gym_trainer.py         # AI Gym Trainer (image, video, webcam, planner, database)
├── exercise_library.py    # Exercise Library (MongoDB-backed catalog)
├── routines.py            # Routines builder
├── diet.py                # Diet Coach logic + standalone nutrition pages
├── nutrition.py           # re-export surface for the nutrition pages
├── habit_tracker.py       # Gym Buddy (FitBot)
├── progress.py            # workout session logging + trends
├── auth.py                # accounts + fitness profiles
├── profile_page.py        # Profile page
├── settings_page.py       # Settings page
├── about.py               # About page (data attribution)
├── storage.py             # MongoDB access (user state + collections)
├── constants.py           # configuration
└── requirements.txt       # pinned dependencies

scripts/seed_exercises.py  # RepDB → MongoDB seeding pipeline
tests/                     # pytest suite
docs/                      # baseline report + data licenses
```

## 📄 License

This project is for educational purposes as part of an academic major project.
Exercise data is licensed separately by RepDB — see docs/LICENSES.md.

*Built with ❤️ using Streamlit · MediaPipe · Gemini AI*
