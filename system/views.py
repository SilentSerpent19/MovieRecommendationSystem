from django.shortcuts import render, redirect, get_object_or_404
from system.models import Movie, Watchlist, CuratedList, Mood, UserSubscription, SubscriptionPlan, UserInteraction
from django.contrib.auth.models import User

from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.conf import settings
from django.contrib import messages
from django.urls import reverse
from django.http import JsonResponse
from paypal.standard.forms import PayPalPaymentsForm
from datetime import datetime, timedelta
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from django.db.models import Count, Q, Avg
from django.core.serializers.json import DjangoJSONEncoder

# Import forms from forms.py
from .forms import EditProfileForm, RecommendationForm, UserRegistrationForm, get_unique_genres

def smart_score(movie, user_genre, user_era, user_rating):
    score = 0
    movie_genres = [g.strip().lower() for g in (movie.genre or '').split(',')]
    if user_genre and user_genre.lower() in movie_genres:
        score += 3
    elif user_genre and any(user_genre.lower() in g for g in movie_genres):
        score += 1
    if user_era:
        era_map = {
            '1980s': (1980, 1989),
            '1990s': (1990, 1999),
            '2000s': (2000, 2009),
            '2010s': (2010, 2019),
            '2020s': (2020, 2029),
        }
        start, end = era_map.get(user_era, (0, 9999))
        if movie.year and movie.year.isdigit() and start <= int(movie.year) <= end:
            score += 2
    if user_rating and movie.imdb_rating:
        if movie.imdb_rating >= float(user_rating):
            score += 1 + (movie.imdb_rating - float(user_rating)) * 0.5
    return score

def recommend_movies(user_genre, user_era, user_rating, user_mood=None, n_results=10):
    movies = [m for m in Movie.objects.all() if m.genre and m.year and m.imdb_rating is not None]
    if not movies:
        return [], False

    def filter_movies(movies, genre=None, era=None, rating=None, mood=None):
        filtered = movies
        if genre:
            filtered = [m for m in filtered if genre.lower() in [g.strip().lower() for g in (m.genre or '').split(',')]]
        if era:
            era_map = {
                '1980s': (1980, 1989),
                '1990s': (1990, 1999),
                '2000s': (2000, 2009),
                '2010s': (2010, 2019),
                '2020s': (2020, 2029),
            }
            if era in era_map:
                start, end = era_map[era]
                filtered = [m for m in filtered if m.year and m.year.isdigit() and start <= int(m.year) <= end]
        if rating:
            filtered = [m for m in filtered if m.imdb_rating is not None and m.imdb_rating >= float(rating)]
        if mood:
            filtered = [m for m in filtered if m.mood and m.mood.name.lower() == mood.lower()]
        return filtered

    strict = filter_movies(movies, user_genre, user_era, user_rating, user_mood)
    strict = sorted(strict, key=lambda m: smart_score(m, user_genre, user_era, user_rating), reverse=True)
    if strict:
        return strict[:n_results], False
    relax1 = filter_movies(movies, user_genre, user_era, user_rating, None)
    relax1 = sorted(relax1, key=lambda m: smart_score(m, user_genre, user_era, user_rating), reverse=True)
    if relax1:
        return relax1[:n_results], True
    relax2 = filter_movies(movies, user_genre, user_era, None, None)
    relax2 = sorted(relax2, key=lambda m: smart_score(m, user_genre, user_era, user_rating), reverse=True)
    if relax2:
        return relax2[:n_results], True
    relax3 = filter_movies(movies, user_genre, None, None, None)
    relax3 = sorted(relax3, key=lambda m: smart_score(m, user_genre, user_era, user_rating), reverse=True)
    if relax3:
        return relax3[:n_results], True
    fallback = sorted(movies, key=lambda m: smart_score(m, user_genre, user_era, user_rating), reverse=True)
    return fallback[:n_results], True

def is_premium(user):
    if not user.is_authenticated:
        return False
    try:
        sub = UserSubscription.objects.get(user=user)
        return sub.active and (not sub.expires_at or sub.expires_at > timezone.now())
    except UserSubscription.DoesNotExist:
        return False

def login_redirect_view(request):
    if request.user.is_authenticated:
        return redirect('recommend')
    return login_view(request)

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, 'Logged in successfully!')
            return redirect('recommend')
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})



def register_view(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful!')
            return redirect('recommend')
        else:
            messages.error(request, 'Registration failed. Please check the form.')
    else:
        form = UserRegistrationForm()
    return render(request, 'register.html', {'form': form})

@login_required
def subscribe_view(request):
    plans = SubscriptionPlan.objects.all()
    try:
        user_sub = UserSubscription.objects.get(user=request.user, active=True)
        plan = user_sub.plan
        messages.info(request, f'You are already subscribed to {plan.name}.')
    except UserSubscription.DoesNotExist:
        user_sub = None
        if request.method == 'POST':
            plan_id = request.POST.get('plan_id')
            if plan_id:
                plan = SubscriptionPlan.objects.get(id=plan_id)
                messages.success(request, f'Subscribed to {plan.name}!')
                return render(request, 'subscribe.html', {'plans': plans, 'user_sub': user_sub})
    return render(request, 'subscribe.html', {'plans': plans, 'user_sub': user_sub})

@login_required
def paypal_payment(request, plan_id):
    plan = SubscriptionPlan.objects.get(id=plan_id)
    paypal_dict = {
        'business': settings.PAYPAL_RECEIVER_EMAIL,
        'amount': str(plan.price),
        'item_name': plan.name,
        'invoice': f'{request.user.id}-{plan.id}-{datetime.now().timestamp()}',
        'currency_code': 'USD',
        'notify_url': request.build_absolute_uri(reverse('paypal-ipn')),
        'return_url': request.build_absolute_uri(reverse('paypal_success')),
        'cancel_return': request.build_absolute_uri(reverse('paypal_cancel')),
        'custom': f'{request.user.id}:{plan.id}',
    }
    form = PayPalPaymentsForm(initial=paypal_dict)
    return render(request, 'paypal_payment.html', {'form': form, 'plan': plan})

def paypal_success(request):
    user_sub = None
    if request.user.is_authenticated:
        user_sub = UserSubscription.objects.filter(user=request.user, active=True).first()
    return render(request, 'subscribe_success.html', {'user_sub': user_sub})

def paypal_cancel(request):
    return render(request, 'subscribe_cancel.html')

MOOD_GENRE_MAP = {
    'funny': ['Comedy', 'Animation', 'Musical'],
    'feel-good': ['Animation', 'Family', 'Comedy', 'Musical'],
    'romantic': ['Romance', 'Musical'],
    'uplifting': ['Family', 'Romance', 'Music', 'Musical', 'Sport'],
    'scary': ['Horror'],
    'dark': ['Horror', 'Crime', 'War'],
    'suspenseful': ['Thriller', 'Mystery', 'Crime'],
    'action-packed': ['Action', 'Western', 'Superhero', 'Super Hero', 'Super-Hero'],
    'excited': ['Action', 'Adventure', 'Fantasy', 'Sci-Fi', 'Science Fiction', 'Sport', 'Superhero', 'Super Hero', 'Super-Hero'],
    'adventurous': ['Adventure', 'Fantasy', 'Western'],
    'thought-provoking': ['Drama', 'History', 'Science Fiction', 'Sci-Fi', 'War', 'Documentary', 'Biography'],
    'sad': ['Drama'],
    'mysterious': ['Mystery', 'Crime', 'Thriller'],
    'inspiring': ['Documentary', 'Biography', 'History'],
}

def recommend_view(request):
    recommendations = []
    fallback_used = False
    current_index = 0
    genre = era = rating = mood = ''
    moods = Mood.objects.all()
    mood_genre_map = MOOD_GENRE_MAP
    if request.method == 'POST':
        print(f"[DEBUG] request.POST: {dict(request.POST)}")
        if 'next' in request.POST:
            genre = request.POST.get('genre', '')
            era = request.POST.get('era', '')
            rating = request.POST.get('rating', '')
            mood = request.POST.get('mood', '')
            current_index = int(request.POST.get('current_index', 0)) + 1
            print(f"[DEBUG] NEXT: genre={genre}, era={era}, rating={rating}, mood={mood}, current_index={current_index}")
            print(f"[DEBUG] Calling recommend_movies with: genre={genre}, era={era}, rating={rating}, mood={mood}")
            recs, fallback_used = recommend_movies(genre, era, rating, mood)
            if recs:
                if current_index >= len(recs):
                    current_index = 0
                recommendations = [recs[current_index]]
            else:
                recommendations = []
            form = RecommendationForm(request.POST, moods=moods)
        else:
            form = RecommendationForm(request.POST, moods=moods)
            if form.is_valid():
                print(f"[DEBUG] form.cleaned_data: {form.cleaned_data}")
                genre = form.cleaned_data['genre']
                era = form.cleaned_data['era']
                rating = form.cleaned_data['rating']
                mood = form.cleaned_data['mood']
                current_index = 0
                print(f"[DEBUG] RECOMMEND (valid): genre={genre}, era={era}, rating={rating}, mood={mood}, current_index={current_index}")
                print(f"[DEBUG] Calling recommend_movies with: genre={genre}, era={era}, rating={rating}, mood={mood}")
                recs, fallback_used = recommend_movies(genre, era, rating, mood)
                if recs:
                    recommendations = [recs[0]]
                else:
                    recommendations = []
            else:
                genre = request.POST.get('genre', '')
                era = request.POST.get('era', '')
                rating = request.POST.get('rating', '')
                mood = request.POST.get('mood', '')
                print(f"[DEBUG] RECOMMEND (invalid): genre={genre}, era={era}, rating={rating}, mood={mood}, current_index={current_index}")
    else:
        form = RecommendationForm(moods=moods)
    print(f"[DEBUG] FINAL: genre={genre}, era={era}, rating={rating}, mood={mood}, current_index={current_index}")
    user_is_premium = is_premium(request.user)
    user_is_pro = False
    if user_is_premium:
        user_sub = UserSubscription.objects.filter(user=request.user, active=True).first()
        if user_sub and user_sub.plan.name == 'Pro':
            user_is_pro = True
    daily_limit = 5
    show_ads = not user_is_premium
    show_upgrade = not user_is_premium
    if not user_is_premium:
        rec_count = request.session.get('rec_count', 0)
        if rec_count >= daily_limit:
            return render(request, 'limit_reached.html', {'show_upgrade': show_upgrade})
        request.session['rec_count'] = rec_count + 1
    if request.user.is_authenticated:
        UserInteraction.objects.create(user=request.user, action='view_recommendation')
    recommendations_json = json.dumps([
        {
            'title': m.title,
            'year': m.year,
            'genre': m.genre,
            'director': m.director,
            'actors': m.actors,
            'rating': m.imdb_rating,
            'runtime': m.runtime,
            'streaming_platform': m.streaming_platform,
            'mood': m.mood.name if m.mood else '',
            'id': m.id,
        } for m in recommendations
    ], cls=DjangoJSONEncoder)
    return render(request, 'recommend.html', {
        'form': form,
        'recommendations': recommendations,
        'recommendations_json': recommendations_json,
        'genre': genre,
        'era': era,
        'rating': rating,
        'mood': mood,
        'current_index': current_index,
        'fallback_used': fallback_used,
        'show_ads': show_ads,
        'show_upgrade': show_upgrade,
        'user_is_premium': user_is_premium,
        'user_is_pro': user_is_pro,
        'moods': moods,
        'mood_genre_map': mood_genre_map,
        'selected_mood': mood,
    })

@login_required
def profile_view(request):
    try:
        user_sub = UserSubscription.objects.get(user=request.user)
    except UserSubscription.DoesNotExist:
        user_sub = None
    return render(request, 'profile.html', {'user_sub': user_sub})

@login_required
def add_to_watchlist(request, movie_id):
    user = request.user
    movie = get_object_or_404(Movie, id=movie_id)
    user_sub = UserSubscription.objects.filter(user=user, active=True).first()
    limit = 5 if not user_sub or user_sub.plan.name == 'Basic' else None
    if limit and Watchlist.objects.filter(user=user).count() >= limit:
        messages.error(request, 'Watchlist limit reached. Upgrade for more!')
    else:
        Watchlist.objects.get_or_create(user=user, movie=movie)
        messages.success(request, f'Added {movie.title} to your watchlist!')
    return redirect('recommend')

@login_required
def remove_from_watchlist(request, movie_id):
    user = request.user
    movie = get_object_or_404(Movie, id=movie_id)
    Watchlist.objects.filter(user=user, movie=movie).delete()
    messages.success(request, f'Removed {movie.title} from your watchlist!')
    return redirect('recommend')

@login_required
def watchlist_view(request):
    watchlist = Watchlist.objects.filter(user=request.user).select_related('movie')
    return render(request, 'watchlist.html', {'watchlist': watchlist})

@login_required
def curated_lists_view(request):
    lists = CuratedList.objects.filter(is_active=True)
    return render(request, 'curated_lists.html', {'lists': lists})

@login_required
def analytics_dashboard(request):
    from django.db.models import Q, Avg
    now = timezone.now()
    last_30 = now - timedelta(days=30)

    popular_movies = (
        Movie.objects.annotate(count=Count('watchlist'))
        .order_by('-count')[:10]
    )
    popular_movies = [(m, m.count) for m in popular_movies if m.count > 0]

    recent_watchlist = Watchlist.objects.filter(added_at__gte=last_30)
    recent_movie_counts = {}
    for w in recent_watchlist:
        recent_movie_counts[w.movie] = recent_movie_counts.get(w.movie, 0) + 1
    trending_movies = sorted(recent_movie_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    genre_counts = {}
    for m in Movie.objects.all():
        for g in (m.genre or '').split(','):
            g = g.strip()
            if g:
                genre_counts[g] = genre_counts.get(g, 0) + Watchlist.objects.filter(movie=m).count()
    popular_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    recent_genre_counts = {}
    for w in recent_watchlist:
        for g in (w.movie.genre or '').split(','):
            g = g.strip()
            if g:
                recent_genre_counts[g] = recent_genre_counts.get(g, 0) + 1
    trending_genres = sorted(recent_genre_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    rec_logs = UserInteraction.objects.filter(action='view_recommendation')
    rec_movie_counts = {}
    rec_genre_counts = {}
    for log in rec_logs:
        if log.movie:
            rec_movie_counts[log.movie] = rec_movie_counts.get(log.movie, 0) + 1
            for g in (log.movie.genre or '').split(','):
                g = g.strip()
                if g:
                    rec_genre_counts[g] = rec_genre_counts.get(g, 0) + 1
    most_rec_movies = sorted(rec_movie_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    most_rec_genres = sorted(rec_genre_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    user_watchlist_counts = (
        Watchlist.objects.values('user')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )
    user_map = {u.id: u for u in User.objects.filter(id__in=[uwc['user'] for uwc in user_watchlist_counts])}
    most_active_users = [
        (user_map.get(uwc['user']), uwc['count']) for uwc in user_watchlist_counts if uwc['user'] in user_map
    ]

    avg_rating = Watchlist.objects.filter(movie__imdb_rating__isnull=False).aggregate(avg=Avg('movie__imdb_rating'))['avg']

    return render(request, 'analytics_dashboard.html', {
        'popular_movies': popular_movies,
        'trending_movies': trending_movies,
        'popular_genres': popular_genres,
        'trending_genres': trending_genres,
        'most_rec_movies': most_rec_movies,
        'most_rec_genres': most_rec_genres,
        'most_active_users': most_active_users,
        'avg_rating': avg_rating,
    })

def privacy_policy_view(request):
    return render(request, 'privacy_policy.html')

@require_http_methods(["POST"])
@csrf_exempt
def secure_payment(request):
    data = json.loads(request.body)
    amount = data['amount']
    currency = data['currency']
    description = data['description']
    return JsonResponse({'status': 'success', 'message': 'Payment processed successfully'})

@login_required
def secure_payment_view(request, plan_id):
    plan = get_object_or_404(SubscriptionPlan, id=plan_id)
    
    if request.method == 'POST':
        try:
            UserSubscription.objects.filter(user=request.user).update(active=False)
            now = timezone.now()
            if plan.duration == 'monthly':
                expires_at = now + timedelta(days=30)
            elif plan.duration == 'yearly':
                expires_at = now + timedelta(days=365)
            elif plan.duration == 'lifetime':
                expires_at = None
            else:
                expires_at = None
            UserSubscription.objects.update_or_create(
                user=request.user,
                defaults={'plan': plan, 'active': True, 'started_at': now, 'expires_at': expires_at}
            )
            messages.success(request, f'Payment successful! You are now subscribed to {plan.name}.')
            return redirect('paypal_success')
        except Exception as e:
            messages.error(request, f'Payment failed: {str(e)}')
            return redirect('paypal_cancel')
    
    return render(request, 'secure_payment.html', {
        'plan': plan,
        'amount': plan.price,
        'currency': 'USD'
    })

@require_http_methods(["POST"])
@csrf_exempt
def process_payment(request):
    try:
        data = json.loads(request.body)
        plan_id = data.get('plan_id')
        plan = get_object_or_404(SubscriptionPlan, id=plan_id)
        now = timezone.now()
        if plan.duration == 'monthly':
            expires_at = now + timedelta(days=30)
        elif plan.duration == 'yearly':
            expires_at = now + timedelta(days=365)
        elif plan.duration == 'lifetime':
            expires_at = None
        else:
            expires_at = None
        UserSubscription.objects.filter(user=request.user).update(active=False)
        UserSubscription.objects.update_or_create(
            user=request.user,
            defaults={'plan': plan, 'active': True, 'started_at': now, 'expires_at': expires_at}
        )
        return JsonResponse({
            'status': 'success',
            'message': 'Payment processed successfully',
            'redirect_url': reverse('paypal_success')
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required
def manage_payment_method(request):
    """
    In production, this view should redirect the user to your payment provider's (e.g., PayPal, Stripe) secure payment method management page.
    You should NOT handle or store card details yourself.
    For PayPal: Use PayPal's Vault or Billing Agreements API to let users update their card securely.
    For Stripe: Use Stripe's customer portal or setup_intent/session to let users update their card securely.
    
    For now, this is a placeholder for testing. Replace with a real redirect in production.
    """
    # Example for production (uncomment and implement):
    # return redirect(payment_provider_generate_update_url(request.user))
    return render(request, 'manage_payment_method.html', {})

@require_http_methods(["POST"])
@csrf_exempt
def next_recommendation_set(request):
    """Handle AJAX request for next set of recommendations"""
    try:
        data = json.loads(request.body)
        genre = data.get('genre', '')
        era = data.get('era', '')
        rating = data.get('rating', '')
        mood = data.get('mood', '')
        current_index = data.get('current_index', 0)
        
        recs, fallback_used = recommend_movies(genre, era, rating, mood)
        
        if recs:
            next_index = (current_index + 1) % len(recs)
            next_movie = recs[next_index]
            
            movie_data = {
                'title': next_movie.title,
                'year': next_movie.year,
                'genre': next_movie.genre,
                'director': next_movie.director,
                'actors': next_movie.actors,
                'rating': next_movie.imdb_rating,
                'runtime': next_movie.runtime,
                'streaming_platform': next_movie.streaming_platform,
                'mood': next_movie.mood.name if next_movie.mood else '',
                'id': next_movie.id,
                'current_index': next_index,
                'total_count': len(recs),
                'fallback_used': fallback_used
            }
            
            return JsonResponse({
                'status': 'success',
                'movie': movie_data
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'No more recommendations available'
            })
            
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required
def edit_profile_view(request):
    if request.method == 'POST':
        form = EditProfileForm(request.user, request.POST)
        if form.is_valid():
            user = request.user
            cd = form.cleaned_data
            changed = False
            if cd.get('username') and cd.get('username') != user.username:
                user.username = cd['username']
                changed = True
            if cd.get('email') and cd.get('email') != user.email:
                user.email = cd['email']
                changed = True
            if cd.get('new_password1'):
                user.set_password(cd['new_password1'])
                changed = True
            if changed:
                user.save()
                messages.success(request, 'Profile updated successfully!')
                if cd.get('new_password1'):
                    from django.contrib.auth import update_session_auth_hash
                    update_session_auth_hash(request, user)
                return redirect('profile')
            else:
                messages.info(request, 'No changes made.')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = EditProfileForm(request.user, initial={'username': request.user.username, 'email': request.user.email})
    return render(request, 'edit_profile.html', {'form': form})
