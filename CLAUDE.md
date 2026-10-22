# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A Django movie recommendation web app: server-rendered templates and a DRF API. Movie data is imported from the Kaggle "The Movies Dataset" CSVs. Users filter by mood, genre, era and minimum rating, and step through matching movies one at a time. There are also accounts, a watchlist, curated lists, an analytics page and Free/Premium/Pro subscriptions.

## Commands

There is no committed virtualenv, linter config or pytest setup. Use Django's own tooling.

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt   # also needs django-paypal (see pitfalls)
python manage.py migrate
python manage.py runserver

# Data pipeline: run in this order. CSVs go in data/ (git-ignored).
python manage.py import_movies_kaggle   # needs data/movies_metadata.csv + data/credits.csv
python manage.py add_moods              # creates Mood rows; assign_moods does nothing without them
python manage.py assign_moods
python manage.py send_weekly_recs       # emails 3 random movies per user (console backend by default)

# Tests (django.test.TestCase)
python manage.py test system
python manage.py test system.tests.BasicFlowTests.test_login   # single test
```

Configuration comes from environment variables or `.env`, read by django-environ. `ENVIRONMENT_SETUP.md` lists them. With nothing set, the app uses SQLite (`db.sqlite3`), `DEBUG=True` and a hardcoded dev `SECRET_KEY`. Setting `DATABASE_URL` switches to another database through dj-database-url.

## Architecture

- `decision/` is the project package. `settings.py` sets `ROOT_URLCONF = 'decision.urls'`, which mounts `system.urls` at `/`, `system.api_urls` at `/api/`, and the django-paypal IPN at `/paypal/`. The top-level `urls.py` is a leftover that Django never loads.
- `system/` is the only app and holds everything else.
- **Recommendation engine** (`system/views.py`, `smart_score` and `recommend_movies`):
  - Rule-based. There's no ML model and no personalization; `scikit-learn` is in `requirements.txt` but never used.
  - Loads every `Movie` into Python and filters strictly on genre, era, rating and mood.
  - When nothing matches, it drops mood, then rating, then era, then genre, and returns `(top_10, fallback_used)`.
  - Three callers use it: `recommend_view` (form POST), `next_recommendation_set` (AJAX "Next" from `recommend.html`, cycling `current_index` through the same top 10), and `api_views.MovieRecommendationView` (which doesn't pass mood).
- **Mood labelling.** Each `Movie` has a single `mood` foreign key, set offline by `assign_moods` from substring matches on the genre string (`GENRE_TO_MOODS`). A second, separate map, `MOOD_GENRE_MAP` in `views.py`, is passed only to the template for UI hints. The two maps are not in sync.
- **Movie fields.** `genre` is one comma-separated string and `year` is a `CharField`. Code everywhere splits and parses them by hand. `imdb_rating` actually holds TMDB `vote_average`. `vote_count` and the TMDB/IMDb IDs are not stored.
- **Premium gating.**
  - `is_premium(user)` checks for an active `UserSubscription` that hasn't expired.
  - Free users get 5 recommendation page loads per *session* (`request.session['rec_count']`), and are capped at 5 watchlist items.
  - Pro is detected by `plan.name == 'Pro'`.
- **Subscriptions** are activated in three places:
  - the PayPal IPN handler in `system/signals.py`, connected in `SystemConfig.ready()`;
  - `secure_payment_view`;
  - `process_payment`, a mock JSON endpoint that is `csrf_exempt` and takes no real payment.
- **Interaction logging.** `UserInteraction` rows with `action='view_recommendation'` are written without a `movie`, so the analytics dashboard's "most recommended" sections are always empty.
- **Templates** all extend `base.html`, which loads Bootstrap 5 and jQuery from a CDN. Styling is in `system/static/cinema.css`.

## Known pitfalls

- `import_movies_kaggle` starts with `Movie.objects.all().delete()`. `Watchlist` uses `on_delete=CASCADE`, so re-importing wipes every user's watchlist and empties curated lists.
- `import_movies_kaggle` imports the first 5,000 rows that qualify, in CSV file order (years 1980–2029, with director and cast present). They are not chosen by quality.
- `assign_moods` skips movies that already have a mood, and picks a mood from `list(set(...))`. The order of a set of strings changes between processes, so its labels are not reproducible.
- `requirements.txt` lists `paypalrestsdk`, but the code imports `paypal.standard` from **django-paypal**, which must be installed separately.
- `system/signals.py` writes `start_date`/`end_date`. The model fields are `started_at`/`expires_at`.
- `BasicFlowTests.test_subscribe_flow` expects `subscribe_view` to create a subscription. It doesn't, so the test fails.
