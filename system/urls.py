from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import (
    add_to_watchlist,
    analytics_dashboard,
    curated_lists_view,
    edit_profile_view,
    feedback_view,
    login_redirect_view,
    login_view,
    privacy_policy_view,
    profile_view,
    recommend_view,
    register_view,
    remove_from_watchlist,
    watchlist_view,
)

urlpatterns = [
    path('', login_redirect_view, name='home'),
    path('recommend/', recommend_view, name='recommend'),
    path('feedback/<int:movie_id>/', feedback_view, name='feedback'),
    path('profile/', profile_view, name='profile'),
    path('profile/edit/', edit_profile_view, name='edit_profile'),
    # Authentication URLs
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('logout/', LogoutView.as_view(next_page='recommend'), name='logout'),

    # Watchlist URLs
    path('watchlist/', watchlist_view, name='watchlist'),
    path('watchlist/add/<int:movie_id>/', add_to_watchlist, name='add_to_watchlist'),
    path('watchlist/remove/<int:movie_id>/', remove_from_watchlist, name='remove_from_watchlist'),

    # Other URLs
    path('curated-lists/', curated_lists_view, name='curated_lists'),
    path('analytics/', analytics_dashboard, name='analytics_dashboard'),
    path('privacy-policy/', privacy_policy_view, name='privacy_policy'),
]
