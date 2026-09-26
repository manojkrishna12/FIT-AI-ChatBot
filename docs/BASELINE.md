# Phase 0 — Baseline Verification Report

**Baseline commit:** `d59fc96` ("Save latest approved UI version", 2026-09-03) — tagged locally as `stable-baseline`.
**Verified on:** 2026-09-26 · Windows · Python 3.12.10 (64-bit) · venv at `.venv/`

## Environment verification

| Item | Result |
|---|---|
| App boot | ✅ `streamlit run app.py` → HTTP 200 (headless, port 8631) |
| All 8 modules import | ✅ `app, m, gym_trainer, diet, diet_fallback, habit_tracker, storage, constants` |
| Free ports | 8501–850x free; smoke test used 8631 |

## Dependency resolution (important)

`requirements.txt` pins only `mediapipe==0.10.14`. Unresolved installs today produce a
**three-way conflict**: latest Streamlit (1.64) needs `protobuf>=5.26`, while
`mediapipe==0.10.14` needs `protobuf<5`. Additionally, **mediapipe ≥ 0.10.2x no longer
provides the legacy `mp.solutions` API on Windows**, which `gym_trainer.py` uses
(`mp.solutions.pose`) — upgrading mediapipe would break the Gym Trainer.

**Known-good resolution (verified):**

```
streamlit==1.60.0        # newest Streamlit still compatible with protobuf<5
mediapipe==0.10.14       # last Windows version with mp.solutions legacy API
protobuf==4.25.9         # satisfies both sides
numpy==2.2.6
opencv-python-headless, Pillow, pandas, python-dotenv, pymongo, dnspython,
google-genai, streamlit-webrtc, av   # latest at time of verification
```

Phase 7 pins these exact versions in `requirements.txt`.

## Import audit (unused dependencies)

Confirmed **unused** in all project modules (safe to prune in Phase 7):

- `kaggle`, `scikit-learn`, `matplotlib`, `seaborn` — not imported anywhere
- `altair` — not imported directly (Streamlit pulls it in automatically)
- `requests` — imported in `habit_tracker.py` but never used (dead import)

Actually used: `PIL`, `cv2`, `mediapipe`, `numpy`, `pandas`, `streamlit`,
`streamlit_webrtc`, `av`, `pymongo`, `dnspython` (for `mongodb+srv`), `google-genai`,
`python-dotenv`.

## Legacy cleanup candidates on `main` (Phase 7, non-destructive)

- Committed `.venv/` (includes `python.exe` binaries), `__pycache__/` (multiple
  Python versions), and `streamlit-*.log` files — remove from tracking with
  `git rm --cached` (no history rewrite).
- Root and project `.gitignore` already cover `.venv/`, `__pycache__/`, `.env`.

## Module-level findings (for later phases)

| Finding | Location | Planned fix |
|---|---|---|
| Dead import | `habit_tracker.py` (`requests`) | Phase 7 |
| Unused deps | `requirements.txt` | Phase 7 prune |
| README lists a "Food Database" tab that no longer exists | `AI_Gym_Project/README.md` | Phase 7 doc refresh |
| Nav labels coupled to routing by exact string | `app.py` (`PAGE_*`) | Phase 1 routes map |
| CSS design system embedded as Python string | `m.py` (`inject_custom_css`) | Phase 1 extraction |
| God-module shared by every page | `m.py` | Additive refactors only |
| `GEMINI_MODEL` default `gemini-3.5-flash` (verify at runtime) | `constants.py` | Env override documented |
| Kaggle CSVs referenced but not committed (`Data/`) | trainer tab 4, `m.load_*` | Phase 2 replaces with licensed catalog |

## Phase 0 definition of done — met

- [x] Repository cloned in-place into `D:\Fit_AI_Version_2.0` (no nested folder)
- [x] `main` clean at `d59fc96`, tagged `stable-baseline`
- [x] `develop` branch created (all work happens here)
- [x] Virtualenv created; known-good dependency set installed and verified
- [x] App boots (HTTP 200) with all modules importing
- [x] Import scan + risk documentation complete
- [x] No source code modified
