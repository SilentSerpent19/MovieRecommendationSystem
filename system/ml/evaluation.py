"""Offline top-k evaluation on held-out future interactions."""
import numpy as np
import scipy.sparse as sp


def top_k(scores: np.ndarray, exclude: sp.csr_matrix, k: int) -> np.ndarray:
    """Indices of the k best items per row, never recommending excluded (already seen) items."""
    scores = scores.copy()
    rows, cols = exclude.nonzero()
    scores[rows, cols] = -np.inf
    part = np.argpartition(-scores, k, axis=1)[:, :k]
    order = np.argsort(-np.take_along_axis(scores, part, axis=1), axis=1, kind='stable')
    return np.take_along_axis(part, order, axis=1)


METRICS = ('precision', 'recall', 'ndcg', 'hit_rate', 'popularity_percentile')


def evaluate(model, train: sp.csr_matrix, seen: sp.csr_matrix, relevant: sp.csr_matrix,
             item_popularity: np.ndarray, k: int = 10, batch: int = 1000, per_user: bool = False) -> dict:
    """Precision/recall/NDCG/hit-rate@k over users with at least one relevant held-out item.

    train:    positives the model may use as the user's history
    seen:     every item the user interacted with before the held-out period (excluded from ranking)
    relevant: held-out positives
    Also reports catalog coverage and novelty (mean popularity percentile of recommended items).
    With per_user=True the per-user NDCG array is returned under '_ndcg' for significance testing.
    """
    users = np.flatnonzero(np.diff(relevant.indptr) > 0)
    discounts = 1.0 / np.log2(np.arange(2, k + 2))
    pop_pct = item_popularity.argsort().argsort() / max(len(item_popularity) - 1, 1)
    values = {m: np.zeros(len(users)) for m in METRICS}
    recommended = np.zeros(train.shape[1], bool)
    for start in range(0, len(users), batch):
        u = users[start:start + batch]
        recs = top_k(model.score(train[u]), seen[u], k)
        recommended[recs.ravel()] = True
        rel = relevant[u]
        for row, items in enumerate(recs):
            i = start + row
            truth = rel.indices[rel.indptr[row]:rel.indptr[row + 1]]
            hits = np.isin(items, truth)
            n_hits = hits.sum()
            values['precision'][i] = n_hits / k
            values['recall'][i] = n_hits / len(truth)
            values['ndcg'][i] = (discounts * hits).sum() / discounts[:min(len(truth), k)].sum()
            values['hit_rate'][i] = n_hits > 0
            values['popularity_percentile'][i] = pop_pct[items].mean()
    result = {f'{m}@{k}': round(float(v.mean()), 4) for m, v in values.items()}
    result['coverage'] = round(float(recommended.mean()), 4)
    result['users_evaluated'] = int(len(users))
    if per_user:
        result['_ndcg'] = values['ndcg']
    return result


def bootstrap_ci(values: np.ndarray, n_boot: int = 1000, seed: int = 0, level: float = 0.95) -> list[float]:
    """Percentile bootstrap confidence interval for the mean of per-user values (or paired differences)."""
    rng = np.random.default_rng(seed)
    means = np.array([values[rng.integers(0, len(values), len(values))].mean() for _ in range(n_boot)])
    tail = (1 - level) / 2
    return [round(float(np.quantile(means, tail)), 4), round(float(np.quantile(means, 1 - tail)), 4)]


def truncate_history(train: sp.csr_matrix, order: sp.csr_matrix, n: int) -> sp.csr_matrix:
    """Keep each user's n most recent positives (by the timestamps stored in `order`): a cold-start profile."""
    order = order.multiply(train).tocsr()
    rows, cols, data = [], [], []
    for u in range(order.shape[0]):
        lo, hi = order.indptr[u], order.indptr[u + 1]
        if hi == lo:
            continue
        idx = order.indices[lo:hi]
        newest = idx[np.argsort(-order.data[lo:hi], kind='stable')[:n]]
        rows.extend([u] * len(newest))
        cols.extend(newest)
        data.extend([1.0] * len(newest))
    return sp.csr_matrix((np.array(data, np.float32), (rows, cols)), shape=train.shape)
