import numpy as np
import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from system.ml.moods import MOOD_TAGS
from system.models import Genre, Mood, Movie, MovieMood

FIELDS = ['imdb_id', 'tmdb_id', 'title', 'year', 'runtime', 'directors', 'imdb_rating', 'imdb_votes',
          'ml_rating_mean', 'ml_rating_count', 'weighted_rating']


def _clean(value):
    return None if pd.isna(value) else value


class Command(BaseCommand):
    help = 'Upsert the processed catalog (movies, genres, mood scores) into the database. Safe to re-run.'

    def add_arguments(self, parser):
        parser.add_argument('--mood-threshold', type=float, default=settings.MOOD_THRESHOLD,
                            help='Minimum mood score for a movie to be tagged with that mood')

    @transaction.atomic
    def handle(self, *args, **opts):
        processed = settings.PROCESSED_DATA_DIR
        if not (processed / 'catalog.csv').exists():
            raise CommandError(f'{processed}/catalog.csv not found; run `manage.py prepare_data` first.')
        cat = pd.read_csv(processed / 'catalog.csv', dtype={'imdb_id': str, 'directors': str})
        mood_scores = np.load(processed / 'mood_scores.npy')
        if len(mood_scores) != len(cat):
            raise CommandError('mood_scores.npy does not match catalog.csv; re-run prepare_data.')

        existing = {m.movielens_id: m for m in Movie.objects.all()}
        to_create, to_update = [], []
        for row in cat.itertuples(index=False):
            values = {f: _clean(getattr(row, f)) for f in FIELDS}
            values['directors'] = values['directors'] or ''
            movie = existing.get(row.movieId)
            if movie is None:
                to_create.append(Movie(movielens_id=row.movieId, **values))
            else:
                for f, v in values.items():
                    setattr(movie, f, v)
                to_update.append(movie)
        Movie.objects.bulk_create(to_create, batch_size=1000)
        Movie.objects.bulk_update(to_update, FIELDS, batch_size=1000)
        movie_id = dict(Movie.objects.values_list('movielens_id', 'id'))
        catalog_pks = [movie_id[m] for m in cat['movieId']]

        genre_names = sorted({g for gs in cat['genres'].dropna() for g in gs.split('|')})
        Genre.objects.bulk_create([Genre(name=g) for g in genre_names], ignore_conflicts=True)
        genre_id = dict(Genre.objects.values_list('name', 'id'))
        through = Movie.genres.through
        through.objects.filter(movie_id__in=catalog_pks).delete()
        through.objects.bulk_create([
            through(movie_id=pk, genre_id=genre_id[g])
            for pk, gs in zip(catalog_pks, cat['genres'].fillna(''), strict=True) for g in gs.split('|') if g
        ], batch_size=5000)

        moods = []
        for name, tags in MOOD_TAGS.items():
            mood, _ = Mood.objects.update_or_create(name=name, defaults={'tags': ', '.join(tags)})
            moods.append(mood)
        MovieMood.objects.filter(movie_id__in=catalog_pks).delete()
        rows, cols = np.nonzero(mood_scores >= opts['mood_threshold'])
        MovieMood.objects.bulk_create([
            MovieMood(movie_id=catalog_pks[r], mood=moods[c], score=round(float(mood_scores[r, c]), 4))
            for r, c in zip(rows, cols, strict=True)
        ], batch_size=5000)

        stale = Movie.objects.exclude(pk__in=catalog_pks).count()
        tagged = len(set(rows.tolist()))
        self.stdout.write(self.style.SUCCESS(
            f'Catalog: {len(to_create)} created, {len(to_update)} updated, {stale} not in current catalog. '
            f'Genres: {len(genre_names)}. Mood labels: {len(rows)} on {tagged}/{len(cat)} movies '
            f'(threshold {opts["mood_threshold"]}).'))
