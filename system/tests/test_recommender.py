import numpy as np
import pytest
import scipy.sparse as sp
from django.contrib.auth.models import User

from system import recommender
from system.ml import artifacts
from system.ml.models import ContentModel, HybridModel, ItemKNNModel, PopularityModel
from system.models import Event, Feedback, Genre, Impression, Mood, Movie, MovieMood, RecommendationRequest, Watchlist
from system.recommender import Filters

N = 24


@pytest.fixture
def catalog(db):
    action, drama = Genre.objects.create(name='Action'), Genre.objects.create(name='Drama')
    funny = Mood.objects.create(name='Funny')
    movies = []
    for i in range(N):
        m = Movie.objects.create(
            movielens_id=1000 + i, title=f'Movie {i}', year=1985 + i, imdb_rating=5.0 + (i % 5),
            ml_rating_mean=3.5, ml_rating_count=100 + i, weighted_rating=3.0 + i / 100,
        )
        m.genres.add(action if i % 2 == 0 else drama)
        if i < 3:
            MovieMood.objects.create(movie=m, mood=funny, score=0.8)
        movies.append(m)
    return movies


@pytest.fixture
def trained_model(tmp_path, settings, catalog):
    rng = np.random.default_rng(0)
    dense = (rng.random((60, N)) < 0.3).astype(np.float32)
    dense[:, 5] = 1.0  # movie 5 is the most popular
    X = sp.csr_matrix(dense)
    genome = rng.random((N, 16)).astype(np.float32)
    model = HybridModel(ItemKNNModel(k=5), ContentModel(n_components=4), PopularityModel()).fit(X, genome)
    artifacts.save(model, np.arange(1000, 1000 + N), tmp_path, 'test-v1', {})
    settings.MODEL_DIR = tmp_path
    recommender.load_model.cache_clear()
    yield
    recommender.load_model.cache_clear()


@pytest.fixture
def user(db):
    return User.objects.create_user('ana', 'ana@example.com', 'pass-123-word')


@pytest.fixture
def anon():
    from django.contrib.auth.models import AnonymousUser
    return AnonymousUser()


def test_falls_back_to_weighted_rating_without_a_model(catalog, settings, tmp_path, anon):
    settings.MODEL_DIR = tmp_path
    recommender.load_model.cache_clear()
    result = recommender.recommend(anon, Filters(), k=3)
    assert result.strategy == 'weighted_rating'
    assert [r.movie.title for r in result.items] == ['Movie 23', 'Movie 22', 'Movie 21']
    recommender.load_model.cache_clear()


def test_anonymous_user_gets_popularity_and_request_is_logged(trained_model, anon):
    result = recommender.recommend(anon, Filters(), k=5, session_key='abc')
    assert result.strategy == 'popularity'
    assert result.items[0].movie.movielens_id == 1005
    req = RecommendationRequest.objects.get(pk=result.request_id)
    assert req.session_key == 'abc' and req.model_version == 'test-v1'
    assert list(Impression.objects.filter(request=req).values_list('rank', flat=True)) == [1, 2, 3, 4, 5]


def test_filters_restrict_candidates(trained_model, anon):
    result = recommender.recommend(anon, Filters(genre='Drama', era='1990s'), k=3)
    assert result.relaxed == []
    for r in result.items:
        assert r.movie.genres.filter(name='Drama').exists()
        assert 1990 <= r.movie.year <= 1999


def test_filters_are_relaxed_in_order_when_too_few_match(trained_model, anon):
    result = recommender.recommend(anon, Filters(mood='Funny', min_rating=9.0, genre='Action'), k=5)
    assert result.relaxed == ['mood', 'min_rating']
    assert len(result.items) == 5
    assert all(r.movie.genres.filter(name='Action').exists() for r in result.items)


def test_history_personalises_and_excludes_seen(trained_model, user, catalog):
    Feedback.objects.create(user=user, movie=catalog[0], value=Feedback.LIKE)
    Feedback.objects.create(user=user, movie=catalog[5], value=Feedback.DISLIKE)
    Watchlist.objects.create(user=user, movie=catalog[1])
    result = recommender.recommend(user, Filters(), k=10)
    assert result.strategy == 'hybrid'
    shown = {r.movie.pk for r in result.items}
    assert shown.isdisjoint({catalog[0].pk, catalog[1].pk, catalog[5].pk})
    assert all(r.reason.startswith('Because you liked Movie ') for r in result.items)


def test_recommend_page_renders_for_anonymous_and_logged_in(client, trained_model, user):
    assert client.get('/recommend/?genre=Action').status_code == 200
    client.force_login(user)
    response = client.get('/recommend/')
    assert response.status_code == 200
    assert b'Movie 5' in response.content


def test_invalid_filter_value_shows_form_errors(client, trained_model):
    response = client.get('/recommend/?genre=NotAGenre')
    assert response.status_code == 200
    assert response.context['result'] is None


def test_feedback_endpoint_records_feedback_and_attributed_event(client, trained_model, user, catalog):
    client.force_login(user)
    rid = recommender.recommend(user, Filters(), k=3).request_id
    url = f'/feedback/{catalog[2].pk}/'
    r = client.post(url, {'value': 'like', 'request_id': rid}, HTTP_ACCEPT='application/json')
    assert r.status_code == 200
    assert Feedback.objects.get(user=user, movie=catalog[2]).value == Feedback.LIKE
    assert Event.objects.get(action='like').request_id is not None
    client.post(url, {'value': 'clear'}, HTTP_ACCEPT='application/json')
    assert not Feedback.objects.filter(user=user).exists()
    assert client.post(url, {'value': 'love'}).status_code == 400


def test_watchlist_changes_require_post_and_login(client, catalog, user):
    url = f'/watchlist/add/{catalog[3].pk}/'
    assert client.post(url).status_code == 302 and not Watchlist.objects.exists()  # redirected to login
    client.force_login(user)
    assert client.get(url).status_code == 405
    client.post(url, HTTP_ACCEPT='application/json')
    assert Watchlist.objects.filter(user=user, movie=catalog[3]).exists()
    assert Event.objects.filter(action=Event.WATCHLIST_ADD).count() == 1
    client.post(f'/watchlist/remove/{catalog[3].pk}/')
    assert not Watchlist.objects.exists()


def test_analytics_is_staff_only(client, user, trained_model):
    client.force_login(user)
    assert client.get('/analytics/').status_code == 302
    user.is_staff = True
    user.save()
    assert client.get('/analytics/').status_code == 200


def test_api_recommend_returns_ranked_results_with_reasons(client, trained_model, user):
    client.force_login(user)
    data = client.get('/api/recommend/?genre=Action&k=4').json()
    assert data['strategy'] == 'popularity' and len(data['results']) == 4
    assert {'movie', 'score', 'reason'} <= set(data['results'][0])
    assert client.get('/api/recommend/?era=1800s').status_code == 400
