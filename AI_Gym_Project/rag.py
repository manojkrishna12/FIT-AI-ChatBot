"""
Grounded RAG over the Exercise Library catalog.

Pipeline: query → Gemini embedding → cosine similarity over the exercise
embeddings stored on the existing `exercises` documents → top-k docs →
compact context text for the Gemini prompt.

Design rules:
- No new packages: embeddings come from the already-installed google-genai
  SDK, similarity from numpy, storage from pymongo.
- No new collections: embeddings live on the exercise documents themselves
  (`embedding` field, set by scripts/build_embeddings.py).
- Strict degradation: when MongoDB is unreachable, the catalog is empty, or
  embeddings have not been built yet, every entry point returns empty
  results / empty context and callers must behave exactly as before RAG.

This module is knowledge-layer only: it never talks to Streamlit session
state and never mutates user data.
"""

from __future__ import annotations

import os
from functools import lru_cache

import numpy as np

from constants import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
    EXERCISE_DB_COLLECTION,
    RAG_MAX_CONTEXT_CHARS,
    RAG_MIN_SCORE,
    RAG_TOP_K,
)

# In-memory cache for the matrix build from MongoDB (avoids re-fetching the
# whole catalog on every question). Invalidated per process when the
# embedding model or catalog version changes.
_MATRIX_CACHE: dict | None = None


# ────────────────────────────────────────────────────────────────────────────
# Embedding helper
# ────────────────────────────────────────────────────────────────────────────


def _embedding_client():
    """Return a google-genai Client, or None when no API key is configured."""
    try:
        from google import genai
    except ImportError:
        return None
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


def embed_texts(texts: list[str]) -> list[list[float]] | None:
    """Embed texts with the Gemini embedding model; None on any failure.

    Uses task_type=RETRIEVAL_DOCUMENT; queries must be embedded separately
    with embed_query() (RETRIEVAL_QUERY) for best retrieval quality.
    """
    if not texts:
        return None
    client = _embedding_client()
    if client is None:
        return None
    try:
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=texts,
            config={
                "task_type": "RETRIEVAL_DOCUMENT",
                "output_dimensionality": EMBEDDING_DIMENSION,
            },
        )
        vectors = [list(e.values) for e in response.embeddings]
        if len(vectors) != len(texts):
            return None
        return vectors
    except Exception:
        return None


def embed_query(text: str) -> list[float] | None:
    """Embed one user query with task_type=RETRIEVAL_QUERY; None on failure."""
    if not (text or "").strip():
        return None
    client = _embedding_client()
    if client is None:
        return None
    try:
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=[text],
            config={
                "task_type": "RETRIEVAL_QUERY",
                "output_dimensionality": EMBEDDING_DIMENSION,
            },
        )
        if not response.embeddings:
            return None
        return list(response.embeddings[0].values)
    except Exception:
        return None


# ────────────────────────────────────────────────────────────────────────────
# Catalog → matrix
# ────────────────────────────────────────────────────────────────────────────


def _exercise_text(doc: dict) -> str:
    """Compact factual text for one exercise document."""
    parts = [f"Exercise: {doc.get('name_en', '')}"]
    meta = ", ".join(
        str(doc.get(f) or "")
        for f in ("category", "difficulty", "equipment", "body_part")
        if doc.get(f)
    )
    if meta:
        parts.append(f"Type: {meta}")
    muscles = (doc.get("primary_muscles") or []) + (doc.get("secondary_muscles") or [])
    if muscles:
        parts.append("Muscles: " + ", ".join(str(m) for m in muscles))
    if doc.get("description_en"):
        parts.append(str(doc["description_en"]))
    steps = doc.get("instructions_en") or []
    if steps:
        parts.append("Instructions: " + " ".join(str(s) for s in steps))
    tips = doc.get("tips_en") or []
    if tips:
        parts.append("Tips: " + " ".join(str(t) for t in tips))
    if doc.get("met"):
        parts.append(f"MET: {doc['met']}")
    return "\n".join(parts)


def build_matrix() -> dict | None:
    """Load embedded exercise docs from MongoDB into a cached matrix.

    Returns None when the catalog is unavailable or has no embeddings yet.
    The returned dict holds numpy arrays plus the doc ids/names for search.
    """
    global _MATRIX_CACHE
    if _MATRIX_CACHE is not None:
        return _MATRIX_CACHE

    from storage import _get_collection

    try:
        coll = _get_collection(EXERCISE_DB_COLLECTION)
        docs = list(
            coll.find(
                {"embedding": {"$exists": True, "$type": "array"}},
                {
                    "_id": 1,
                    "name_en": 1,
                    "embedding": 1,
                    "provenance.embedding_model": 1,
                },
            )
        )
    except Exception:
        return None

    docs = [
        d
        for d in docs
        if isinstance(d.get("embedding"), list)
        and len(d["embedding"]) == EMBEDDING_DIMENSION
    ]
    if not docs:
        return None

    matrix = np.asarray([d["embedding"] for d in docs], dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    matrix = matrix / norms

    _MATRIX_CACHE = {
        "matrix": matrix,
        "ids": [d["_id"] for d in docs],
        "names": [d.get("name_en", "") for d in docs],
        "models": [((d.get("provenance") or {}).get("embedding_model")) for d in docs],
        "model": EMBEDDING_MODEL,
    }
    return _MATRIX_CACHE


def reset_matrix_cache() -> None:
    """Drop the in-memory matrix (used after building new embeddings)."""
    global _MATRIX_CACHE
    _MATRIX_CACHE = None


# ────────────────────────────────────────────────────────────────────────────
# Search & context formatting
# ────────────────────────────────────────────────────────────────────────────


def search(query: str, top_k: int | None = None, min_score: float | None = None) -> list[dict]:
    """Return the top-k matching exercise docs with cosine scores.

    Each result is {'id', 'name', 'score'} plus the full exercise document
    under 'doc'. Returns [] on any unavailability — never raises.
    """
    q = (query or "").strip()
    if not q:
        return []

    bundle = build_matrix()
    if bundle is None:
        return []
    # Skip cleanly when embeddings were built with a different model.
    if any(m and m != bundle["model"] for m in bundle["models"]):
        return []

    q_vec = embed_query(q)
    if q_vec is None or len(q_vec) != EMBEDDING_DIMENSION:
        return []

    q_np = np.asarray([q_vec], dtype=np.float32)
    q_norm = np.linalg.norm(q_np)
    if q_norm == 0:
        return []
    q_np = q_np / q_norm

    k = top_k or RAG_TOP_K
    floor = RAG_MIN_SCORE if min_score is None else min_score

    scores = (bundle["matrix"] @ q_np.T).ravel()
    order = np.argsort(scores)[::-1]

    from storage import _get_collection

    results: list[dict] = []
    try:
        coll = _get_collection(EXERCISE_DB_COLLECTION)
    except Exception:
        return []
    for idx in order:
        score = float(scores[idx])
        if score < floor or len(results) >= k:
            break
        doc = coll.find_one({"_id": bundle["ids"][idx]})
        if doc is None:
            continue
        doc.pop("embedding", None)
        results.append({"id": doc["_id"], "name": bundle["names"][idx], "score": round(score, 4), "doc": doc})
    return results


def build_context(results: list[dict], max_chars: int | None = None) -> str:
    """Format search results into a compact grounded-context block."""
    if not results:
        return ""
    limit = max_chars or RAG_MAX_CONTEXT_CHARS
    blocks: list[str] = []
    used = 0
    for r in results:
        doc = r.get("doc") or {}
        parts = [f"### {doc.get('name_en', r.get('name', ''))}"]
        meta = ", ".join(
            str(doc.get(f) or "")
            for f in ("category", "difficulty", "equipment", "body_part")
            if doc.get(f)
        )
        if meta:
            parts.append(f"Type: {meta}")
        muscles = (doc.get("primary_muscles") or []) + (doc.get("secondary_muscles") or [])
        if muscles:
            parts.append("Muscles: " + ", ".join(str(m) for m in muscles))
        if doc.get("description_en"):
            parts.append(str(doc["description_en"]))
        steps = doc.get("instructions_en") or []
        if steps:
            parts.append("Instructions: " + " ".join(str(s) for s in steps))
        tips = doc.get("tips_en") or []
        if tips:
            parts.append("Tips: " + " ".join(str(t) for t in tips))
        block = "\n".join(parts)
        if used + len(block) > limit and blocks:
            break
        used += len(block)
        blocks.append(block)
    return "\n\n".join(blocks)


def knowledge_base_status() -> dict:
    """Small status snapshot for the Settings page / debugging."""
    bundle = build_matrix()
    if bundle is None:
        return {"available": False, "embedded": 0}
    return {
        "available": True,
        "embedded": len(bundle["ids"]),
        "model": bundle["model"],
    }
