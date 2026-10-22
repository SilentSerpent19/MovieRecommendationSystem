import zipfile

import numpy as np
import pandas as pd
import pytest

from system.ml import enrich, moods, movielens, prepare


@pytest.fixture
def ml_zip(tmp_path):
    """A tiny ml-25m-shaped zip: 4 movies, 3 genome tags, 6 users."""
    ratings = pd.DataFrame({
        'userId':    [1, 1, 1, 2, 2, 3, 4, 4, 5, 6],
        'movieId':   [10, 20, 30, 10, 20, 10, 10, 40, 20, 10],
        'rating':    [4.0, 3.0, 5.0, 2.0, 4.5, 5.0, 3.5, 1.0, 4.0, 4.0],
        'timestamp': range(10),
    })
    movies = pd.DataFrame({
        'movieId': [10, 20, 30, 40],
        'title': ['Matrix, The (1999)', 'Toy Story (1995)', 'Heat (1995)', 'Untitled'],
        'genres': ['Action|Sci-Fi', 'Animation|Comedy', 'Crime', '(no genres listed)'],
    })
    links = pd.DataFrame({'movieId': [10, 20, 30, 40], 'imdbId': ['133093', '114709', '113277', '1'],
                          'tmdbId': [603, 862, 949, None]})
    tags = pd.DataFrame({'tagId': [1, 2, 3], 'tag': ['funny', 'dark', 'epic']})
    genome = pd.DataFrame([(m, t, r) for m, rel in [(10, (0.1, 0.8, 0.9)), (20, (0.9, 0.1, 0.2)),
                                                    (30, (0.2, 0.7, 0.3))]
                           for t, r in zip((1, 2, 3), rel, strict=True)],
                          columns=['movieId', 'tagId', 'relevance'])
    path = tmp_path / 'ml-25m.zip'
    with zipfile.ZipFile(path, 'w') as zf:
        for name, df in [('ratings', ratings), ('movies', movies), ('links', links),
                         ('genome-tags', tags), ('genome-scores', genome)]:
            zf.writestr(f'ml-25m/{name}.csv', df.to_csv(index=False))
    return path


def test_scan_ratings_counts_all_users_but_keeps_only_pool_rows(ml_zip):
    scan = movielens.scan_ratings(ml_zip, pool=np.array([1, 4], np.int32), max_user_id=10, chunksize=3)
    assert scan.total_ratings == 10
    assert scan.movie_counts[10] == 5 and scan.movie_counts[40] == 1
    assert scan.movie_sums[10] == pytest.approx(4 + 2 + 5 + 3.5 + 4)
    assert set(scan.pool_ratings['userId']) == {1, 4}
    assert len(scan.pool_ratings) == 5


def test_scan_ratings_rejects_user_ids_beyond_sampling_range(ml_zip):
    with pytest.raises(ValueError):
        movielens.scan_ratings(ml_zip, pool=np.array([1]), max_user_id=3, chunksize=100)


def test_user_pool_is_reproducible_and_seed_dependent():
    a = movielens.user_pool(10_000, 0.1, seed=1)
    assert np.array_equal(a, movielens.user_pool(10_000, 0.1, seed=1))
    assert not np.array_equal(a, movielens.user_pool(10_000, 0.1, seed=2))
    assert 800 < len(a) < 1200


def test_read_genome_only_returns_requested_movies(ml_zip):
    genome, tags = movielens.read_genome(ml_zip, np.array([10, 30]), chunksize=4)
    assert tags == ['funny', 'dark', 'epic']
    np.testing.assert_allclose(genome, [[0.1, 0.8, 0.9], [0.2, 0.7, 0.3]], rtol=1e-6)


def test_read_genome_fails_loudly_for_movies_without_scores(ml_zip):
    with pytest.raises(ValueError):
        movielens.read_genome(ml_zip, np.array([10, 40]), chunksize=100)


def test_read_movies_parses_year_article_genres_and_ids(ml_zip):
    df = movielens.read_movies(ml_zip).set_index('movieId')
    assert df.loc[10, 'title'] == 'The Matrix'
    assert df.loc[10, 'year'] == 1999
    assert df.loc[10, 'genres'] == ['Action', 'Sci-Fi']
    assert df.loc[40, 'genres'] == []
    assert pd.isna(df.loc[40, 'year'])
    assert df.loc[20, 'imdb_id'] == 'tt0114709'


def test_select_catalog_takes_most_rated_movies_with_genome():
    counts = np.array([0, 0, 50, 10, 99, 50, 7])
    genome_ids = np.array([2, 3, 5, 6])  # movie 4 is most rated but has no genome
    assert prepare.select_catalog(counts, genome_ids, n_movies=2).tolist() == [2, 5]


def test_sample_users_applies_min_ratings_then_samples_deterministically():
    ratings = pd.DataFrame({'userId': [1] * 5 + [2] * 2 + [3] * 6, 'movieId': range(13)})
    kept, stats = prepare.sample_users(ratings, n_users=10, min_ratings=5, seed=0)
    assert set(kept['userId']) == {1, 3}
    assert stats == {'pool_users': 3, 'eligible_users': 2, 'sampled_users': 2}
    one, _ = prepare.sample_users(ratings, n_users=1, min_ratings=5, seed=0)
    again, _ = prepare.sample_users(ratings, n_users=1, min_ratings=5, seed=0)
    assert one.equals(again)


def test_bayesian_average_shrinks_low_count_items_towards_prior():
    out = enrich.bayesian_average(np.array([5.0, 5.0]), np.array([2, 2000]), prior_mean=3.5, prior_count=100)
    assert out[0] < 3.6 < out[1] < 5.0


def test_mood_scores_average_mood_tags():
    tags = sorted({t for ts in moods.MOOD_TAGS.values() for t in ts})
    genome = np.zeros((2, len(tags)), np.float32)
    genome[0, [tags.index(t) for t in moods.MOOD_TAGS['Funny']]] = 1.0
    scores = moods.mood_scores(genome, tags)
    funny = list(moods.MOOD_TAGS).index('Funny')
    assert scores.shape == (2, len(moods.MOOD_TAGS))
    assert scores[0, funny] == 1.0 and scores[1, funny] == 0.0


def test_mood_scores_reject_unknown_tags():
    with pytest.raises(KeyError):
        moods.mood_scores(np.zeros((1, 1), np.float32), ['not-a-mood-tag'])


def test_assign_moods_is_thresholded_and_sorted_by_strength():
    scores = np.array([[0.2, 0.7, 0.9], [0.1, 0.1, 0.1]], np.float32)
    assert moods.assign_moods(scores, threshold=0.5) == [[(2, pytest.approx(0.9)), (1, pytest.approx(0.7))], []]
