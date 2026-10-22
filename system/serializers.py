from django.contrib.auth.models import User
from rest_framework import serializers

from .models import CuratedList, Movie, Watchlist


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']


class MovieSerializer(serializers.ModelSerializer):
    genres = serializers.StringRelatedField(many=True)
    moods = serializers.StringRelatedField(many=True)

    class Meta:
        model = Movie
        fields = ['id', 'movielens_id', 'imdb_id', 'title', 'year', 'runtime', 'directors', 'genres', 'moods',
                  'imdb_rating', 'imdb_votes', 'ml_rating_mean', 'ml_rating_count', 'weighted_rating']


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
