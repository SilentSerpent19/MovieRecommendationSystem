from django.contrib import admin
from .models import Movie, Mood, UserInteraction, Watchlist, CuratedList, SubscriptionPlan, UserSubscription

# Register your models here.

@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ('title', 'year', 'genre', 'imdb_rating')
    list_filter = ('genre', 'year')
    search_fields = ('title', 'genre')
    ordering = ('-imdb_rating',)

@admin.register(Mood)
class MoodAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
    ordering = ('name',)

@admin.register(UserInteraction)
class UserInteractionAdmin(admin.ModelAdmin):
    list_display = ('user', 'movie', 'action', 'timestamp')
    list_filter = ('action', 'timestamp')
    search_fields = ('user__username', 'movie__title')
    ordering = ('-timestamp',)

@admin.register(Watchlist)
class WatchlistAdmin(admin.ModelAdmin):
    list_display = ('user', 'movie', 'added_at')
    list_filter = ('added_at',)
    search_fields = ('user__username', 'movie__title')
    ordering = ('-added_at',)

@admin.register(CuratedList)
class CuratedListAdmin(admin.ModelAdmin):
    list_display = ('title', 'description', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('title', 'description')
    ordering = ('title',)

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'duration', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    ordering = ('name',)

@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'active', 'started_at', 'expires_at')
    list_filter = ('active', 'started_at', 'expires_at')
    search_fields = ('user__username', 'plan__name')
    ordering = ('-started_at',)