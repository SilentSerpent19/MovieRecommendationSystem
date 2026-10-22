# Movie Recommendation System

A Django web app backed by a small, reproducible recommender-systems pipeline built on **MovieLens 25M**.
Users filter by genre, era, IMDb rating and mood. A hybrid model (item-kNN collaborative filtering plus
Tag Genome content similarity) ranks the matches using what each user has liked or saved, and explains every pick.

The project is sized for a laptop: each pipeline step finishes in under 1.5 minutes, with a peak of about 430 MB of RAM.

## Results

Offline evaluation on each user's held-out *future* interactions (9,817 users). The full report, with tuning grids
and confidence intervals, is in [`reports/evaluation.md`](reports/evaluation.md).

| model | NDCG@10 (95% CI) | Recall@10 | Hit rate@10 | Catalog coverage | Cold-start NDCG@10 (95% CI) |
|---|---|---|---|---|---|
| random | 0.004 | 0.003 | 0.03 | 1.00 | 0.003 |
| popularity | 0.079 [0.076, 0.082] | 0.057 | 0.35 | 0.03 | 0.079 [0.075, 0.083] |
| content (Tag Genome) | 0.058 [0.056, 0.060] | 0.045 | 0.32 | 0.65 | 0.051 [0.048, 0.055] |
| item-kNN | 0.125 [0.122, 0.129] | 0.094 | 0.48 | 0.21 | 0.114 [0.109, 0.119] |
| **hybrid (served)** | **0.127** [0.123, 0.130] | **0.096** | **0.49** | 0.23 | **0.115** [0.110, 0.120] |

"Cold start" means half of the users (4,912 evaluated) have their training history cut to their 3 most recent likes
*before* the models are fit, which mirrors a new user of the app.

What the numbers say:

- **Collaborative filtering clearly beats popularity.** Item-kNN adds +0.046 NDCG with full histories
  (paired bootstrap 95% CI [+0.043, +0.049]) and +0.035 with only 3 likes ([+0.030, +0.040]).
- **The hybrid adds no meaningful accuracy over item-kNN.** The gain is +0.001 NDCG: statistically detectable with
  full histories, and not significant at cold start (CI [-0.001, +0.003]). It is served because it covers more of the
  catalog (0.67 vs 0.64 at cold start), recommends slightly less mainstream titles, and has a content-based answer
  for items with thin collaborative signal. It is not served for an accuracy gain.
- **Content similarity alone is less accurate than popularity but far more diverse.** It recommends 65–88% of the
  catalog, against 3% for popularity. This is the usual accuracy versus coverage trade-off.

## Data

| source | used for | size |
|---|---|---|
| [MovieLens 25M](https://grouplens.org/datasets/movielens/25m/) (GroupLens) | ratings, Tag Genome, movie metadata, IMDb/TMDB links | 262 MB zip, never extracted |
| [IMDb `title.ratings`](https://developer.imdb.com/non-commercial-datasets/) | real IMDb rating and vote count | 9 MB |
| [Wikidata](https://www.wikidata.org/) (CC0) | directors and runtime, looked up by IMDb id and cached | ~25 requests |

**Subset, chosen to stay valid while fitting in memory:**

- **Catalog:** the 5,000 most-rated movies that have Tag Genome scores. They account for 92% of all 25M ratings,
  and every one has at least 584 ratings.
- **Users:** a seeded random pool (12.5% of user ids). Users with at least 20 ratings in the catalog are kept, then
  10,000 are sampled. That gives 1.45M interactions, a median of 69 ratings per user, and 2.9% density.
- **Feedback:** ratings of 4 stars or more count as positive (implicit "liked").
- **Ratings shown to users:** the MovieLens mean is shrunk towards the global mean with a Bayesian prior
  (`weighted_rating`), so a movie rated 5.0 by two people doesn't outrank a classic.
- **Moods:** each mood is the mean relevance of a few Tag Genome tags, for example
  Dark = `dark`, `bleak`, `disturbing`, `depressing`; see `system/ml/moods.py`. They are multi-label, scored and
  deterministic. At a threshold of 0.5, 72% of movies have at least one mood. For example, *The Shining* is
  Scary/Suspenseful/Dark and *Inception* is Thought-Provoking/Action-Packed/Atmospheric.

Every run of `prepare_data` writes `data/processed/manifest.json`. It records the config, source checksums and a
data-quality report: what was dropped and why, missing values, rating distribution, and mood score quantiles.

## Pipeline

```
prepare_data          ──► data/processed/   catalog.csv, genome.npy, mood_scores.npy, interactions.npz, manifest.json
load_catalog          ──► database          idempotent upsert of Movie, Genre, Mood, MovieMood
evaluate_recommenders ──► reports/          evaluation.json + evaluation.md
train_recommender     ──► data/models/<version>/   7 MB: sparse similarity, embeddings, popularity, meta.json
web / API / emails    ──► system/recommender.py
```

Serving pipeline (`system/recommender.py`), shared by the web page, the REST API and the weekly email:

1. **Candidates.** Apply the filters. If fewer than 10 movies match, relax them one at a time
   (mood, then rating, then era, then genre) and tell the user which ones were dropped.
2. **Exclude** movies the user has already liked, saved or disliked.
3. **Score** with the hybrid model, using the user's likes and watchlist as history. Popularity is used when the
   user has no history; the Bayesian rating is used when no model is trained.
4. **Re-rank** the top 200 for diversity with Maximal Marginal Relevance on genome embeddings.
5. **Explain** each pick as "Because you liked X", where X is the most similar item in the user's history.
6. **Log** a `RecommendationRequest`, plus an `Impression` per item. Likes, dislikes and watchlist actions are stored
   as `Event`s linked to the request that showed them, so the staff analytics page can report an online action rate
   next to the offline metrics.

Typical response time is 3–7 ms per request once the model is loaded.

## ML design

- **Evaluation protocol:** a per-user chronological split. Each user's oldest 70% of interactions are used for
  training, the next 10% for validation, and the newest 20% for test. Interactions that share the boundary timestamp
  all go to the later fold.
  - Hyperparameters are tuned on validation (a seeded sample of 3,000 users). The chosen configurations are refitted
    on train+validation and evaluated on test once.
  - Items a user rated before the test period are never recommended to them.
- **Cold start without leakage:** the models are refit after the cold users' histories are truncated, so their
  remaining likes never shape the similarities. An independent review caught the earlier version, which leaked.
- **Metrics:** precision, recall, NDCG and hit rate @10; catalog coverage; novelty (mean popularity percentile);
  bootstrap 95% CIs; and paired bootstrap differences between models.
- **Item-kNN:** cosine similarity with shrinkage, computed 500 items at a time. Only the top-k neighbours per item
  are kept as a sparse matrix, so the 5,000 × 5,000 dense similarity matrix is never built.
- **Content model:** the Tag Genome is standardised and reduced with TruncatedSVD (128 dimensions). A user's profile
  is the sum of the embeddings of the movies they liked.
- **Hybrid:** row-normalised kNN and content scores are blended with weight `n / (n + prior)`, where `n` is the
  user's history size. The blend is tuned on the mean of full-history and cold-start validation NDCG.
- **Resource budget, measured on an 8 GB M1:**

  | step | time | peak memory |
  |---|---|---|
  | `prepare_data` | 85 s (50 s of it Wikidata, cached after the first run) | 430 MB |
  | `evaluate_recommenders` | 49 s | 385 MB |
  | `train_recommender` | ~1 s | small |

## Quickstart

```bash
uv venv --python 3.12 venv && source venv/bin/activate      # or: python3.12 -m venv venv
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py prepare_data            # downloads ~270 MB on first run, then builds data/processed/
python manage.py load_catalog
python manage.py evaluate_recommenders   # optional: regenerates reports/
python manage.py train_recommender       # uses the hyperparameters selected by the evaluation
python manage.py createsuperuser         # staff users can open /analytics/
python manage.py runserver
```

You can change the dataset size with `prepare_data --movies 3000 --users 5000`. Use `--skip-wikidata` to work offline.

Tests and lint:

```bash
pytest                                              # 40 tests, no downloads needed
pytest system/tests/test_ml_models.py -k knn        # a single test
ruff check system/
```

## Project layout

```
system/ml/            framework-free data and ML code (also used by the tests)
  sources.py          download + checksum       movielens.py   streaming zip readers
  prepare.py          builds the processed set  moods.py       Tag Genome moods
  data.py             splits, sparse matrices   models.py      popularity, content, item-kNN, hybrid, MMR
  evaluation.py       metrics, bootstrap        experiment.py  tuning + test protocol
  artifacts.py        versioned model save/load
system/recommender.py serving pipeline (filters → candidates → score → diversify → explain → log)
system/management/commands/  prepare_data, load_catalog, evaluate_recommenders, train_recommender, send_weekly_recs
reports/              committed evaluation results
```

## Limitations

- **Some inputs look ahead in time.** The Tag Genome and the catalog selection (most-rated movies) were computed from
  data that includes ratings after the test cut-off. The split is per user, not global, so co-occurrences from other
  users' later activity are learned. Absolute scores are therefore somewhat optimistic; comparisons between models
  are fairer.
- **The results come from one sample.** There is one seed and one 10,000-user sample over the 5,000 most-rated
  movies, so the numbers say nothing about long-tail items. The confidence intervals cover user sampling only, not
  tuning or split variance.
- **Serving-time choices are not evaluated offline.** MMR diversity (0.3) and filter relaxation have no offline score.
- **The model learns only from MovieLens users.** App users get personalised results through item similarity from
  their likes, but their behaviour is logged, not used to retrain the model.
- **The data ends in November 2019**, so newer movies aren't in the catalog.

## Data licence and citation

The data is used for **non-commercial research and learning only**.

- MovieLens may not be redistributed and may not be used commercially without permission from GroupLens.
  The raw and processed data are git-ignored for this reason.
- IMDb datasets are licensed for personal, non-commercial use.

> F. Maxwell Harper and Joseph A. Konstan. 2015. The MovieLens Datasets: History and Context.
> ACM Transactions on Interactive Intelligent Systems 5, 4: 19:1–19:19. https://doi.org/10.1145/2827872
>
> Jesse Vig, Shilad Sen, and John Riedl. 2012. The Tag Genome: Encoding Community Knowledge to Support Novel
> Interaction. ACM TiiS 2, 3: 13:1–13:44. https://doi.org/10.1145/2362394.2362395

The code is under the [MIT License](LICENSE).
