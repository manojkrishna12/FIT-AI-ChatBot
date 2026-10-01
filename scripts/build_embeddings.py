"""
Build Gemini embeddings for the Exercise Library catalog (one-time backfill).

For every exercise document in the `exercises` collection this script
computes a factual text representation (rag._exercise_text), embeds it with
the Gemini embedding model (same GEMINI_API_KEY as the app), and stores the
vector on the document under `embedding` together with provenance. Nothing
about the exercise data itself is modified — the field is additive.

The catalog must be reachable first (the same MongoDB the app uses). On the
known local setup, start the dedicated mongod against .mongodb-data before
running this script.

Usage (repository root, virtualenv activated):

    python scripts/build_embeddings.py --dry-run
    python scripts/build_embeddings.py
    python scripts/build_embeddings.py --limit 10        # small test batch
    python scripts/build_embeddings.py --force           # re-embed everything
    python scripts/build_embeddings.py --model <name>    # override model

Options:
    --dry-run    Show what would be embedded, write nothing
    --limit N    Embed only the first N missing exercises
    --force      Re-embed exercises that already carry embeddings
    --model      Embedding model name (default from EMBEDDING_MODEL env/constant)
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "AI_Gym_Project"))

from constants import (  # noqa: E402
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
    EXERCISE_DB_COLLECTION,
)


def connect():
    from storage import _get_collection

    return _get_collection(EXERCISE_DB_COLLECTION)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Gemini embeddings for the exercise catalog.")
    parser.add_argument("--dry-run", action="store_true", help="Show the plan without writing or calling the API")
    parser.add_argument("--limit", type=int, default=0, help="Embed only the first N missing exercises")
    parser.add_argument("--force", action="store_true", help="Re-embed exercises that already have embeddings")
    parser.add_argument("--model", default=EMBEDDING_MODEL, help="Embedding model name")
    args = parser.parse_args()

    if not os.environ.get("GEMINI_API_KEY", "").strip():
        raise SystemExit("error: GEMINI_API_KEY is not set — add it to .env first")

    try:
        coll = connect()
    except Exception as exc:
        raise SystemExit(f"error: MongoDB unavailable ({exc}) — start the catalog instance first")

    filter_query = {} if args.force else {"embedding": {"$exists": False}}
    cursor = coll.find(filter_query, {"_id": 1, "name_en": 1}).sort("name_en", 1)
    targets = list(cursor)
    if args.limit and args.limit > 0:
        targets = targets[: args.limit]

    total = coll.count_documents({})
    already = total - coll.count_documents({"embedding": {"$exists": False}})

    print(f"catalog   : {total} exercises in '{EXERCISE_DB_COLLECTION}'")
    print(f"embedded  : {already} already, {len(targets)} to embed ({args.model}, dim={EMBEDDING_DIMENSION})")
    if args.dry_run:
        print("dry-run   : no changes written, no API calls made.")
        return
    if not targets:
        print("nothing to do — all exercises are embedded.")
        return

    from rag import _exercise_text, embed_texts

    ok = failed = 0
    started = time.time()
    batch_size = 32
    for start in range(0, len(targets), batch_size):
        batch = targets[start : start + batch_size]
        docs = [coll.find_one({"_id": t["_id"]}) for t in batch]
        docs = [d for d in docs if d is not None]
        if not docs:
            continue
        texts = [_exercise_text(d) for d in docs]
        vectors = embed_texts(texts)
        if vectors is None:
            print(f"batch {start // batch_size + 1}: embedding failed — aborting (no partial writes this batch)")
            failed += len(docs)
            continue
        now = datetime.now(timezone.utc).isoformat()
        for doc, vec in zip(docs, vectors):
            if len(vec) != EMBEDDING_DIMENSION:
                failed += 1
                continue
            coll.update_one(
                {"_id": doc["_id"]},
                {
                    "$set": {
                        "embedding": vec,
                        "provenance.embedding_model": args.model,
                        "provenance.embedded_at": now,
                    }
                },
            )
            ok += 1
        print(f"batch {start // batch_size + 1}: {ok} embedded so far")

    elapsed = time.time() - started
    print(f"done      : {ok} embedded, {failed} failed in {elapsed:.1f}s")
    if ok:
        print("note      : restart the app (or call rag.reset_matrix_cache()) to pick up the new matrix.")


if __name__ == "__main__":
    main()
