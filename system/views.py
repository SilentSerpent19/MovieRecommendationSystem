import json
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import recommender
from .forms import EditProfileForm, RecommendationForm, UserRegistrationForm
from .ml import artifacts
from .models import CuratedList, Event, Feedback, Impression, Movie, RecommendationRequest, Watchlist


def login_redirect_view(request):
    if request.user.is_authenticated:
        return redirect('recommend')
    return login_view(request)


def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            messages.success(request, 'Logged in successfully!')
            return redirect('recommend')
        messages.error(request, 'Invalid username or password.')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})


def register_view(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            login(request, form.save())
            messages.success(request, 'Registration successful!')
            return redirect('recommend')
        messages.error(request, 'Registration failed. Please check the form.')
    else:
        form = UserRegistrationForm()
    return render(request, 'register.html', {'form': form})


def recommend_view(request):
    """GET-only: filters live in the query string, so result pages are bookmarkable and need no CSRF."""
    form = RecommendationForm(request.GET or None)
    result = None
    if not form.is_bound or form.is_valid():
        if not request.session.session_key:
            request.session.save()
        filters = form.to_filters() if form.is_bound else recommender.Filters()
        result = recommender.recommend(request.user, filters, session_key=request.session.session_key)
    feedback, watchlist = {}, set()
    if request.user.is_authenticated:
        feedback = dict(Feedback.objects.filter(user=request.user).values_list('movie_id', 'value'))
        watchlist = set(Watchlist.objects.filter(user=request.user).values_list('movie_id', flat=True))
    return render(request, 'recommend.html', {
        'form': form,
        'result': result,
        'liked': {m for m, v in feedback.items() if v == Feedback.LIKE},
        'disliked': {m for m, v in feedback.items() if v == Feedback.DISLIKE},
        'watchlist_ids': watchlist,
    })


def _attributed_request(request):
    """The RecommendationRequest an action came from, if the client sent a valid id."""
    try:
        rid = uuid.UUID(request.POST.get('request_id', ''))
    except ValueError:
        return None
    return RecommendationRequest.objects.filter(pk=rid).first()


def _respond(request, payload: dict, fallback: str):
    if request.headers.get('Accept') == 'application/json':
        return JsonResponse(payload)
    return redirect(request.POST.get('next') or fallback)


@login_required
@require_POST
def feedback_view(request, movie_id):
    movie = get_object_or_404(Movie, pk=movie_id)
    value = request.POST.get('value')
    if value == 'clear':
        Feedback.objects.filter(user=request.user, movie=movie).delete()
    elif value in ('like', 'dislike'):
        fb = Feedback.LIKE if value == 'like' else Feedback.DISLIKE
        Feedback.objects.update_or_create(user=request.user, movie=movie, defaults={'value': fb})
        Event.objects.create(user=request.user, movie=movie, action=value, request=_attributed_request(request))
    else:
        return JsonResponse({'error': 'value must be like, dislike or clear'}, status=400)
    return _respond(request, {'movie': movie.pk, 'value': value}, 'recommend')


@login_required
@require_POST
def add_to_watchlist(request, movie_id):
    movie = get_object_or_404(Movie, pk=movie_id)
    _, created = Watchlist.objects.get_or_create(user=request.user, movie=movie)
    if created:
        Event.objects.create(user=request.user, movie=movie, action=Event.WATCHLIST_ADD,
                             request=_attributed_request(request))
    return _respond(request, {'movie': movie.pk, 'in_watchlist': True}, 'recommend')


@login_required
@require_POST
def remove_from_watchlist(request, movie_id):
    movie = get_object_or_404(Movie, pk=movie_id)
    deleted, _ = Watchlist.objects.filter(user=request.user, movie=movie).delete()
    if deleted:
        Event.objects.create(user=request.user, movie=movie, action=Event.WATCHLIST_REMOVE,
                             request=_attributed_request(request))
    return _respond(request, {'movie': movie.pk, 'in_watchlist': False}, 'watchlist')


@login_required
def profile_view(request):
    return render(request, 'profile.html')


@login_required
def watchlist_view(request):
    watchlist = (Watchlist.objects.filter(user=request.user).select_related('movie')
                 .prefetch_related('movie__genres').order_by('-added_at'))
    return render(request, 'watchlist.html', {'watchlist': watchlist})


@login_required
def curated_lists_view(request):
    lists = CuratedList.objects.filter(is_active=True).prefetch_related('movies__genres', 'movies__moods')
    return render(request, 'curated_lists.html', {'lists': lists})


@staff_member_required
def analytics_dashboard(request):
    """Online behaviour (impressions and attributed actions) next to the offline evaluation report."""
    positive = Q(events__action__in=[Event.LIKE, Event.WATCHLIST_ADD])
    by_strategy = list(RecommendationRequest.objects.values('strategy')
                       .annotate(requests=Count('id', distinct=True),
                                 impressions=Count('impressions', distinct=True),
                                 positive_actions=Count('events', filter=positive, distinct=True),
                                 relaxed=Count('id', filter=~Q(relaxed=[]), distinct=True))
                       .order_by('-requests'))
    for row in by_strategy:
        row['action_rate'] = row['positive_actions'] / row['impressions'] if row['impressions'] else 0.0
    top_recommended = (Impression.objects.values('movie__title', 'movie__year')
                       .annotate(n=Count('id')).order_by('-n')[:10])
    top_liked = (Feedback.objects.filter(value=Feedback.LIKE).values('movie__title', 'movie__year')
                 .annotate(n=Count('id')).order_by('-n')[:10])
    events = dict(Event.objects.values_list('action').annotate(n=Count('id')))
    report_path = settings.BASE_DIR / 'reports' / 'evaluation.json'
    report = json.loads(report_path.read_text()) if report_path.exists() else None
    offline = []
    if report:
        k = report['protocol']['k']
        offline = [{'model': name, 'ndcg': r[f'ndcg@{k}'], 'recall': r[f'recall@{k}'], 'hit_rate': r[f'hit_rate@{k}'],
                    'coverage': r['coverage'], 'cold_ndcg': report['test_results_cold_start'][name][f'ndcg@{k}']}
                   for name, r in report['test_results'].items()]
    return render(request, 'analytics_dashboard.html', {
        'offline': offline,
        'by_strategy': by_strategy,
        'top_recommended': top_recommended,
        'top_liked': top_liked,
        'events': events,
        'report': report,
        'model_version': artifacts.latest_version(settings.MODEL_DIR),
    })


def privacy_policy_view(request):
    return render(request, 'privacy_policy.html')


@login_required
def edit_profile_view(request):
    if request.method == 'POST':
        form = EditProfileForm(request.user, request.POST)
        if form.is_valid():
            user = request.user
            cd = form.cleaned_data
            changed = False
            if cd.get('username') and cd['username'] != user.username:
                user.username = cd['username']
                changed = True
            if cd.get('email') and cd['email'] != user.email:
                user.email = cd['email']
                changed = True
            if cd.get('new_password1'):
                user.set_password(cd['new_password1'])
                changed = True
            if changed:
                user.save()
                if cd.get('new_password1'):
                    update_session_auth_hash(request, user)
                messages.success(request, 'Profile updated successfully!')
                return redirect('profile')
            messages.info(request, 'No changes made.')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = EditProfileForm(request.user, initial={'username': request.user.username, 'email': request.user.email})
    return render(request, 'edit_profile.html', {'form': form})
