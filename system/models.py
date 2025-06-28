from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class SubscriptionPlan(models.Model):
    DURATION_CHOICES = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
        ('lifetime', 'Lifetime'),
    ]
    
    name = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    description = models.TextField()
    duration = models.CharField(max_length=20, choices=DURATION_CHOICES, default='monthly')
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name
    
    def get_duration_display_text(self):
        if self.duration == 'monthly':
            return 'per month'
        elif self.duration == 'yearly':
            return 'per year'
        elif self.duration == 'lifetime':
            return 'one-time payment'
        return ''

class UserSubscription(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True)
    active = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

class UserInteraction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    action = models.CharField(max_length=100)
    movie = models.ForeignKey('Movie', on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    extra_data = models.JSONField(default=dict, blank=True)

class Mood(models.Model):
    name = models.CharField(max_length=50)
    def __str__(self):
        return self.name

class Watchlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    movie = models.ForeignKey('Movie', on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ('user', 'movie')

class CuratedList(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField()
    movies = models.ManyToManyField('Movie')
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return self.title

class Movie(models.Model):
    title = models.CharField(max_length=255)
    year = models.CharField(max_length=10)
    genre = models.CharField(max_length=255)
    director = models.CharField(max_length=255, blank=True, null=True)
    actors = models.CharField(max_length=500, blank=True, null=True)
    imdb_rating = models.FloatField(blank=True, null=True)
    mood = models.ForeignKey(Mood, on_delete=models.SET_NULL, null=True, blank=True)
    runtime = models.IntegerField(null=True, blank=True)
    streaming_platform = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.title} ({self.year})"
