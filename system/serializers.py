from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import CuratedList, Movie, Watchlist


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password']

    def validate(self, attrs):
        validate_password(attrs['password'], User(username=attrs.get('username'), email=attrs.get('email')))
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


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
