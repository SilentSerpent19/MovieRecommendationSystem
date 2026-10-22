from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Movie, Watchlist, CuratedList

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']

class MovieSerializer(serializers.ModelSerializer):
    class Meta:
        model = Movie
        fields = ['id', 'title', 'year', 'genre', 'director', 'actors', 'imdb_rating', 'mood', 'runtime', 'streaming_platform']

class WatchlistSerializer(serializers.ModelSerializer):
    movie = MovieSerializer(read_only=True)
    class Meta:
        model = Watchlist
        fields = ['id', 'movie', 'added_at']

class CuratedListSerializer(serializers.ModelSerializer):
    movies = MovieSerializer(many=True, read_only=True)
    class Meta:
        model = CuratedList
        fields = ['id', 'title', 'description', 'movies', 'is_active']
