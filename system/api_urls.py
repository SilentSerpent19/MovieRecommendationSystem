from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api_views import (
    CuratedListViewSet,
    LoginView,
    MovieRecommendationView,
    ProfileView,
    RegisterView,
    WatchlistViewSet,
)

router = DefaultRouter()
router.register(r'watchlist', WatchlistViewSet, basename='watchlist')
router.register(r'curated-lists', CuratedListViewSet, basename='curatedlist')

urlpatterns = [
    path('register/', RegisterView.as_view(), name='api-register'),
    path('login/', LoginView.as_view(), name='api-login'),
    path('profile/', ProfileView.as_view(), name='api-profile'),
    path('recommend/', MovieRecommendationView.as_view(), name='api-recommend'),
    path('', include(router.urls)),
]
