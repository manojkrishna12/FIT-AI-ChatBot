# Data & Asset Licenses

This project contains no scraped exercise content. All third-party data and
imagery is used under the documented licenses below. No RepDB-derived files
are committed to this repository (license term 3): the dataset is downloaded
once by an operator and seeded into MongoDB with `scripts/seed_exercises.py`.

## RepDB free-tier exercise dataset

- **Source:** <https://github.com/RepDB/exercise-dataset> (canonical free-tier
  distribution published by RepDB itself)
- **License:** RepDB Free Tier License v1.0 — full text:
  <https://github.com/RepDB/exercise-dataset/blob/main/LICENSE-DATA.md>
- **Scope used:** 601-exercise JSON catalog + 512px flat WebP illustrations
  (379 curated exercises seeded — see `constants.LIBRARY_*`)

### License terms (summary — the license text above is authoritative)

1. Free for personal and commercial use inside applications.
2. **Attribution required:** a visible link — "Exercise data by RepDB
   (repdb.co)" — in the app's about/credits screen, the project README, or
   the website footer.
3. No redistribution as a dataset — the dataset (or a derivative) may not be
   republished, resold, or repackaged as a dataset, dataset repo, or API.
   In-app use only.
4. Images may be resized/cropped/recolored for in-app use; upscaled or
   background-removed derivatives still fall under term 3.
5. No generative-AI derivation from the images.
6. Paid-tier preview animations are evaluation-only (not used by this project).
7. No warranty; not medical advice.

### How FIT-AI complies

| Term | Compliance |
|---|---|
| 1 — in-app use | Data lives inside the app's MongoDB; no dataset distribution. |
| 2 — attribution | Visible credit + link on the **About page** and in the **README**. |
| 3 — no redistribution | `AI_Gym_Project/.gitignore` excludes `Data/repdb/`; nothing RepDB-derived is committed or packaged. |
| 4 — image modifications | Images are stored unmodified in GridFS; served as-is. |
| 5 — no gen-AI derivation | Images are not used as model input or training material. |
| 6 — preview animations | Not used. |
| 7 — not medical advice | The app already shows medical disclaimers on relevant pages. |

### Operator workflow (seed)

```bash
# 1. Download the dataset once (any of the canonical channels):
#    https://github.com/RepDB/exercise-dataset  (Code ZIP)
# 2. Seed into MongoDB:
python scripts/seed_exercises.py --source <path-to-exercise-dataset-main>
# 3. Verify:
python scripts/seed_exercises.py --source <path-to-exercise-dataset-main> --dry-run
```

## Other third-party assets

- **App design system** (`assets/styles.css`, module code): this project's own work.
- **Hero/feature photography** (`assets/*.jpg`): operator-supplied project assets.
- **Fonts:** Inter via Google Fonts (SIL Open Font License).
