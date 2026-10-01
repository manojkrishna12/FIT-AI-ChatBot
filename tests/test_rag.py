"""RAG foundation tests — pure logic and degradation, no API/DB required.

Embedding calls are faked by monkeypatching rag.embed_query / rag.embed_texts,
so the suite runs offline and never consumes Gemini quota.
"""

from __future__ import annotations

import numpy as np
import pytest

import rag  # noqa: E402  (path configured in conftest)


# ── _exercise_text ────────────────────────────────────────────────────────────

def _sample_doc() -> dict:
    return {
        "_id": "ex1",
        "name_en": "Barbell Squat",
        "category": "strength",
        "difficulty": "intermediate",
        "equipment": "barbell",
        "body_part": "legs",
        "primary_muscles": ["quadriceps"],
        "secondary_muscles": ["glutes"],
        "description_en": "A compound lower-body lift.",
        "instructions_en": ["Stand tall.", "Squat down.", "Drive up."],
        "tips_en": ["Keep your chest up."],
        "met": 6.0,
    }


def test_exercise_text_contains_all_key_fields():
    text = rag._exercise_text(_sample_doc())
    for needle in ("Barbell Squat", "strength", "barbell", "quadriceps",
                   "A compound lower-body lift.", "Squat down.", "Keep your chest up.", "MET: 6.0"):
        assert needle in text


def test_exercise_text_handles_minimal_doc():
    text = rag._exercise_text({"name_en": "Unknown Move"})
    assert "Unknown Move" in text


# ── build_context ─────────────────────────────────────────────────────────────

def test_build_context_empty_results():
    assert rag.build_context([]) == ""


def test_build_context_includes_name_and_metadata():
    results = [{"id": "ex1", "name": "Barbell Squat", "score": 0.9, "doc": _sample_doc()}]
    ctx = rag.build_context(results)
    assert "### Barbell Squat" in ctx
    assert "Instructions:" in ctx
    assert "Tips:" in ctx


def test_build_context_respects_char_limit():
    docs = [
        {"id": f"ex{i}", "name": f"Exercise {i}", "score": 0.8,
         "doc": {**_sample_doc(), "name_en": f"Exercise {i}", "_id": f"ex{i}"}}
        for i in range(10)
    ]
    ctx = rag.build_context(docs, max_chars=400)
    assert len(ctx) <= 400 + 600  # one block may exceed; no further blocks added
    assert ctx.count("### Exercise") >= 1


# ── search degradation (no MongoDB / no embeddings) ──────────────────────────

def test_search_returns_empty_when_matrix_unavailable(monkeypatch):
    monkeypatch.setattr(rag, "build_matrix", lambda: None)
    assert rag.search("best squat variation") == []


def test_search_returns_empty_for_blank_query():
    assert rag.search("   ") == []


def test_search_returns_empty_when_query_embedding_fails(monkeypatch):
    bundle = {
        "matrix": np.eye(3, dtype=np.float32),
        "ids": ["a", "b", "c"],
        "names": ["A", "B", "C"],
        "models": [rag.EMBEDDING_MODEL] * 3,
        "model": rag.EMBEDDING_MODEL,
    }
    monkeypatch.setattr(rag, "build_matrix", lambda: bundle)
    monkeypatch.setattr(rag, "embed_query", lambda q: None)
    assert rag.search("anything") == []


def test_search_ranks_by_cosine_and_respects_top_k(monkeypatch):
    # Small dimension for test vectors; the logic is dimension-agnostic.
    monkeypatch.setattr(rag, "EMBEDDING_DIMENSION", 2)
    # Query aligned with vector #1 (index 1) → expect it first.
    vectors = np.array([
        [1.0, 0.0],
        [0.0, 1.0],
        [0.7, 0.7],
    ], dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    bundle = {
        "matrix": vectors / norms,
        "ids": ["push", "squat", "lunge"],
        "names": ["Push-up", "Squat", "Lunge"],
        "models": [rag.EMBEDDING_MODEL] * 3,
        "model": rag.EMBEDDING_MODEL,
    }
    monkeypatch.setattr(rag, "build_matrix", lambda: bundle)
    monkeypatch.setattr(rag, "embed_query", lambda q: [0.0, 1.0])
    monkeypatch.setattr(rag, "RAG_TOP_K", 2)
    monkeypatch.setattr(rag, "RAG_MIN_SCORE", 0.0)

    calls = {"n": 0}

    def fake_find_one(query):
        calls["n"] += 1
        return {"_id": query["_id"], "name_en": bundle["names"][["push", "squat", "lunge"].index(query["_id"])]}

    import storage
    monkeypatch.setattr(storage, "_get_collection", lambda name: type("C", (), {"find_one": staticmethod(fake_find_one)})())
    results = rag.search("leg exercise", top_k=2, min_score=0.0)

    assert [r["name"] for r in results] == ["Squat", "Lunge"]
    assert results[0]["score"] > results[1]["score"]
    assert calls["n"] == 2


def test_search_skips_mismatched_embedding_model(monkeypatch):
    bundle = {
        "matrix": np.eye(2, dtype=np.float32),
        "ids": ["a", "b"],
        "names": ["A", "B"],
        "models": ["some-old-model", "some-old-model"],
        "model": rag.EMBEDDING_MODEL,
    }
    monkeypatch.setattr(rag, "build_matrix", lambda: bundle)
    assert rag.search("anything") == []


# ── build_matrix degradation ──────────────────────────────────────────────────

def test_build_matrix_returns_none_without_mongo(monkeypatch):
    import storage

    def boom(name):
        raise RuntimeError("no mongo")

    monkeypatch.setattr(storage, "_get_collection", boom)
    monkeypatch.setattr(rag, "_MATRIX_CACHE", None)
    assert rag.build_matrix() is None


def test_build_matrix_returns_none_when_no_embeddings(monkeypatch):
    import storage

    monkeypatch.setattr(storage, "_get_collection", lambda name: type("C", (), {"find": staticmethod(lambda q, p: [])})())
    monkeypatch.setattr(rag, "_MATRIX_CACHE", None)
    assert rag.build_matrix() is None


def test_build_matrix_normalizes_and_caches(monkeypatch):
    import storage

    monkeypatch.setattr(rag, "EMBEDDING_DIMENSION", 2)
    docs = [
        {"_id": "a", "name_en": "A", "embedding": [3.0, 4.0], "provenance": {"embedding_model": rag.EMBEDDING_MODEL}},
        {"_id": "b", "name_en": "B", "embedding": [0.0, 2.0], "provenance": {"embedding_model": rag.EMBEDDING_MODEL}},
        {"_id": "bad", "name_en": "Bad", "embedding": [1.0, 2.0, 3.0]},  # wrong dim → filtered
    ]
    monkeypatch.setattr(storage, "_get_collection", lambda name: type("C", (), {"find": staticmethod(lambda q, p: docs)})())
    monkeypatch.setattr(rag, "_MATRIX_CACHE", None)
    bundle = rag.build_matrix()
    assert bundle is not None
    assert bundle["ids"] == ["a", "b"]
    # Row norms must be 1 after L2 normalization.
    assert np.allclose(np.linalg.norm(bundle["matrix"], axis=1), 1.0)
    # Second call must come from cache (monkeypatch removal would not matter).
    assert rag.build_matrix() is bundle
    rag.reset_matrix_cache()


# ── knowledge_base_status ─────────────────────────────────────────────────────

def test_status_reports_unavailable(monkeypatch):
    monkeypatch.setattr(rag, "build_matrix", lambda: None)
    assert rag.knowledge_base_status() == {"available": False, "embedded": 0}


def test_status_reports_counts(monkeypatch):
    monkeypatch.setattr(rag, "build_matrix", lambda: {"ids": [1, 2, 3], "model": rag.EMBEDDING_MODEL})
    status = rag.knowledge_base_status()
    assert status["available"] is True
    assert status["embedded"] == 3
