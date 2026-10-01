"""
Virtual Gym Buddy page with Mongo-backed per-user persistence.
"""

from __future__ import annotations

import random
from datetime import date, datetime

import streamlit as st

from constants import CHAT_CONTEXT_TURNS, MOTIVATIONAL_QUOTES
from m import page_header, get_gemini_response
from storage import save_current_user_state
from ui import section_header


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



_GROUNDING_RULES = """
Reference knowledge (from the FitAI exercise library) may accompany the user's message below.
When it is present:
- Use it as the source of truth for exercise-specific facts: names, muscles, equipment,
  difficulty, steps and tips.
- Do not invent exercise-specific details that the reference knowledge does not support.
- Do not mention the reference knowledge, retrieval, embeddings, scores or any internal
  systems in your reply — just answer naturally as FitBot.
When it is absent or irrelevant to the question, simply answer normally.
"""


def build_grounded_context(user_msg: str) -> str:
    """Retrieve exercise knowledge for a user message.

    Returns '' whenever retrieval yields nothing (unrelated question, empty
    knowledge base, MongoDB/RAG unavailable or any internal failure) — Gym
    Buddy must behave exactly as before in every one of those cases.
    """
    try:
        from rag import build_context, search

        return build_context(search(user_msg))
    except Exception:
        return ""


def chat_with_buddy(user_msg: str, history: list[dict]) -> str:
    """Generate a FitBot reply using recent conversation context.

    Exercise knowledge retrieved for the user message (when any) is prepended
    to the user turn as clearly separated reference material; the conversation
    flow itself is unchanged.
    """
    user_content = user_msg
    reference = build_grounded_context(user_msg)
    if reference:
        user_content = (
            "--- REFERENCE KNOWLEDGE (do not mention to the user) ---\n"
            f"{reference}\n"
            "--- END REFERENCE KNOWLEDGE ---\n\n"
            f"User's message: {user_msg}"
        )

    messages = [{"role": "system", "content": _BUDDY_SYSTEM + _GROUNDING_RULES}]

    for turn in history[-CHAT_CONTEXT_TURNS:]:
        messages.append({"role": turn["role"], "content": turn["content"]})

    messages.append({"role": "user", "content": user_content})

    prompt = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
    return get_gemini_response(prompt)


def ai_daily_challenge() -> str:
    """Generate one short daily challenge."""
    messages = [
        {"role": "system", "content": _BUDDY_SYSTEM},
        {"role": "user", "content": "Generate one beginner-friendly, equipment-free fitness challenge that takes 10 minutes or less.\n\nFormat:\nChallenge: [name]\nDuration: [minutes]\nTask: [1 to 2 sentences]\nWhy it helps: [1 sentence]\nSign-off: [1 motivating sentence]"}
    ]
    prompt = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
    return get_gemini_response(prompt)


def ai_mood_boost(mood: str) -> str:
    """Return a short motivational response for the current mood."""
    messages = [
        {"role": "system", "content": _BUDDY_SYSTEM},
        {"role": "user", "content": f"The user feels '{mood}' about fitness today.\n\nReply in under 120 words with:\n1. A real acknowledgement of the feeling\n2. One motivating insight\n3. One tiny action they can take right now\n4. One memorable closing line\n\nWrite it like a supportive message from a friend."}
    ]
    prompt = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
    return get_gemini_response(prompt)


def ai_weekly_tip(focus: str) -> str:
    """Return one specific practical tip."""
    messages = [
        {"role": "system", "content": _BUDDY_SYSTEM},
        {"role": "user", "content": f"Give one expert tip about {focus}.\nKeep it under 80 words, practical, and easy to apply.\nStart with one fitting emoji."}
    ]
    prompt = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
    return get_gemini_response(prompt)


def _ensure_welcome_message() -> None:
    """Seed the chat with a welcome message when a user has no history yet."""
    if "chat_history" not in st.session_state:
        from datetime import datetime
        welcome = (
            f"Hey there! I'm **FitBot** — your fitness companion for training, "
            f"nutrition, and staying consistent.\n\n"
            f"Today is **{datetime.now().strftime('%A, %B %d')}**. "
            f"How are you feeling about your fitness journey today?"
        )
        st.session_state["chat_history"] = [{"role": "assistant", "content": welcome}]


def render_gym_buddy_page() -> None:
    """Render the Virtual Gym Buddy page."""
    page_header(
        "Gym Buddy",
        "Your AI fitness companion for motivation, advice and guidance",
    )

    _ensure_welcome_message()

    chat_col, side_col = st.columns([2.6, 1], gap="large")

    with chat_col:
        section_header("Chat with FitBot")
        for msg in st.session_state["chat_history"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    with side_col:
        section_header("Today's challenge")
        if st.button("Get my challenge", use_container_width=True, key="buddy_challenge"):
            with st.spinner("Getting your challenge..."):
                challenge = ai_daily_challenge()
            st.session_state["chat_history"].append(
                {
                    "role": "assistant",
                    "content": f"Here's your daily challenge. Ready for it?\n\n{challenge}",
                }
            )
            st.rerun()

        section_header("Mood check")
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
        selected_mood = st.selectbox("How are you feeling?", mood_options, label_visibility="collapsed", key="buddy_mood")
        if st.button("Get mood boost", use_container_width=True, key="buddy_boost"):
            with st.spinner("FitBot is thinking..."):
                boost = ai_mood_boost(selected_mood)
            st.session_state["chat_history"].append(
                {
                    "role": "assistant",
                    "content": f"I can feel the vibe. Let me help.\n\n{boost}",
                }
            )
            st.rerun()

        section_header("Quick tips")
        tip_topics = [
            "Recovery",
            "Sleep & Fitness",
            "Hydration",
            "Pre-workout nutrition",
            "Muscle soreness",
            "Motivation hacks",
            "Form & injury prevention",
        ]
        selected_tip = st.selectbox("Choose a topic", tip_topics, label_visibility="collapsed", key="buddy_tip")
        if st.button("Get tip", use_container_width=True, key="buddy_get_tip"):
            with st.spinner("Fetching tip..."):
                tip = ai_weekly_tip(selected_tip)
            st.session_state["chat_history"].append(
                {
                    "role": "assistant",
                    "content": f"Here's a tip on **{selected_tip}**:\n\n{tip}",
                }
            )
            st.rerun()

        section_header("Workout check-in")
        if not st.session_state.get("checkin_done_today", False):
            workout_done = st.checkbox("I completed a workout today!", key="buddy_checkin")
            if workout_done:
                today = date.today()
                if st.session_state.get("last_checkin_date") != today:
                    st.session_state["streak_days"] = st.session_state.get("streak_days", 0) + 1
                    st.session_state["last_checkin_date"] = today
                    st.session_state["checkin_done_today"] = True
                    congrats = (
                        f"Yes! You checked in today — that's **{st.session_state['streak_days']} day(s)** "
                        f"on your streak. {random.choice(MOTIVATIONAL_QUOTES)}"
                    )
                    st.session_state["chat_history"].append({"role": "assistant", "content": congrats})
                    save_current_user_state()
                    st.rerun()
        else:
            st.success("Workout logged today.")
        st.caption(f"Current streak: **{st.session_state.get('streak_days', 0)} days**")

        section_header("Session stats")
        user_messages = [msg for msg in st.session_state["chat_history"] if msg["role"] == "user"]
        if user_messages:
            sentiments = [analyze_sentiment(msg["content"]) for msg in user_messages]
            positivity = int(sentiments.count("positive") / len(sentiments) * 100)
            latest_sentiment = sentiments[-1]
            st.caption(f"Messages: **{len(user_messages)}** · Positivity: **{positivity}%**")
            st.caption(
                f"Latest vibe: {sentiment_emoji(latest_sentiment)} {latest_sentiment.capitalize()}"
            )
        else:
            st.caption("Send a message to see your stats.")

        if st.button("Clear chat", use_container_width=True, key="buddy_clear"):
            del st.session_state["chat_history"]
            st.rerun()

    with chat_col:
        prompt = st.chat_input("Ask anything — workout tips, diet advice, motivation...")
        if prompt:
            st.session_state["chat_history"].append({"role": "user", "content": prompt})

            with st.chat_message("user"):
                st.markdown(prompt)

            sentiment = analyze_sentiment(prompt)
            with st.chat_message("assistant"):
                with st.spinner("FitBot is typing..."):
                    reply = chat_with_buddy(prompt, st.session_state["chat_history"][:-1])
                st.markdown(reply)

            st.session_state["chat_history"].append({"role": "assistant", "content": reply})

            if sentiment == "negative" and random.random() < 0.6:
                st.toast(random.choice(MOTIVATIONAL_QUOTES), icon="💪")

            st.rerun()
