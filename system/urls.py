from django.urls import path
from .views import (
    recommend_view, profile_view, subscribe_view, 
    paypal_payment, paypal_success, paypal_cancel, login_view, register_view,
    watchlist_view, add_to_watchlist, remove_from_watchlist, curated_lists_view,
    analytics_dashboard, privacy_policy_view, secure_payment_view, manage_payment_method,
    next_recommendation_set, edit_profile_view, login_redirect_view, secure_payment, process_payment
)
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path('', login_redirect_view, name='home'),
    path('recommend/', recommend_view, name='recommend'),
    path('recommend/next-set/', next_recommendation_set, name='next_recommendation_set'),
    path('profile/', profile_view, name='profile'),
    path('profile/edit/', edit_profile_view, name='edit_profile'),
    path('subscribe/', subscribe_view, name='subscribe'),
    path('subscribe/paypal/<int:plan_id>/', paypal_payment, name='paypal_payment'),
    path('subscribe/success/', paypal_success, name='paypal_success'),
    path('subscribe/cancel/', paypal_cancel, name='paypal_cancel'),
    
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
    path('secure-payment/<int:plan_id>/', secure_payment_view, name='secure_payment'),
    path('api/secure-payment/', secure_payment, name='secure_payment_api'),
    path('api/process-payment/', process_payment, name='process_payment'),
    path('manage-payment-method/', manage_payment_method, name='manage_payment_method'),
    
]
