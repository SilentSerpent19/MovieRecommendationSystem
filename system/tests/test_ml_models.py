import numpy as np
import pytest
import scipy.sparse as sp

from system.ml import artifacts
from system.ml.data import interaction_matrix, temporal_split
from system.ml.evaluation import evaluate, top_k
from system.ml.models import ContentModel, HybridModel, ItemKNNModel, PopularityModel, mmr_rerank


@pytest.fixture
def X():
    rng = np.random.default_rng(0)
    dense = (rng.random((40, 12)) < 0.3).astype(np.float32)
    return sp.csr_matrix(dense)


@pytest.fixture
def genome():
    return np.random.default_rng(1).random((12, 20)).astype(np.float32)


def test_temporal_split_holds_out_each_users_latest_interactions():
    users = np.array([0] * 10 + [1] * 5)
    ts = np.array([9, 8, 7, 6, 5, 4, 3, 2, 1, 0, 10, 20, 30, 40, 50])
    fold = temporal_split(users, ts, val_frac=0.1, test_frac=0.2)
    assert fold[:10].tolist() == [2, 2, 1, 0, 0, 0, 0, 0, 0, 0]  # user 0's two newest are test
    assert fold[10:].tolist() == [0, 0, 0, 1, 2]
    for u in (0, 1):
        m = users == u
        assert ts[m][fold[m] == 0].max() < ts[m][fold[m] == 2].min()


def test_interaction_matrix_is_binary():
    m = interaction_matrix(np.array([0, 0, 1]), np.array([2, 2, 0]), 2, 3)
    assert m.toarray().tolist() == [[0, 0, 1], [1, 0, 0]]


def test_blockwise_knn_matches_bruteforce(X, genome):
    model = ItemKNNModel(k=4, shrink=5.0, block=5).fit(X, genome)
    dense = X.toarray()
    co = dense.T @ dense
    n = np.sqrt(dense.sum(0))
    sim = co / (np.outer(n, n) + 5.0 + 1e-9)
    np.fill_diagonal(sim, 0)
    S = model.similarity.toarray()
    for i in range(X.shape[1]):
        expected = np.sort(sim[i])[-4:]
        np.testing.assert_allclose(np.sort(S[i][S[i] > 0]), expected[expected > 0], rtol=1e-5)
    assert model.similarity.nnz <= 4 * X.shape[1]


def test_top_k_never_returns_seen_items():
    scores = np.array([[0.9, 0.8, 0.7, 0.1]], np.float32)
    seen = sp.csr_matrix([[1, 0, 1, 0]])
    assert top_k(scores, seen, 2).tolist() == [[1, 3]]


class _Oracle:
    """Scores the held-out items highest: every metric should be perfect."""

    def __init__(self, relevant):
        self.relevant = relevant

    def score(self, X_users):
        return self.relevant[: X_users.shape[0]].toarray().astype(np.float32)


def test_evaluate_perfect_ranking_scores_one():
    relevant = sp.csr_matrix(np.eye(3, 20, k=5))
    empty = sp.csr_matrix((3, 20))
    r = evaluate(_Oracle(relevant), empty, empty, relevant, np.arange(20.0), k=5)
    assert r['recall@5'] == 1.0 and r['ndcg@5'] == 1.0 and r['hit_rate@5'] == 1.0
    assert r['precision@5'] == 0.2
    assert r['users_evaluated'] == 3


def test_hybrid_without_history_falls_back_to_popularity(X, genome):
    hybrid = HybridModel(ItemKNNModel(k=4), ContentModel(n_components=4), PopularityModel()).fit(X, genome)
    scores = hybrid.score(sp.csr_matrix((1, X.shape[1])))
    assert np.argmax(scores[0]) == np.argmax(np.asarray(X.sum(0)).ravel())


def test_content_model_prefers_items_similar_to_history(genome):
    model = ContentModel(n_components=8).fit(sp.csr_matrix((1, 12)), genome)
    history = sp.csr_matrix(([1.0], ([0], [3])), shape=(1, 12))
    assert np.argmax(model.score(history)[0]) == 3


def test_mmr_without_diversity_is_plain_ranking():
    embeddings = np.eye(14, dtype=np.float32)
    out = mmr_rerank(np.array([10, 11, 12, 13]), np.array([0.1, 0.9, 0.5, 0.7]), embeddings, 3, 0.0)
    assert out.tolist() == [11, 13, 12]


def test_mmr_skips_near_duplicates():
    emb = np.array([[1, 0], [1, 0], [0, 1]], np.float32)
    out = mmr_rerank(np.array([0, 1, 2]), np.array([1.0, 0.99, 0.5]), emb, 2, diversity=0.5)
    assert out.tolist() == [0, 2]


def test_artifacts_round_trip_preserves_scores(tmp_path, X, genome):
    model = HybridModel(ItemKNNModel(k=4), ContentModel(n_components=4), PopularityModel(),
                        history_prior=3.0, popularity_weight=0.2).fit(X, genome)
    item_ids = np.arange(100, 112)
    artifacts.save(model, item_ids, tmp_path, 'v1', {'note': 'test'})
    assert artifacts.latest_version(tmp_path) == 'v1'
    loaded, ids, meta = artifacts.load(tmp_path, 'v1')
    np.testing.assert_array_equal(ids, item_ids)
    np.testing.assert_allclose(loaded.score(X[:5]), model.score(X[:5]), rtol=1e-6)
    assert meta['params']['history_prior'] == 3.0


def test_truncate_history_keeps_most_recent_positives():
    from system.ml.evaluation import truncate_history
    train = sp.csr_matrix(np.array([[1, 1, 1, 0], [0, 1, 0, 0]], np.float32))
    order = sp.csr_matrix(np.array([[5, 9, 7, 0], [0, 3, 0, 0]], np.float64))
    out = truncate_history(train, order, 2).toarray()
    assert out.tolist() == [[0, 1, 1, 0], [0, 1, 0, 0]]


def test_bootstrap_ci_brackets_the_mean():
    from system.ml.evaluation import bootstrap_ci
    values = np.random.default_rng(0).normal(0.3, 0.1, 2000)
    lo, hi = bootstrap_ci(values)
    assert lo < values.mean() < hi and hi - lo < 0.02


def test_temporal_split_never_puts_same_timestamp_in_two_folds():
    users = np.zeros(10, int)
    ts = np.array([1, 2, 3, 4, 5, 6, 7, 8, 8, 8])  # three ratings in the same second at the end
    fold = temporal_split(users, ts, val_frac=0.1, test_frac=0.2)
    assert fold[ts == 8].tolist() == [2, 2, 2]
    for t in np.unique(ts):
        assert len(set(fold[ts == t])) == 1


def test_random_model_gives_different_rows_across_batches():
    from system.ml.models import RandomModel
    m = RandomModel(seed=0).fit(sp.csr_matrix((4, 50)), None)
    assert not np.array_equal(m.score(sp.csr_matrix((1, 50))), m.score(sp.csr_matrix((1, 50))))


def test_intra_list_diversity_bounds():
    from system.ml.evaluation import intra_list_diversity
    same = np.tile(np.array([[1.0, 0.0]], np.float32), (3, 1))
    orthogonal = np.eye(3, dtype=np.float32)
    assert intra_list_diversity(same) == pytest.approx(0.0)
    assert intra_list_diversity(orthogonal) == pytest.approx(1.0)


def test_evaluate_with_diversity_increases_ild(X, genome):
    content = ContentModel(n_components=4).fit(X, genome)
    model = PopularityModel().fit(X, genome)
    relevant = sp.csr_matrix(np.ones((5, 12), np.float32))
    empty = sp.csr_matrix((5, 12))
    plain = evaluate(model, X[:5], empty, relevant, np.arange(12.0), k=3, embeddings=content.embeddings)
    diverse = evaluate(model, X[:5], empty, relevant, np.arange(12.0), k=3, embeddings=content.embeddings,
                       diversity=0.9, pool=12)
    assert diverse['ild@3'] >= plain['ild@3']


def test_als_solve_matches_dense_normal_equations():
    from system.ml.models import ALSModel
    rng = np.random.default_rng(3)
    F = rng.normal(size=(15, 4)).astype(np.float32)
    R = sp.csr_matrix((rng.random((3, 15)) < 0.4).astype(np.float32))
    model = ALSModel(factors=4, reg=0.5, alpha=10.0)
    got = model._solve(R, F)
    F64 = F.astype(np.float64)
    for u in range(3):
        p = R[u].toarray().ravel()
        C = np.diag(1 + 10.0 * p)  # full confidence matrix, written out explicitly
        expected = np.linalg.solve(F64.T @ C @ F64 + 0.5 * np.eye(4), F64.T @ C @ p)
        np.testing.assert_allclose(got[u], expected, rtol=1e-4, atol=1e-6)


def test_als_learns_block_structure_and_handles_empty_history():
    from system.ml.models import ALSModel
    dense = np.zeros((40, 10), np.float32)
    dense[:20, :5] = (np.random.default_rng(0).random((20, 5)) < 0.7)
    dense[20:, 5:] = (np.random.default_rng(1).random((20, 5)) < 0.7)
    model = ALSModel(factors=2, reg=0.1, alpha=10.0, iterations=10).fit(sp.csr_matrix(dense), None)
    scores = model.score(sp.csr_matrix(np.array([[1, 1, 0, 0, 0, 0, 0, 0, 0, 0]], np.float32)))[0]
    assert scores[2:5].mean() > scores[5:].mean()  # unseen items from the user's block score higher
    assert 2 <= np.argmax(scores[2:]) + 2 <= 4
    assert not model.score(sp.csr_matrix((1, 10))).any()
