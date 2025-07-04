import pandas as pd
from django.core.management.base import BaseCommand
from system.models import Movie
import ast
import os
from django.db import transaction

class Command(BaseCommand):
    help = 'Import movies from Kaggle CSV files into the Movie model.'

    @transaction.atomic
    def handle(self, *args, **options):
        metadata_path = 'data/movies_metadata.csv'
        credits_path = 'data/credits.csv'

        self.stdout.write('Deleting all existing movies...')
        Movie.objects.all().delete()

        self.stdout.write('Loading movies_metadata.csv...')
        movies_df = pd.read_csv(metadata_path, low_memory=False)
        self.stdout.write('Loading credits.csv...')
        credits_df = pd.read_csv(credits_path)

        movies_df['id'] = movies_df['id'].astype(str)
        credits_df['id'] = credits_df['id'].astype(str)

        merged_df = pd.merge(movies_df, credits_df, on='id')

        merged_df = merged_df[
            merged_df['title'].notnull() &
            merged_df['release_date'].notnull() &
            merged_df['genres'].notnull() &
            merged_df['vote_average'].notnull()
        ]
        merged_df = merged_df[
            (merged_df['title'].str.strip() != '') &
            (merged_df['release_date'].str.strip() != '') &
            (merged_df['genres'].str.strip() != '')
        ]

        merged_df['year'] = merged_df['release_date'].str[:4]
        merged_df = merged_df[merged_df['year'].str.isdigit()]
        merged_df = merged_df[(merged_df['year'].astype(int) >= 1980) & (merged_df['year'].astype(int) <= 2029)]

        self.stdout.write(f'Found {len(merged_df)} movies with basic data quality...')

        target_movies = 5000
        processed_count = 0
        imported_count = 0
        skipped_count = 0

        for _, row in merged_df.iterrows():
            if imported_count >= target_movies:
                break
                
            processed_count += 1
            title = str(row.get('title', '')).strip()
            year = str(row.get('release_date', '')[:4]).strip() if pd.notnull(row.get('release_date', '')) else ''
            genre = ''
            try:
                genres = ast.literal_eval(row.get('genres', '[]'))
                genre = ', '.join([g['name'].strip() for g in genres if 'name' in g and g['name'].strip()])
            except Exception:
                pass
            director = ''
            try:
                crew = ast.literal_eval(row.get('crew', '[]'))
                directors = [c['name'].strip() for c in crew if c.get('job') == 'Director' and c.get('name') and c['name'].strip()]
                director = ', '.join(directors)
            except Exception:
                pass
            actors = ''
            try:
                cast = ast.literal_eval(row.get('cast', '[]'))
                actors = ', '.join([c['name'].strip() for c in cast[:5] if c.get('name') and c['name'].strip()])  # Top 5 actors
            except Exception:
                pass
            imdb_rating = None
            try:
                imdb_rating = float(row.get('vote_average', None)) if pd.notnull(row.get('vote_average', None)) else None
            except Exception:
                pass

            if not (title and year and genre and director and actors and imdb_rating is not None):
                skipped_count += 1
                continue

            if Movie.objects.filter(title=title, year=year).exists():
                skipped_count += 1
                continue

            Movie.objects.create(
                title=title,
                year=year,
                genre=genre,
                director=director,
                actors=actors,
                imdb_rating=imdb_rating,
            )
            imported_count += 1
            if imported_count % 200 == 0:
                self.stdout.write(f'Imported {imported_count} movies...')

        self.stdout.write(self.style.SUCCESS(f'Import complete. Total movies imported: {imported_count}'))
        self.stdout.write(self.style.WARNING(f'Total movies processed: {processed_count}'))
        self.stdout.write(self.style.WARNING(f'Total movies skipped: {skipped_count}')) 