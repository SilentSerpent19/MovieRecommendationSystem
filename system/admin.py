from django.contrib import admin

from .models import CuratedList, Genre, Mood, Movie, MovieMood, UserInteraction, Watchlist


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
    filter_horizontal = ('movies',)
