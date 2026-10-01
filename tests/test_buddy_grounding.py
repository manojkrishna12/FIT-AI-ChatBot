"""Gym Buddy grounding tests — offline, no Gemini calls, no MongoDB required.

rag.search is monkeypatched so retrieval behavior is simulated deterministically;
get_gemini_response is monkeypatched to capture the prompt it would receive.
"""

from __future__ import annotations

import habit_tracker  # noqa: E402  (path configured in conftest)


_HISTORY = [
    {"role": "user", "content": "hello"},
    {"role": "assistant", "content": "hi there"},
    {"role": "user", "content": "how are you"},
    {"role": "assistant", "content": "great"},
]


def _capture_reply(monkeypatch, reply="OK"):
    """Monkeypatch get_gemini_response; return the list capturing prompts."""
    prompts: list[str] = []
    monkeypatch.setattr(habit_tracker, "get_gemini_response", lambda p: prompts.append(p) or reply)
    return prompts


# ── B. exercise question invokes retrieval ────────────────────────────────────

def test_exercise_question_invokes_retrieval(monkeypatch):
    calls: list[str] = []

    def fake_search(q):
        calls.append(q)
        return []

    import rag
    monkeypatch.setattr(rag, "search", fake_search)
    prompts = _capture_reply(monkeypatch)

    habit_tracker.chat_with_buddy("What muscles do squats work?", list(_HISTORY))
    assert calls == ["What muscles do squats work?"]
    assert prompts and prompts[0]


# ── C. retrieved context reaches the prompt, clearly separated ────────────────

def test_retrieved_context_reaches_prompt(monkeypatch):
    doc = {"name_en": "Dumbbell Fly", "body_part": "chest", "description_en": "A chest isolation move."}
    import rag
    monkeypatch.setattr(rag, "search", lambda q: [{"id": "fly", "name": "Dumbbell Fly", "score": 0.8, "doc": doc}])
    monkeypatch.setattr(rag, "build_context", lambda results: "### Dumbbell Fly\nA chest isolation move.")
    prompts = _capture_reply(monkeypatch)

    habit_tracker.chat_with_buddy("best chest exercise?", list(_HISTORY))
    prompt = prompts[0]
    assert "REFERENCE KNOWLEDGE" in prompt
    assert "Dumbbell Fly" in prompt
    assert "END REFERENCE KNOWLEDGE" in prompt
    # Grounding rules instruct silence about internals and no invention.
    assert "Do not mention the reference knowledge" in prompt
    assert "Do not invent exercise-specific details" in prompt
    # User's actual message must still be present as the user turn.
    assert "User's message: best chest exercise?" in prompt


# ── D. unrelated question: no useful context → prompt like before ────────────

def test_unrelated_question_gets_no_reference_block(monkeypatch):
    import rag
    monkeypatch.setattr(rag, "search", lambda q: [])  # no results
    prompts = _capture_reply(monkeypatch)

    habit_tracker.chat_with_buddy("I had a rough day", list(_HISTORY))
    prompt = prompts[0]
    assert "REFERENCE KNOWLEDGE" not in prompt
    assert "I had a rough day" in prompt
    # History window (last 8 turns) still included, unchanged.
    assert "hello" in prompt and "hi there" in prompt


# ── E. simulated RAG failure falls back to normal behavior ───────────────────

def test_rag_failure_falls_back(monkeypatch):
    import rag

    def boom(q):
        raise RuntimeError("mongo down")

    monkeypatch.setattr(rag, "search", boom)
    prompts = _capture_reply(monkeypatch)

    reply = habit_tracker.chat_with_buddy("any chest tips?", list(_HISTORY))
    assert reply == "OK"  # no exception escaped; normal reply produced
    assert prompts and "REFERENCE KNOWLEDGE" not in prompts[0]


def test_build_grounded_context_swallows_internal_errors(monkeypatch):
    import rag
    monkeypatch.setattr(rag, "search", lambda q: (_ for _ in ()).throw(RuntimeError("x")))
    assert habit_tracker.build_grounded_context("q") == ""


# ── F. conversation-history behavior unchanged ────────────────────────────────

def test_history_window_unchanged_with_grounding(monkeypatch):
    doc = {"name_en": "Plank", "body_part": "core"}
    import rag
    monkeypatch.setattr(rag, "search", lambda q: [{"id": "plank", "name": "Plank", "score": 0.9, "doc": doc}])
    monkeypatch.setattr(rag, "build_context", lambda results: "### Plank")
    prompts = _capture_reply(monkeypatch)

    long_history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"turn {i}"}
        for i in range(20)
    ]
    habit_tracker.chat_with_buddy("core workout?", long_history)
    prompt = prompts[0]
    # Only the last CHAT_CONTEXT_TURNS appear; earlier turns are absent.
    assert "turn 19" in prompt and "turn 12" in prompt
    assert "turn 0" not in prompt and "turn 5" not in prompt
    # The grounding block never masquerades as conversation turns.
    assert prompt.count("user:") >= 1  # flat format preserved
    assert prompt.splitlines()[0].startswith("system:")


# ── G. no persistence: nothing written anywhere ──────────────────────────────

def test_no_persistence_calls(monkeypatch):
    doc = {"name_en": "Row", "body_part": "back"}
    import rag
    monkeypatch.setattr(rag, "search", lambda q: [{"id": "row", "name": "Row", "score": 0.7, "doc": doc}])
    monkeypatch.setattr(rag, "build_context", lambda results: "### Row")
    _capture_reply(monkeypatch)

    called = {"save": 0}
    import storage
    monkeypatch.setattr(storage, "save_current_user_state", lambda: called.__setitem__("save", called["save"] + 1) or True)

    habit_tracker.chat_with_buddy("back exercise?", list(_HISTORY))
    assert called["save"] == 0  # chat_with_buddy performs no persistence
