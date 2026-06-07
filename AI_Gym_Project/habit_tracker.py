"""
Virtual Gym Buddy page with Mongo-backed per-user persistence.
"""

from __future__ import annotations

import random
from datetime import date, datetime

import streamlit as st

from constants import CHAT_CONTEXT_TURNS, GEMINI_REQUEST_TIMEOUT_S, MOTIVATIONAL_QUOTES
from m import get_gemini_response, initialize_gemini, page_header
from storage import save_current_user_state


_POS_WORDS = {
    "great",
    "good",
    "amazing",
    "excellent",
    "happy",
    "motivated",
    "energetic",
    "strong",
    "awesome",
    "fantastic",
    "love",
    "excited",
    "ready",
    "pumped",
    "progress",
    "gains",
    "win",
    "proud",
    "accomplished",
    "achieved",
}

_NEG_WORDS = {
    "tired",
    "exhausted",
    "sad",
    "bad",
    "lazy",
    "unmotivated",
    "skip",
    "pain",
    "hurt",
    "stressed",
    "depressed",
    "sick",
    "weak",
    "struggling",
    "failed",
    "quit",
    "hate",
    "bored",
    "overwhelmed",
    "gave",
    "impossible",
}

_BUDDY_SYSTEM = """
You are FitBot, a friendly and knowledgeable AI gym buddy.

Your style:
- Warm, supportive, and practical.
- Concise: 2 to 4 short paragraphs.
- Helpful with fitness, nutrition, recovery, habits, and motivation.
- If the user seems low or frustrated, acknowledge that first before advising.
- End with one light follow-up question or one small next step.

Safety:
- Never provide medical diagnoses.
- Recommend a professional for injuries or serious health issues.
"""


def analyze_sentiment(text: str) -> str:
    """Return positive, negative, or neutral from simple keyword matching."""
    words = set(text.lower().split())
    pos_score = len(words & _POS_WORDS)
    neg_score = len(words & _NEG_WORDS)
    if pos_score > neg_score:
        return "positive"
    if neg_score > pos_score:
        return "negative"
    return "neutral"


def sentiment_emoji(sentiment: str) -> str:
    """Return a simple emoji for a sentiment bucket."""
    return {"positive": "😊", "negative": "😔", "neutral": "😐"}.get(sentiment, "😐")


def chat_with_buddy(user_msg: str, history: list[dict], model=None) -> str:
    """Generate a FitBot reply using recent conversation context."""
    if model is None:
        model = initialize_gemini()
    if model is None:
        return "Add a Gemini API key in the sidebar so FitBot can reply."

    context = _BUDDY_SYSTEM + "\n\nConversation so far:\n"
    for turn in history[-CHAT_CONTEXT_TURNS:]:
        role = "FitBot" if turn["role"] == "assistant" else "User"
        context += f"{role}: {turn['content']}\n"
    context += f"User: {user_msg}\nFitBot:"

    try:
        response = model.generate_content(
            context,
            request_options={"timeout": GEMINI_REQUEST_TIMEOUT_S},
        )
        return response.text.strip()
    except Exception as exc:
        return f"Connection hiccup: {exc}. Try again in a moment."


def ai_daily_challenge(model=None) -> str:
    """Generate one short daily challenge."""
    prompt = """
Generate one beginner-friendly, equipment-free fitness challenge that takes 10 minutes or less.

Format:
Challenge: [name]
Duration: [minutes]
Task: [1 to 2 sentences]
Why it helps: [1 sentence]
Sign-off: [1 motivating sentence]
"""
    return get_gemini_response(prompt, model)


def ai_mood_boost(mood: str, model=None) -> str:
    """Return a short motivational response for the current mood."""
    prompt = f"""
The user feels "{mood}" about fitness today.

Reply in under 120 words with:
1. A real acknowledgement of the feeling
2. One motivating insight
3. One tiny action they can take right now
4. One memorable closing line

Write it like a supportive message from a friend.
"""
    return get_gemini_response(prompt, model)


def ai_weekly_tip(focus: str, model=None) -> str:
    """Return one specific practical tip."""
    prompt = f"""
Give one expert tip about {focus}.
Keep it under 80 words, practical, and easy to apply.
Start with one fitting emoji.
"""
    return get_gemini_response(prompt, model)


def _ensure_welcome_message() -> None:
    """Seed the chat with a welcome message when a user has no history yet."""
    if st.session_state.get("chat_history"):
        return
    welcome = (
        f"Hey there! 👋 I'm **FitBot** — your personal AI gym buddy. "
        f"I'm here to help with workouts, nutrition, motivation, and consistency.\n\n"
        f"Today is **{datetime.now().strftime('%A, %B %d')}**. "
        f"How are you feeling about your fitness journey today?"
    )
    st.session_state["chat_history"] = [{"role": "assistant", "content": welcome}]
    save_current_user_state()


def render_gym_buddy_page() -> None:
    """Render the Virtual Gym Buddy page."""
    page_header(
        "🤝",
        "Virtual Gym Buddy — FitBot",
        "Your AI fitness companion: motivator, coach, and friend — all in one",
    )

    model = None
    _ensure_welcome_message()

    with st.sidebar:
        st.markdown("### 🎯 Quick Actions")

        if st.button("💪 Today's Challenge", use_container_width=True):
            with st.spinner("Getting your challenge..."):
                challenge = ai_daily_challenge(model)
            st.session_state["chat_history"].append(
                {
                    "role": "assistant",
                    "content": f"Here's your daily challenge. Ready for it?\n\n{challenge}",
                }
            )
            save_current_user_state()
            st.rerun()

        st.markdown("---")
        st.markdown("### 😊 Mood Check")
        mood_options = [
            "Pumped Up",
            "Tired & Low Energy",
            "Unmotivated",
            "Happy & Ready",
            "Stressed Out",
            "Feeling Sore",
            "Hit a Plateau",
            "Just Crushed a PR!",
        ]
        selected_mood = st.selectbox("How are you feeling?", mood_options, label_visibility="collapsed")
        if st.button("🚀 Get Mood Boost", use_container_width=True):
            with st.spinner("FitBot is thinking..."):
                boost = ai_mood_boost(selected_mood, model)
            st.session_state["chat_history"].append(
                {
                    "role": "assistant",
                    "content": f"I can feel the vibe. Let me help.\n\n{boost}",
                }
            )
            save_current_user_state()
            st.rerun()

        st.markdown("---")
        st.markdown("### 💡 Quick Tips")
        tip_topics = [
            "Recovery",
            "Sleep & Fitness",
            "Hydration",
            "Pre-workout nutrition",
            "Muscle soreness",
            "Motivation hacks",
            "Form & injury prevention",
        ]
        selected_tip = st.selectbox("Choose a topic", tip_topics, label_visibility="collapsed")
        if st.button("💡 Get Tip", use_container_width=True):
            with st.spinner("Fetching tip..."):
                tip = ai_weekly_tip(selected_tip, model)
            st.session_state["chat_history"].append(
                {
                    "role": "assistant",
                    "content": f"Here's a tip on **{selected_tip}**:\n\n{tip}",
                }
            )
            save_current_user_state()
            st.rerun()

        st.markdown("---")
        st.markdown("### ✅ Workout Check-In")
        if not st.session_state.get("checkin_done_today", False):
            workout_done = st.checkbox("I completed a workout today!")
            if workout_done:
                today = date.today()
                if st.session_state.get("last_checkin_date") != today:
                    st.session_state["streak_days"] = st.session_state.get("streak_days", 0) + 1
                    st.session_state["last_checkin_date"] = today
                    st.session_state["checkin_done_today"] = True
                    st.balloons()
                    congrats = (
                        f"Yes! You checked in today — that's **{st.session_state['streak_days']} day(s)** "
                        f"on your streak. {random.choice(MOTIVATIONAL_QUOTES)}"
                    )
                    st.session_state["chat_history"].append({"role": "assistant", "content": congrats})
                    save_current_user_state()
                    st.rerun()
        else:
            st.success("Workout logged today.")

        st.metric("🔥 Current Streak", f"{st.session_state.get('streak_days', 0)} days")

        st.markdown("---")
        st.markdown("### 📊 Session Stats")
        user_messages = [msg for msg in st.session_state["chat_history"] if msg["role"] == "user"]
        if user_messages:
            sentiments = [analyze_sentiment(msg["content"]) for msg in user_messages]
            positivity = int(sentiments.count("positive") / len(sentiments) * 100)
            latest_sentiment = sentiments[-1]
            st.metric("Messages", len(user_messages))
            st.metric("Positivity", f"{positivity}%")
            st.caption(
                f"Latest vibe: {sentiment_emoji(latest_sentiment)} {latest_sentiment.capitalize()}"
            )
        else:
            st.caption("Send a message to see your stats.")

        st.markdown("---")
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state["chat_history"] = []
            save_current_user_state()
            st.rerun()

    st.subheader("💬 Chat with FitBot")
    for msg in st.session_state["chat_history"]:
        avatar = "🤖" if msg["role"] == "assistant" else "👤"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    prompt = st.chat_input("Ask anything — workout tips, diet advice, motivation...")
    if prompt:
        st.session_state["chat_history"].append({"role": "user", "content": prompt})
        save_current_user_state()

        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)

        sentiment = analyze_sentiment(prompt)
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("FitBot is typing..."):
                reply = chat_with_buddy(prompt, st.session_state["chat_history"][:-1], model)
            st.markdown(reply)

        st.session_state["chat_history"].append({"role": "assistant", "content": reply})
        save_current_user_state()

        if sentiment == "negative" and random.random() < 0.6:
            st.toast(random.choice(MOTIVATIONAL_QUOTES), icon="💪")

        st.rerun()
