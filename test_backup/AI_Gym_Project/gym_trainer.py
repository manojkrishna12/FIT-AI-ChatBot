"""
gym_trainer.py  —  AI Gym Trainer Module
=========================================
Use-case 1: AI Gym Trainer (Workout Detection & Feedback System)

Features:
  • Pose detection & landmark drawing on uploaded images/videos
  • Joint-angle calculation → rep counting with state machine
  • Per-exercise form feedback (rule-based + Gemini AI)
  • Personalised 7-day workout plan generator (Gemini)
  • Kaggle exercise database browser
"""

import os
from datetime import datetime
try:
    import cv2
except ImportError:
    cv2 = None
import tempfile
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image

try:
    from streamlit_webrtc import webrtc_streamer, VideoProcessorBase, WebRtcMode
    import av
except ImportError:
    webrtc_streamer = None
    VideoProcessorBase = object

try:
    import mediapipe as mp
except ImportError:
    mp = None

from m import (
    calculate_angle,
    get_landmark_coords,
    get_gemini_response,
    initialize_gemini,
    load_exercise_data,
    page_header,
    show_metrics_row,
)
from storage import append_session_history, save_current_user_state
from constants import (
    EXERCISE_CONFIG,
    MIN_DETECTION_CONFIDENCE,
    MIN_TRACKING_CONFIDENCE,
    MAX_VIDEO_FRAMES,
)

# ── MediaPipe shortcuts ─────────────────────────────────────────
if mp is not None:
    mp_pose = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils
    mp_drawing_styles = mp.solutions.drawing_styles
    LANDMARK_STYLE = mp_drawing_styles.get_default_pose_landmarks_style()
    CONNECTION_STYLE = mp_drawing.DrawingSpec(color=(0, 212, 255), thickness=2)
else:
    mp_pose = None
    mp_drawing = None
    mp_drawing_styles = None
    LANDMARK_STYLE = None
    CONNECTION_STYLE = None


def _pose_stack_available() -> bool:
    return cv2 is not None and mp is not None


# ══════════════════════════════════════════════════════════════
# 🖼️  IMAGE PROCESSING
# ══════════════════════════════════════════════════════════════

def process_image(image_bgr: np.ndarray, exercise: str = "Squat") -> dict:
    """
    Run MediaPipe Pose on a single BGR image.

    Returns
    -------
    dict with keys:
        pose_detected  : bool
        angle          : float | None
        rep_stage      : str   ("UP" / "DOWN" / "MID")
        feedback       : list[str]
        annotated      : np.ndarray (BGR, same shape as input)
    """
    result = {
        "pose_detected": False,
        "angle": None,
        "rep_stage": None,
        "feedback": [],
        "annotated": image_bgr.copy(),
    }

    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

    with mp_pose.Pose(
        static_image_mode=True,
        min_detection_confidence=MIN_DETECTION_CONFIDENCE,
    ) as pose:
        out = pose.process(rgb)

        if not out.pose_landmarks:
            result["feedback"].append(
                "❌ No pose detected. Ensure your full body is clearly visible."
            )
            return result

        result["pose_detected"] = True

        # Draw skeleton
        annotated = image_bgr.copy()
        mp_drawing.draw_landmarks(
            annotated,
            out.pose_landmarks,
            mp_pose.POSE_CONNECTIONS,
            landmark_drawing_spec=LANDMARK_STYLE,
            connection_drawing_spec=CONNECTION_STYLE,
        )
        result["annotated"] = annotated

        # Angle & stage
        cfg = EXERCISE_CONFIG.get(exercise, EXERCISE_CONFIG["Squat"])
        try:
            lms = out.pose_landmarks.landmark
            A = get_landmark_coords(lms, cfg["landmarks"][0], image_bgr.shape)
            B = get_landmark_coords(lms, cfg["landmarks"][1], image_bgr.shape)
            C = get_landmark_coords(lms, cfg["landmarks"][2], image_bgr.shape)

            angle = calculate_angle(A, B, C)
            result["angle"] = angle

            if angle > cfg["up_angle"]:
                result["rep_stage"] = "UP / REST"
            elif angle < cfg["down_angle"]:
                result["rep_stage"] = "DOWN / PEAK"
            else:
                result["rep_stage"] = "MID-RANGE"

            result["feedback"] = _form_feedback(angle, exercise, cfg)

        except Exception as exc:
            result["feedback"].append(f"⚠️ Angle calculation error: {exc}")

    return result


def _form_feedback(angle: float, exercise: str, cfg: dict) -> list[str]:
    """Rule-based form feedback based on joint angle and exercise type."""
    fb = []

    if exercise == "Squat":
        if angle < 70:
            fb.append("⚠️ Going very deep — ensure knees aren't caving inward.")
        elif angle <= 100:
            fb.append("✅ Excellent squat depth! Maintain that neutral spine.")
        elif angle <= 140:
            fb.append("📊 Partial squat — try to reach at least 90° for full benefit.")
        else:
            fb.append("🔝 Standing position detected.")

    elif exercise == "Bicep Curl":
        if angle < 30:
            fb.append("✅ Full contraction! Squeeze at the top for 1 second.")
        elif angle < 90:
            fb.append("📊 Good curl — complete the full range for max activation.")
        else:
            fb.append("🔝 Starting position. Curl the weight all the way up.")

    elif exercise == "Push-up":
        if angle < 70:
            fb.append("✅ Good depth on push-up — full chest stretch.")
        elif angle < 120:
            fb.append("📊 Mid push-up. Keep going — don't flare elbows.")
        else:
            fb.append("🔝 Top position. Control the descent, don't drop.")

    elif exercise == "Shoulder Press":
        if angle > 155:
            fb.append("✅ Arms nearly locked out. Avoid hyperextension.")
        elif angle > 100:
            fb.append("📊 Mid-press. Drive through the heels and engage core.")
        else:
            fb.append("🔝 Starting/bottom position. Press explosively.")

    elif exercise == "Lunge":
        if angle < 90:
            fb.append("✅ Deep lunge — great hip flexor stretch.")
        elif angle < 135:
            fb.append("📊 Mid-range lunge.")
        else:
            fb.append("🔝 Standing position.")

    else:
        if angle < cfg["down_angle"] + 15:
            fb.append("✅ Peak contraction position detected.")
        elif angle > cfg["up_angle"] - 15:
            fb.append("🔝 Rest / starting position detected.")
        else:
            fb.append("📊 Mid-range position.")

    fb.append(f"💡 Coaching cue: {cfg['description']}")
    fb.append(f"🎯 Target muscle: {cfg.get('muscle', 'N/A')}")
    return fb


class RepCounter:
    def __init__(self, exercise: str):
        self.exercise = exercise
        self.cfg = EXERCISE_CONFIG.get(exercise, EXERCISE_CONFIG["Squat"])
        self.rep_count = 0
        self.stage = None
        
    def process_angle(self, angle: float) -> tuple[int, str]:
        if angle > self.cfg["up_angle"]:
            self.stage = "up"
        if angle < self.cfg["down_angle"] and self.stage == "up":
            self.stage = "down"
            self.rep_count += 1
        return self.rep_count, self.stage


# ══════════════════════════════════════════════════════════════
# 🎬  VIDEO PROCESSING
# ══════════════════════════════════════════════════════════════

def process_video(video_path: str, exercise: str = "Squat") -> dict:
    """
    Process an uploaded video file frame-by-frame.

    Returns
    -------
    dict:
        rep_count    : int
        avg_angle    : float
        angles       : list[float]
        sample_frames: list[np.ndarray] (BGR, up to 3 annotated frames)
        total_frames : int
    """
    cap = cv2.VideoCapture(video_path)
    cfg = EXERCISE_CONFIG.get(exercise, EXERCISE_CONFIG["Squat"])
    counter = RepCounter(exercise)

    angles      = []
    all_frames  = []
    frame_idx   = 0
    SKIP        = 2             # process every 2nd frame

    with mp_pose.Pose(
        min_detection_confidence=MIN_DETECTION_CONFIDENCE,
        min_tracking_confidence=MIN_TRACKING_CONFIDENCE,
    ) as pose:
        while cap.isOpened() and frame_idx < MAX_VIDEO_FRAMES:
            ret, frame = cap.read()
            if not ret:
                break
            frame_idx += 1
            if frame_idx % SKIP != 0:
                continue

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            out = pose.process(rgb)

            if out.pose_landmarks:
                lms = out.pose_landmarks.landmark
                try:
                    A = get_landmark_coords(lms, cfg["landmarks"][0], frame.shape)
                    B = get_landmark_coords(lms, cfg["landmarks"][1], frame.shape)
                    C = get_landmark_coords(lms, cfg["landmarks"][2], frame.shape)
                    angle = calculate_angle(A, B, C)
                    angles.append(angle)

                    # ── Rep counting state machine ──
                    reps, stage = counter.process_angle(angle)

                    # Annotate frame
                    mp_drawing.draw_landmarks(
                        frame,
                        out.pose_landmarks,
                        mp_pose.POSE_CONNECTIONS,
                        connection_drawing_spec=CONNECTION_STYLE,
                    )
                    _overlay_stats(frame, reps, int(angle), stage or "")

                except Exception:
                    pass

            all_frames.append(frame)

    cap.release()

    # Pick 3 representative sample frames (start / mid / end)
    samples = []
    if all_frames:
        indices = [0, len(all_frames) // 2, len(all_frames) - 1]
        for i in indices:
            samples.append(cv2.cvtColor(all_frames[i], cv2.COLOR_BGR2RGB))

    return {
        "rep_count"    : counter.rep_count,
        "avg_angle"    : round(np.mean(angles), 1) if angles else 0.0,
        "angles"       : angles,
        "sample_frames": samples,
        "total_frames" : len(all_frames),
    }


def _overlay_stats(frame: np.ndarray, reps: int, angle: int, stage: str) -> None:
    """Draw rep counter / angle overlay on a video frame in-place."""
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (220, 160), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

    cv2.putText(frame, f"Reps : {reps}", (10, 45),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 100), 3)
    cv2.putText(frame, f"Angle: {angle}deg", (10, 90),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 200, 255), 2)
    cv2.putText(frame, f"Stage: {stage.upper()}", (10, 135),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 200, 0), 2)


# ══════════════════════════════════════════════════════════════
# 🔴  WEBRTC LIVE WEBCAM PROCESSING
# ══════════════════════════════════════════════════════════════

class GymVideoProcessor(VideoProcessorBase):
    def __init__(self):
        self.exercise = "Squat"
        self.counter = RepCounter(self.exercise)
        if mp_pose is not None:
            self.pose = mp_pose.Pose(
                min_detection_confidence=MIN_DETECTION_CONFIDENCE,
                min_tracking_confidence=MIN_TRACKING_CONFIDENCE,
            )
        else:
            self.pose = None

    def set_exercise(self, exercise: str):
        if self.exercise != exercise:
            self.exercise = exercise
            self.counter = RepCounter(exercise)

    def recv(self, frame):
        img = frame.to_ndarray(format="bgr24")
        if self.pose is None:
            return av.VideoFrame.from_ndarray(img, format="bgr24")

        cfg = EXERCISE_CONFIG.get(self.exercise, EXERCISE_CONFIG["Squat"])
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        out = self.pose.process(rgb)
        
        reps = self.counter.rep_count
        stage = self.counter.stage or ""
        angle_val = 0
        fb_msg = ""
        
        if out.pose_landmarks:
            mp_drawing.draw_landmarks(
                img,
                out.pose_landmarks,
                mp_pose.POSE_CONNECTIONS,
                connection_drawing_spec=CONNECTION_STYLE,
            )
            try:
                lms = out.pose_landmarks.landmark
                A = get_landmark_coords(lms, cfg["landmarks"][0], img.shape)
                B = get_landmark_coords(lms, cfg["landmarks"][1], img.shape)
                C = get_landmark_coords(lms, cfg["landmarks"][2], img.shape)
                angle = calculate_angle(A, B, C)
                angle_val = int(angle)
                
                reps, stage = self.counter.process_angle(angle)
                fb = _form_feedback(angle, self.exercise, cfg)
                fb_msg = fb[0] if fb else ""
            except Exception:
                pass
        else:
            fb_msg = "⚠️ No person detected. Move into the frame."
        
        _overlay_stats(img, reps, angle_val, stage)
        
        # Add feedback at the bottom (handle long feedback gracefully)
        if fb_msg:
            # Clean emojis for cv2 which can't render them well, but it's okay, they usually show as '?' or boxes, so we strip them
            clean_msg = fb_msg.replace("✅", "").replace("⚠️", "WARN:").replace("📊", "INFO:").replace("🔝", "TOP:").strip()
            cv2.putText(img, clean_msg, (10, img.shape[0] - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                        
        return av.VideoFrame.from_ndarray(img, format="bgr24")


# ══════════════════════════════════════════════════════════════
# 🤖  GEMINI-POWERED FEATURES
# ══════════════════════════════════════════════════════════════

def ai_form_analysis(exercise: str, angle: float, model=None) -> str:
    """Detailed form analysis from Gemini for detected angle."""
    prompt = f"""
You are an expert certified personal trainer.

Exercise performed: {exercise}
Detected joint angle: {angle:.1f}°
Exercise description: {EXERCISE_CONFIG.get(exercise, {}).get('description', '')}

Provide a concise coaching report (max 120 words) covering:
1. ✅/⚠️ Form assessment based on the angle
2. Specific correction (if needed)
3. One power tip to improve this exercise
4. Safety note (if applicable)

Keep the tone motivating and practical.
"""
    return get_gemini_response(prompt, model)


def ai_workout_plan(user_data: dict, model=None) -> str:
    """Generate a personalised 7-day workout plan via Gemini."""
    prompt = f"""
You are an elite AI Personal Trainer. Design a structured 7-day workout program for:

• Name          : {user_data.get('name', 'Athlete')}
• Age           : {user_data.get('age', 25)} yrs
• Weight        : {user_data.get('weight', 70)} kg
• Height        : {user_data.get('height', 170)} cm
• Fitness Level : {user_data.get('level', 'Beginner')}
• Primary Goal  : {user_data.get('goal', 'General Fitness')}
• Equipment     : {user_data.get('equipment', 'None')}
• Days per week : {user_data.get('days', 3)}
• Health notes  : {user_data.get('health', 'None')}

Format each day clearly:
  DAY X — [Focus Area]
  Warm-up  : ...
  Exercises: Name | Sets × Reps | Rest | Notes
  Cool-down: ...
  Daily tip : ...

End with a weekly summary and top motivational note.
"""
    return get_gemini_response(prompt, model)


# ══════════════════════════════════════════════════════════════
# 🖥️  STREAMLIT PAGE RENDERER
# ══════════════════════════════════════════════════════════════

def render_gym_trainer_page() -> None:
    """Entry point called by app.py for the Gym Trainer page."""
    page_header("🏋️", "AI Gym Trainer",
                "Upload a photo or video — get instant pose analysis, rep counts & AI coaching")

    model       = None
    exercise_df = load_exercise_data()
    pose_stack_ready = _pose_stack_available()

    if not pose_stack_ready:
        st.warning(
            "Pose analysis is unavailable because `opencv-python-headless` and/or "
            "`mediapipe` are not installed in the current Python environment."
        )
        st.caption(
            "Image analysis and video rep counting are temporarily disabled. "
            "The workout planner and exercise database still work."
        )

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["📸 Image Analysis", "🎬 Video & Rep Counter",
         "📋 Workout Plan Generator", "🗂️ Exercise Database",
         "🔴 Live Webcam"]
    )

    # ── TAB 1 : Image Analysis ────────────────────────────────────
    with tab1:
        st.subheader("Single-Frame Pose Analysis")
        col_l, col_r = st.columns([1, 2])

        with col_l:
            exercise  = st.selectbox("Select Exercise", list(EXERCISE_CONFIG.keys()), key="img_ex")
            img_file  = st.file_uploader(
                "Upload Image (JPG / PNG)", type=["jpg", "jpeg", "png"], key="img_up"
            )

        if img_file:
            pil_img   = Image.open(img_file).convert("RGB")
            img_arr   = np.array(pil_img)
            img_bgr   = cv2.cvtColor(img_arr, cv2.COLOR_RGB2BGR)

            with st.spinner("🔍 Detecting pose …"):
                res = process_image(img_bgr, exercise)

            c1, c2 = st.columns(2)
            c1.image(pil_img, caption="Original", width="stretch")
            if res["annotated"] is not None:
                c2.image(
                    cv2.cvtColor(res["annotated"], cv2.COLOR_BGR2RGB),
                    caption="Pose Detected",
                    width="stretch",
                )

            if res["pose_detected"]:
                st.success(
                    f"✅ Pose detected!  |  Joint Angle: **{res['angle']}°**  "
                    f"|  Stage: **{res['rep_stage']}**"
                )
                st.subheader("📌 Form Feedback")
                for line in res["feedback"]:
                    st.write(line)

                with st.expander("🤖 Get Detailed AI Coach Analysis"):
                    with st.spinner("Asking AI coach …"):
                        analysis = ai_form_analysis(exercise, res["angle"], model)
                    st.info(analysis)
            else:
                for line in res["feedback"]:
                    st.warning(line)

    # ── TAB 2 : Video Analysis ────────────────────────────────────
    with tab2:
        st.subheader("Video Rep Counter & Angle Tracking")
        col_l, _ = st.columns([1, 1])
        with col_l:
            exercise_v = st.selectbox("Select Exercise", list(EXERCISE_CONFIG.keys()), key="vid_ex")
            vid_file   = st.file_uploader(
                "Upload Video (MP4 / MOV / AVI)", type=["mp4", "mov", "avi"], key="vid_up"
            )

        if vid_file:
            tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            tfile.write(vid_file.read())
            tfile.close()

            with st.spinner(f"Processing video for {exercise_v} …"):
                vres = process_video(tfile.name, exercise_v)
            os.unlink(tfile.name)

            # Metrics row
            show_metrics_row({
                "🔁 Total Reps"      : vres["rep_count"],
                "📐 Avg Joint Angle" : f"{vres['avg_angle']}°",
                "🎞️ Frames Analyzed" : vres["total_frames"],
            })

            # Angle chart
            if vres["angles"]:
                df_angle = pd.DataFrame(
                    {"Frame": range(len(vres["angles"])),
                     "Joint Angle (°)": vres["angles"]}
                )
                st.line_chart(df_angle.set_index("Frame"), height=250)
                st.caption("Joint angle throughout the movement — peaks = rep tops, valleys = rep bottoms")

            # Sample frames
            if vres["sample_frames"]:
                st.subheader("📷 Sample Frames")
                cols = st.columns(len(vres["sample_frames"]))
                labels = ["Start", "Middle", "End"]
                for col, frame, lbl in zip(cols, vres["sample_frames"], labels):
                    col.image(frame, caption=lbl, width="stretch")

            if vres["rep_count"] == 0:
                st.warning(
                    "⚠️ No reps detected. Ensure the full body is visible "
                    "and the selected exercise matches the video."
                )

    # ── TAB 3 : Workout Plan ─────────────────────────────────────
    with tab3:
        st.subheader("🎯 AI Personalised Workout Plan Generator")

        if st.session_state.get("workout_plan_history"):
            with st.expander("Saved Workout Plans"):
                for item in st.session_state["workout_plan_history"][:5]:
                    st.markdown(f"**{item['created_at']}** - {item.get('goal', 'Workout Plan')}")
                    st.caption(item["plan"][:280] + "...")

        with st.form("workout_form"):
            r1c1, r1c2 = st.columns(2)
            with r1c1:
                name   = st.text_input("Your Name", "Athlete")
                age    = st.number_input("Age", 12, 80, 22)
                weight = st.number_input("Weight (kg)", 30.0, 200.0, 68.0, step=0.5)
                height = st.number_input("Height (cm)", 100.0, 250.0, 170.0, step=0.5)
            with r1c2:
                level   = st.selectbox("Fitness Level", ["Beginner", "Intermediate", "Advanced"])
                goal    = st.selectbox(
                    "Primary Goal",
                    ["Weight Loss", "Muscle Gain", "General Fitness",
                     "Endurance", "Strength", "Flexibility"]
                )
                equip   = st.multiselect(
                    "Equipment Available",
                    ["Dumbbells", "Barbell", "Resistance Bands",
                     "Pull-up Bar", "Treadmill", "Kettlebell", "None"],
                    default=["None"]
                )
                days    = st.slider("Training Days per Week", 1, 7, 4)
                health  = st.text_input("Health notes / injuries (optional)", "None")

            submitted = st.form_submit_button("🚀 Generate My Workout Plan", use_container_width=True)

        if submitted:
            user_data = {
                "name": name, "age": age, "weight": weight, "height": height,
                "level": level, "goal": goal,
                "equipment": ", ".join(equip) if equip else "None",
                "days": days, "health": health,
            }
            with st.spinner("🤖 Creating your personalised plan …"):
                plan = ai_workout_plan(user_data, model)
            st.success("✅ Your workout plan is ready!")
            st.markdown(plan)
            append_session_history(
                "workout_plan_history",
                {
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "goal": goal,
                    "plan": plan,
                },
            )
            save_current_user_state()
            st.download_button(
                "📥 Download Plan",
                plan, file_name=f"{name}_workout_plan.txt", mime="text/plain"
            )

    # ── TAB 4 : Exercise Database ─────────────────────────────────
    with tab4:
        st.subheader("🗂️ Kaggle Exercise Database")
        if not exercise_df.empty:
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                search = st.text_input("🔍 Search exercise", placeholder="e.g. chest, deadlift")
            with col_f2:
                body_parts = ["All"]
                bp_col = next((c for c in exercise_df.columns if "body" in c.lower()), None)
                if bp_col:
                    body_parts += sorted(exercise_df[bp_col].dropna().unique().tolist())
                bp_filter = st.selectbox("Filter by body part", body_parts)

            filtered = exercise_df.copy()
            if search:
                title_col = next((c for c in filtered.columns if "title" in c.lower()), filtered.columns[0])
                filtered = filtered[
                    filtered[title_col].astype(str).str.lower().str.contains(search.lower(), na=False)
                ]
            if bp_filter != "All" and bp_col:
                filtered = filtered[filtered[bp_col] == bp_filter]

            st.dataframe(filtered.head(50), use_container_width=True)
            st.caption(f"Showing {min(50, len(filtered))} of {len(filtered)} exercises")
        else:
            st.info("Place exercises.csv in the Data/ folder to enable the full exercise database.")


    # ── TAB 5 : Live Webcam ───────────────────────────────────────
    with tab5:
        st.subheader("🔴 Live Real-Time WebRTC Tracking")
        st.markdown(
            "Start your camera and perform the exercise. "
            "Reps and form feedback will be shown live on your screen!"
        )
        
        if webrtc_streamer is None:
            st.error("`streamlit-webrtc` is not installed. Please install it to use Live Webcam.")
        else:
            rtc_configuration = {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
            
            ex_webcam = st.selectbox("Select Exercise for Live Tracking", list(EXERCISE_CONFIG.keys()), key="webcam_ex")
            
            ctx = webrtc_streamer(
                key="gym-trainer",
                mode=WebRtcMode.SENDRECV,
                rtc_configuration=rtc_configuration,
                video_processor_factory=GymVideoProcessor,
                media_stream_constraints={"video": True, "audio": False},
                async_processing=True,
            )
            
            if ctx.video_processor:
                ctx.video_processor.set_exercise(ex_webcam)
