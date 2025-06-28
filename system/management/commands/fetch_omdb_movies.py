from django.core.management.base import BaseCommand
from system.models import Movie
import requests
import os

OMDB_API_KEY = os.environ.get('OMDB_API_KEY')  # Set your OMDb API key as an environment variable
OMDB_API_URL = 'http://www.omdbapi.com/'

class Command(BaseCommand):
    help = 'Fetch movies from OMDb and store them in the database.'

    def add_arguments(self, parser):
        parser.add_argument('titles', nargs='+', type=str, help='List of movie titles to fetch from OMDb')

    def handle(self, *args, **options):
        if not OMDB_API_KEY:
            self.stderr.write(self.style.ERROR('OMDB_API_KEY environment variable not set.'))
            return
        for title in options['titles']:
            params = {
                't': title,
                'apikey': OMDB_API_KEY
            }
            response = requests.get(OMDB_API_URL, params=params)
            data = response.json()
            if data.get('Response') == 'True':
                movie, created = Movie.objects.get_or_create(
                    title=data.get('Title', ''),
                    year=data.get('Year', ''),
                    defaults={
                        'genre': data.get('Genre', ''),
                        'director': data.get('Director', ''),
                        'actors': data.get('Actors', ''),
                        'imdb_rating': float(data.get('imdbRating', 0)) if data.get('imdbRating', 'N/A') != 'N/A' else None,
                    }
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f"Added movie: {movie}"))
                else:
                    self.stdout.write(self.style.WARNING(f"Movie already exists: {movie}"))
            else:
                self.stderr.write(self.style.ERROR(f"Failed to fetch '{title}': {data.get('Error', 'Unknown error')}")) 