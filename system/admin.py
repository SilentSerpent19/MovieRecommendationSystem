from django.contrib import admin

from .models import (
    CuratedList,
    Event,
    Feedback,
    Genre,
    Impression,
    Mood,
    Movie,
    MovieMood,
    RecommendationRequest,
    Watchlist,
)


class MovieMoodInline(admin.TabularInline):
    model = MovieMood
    extra = 0


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ('title', 'year', 'imdb_rating', 'weighted_rating', 'ml_rating_count')
    list_filter = ('genres', 'moods')
    search_fields = ('title', 'directors', 'imdb_id')
    inlines = [MovieMoodInline]


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    search_fields = ('name',)


@admin.register(Mood)
class MoodAdmin(admin.ModelAdmin):
    list_display = ('name', 'tags')
    search_fields = ('name',)


class ImpressionInline(admin.TabularInline):
    model = Impression
    extra = 0
    readonly_fields = ('movie', 'rank', 'score')


@admin.register(RecommendationRequest)
class RecommendationRequestAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'strategy', 'model_version', 'history_size', 'filters', 'relaxed')
    list_filter = ('strategy', 'model_version')
    inlines = [ImpressionInline]


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'action', 'movie', 'request')
    list_filter = ('action',)
    search_fields = ('user__username', 'movie__title')


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('user', 'movie', 'value', 'updated_at')
    list_filter = ('value',)


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
    filter_horizontal = ('movies',)
