import uuid

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


class Feedback(models.Model):
    """Explicit like/dislike. Likes (with watchlist items) form the user's history for the recommender."""

    LIKE, DISLIKE = 1, -1
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    movie = models.ForeignKey(Movie, on_delete=models.PROTECT)
    value = models.SmallIntegerField(choices=[(LIKE, 'like'), (DISLIKE, 'dislike')])
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'movie'], name='unique_feedback')]


class RecommendationRequest(models.Model):
    """One served recommendation list, with everything needed to reproduce and evaluate it."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    session_key = models.CharField(max_length=40, blank=True)
    filters = models.JSONField(default=dict)
    relaxed = models.JSONField(default=list, help_text='Filters dropped because too few movies matched')
    strategy = models.CharField(max_length=30)
    model_version = models.CharField(max_length=30, blank=True)
    history_size = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class Impression(models.Model):
    request = models.ForeignKey(RecommendationRequest, on_delete=models.CASCADE, related_name='impressions')
    movie = models.ForeignKey(Movie, on_delete=models.PROTECT)
    rank = models.PositiveSmallIntegerField()
    score = models.FloatField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['request', 'rank'], name='unique_impression_rank')]


class Event(models.Model):
    """A user action on a movie, attributed to the recommendation list it came from when known."""

    LIKE, DISLIKE, WATCHLIST_ADD, WATCHLIST_REMOVE = 'like', 'dislike', 'watchlist_add', 'watchlist_remove'
    ACTIONS = [(a, a) for a in (LIKE, DISLIKE, WATCHLIST_ADD, WATCHLIST_REMOVE)]
    request = models.ForeignKey(RecommendationRequest, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='events')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    movie = models.ForeignKey(Movie, on_delete=models.PROTECT)
    action = models.CharField(max_length=20, choices=ACTIONS)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


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
