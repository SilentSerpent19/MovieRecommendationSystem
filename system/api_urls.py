from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import RegisterView, LoginView, ProfileView, MovieRecommendationView, WatchlistViewSet, CuratedListViewSet, AnalyticsView

router = DefaultRouter()
router.register(r'watchlist', WatchlistViewSet, basename='watchlist')
router.register(r'curated-lists', CuratedListViewSet, basename='curatedlist')

urlpatterns = [
    path('register/', RegisterView.as_view(), name='api-register'),
    path('login/', LoginView.as_view(), name='api-login'),
    path('profile/', ProfileView.as_view(), name='api-profile'),
    path('recommend/', MovieRecommendationView.as_view(), name='api-recommend'),
    path('analytics/', AnalyticsView.as_view(), name='api-analytics'),
    path('', include(router.urls)),
] 