"""
Seed the Exercise Library from a local RepDB free-tier dataset copy.

The dataset (JSON + WebP images) is NOT committed to this repository per the
RepDB free-tier license (see docs/LICENSES.md): it is downloaded once by the
operator and seeded into MongoDB — exercises into the `exercises` collection,
images into GridFS (`exercise_images` bucket by default).

Curated selection is deterministic (see constants.LIBRARY_CATEGORIES /
LIBRARY_EQUIPMENT): strength exercises with the most common equipment plus
stretching — ~370 of the dataset's 601 exercises. Widen the constants and
re-run to grow the catalog. Nothing about the data is invented: every field
stored here comes verbatim from the dataset.

Usage (from the repository root, virtualenv activated):

    python scripts/seed_exercises.py --source <path-to-exercise-dataset-main> --dry-run
    python scripts/seed_exercises.py --source <path-to-exercise-dataset-main>
    python scripts/seed_exercises.py --replace --source <path-to-exercise-dataset-main>

Options:
    --source        Directory containing exercises.json and images/ (required)
    --dry-run       Validate and print the plan without writing to MongoDB
    --skip-images   Seed exercise documents only (images resolve to URL fallback)
    --force-images  Re-store images even if GridFS already contains them
    --replace       Delete the existing catalog first (confirmed interactively)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "AI_Gym_Project"))

from constants import (  # noqa: E402
    EXERCISE_DB_COLLECTION,
    LIBRARY_CATEGORIES,
    LIBRARY_EQUIPMENT,
    MONGODB_DB_NAME,
    REPDB_DATASET_URL,
    REPDB_SOURCE_URL,
)

# ────────────────────────────────────────────────────────────────────────────
# Dataset access
# ────────────────────────────────────────────────────────────────────────────


def load_repdb(source_dir: Path) -> tuple[dict, list[dict]]:
    """Load exercises.json and its metadata from the dataset directory."""
    json_path = source_dir / "exercises.json"
    if not json_path.exists():
        raise SystemExit(f"error: {json_path} not found — point --source at the dataset directory")
    raw = json.loads(json_path.read_text(encoding="utf-8"))
    exercises = raw.get("exercises")
    if not isinstance(exercises, list) or not exercises:
        raise SystemExit("error: exercises.json does not contain an 'exercises' list")
    meta = {k: v for k, v in raw.items() if k != "exercises"}
    return meta, exercises


def select_curated(exercises: list[dict]) -> list[dict]:
    """Apply the deterministic curated-library filter from constants."""
    selected = [
        ex
        for ex in exercises
        if ex.get("category") in LIBRARY_CATEGORIES
        and (ex.get("equipment") or "bodyweight") in LIBRARY_EQUIPMENT
    ]
    return selected


# ────────────────────────────────────────────────────────────────────────────
# Document shaping (verbatim data + provenance only — nothing fabricated)
# ────────────────────────────────────────────────────────────────────────────

_VERBATIM_FIELDS = (
    "name_en",
    "name_de",
    "name_es",
    "description_en",
    "description_de",
    "description_es",
    "instructions_en",
    "instructions_de",
    "instructions_es",
    "tips_en",
    "tips_de",
    "tips_es",
    "category",
    "force_type",
    "mechanic",
    "difficulty",
    "equipment",
    "body_part",
    "primary_muscles",
    "secondary_muscles",
    "goals",
    "tags",
    "met",
    "is_unilateral",
    "is_bodyweight",
)


def image_paths(ex: dict) -> dict:
    """Normalize the RepDB images shape into {start, peak} / {main} paths."""
    flat = ((ex.get("images") or {}).get("flat")) or {}
    return {k: v for k, v in flat.items() if isinstance(v, str)}


def normalize_exercise(ex: dict, dataset_meta: dict) -> dict:
    """Build the application-facing exercise document from a dataset record."""
    images = image_paths(ex)
    doc = {field: ex.get(field) for field in _VERBATIM_FIELDS}
    doc["_id"] = ex.get("id") or hashlib.sha1(ex.get("name_en", "").encode()).hexdigest()[:16]
    doc["search_text"] = " ".join(
        str(doc.get(f, "") or "")
        for f in ("name_en", "name_de", "name_es", "description_en")
        + tuple(doc.get("primary_muscles") or [])
        + tuple(doc.get("secondary_muscles") or [])
        + tuple(doc.get("tags") or [])
    ).lower()
    doc["images"] = images
    doc["provenance"] = {
        "dataset": "RepDB free tier",
        "source_url": REPDB_SOURCE_URL,
        "dataset_url": REPDB_DATASET_URL,
        "schema_version": dataset_meta.get("schema_version"),
        "license": dataset_meta.get("license"),
        "seeded_at": datetime.now(timezone.utc).isoformat(),
    }
    return doc


# ────────────────────────────────────────────────────────────────────────────
# MongoDB writers
# ────────────────────────────────────────────────────────────────────────────


def connect_db():
    """Connect through the app's storage layer (same client/config as the app)."""
    from storage import _get_users_collection

    return _get_users_collection().database


def store_images(db, exercises_docs: list[dict], source_dir: Path, force: bool) -> tuple[int, int, list[str]]:
    """Store referenced WebP images in GridFS. Returns (stored, skipped, missing)."""
    from storage import get_exercise_images_bucket

    bucket = get_exercise_images_bucket()
    if bucket is None:
        raise SystemExit("error: GridFS unavailable — check the MongoDB connection")

    try:
        from gridfs.errors import NoFile
    except ImportError:  # pragma: no cover
        from gridfs import errors as _gfs_errors

        NoFile = _gfs_errors.NoFile

    stored = skipped = 0
    missing: list[str] = []
    for doc in exercises_docs:
        for key, rel in doc["images"].items():
            if not rel or ".." in rel.replace("\\", "/"):
                missing.append(f"{doc['_id']}:{key}")
                continue
            name = rel.replace("\\", "/")
            try:
                exists = bucket.get_last_version(name) is not None
            except NoFile:
                exists = False
            if not force and exists:
                skipped += 1
                continue
            img_path = source_dir / name
            if not img_path.exists():
                missing.append(f"{doc['_id']}:{key}")
                continue
            bucket.put(
                img_path.read_bytes(),
                filename=name,
                metadata={
                    "exercise_id": doc["_id"],
                    "pose": key,
                    "content_type": "image/webp",
                    "source": "RepDB free tier",
                },
            )
            stored += 1
    return stored, skipped, missing


def seed_documents(db, exercises_docs: list[dict]) -> int:
    collection = db[EXERCISE_DB_COLLECTION]
    collection.create_index("name_en")
    collection.create_index("body_part")
    collection.create_index("category")
    collection.create_index("equipment")
    collection.create_index("difficulty")
    collection.create_index("primary_muscles")
    collection.create_index([("search_text", "text")], sparse=True)
    now = datetime.now(timezone.utc).isoformat()
    for doc in exercises_docs:
        collection.update_one(
            {"_id": doc["_id"]},
            {"$set": {**{k: v for k, v in doc.items() if k != "_id"}, "updated_at": now},
             "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
    return collection.count_documents({})


# ────────────────────────────────────────────────────────────────────────────
# Entry point
# ────────────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Exercise Library from a RepDB free-tier copy.")
    parser.add_argument("--source", required=True, help="Directory containing exercises.json and images/")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing to MongoDB")
    parser.add_argument("--skip-images", action="store_true", help="Store exercise documents only")
    parser.add_argument("--force-images", action="store_true", help="Re-store images already present in GridFS")
    parser.add_argument("--replace", action="store_true", help="Delete the existing catalog before seeding")
    args = parser.parse_args()

    source_dir = Path(args.source).expanduser().resolve()
    meta, exercises = load_repdb(source_dir)
    selected = select_curated(exercises)

    print(f"dataset : {source_dir} (count={meta.get('count')}, license={meta.get('license')})")
    print(f"selected: {len(selected)} of {len(exercises)} exercises (curated filter in constants.py)")

    by_cat: dict[str, int] = {}
    for ex in selected:
        by_cat[ex.get("category", "?")] = by_cat.get(ex.get("category", "?"), 0) + 1
    print(f"by category: {by_cat}")

    no_img = [ex["id"] for ex in selected if not image_paths(ex)]
    if no_img:
        print(f"warning: {len(no_img)} selected exercises have no flat images: {no_img[:5]}…")

    docs = [normalize_exercise(ex, meta) for ex in selected]
    ids = [d["_id"] for d in docs]
    if len(set(ids)) != len(ids):
        raise SystemExit("error: duplicate exercise ids in selection")

    if args.dry_run:
        print("dry-run: no changes written.")
        return

    db = connect_db()
    print(f"connected to MongoDB: {MONGODB_DB_NAME}")

    if args.replace:
        answer = input(f"Delete ALL documents in '{EXERCISE_DB_COLLECTION}'? type 'yes' to confirm: ")
        if answer.strip().lower() != "yes":
            raise SystemExit("aborted")
        db[EXERCISE_DB_COLLECTION].delete_many({})
        print("existing catalog deleted")

    if not args.skip_images:
        stored, skipped, missing = store_images(db, docs, source_dir, force=args.force_images)
        print(f"images  : {stored} stored, {skipped} already present, {len(missing)} missing")

    total = seed_documents(db, docs)
    print(f"seeded  : catalog now holds {total} exercises in '{EXERCISE_DB_COLLECTION}'")
    print("attribution (license term 2) is shown on the About page and in the README.")


if __name__ == "__main__":
    main()
