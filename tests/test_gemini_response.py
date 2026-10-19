"""get_gemini_response: retries, error classification, and safe messages.

All Gemini calls are mocked; the suite never touches the network.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "AI_Gym_Project"))

import m  # noqa: E402


class _StubResponse:
    def __init__(self, text="hello"):
        self.text = text


class _FlakyModel:
    """generate_content fails n times, then returns a stub response."""

    def __init__(self, failures: int, exc: Exception):
        self.failures = failures
        self.exc = exc
        self.calls = 0

    def generate_content(self, model=None, contents=None):
        self.calls += 1
        if self.calls <= self.failures:
            raise self.exc
        return _StubResponse()


def _no_sleep(monkeypatch):
    monkeypatch.setattr(m.time, "sleep", lambda s: None)


def _key(monkeypatch, key="test-key"):
    monkeypatch.setenv("GEMINI_API_KEY", key)


# ── success path ──────────────────────────────────────────────────────────

def test_success_after_transient_failure_retries(monkeypatch):
    _key(monkeypatch)
    _no_sleep(monkeypatch)
    model = _FlakyModel(2, RuntimeError("connection reset"))
    monkeypatch.setattr(m, "GEMINI_MAX_ATTEMPTS", 3)
    client = type("C", (), {"models": model})()
    reply = m.get_gemini_response("hi", client=client)
    assert reply == "hello"
    assert model.calls == 3


def test_permanent_auth_error_fails_fast_without_retry(monkeypatch):
    _key(monkeypatch)
    _no_sleep(monkeypatch)
    model = _FlakyModel(99, RuntimeError("API key not valid"))
    monkeypatch.setattr(m, "GEMINI_MAX_ATTEMPTS", 3)
    client = type("C", (), {"models": model})()
    reply = m.get_gemini_response("hi", client=client)
    assert "API key" in reply and "may be invalid" in reply
    assert model.calls == 1  # auth problems are not retried


def test_missing_key_returns_clear_message(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    reply = m.get_gemini_response("hi")
    assert "GEMINI_API_KEY" in reply
    assert "not configured" in reply


def test_transient_exhaustion_returns_safe_message(monkeypatch):
    _key(monkeypatch)
    _no_sleep(monkeypatch)
    model = _FlakyModel(999, RuntimeError("network unreachable"))
    monkeypatch.setattr(m, "GEMINI_MAX_ATTEMPTS", 2)
    client = type("C", (), {"models": model})()
    reply = m.get_gemini_response("hi", client=client)
    assert "still busy" in reply
    # The raw exception text must not leak to the UI.
    assert "network unreachable" not in reply
    assert model.calls == 2


def test_unknown_model_gets_named_check_message(monkeypatch):
    _key(monkeypatch)
    _no_sleep(monkeypatch)
    exc = RuntimeError("models/gemini-bad-model is not found")
    exc.code = 404
    model = _FlakyModel(99, exc)
    monkeypatch.setattr(m, "GEMINI_MAX_ATTEMPTS", 3)
    client = type("C", (), {"models": model})()
    reply = m.get_gemini_response("hi", client=client)
    assert "GEMINI_MODEL" in reply
    assert "gemini-bad-model" not in reply  # internal detail stays out


def test_implicit_client_path_works_without_explicit_client(monkeypatch):
    """Regression: 'genai' import was dropped from m.py once, crashing the
    live chat with NameError while every client-injected test stayed green.
    This exercises the real code path the chat UI uses (no client arg)."""
    _key(monkeypatch)
    _no_sleep(monkeypatch)
    model = type("M", (), {"generate_content": staticmethod(lambda model=None, contents=None: _StubResponse(text="hi there"))})()
    fake_client = type("C", (), {"models": model})()
    monkeypatch.setattr(m.genai, "Client", lambda **kwargs: fake_client)
    reply = m.get_gemini_response("hi")  # no client= argument on purpose
    assert reply == "hi there"


def test_empty_completion_is_flagged_not_masked(monkeypatch):
    _key(monkeypatch)
    _no_sleep(monkeypatch)
    model = type("M", (), {"generate_content": staticmethod(lambda model=None, contents=None: _StubResponse(text=""))})()
    client = type("C", (), {"models": model})()
    reply = m.get_gemini_response("hi", client=client)
    assert "no content" in reply


# ── classifier directly ──────────────────────────────────────────────────

def test_classifier_categories():
    assert m._classify_gemini_error(RuntimeError("api key not valid")) == "auth"
    assert m._classify_gemini_error(RuntimeError("unauthenticated client")) == "auth"
    assert m._classify_gemini_error(RuntimeError("connection reset")) == "transient"
    assert m._classify_gemini_error(TimeoutError("request timed out")) == "transient"
    err429 = RuntimeError("quota exceeded")
    err429.code = 429
    assert m._classify_gemini_error(err429) == "transient"
    err503 = RuntimeError("service unavailable")
    err503.code = 503
    assert m._classify_gemini_error(err503) == "transient"


def test_transient_marker_sniffing():
    assert "still busy after" in m._TRANSIENT_MARKERS
