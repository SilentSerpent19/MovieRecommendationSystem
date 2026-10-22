from django.contrib.auth.models import User
from django.db import models


class Genre(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Mood(models.Model):
    """A mood label. Scores per movie live in MovieMood; see system/ml/moods.py for how they are derived."""

    name = models.CharField(max_length=50, unique=True)
    tags = models.CharField(max_length=255, blank=True, help_text='Tag Genome tags averaged into this mood')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Movie(models.Model):
    movielens_id = models.PositiveIntegerField(unique=True)
    imdb_id = models.CharField(max_length=12, blank=True, db_index=True)
    tmdb_id = models.PositiveIntegerField(null=True, blank=True)
    title = models.CharField(max_length=255)
    year = models.PositiveSmallIntegerField(null=True, blank=True, db_index=True)
    runtime = models.PositiveSmallIntegerField(null=True, blank=True, help_text='minutes')
    directors = models.CharField(max_length=255, blank=True)
    genres = models.ManyToManyField(Genre, related_name='movies', blank=True)
    moods = models.ManyToManyField(Mood, through='MovieMood', related_name='movies', blank=True)
    imdb_rating = models.FloatField(null=True, blank=True)
    imdb_votes = models.PositiveIntegerField(null=True, blank=True)
    ml_rating_mean = models.FloatField(help_text='MovieLens mean rating, 0.5-5 stars')
    ml_rating_count = models.PositiveIntegerField(help_text='MovieLens number of ratings')
    weighted_rating = models.FloatField(db_index=True, help_text='Bayesian-shrunk MovieLens mean')

    class Meta:
        ordering = ['-weighted_rating']

    def __str__(self):
        return f'{self.title} ({self.year})' if self.year else self.title


class MovieMood(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    mood = models.ForeignKey(Mood, on_delete=models.CASCADE)
    score = models.FloatField(help_text='Mean Tag Genome relevance of the mood tags, 0-1')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['movie', 'mood'], name='unique_movie_mood')]
        indexes = [models.Index(fields=['mood', '-score'])]


class UserInteraction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    action = models.CharField(max_length=100)
    movie = models.ForeignKey(Movie, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    extra_data = models.JSONField(default=dict, blank=True)


class Watchlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    movie = models.ForeignKey(Movie, on_delete=models.PROTECT)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'movie'], name='unique_watchlist_item')]


class CuratedList(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField()
    movies = models.ManyToManyField(Movie)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title
