"""RAG Build 3 targeted tests — offline: no Gemini API, no MongoDB required.

Covers the production-quality additions on top of the RAG foundation:
  - query-embedding cache (TTL + FIFO bound + failure non-caching),
  - exact build_context boundary behavior,
  - explicit min_score floor semantics,
  - Settings-page knowledge-base observability,
  - the expanded Phase-E grounding rules contract in Gym Buddy.
"""

from __future__ import annotations

import numpy as np
import pytest

import rag  # noqa: E402  (path configured in conftest)


class _FakeEmbedding:
    """Stand-in for one Gemini embedding: unit vector along axis 0.

    Aligned with the single identity-matrix row used by _matrix_bundle so
    the cosine score (1.0) clears RAG_MIN_SCORE in search-path tests.
    """

    def __init__(self, dim):
        vec = [0.0] * dim
        vec[0] = 1.0
        self.values = vec


class _FakeModels:
    def __init__(self, dim):
        self._dim = dim
        self.calls = 0

    def embed_content(self, **kw):
        self.calls += 1
        return type("R", (), {"embeddings": [_FakeEmbedding(self._dim)]})()


class _FakeClient:
    def __init__(self, dim=None):
        self.models = _FakeModels(dim if dim is not None else rag.EMBEDDING_DIMENSION)


# ── query-embedding cache ─────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clean_query_cache():
    rag.reset_query_cache()
    yield
    rag.reset_query_cache()


def _matrix_bundle(dim=4):
    return {
        "matrix": np.eye(dim, dtype=np.float32)[:1],  # one row — matches ids below
        "ids": ["a"],
        "names": ["A"],
        "models": [rag.EMBEDDING_MODEL],
        "model": rag.EMBEDDING_MODEL,
    }


def test_embed_query_result_cached_per_process(monkeypatch):
    rag.reset_query_cache()
    counter = _FakeClient()

    def fake_client():
        return counter

    monkeypatch.setattr(rag, "_embedding_client", fake_client)
    v1 = rag.embed_query("how do i squat?")
    v2 = rag.embed_query("how do i squat?")
    assert v1 == v2
    assert counter.models.calls == 1  # second call served from cache
    # different text → new API call
    rag.embed_query("bench press muscles?")
    assert counter.models.calls == 2


def test_embed_query_failure_not_cached(monkeypatch):
    """A failed embed must not poison the cache — the retry re-embeds."""
    rag.reset_query_cache()

    ok_client = _FakeClient()
    calls = {"n": 0}

    def flaky_client():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient API outage")
        return ok_client

    monkeypatch.setattr(rag, "_embedding_client", flaky_client)
    # call 1: client construction raises → caught inside embed_query → None
    assert rag.embed_query("retry me") is None
    # call 2: succeeds and caches
    v2 = rag.embed_query("retry me")
    assert v2 is not None and len(v2) == rag.EMBEDDING_DIMENSION
    assert calls["n"] == 2
    # call 3: served from cache — no client usage at all
    v3 = rag.embed_query("retry me")
    assert v3 == v2
    assert calls["n"] == 2  # unchanged
    assert len(rag._QUERY_CACHE) == 1


def test_embed_query_cache_bounded_and_ttl(monkeypatch):
    rag.reset_query_cache()

    counter = _FakeClient()
    monkeypatch.setattr(rag, "_embedding_client", lambda: counter)

    for i in range(rag._QUERY_CACHE_MAX + 4):
        rag.embed_query(f"question {i}")
    assert len(rag._QUERY_CACHE) <= rag._QUERY_CACHE_MAX

    # expire one entry via TTL and confirm re-embed
    rag.embed_query("ttl probe")
    vector, stamp = rag._QUERY_CACHE["ttl probe"]
    rag._QUERY_CACHE["ttl probe"] = (vector, stamp - (rag.RAG_QUERY_CACHE_TTL_S + 1))
    before = counter.models.calls
    rag.embed_query("ttl probe")
    assert counter.models.calls == before + 1  # expired → re-embedded


def test_search_uses_query_cache_not_the_document_cache(monkeypatch):
    """search() with an identical query twice embeds the query only once."""
    rag.reset_query_cache()
    counter = _FakeClient()
    monkeypatch.setattr(rag, "_embedding_client", lambda: counter)
    monkeypatch.setattr(rag, "build_matrix", lambda: _matrix_bundle(rag.EMBEDDING_DIMENSION))
    import storage

    monkeypatch.setattr(storage, "_get_collection", lambda name: type("C", (), {
        "find_one": staticmethod(lambda q: {"_id": "a", "name_en": "A"})
    })())

    first = rag.search("hamstring exercise")
    second = rag.search("hamstring exercise")
    assert first and second
    assert first[0]["id"] == second[0]["id"] == "a"
    assert counter.models.calls == 1  # query embedding cached end-to-end


# ── build_context boundary ────────────────────────────────────────────────────

def _long_doc(marker: str, n_chars: int) -> dict:
    return {
        "_id": marker,
        "name_en": f"Exercise {marker}",
        "description_en": "x" * n_chars,
    }


def test_build_context_exact_pixel_boundary(monkeypatch):
    r1 = {"id": "1", "name": "E1", "score": 0.9, "doc": _long_doc("1", 300)}
    r2 = {"id": "2", "name": "E2", "score": 0.8, "doc": _long_doc("2", 300)}
    r3 = {"id": "3", "name": "E3", "score": 0.7, "doc": _long_doc("3", 300)}

    # Overhead per block: "### Exercise N\n" + "x"*300 + "\n\n" — derive it.
    ctx_all = rag.build_context([r1], max_chars=10_000)
    block_len = len(ctx_all.rstrip("\n"))
    # limit that fits exactly two blocks
    limit = block_len * 2 + 1  # joining "\n\n" counts once between blocks
    ctx = rag.build_context([r1, r2, r3], max_chars=limit)
    assert ctx.count("###") == 2

    # one char tighter → only one block fits
    ctx_one = rag.build_context([r1, r2, r3], max_chars=limit - 2)
    assert ctx_one.count("###") == 1


def test_build_context_first_block_always_included_even_if_oversized():
    huge = _long_doc("H", 5000)
    r = {"id": "h", "name": "Huge", "score": 0.9, "doc": huge}
    ctx = rag.build_context([r], max_chars=100)
    assert "### Exercise H" in ctx and len(ctx) > 100


# ── min_score semantics ───────────────────────────────────────────────────────

def _rank_bundle():
    vectors = np.array([[1.0, 0.0], [0.0, 1.0], [0.6, 0.8]], dtype=np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    return {
        "matrix": vectors,
        "ids": ["push", "squat", "near"],
        "names": ["Push-up", "Squat", "Near-copy"],
        "models": [rag.EMBEDDING_MODEL] * 3,
        "model": rag.EMBEDDING_MODEL,
    }


def test_search_min_score_excludes_weak_matches(monkeypatch):
    monkeypatch.setattr(rag, "build_matrix", _rank_bundle)
    monkeypatch.setattr(rag, "embed_query", lambda q: [1.0, 0.0])
    import storage

    def find_one(q):
        names = {"push": "Push-up", "squat": "Squat", "near": "Near-copy"}
        return {"_id": q["_id"], "name_en": names[q["_id"]]}

    monkeypatch.setattr(storage, "_get_collection", lambda name: type("C", (), {"find_one": staticmethod(find_one)})())

    # cosine(query=[1,0], [0,1]) = 0 → excluded even when top_k=2
    results = rag.search("push", top_k=3, min_score=0.05)
    assert [r["id"] for r in results] == ["push", "near"]

    results_high = rag.search("push", top_k=3, min_score=0.98)
    assert [r["id"] for r in results_high] == ["push"]


# ── Settings observability ────────────────────────────────────────────────────

def test_knowledge_base_status_shape(monkeypatch):
    monkeypatch.setattr(rag, "build_matrix", lambda: None)
    assert rag.knowledge_base_status() == {"available": False, "embedded": 0}

    fake = {"ids": [1, 2], "model": rag.EMBEDDING_MODEL, "matrix": None, "names": [], "models": []}
    monkeypatch.setattr(rag, "build_matrix", lambda: fake)
    status = rag.knowledge_base_status()
    assert status == {"available": True, "embedded": 2, "model": rag.EMBEDDING_MODEL}


# ── Phase-E grounding rules contract ─────────────────────────────────────────

def test_grounding_rules_cover_evidence_boundaries():
    import habit_tracker

    rules = habit_tracker._GROUNDING_RULES
    # actual exercise names
    assert "actual exercise names" in rules
    # equipment information
    assert "equipment information" in rules
    # primary vs Secondary muscle distinction
    assert "primary" in rules and "secondary" in rules
    # exercise facts vs general coaching advice
    assert "coaching suggestion" in rules


def test_grounding_rules_still_require_silence_about_internals():
    import habit_tracker

    rules = habit_tracker._GROUNDING_RULES
    assert "Do not mention the reference knowledge" in rules
    assert "Do not invent exercise-specific details" in rules
