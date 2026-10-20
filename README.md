# 💪 FIT-AI v2.0 — AI Fitness Assistant

An AI-powered fitness assistant built with Python and Streamlit: real-time
exercise coaching with MediaPipe pose analysis, an AI nutritionist powered by
Google Gemini, a searchable exercise library, and per-user progress tracking
in MongoDB.

> **Version 2.0 stable** — tagged [`v2.0.1-stable`](../../releases). See
> [Tags](../../tags) for the full history (`v2.0-stable-checkpoint`,
> `fit-ai-rag-complete-2026-10-02`, …).

## ✨ Features

**Training**
- 🏋️ **AI Gym Trainer** — image/video pose analysis and live webcam rep
  counting with form feedback (MediaPipe BlazePose).
- 📚 **Exercise Library** — 410 curated exercises (RepDB free-tier data) with
  search, filters, images, muscles and equipment. Semantic (RAG) search built
  on Gemini embeddings.
- 🗓️ **Workouts & Routines** — build multi-day routines from the library,
  log sessions with set/weight tracking.

**Nutrition**
- 🥗 **Diet Coach** — BMI/TDEE targets from your profile and personalised
  7-day meal plans (validated JSON + deterministic fallback).
- 🍽️ **Meal Analyser** — instant nutritional breakdown of any meal.
- 📊 **Calorie Tracker** — read-only daily dashboard: goal (profile-based),
  consumed, remaining, progress bar, and today's log shared with the Meal
  Analyser.

**Coach, Progress & Accounts**
- 🤝 **Gym Buddy** — conversational AI coach with streak check-ins and daily
  challenges.
- 📈 **Progress** — workout sessions with streak and volume trends.
- 👤 **Accounts & Profile** — password sign-up/sign-in (bcrypt-hashed),
  per-user state in MongoDB Atlas or a local MongoDB.

## 🛠️ Tech Stack

Python 3.12 · Streamlit · Google Gemini (`google-genai`) · MediaPipe
BlazePose · OpenCV · streamlit-webrtc · MongoDB (PyMongo + GridFS) · Pandas ·
bcrypt · pytest

## 📋 Prerequisites

- **Python 3.12** (a 3.12+ virtual environment is expected at `.venv\`)
- **MongoDB Atlas** free cluster **or** a local MongoDB instance
- **Google Gemini API key** (free tier works)

## ⚙️ Setup

```bat
git clone https://github.com/manojkrishna12/FIT-AI-ChatBot.git
cd FIT-AI-ChatBot
python -m venv .venv
.venv\Scripts\pip install -r AI_Gym_Project\requirements.txt
copy .env.example AI_Gym_Project\.env   :: then fill in your keys
```

### `.env` configuration

Copy `.env.example` (repo root or `AI_Gym_Project/`) and fill in:

| Key | Purpose |
| --- | --- |
| `GEMINI_API_KEY` | Google Gemini API key (required) |
| `MONGODB_URI` | Atlas SRV URI or `mongodb://127.0.0.1:27017` |
| `MONGODB_DB_NAME` | Database name (default `ai_gym_assistant`) |

**Never commit your real `.env`.** It is git-ignored.

## 🚀 Start / Stop

Double-click (or run from any directory):

```bat
START_FIT_AI.bat   :: DB check → starts Streamlit on port 8631 → opens browser
STOP_FIT_AI.bat    :: stops only this project's server, leaves MongoDB running
```

What `START_FIT_AI.bat` does:

1. **Database check** — pings MongoDB. If Atlas blocks the current public IP
   (common with home connections), `tools/fix_db_access.py` prints the exact
   IP to add in Atlas *Network Access* — or adds it automatically when Atlas
   API keys are configured in `.env` (`ATLAS_PUBLIC_KEY`, `ATLAS_PRIVATE_KEY`,
   `ATLAS_GROUP_ID`). It never uses `0.0.0.0/0`.
2. **Starts the app** from this project's `.venv` via
   `tools/run_fitai.py` (selector event-loop fix for Windows) on
   <http://localhost:8631>, then opens your browser.

Manual start, if you prefer:

```bat
.venv\Scripts\python tools\run_fitai.py
```

## 🧪 Tests

```bat
.venv\Scripts\python -m pytest tests\ -q
```

145 tests cover diet targets, meal analysis normalization, the calorie
tracker's shared-log logic, RAG grounding, storage fallbacks, and navigation
labels. MongoDB and the Gemini API are mocked — no keys needed.

## 🔧 Troubleshooting

| Symptom | Fix |
| --- | --- |
| "Database unavailable — cannot sign in right now." | Your public IP changed (dynamic ISP). Run `START_FIT_AI.bat` and follow the printed Atlas step, or configure the Atlas API keys for the automatic fix. |
| Port 8631 already in use | Run `STOP_FIT_AI.bat`, then start again. |
| App starts but pages fail | Check `tools/live_restart.log` / console output; verify `.env` keys. |
| Exercise Library is empty | Seed the catalog: see `scripts/seed_exercises.py --help`. |
| Launcher says "does not look like this project's app" | Another program owns port 8631 — close it or change the port in `START_FIT_AI.bat` / `tools/run_fitai.py`. |

## 📁 Project Layout

```
AI_Gym_Project/     Streamlit app (pages, UI kit, storage, RAG)
tests/              pytest suite (145 tests)
scripts/            seed_exercises.py, build_embeddings.py
tools/              launcher scripts + DB access fixer (binaries git-ignored)
docs/               architecture and data notes
```

## 📄 Licenses & Attribution

- Exercise data: [RepDB](https://github.com/RepDB/exercise-dataset) free tier
  — attribution shown in-app (About page); dataset files are not committed.
- Application code: see repository settings.
