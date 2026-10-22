# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A DS/ML learning and portfolio project: a Django movie recommender built on MovieLens 25M, with Tag Genome moods,
IMDb ratings and Wikidata metadata. It must stay runnable on an 8 GB laptop. Prefer streaming, sampling and sparse
matrices, and never build dense user×item or item×item matrices. There are no payments or subscriptions; they were
removed on purpose.

## Commands

```bash
uv venv --python 3.12 venv && source venv/bin/activate && pip install -r requirements-dev.txt
python manage.py migrate
python manage.py prepare_data            # download (md5-checked) + stream -> data/processed/ (~85 s, ~430 MB peak)
python manage.py load_catalog            # idempotent upsert into the DB
python manage.py evaluate_recommenders   # tune on validation, score test once -> reports/evaluation.{json,md}
python manage.py train_recommender       # fit on all data with the selected params -> data/models/<version>/, LATEST
python manage.py runserver

pytest                                   # all tests; none need downloads
pytest system/tests/test_recommender.py::test_filters_restrict_candidates   # single test
ruff check system/
```

## Architecture

- `system/ml/` is pure Python/numpy/scipy/sklearn with **no Django imports**. The offline experiment and the web app
  share these model classes, so evaluation and serving cannot drift apart.
  - `prepare.py` orchestrates `movielens.py` (streaming zip readers), `moods.py` and `enrich.py`.
    Its outputs are index-aligned: row *i* of `catalog.csv` is item *i* in every `.npy` array and model artifact.
  - `models.py`: every model has `fit(X_users×items CSR of positives, genome)` and `score(X_users) -> dense batch×items`.
    The hybrid min-max-normalises item-kNN and content scores per row and blends them with weight `n/(n+history_prior)`.
  - `experiment.py`: per-user chronological 70/10/20 split (ties at the boundary go to the later fold).
    Hyperparameters are chosen on validation. Cold start is evaluated *leak-free*: cold users are truncated to 3
    likes inside the training matrix before fitting.
  - `artifacts.py`: versioned model directory plus a `LATEST` pointer.
- `system/recommender.py` is the only serving path; the web view, `/api/recommend/` and `send_weekly_recs` all use it.
  - Pipeline: filter candidates in the DB → relax filters in `RELAX_ORDER` until ≥ k match → exclude liked, saved and
    disliked movies → score with the hybrid (popularity when there's no history) → MMR re-rank on genome embeddings →
    "Because you liked X" → log `RecommendationRequest` + `Impression`.
  - It falls back to `weighted_rating` when no model exists. The model is re-resolved from `LATEST` on each call.
- User history means watchlist items plus likes (`Feedback.value == 1`). Actions are logged as `Event`s carrying the
  `request_id` of the list that showed them; the staff-only `/analytics/` page uses this to compute an online action
  rate.
- Moods are scored per movie (`MovieMood.score`, assigned when ≥ `MOOD_THRESHOLD`, 0.5 by default). They come from
  genome tags listed in `system/ml/moods.py`, not from genres.

## Conventions and pitfalls

- After changing anything in `system/ml/`, rerun `evaluate_recommenders` and commit the updated `reports/`. Claims in
  the README must match `reports/evaluation.md`.
- `data/` is git-ignored except `data/README.md`. The MovieLens and IMDb licences forbid redistribution and
  commercial use.
- Watchlist, feedback and logging foreign keys to `Movie` are `PROTECT`, and `load_catalog` never deletes movies.
- Changing the catalog size or seed changes item indices. After `prepare_data`, always rerun `load_catalog` and
  `train_recommender`.
- Known evaluation caveats: the Tag Genome and the catalog selection use all ratings, including the test period, and
  there is no global time cut.
