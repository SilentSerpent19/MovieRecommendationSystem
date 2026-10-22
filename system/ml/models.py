"""Recommendation models sharing one interface.

fit(X, genome) learns from a binary users x items CSR matrix of positives (+ item side information).
score(X_users) returns a dense (batch x n_items) float32 array; higher = better. The same call serves
offline evaluation (thousands of MovieLens users per batch) and the web app (one user's history).
"""
import numpy as np
import scipy.sparse as sp
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import StandardScaler, normalize


class RandomModel:
    name = 'random'

    def __init__(self, seed: int = 0):
        self.seed = seed

    def fit(self, X: sp.csr_matrix, genome: np.ndarray):
        self.n_items = X.shape[1]
        return self

    def score(self, X_users: sp.csr_matrix) -> np.ndarray:
        rng = np.random.default_rng(self.seed)
        return rng.random((X_users.shape[0], self.n_items), dtype=np.float32)


class PopularityModel:
    """Number of users who liked each item. Non-personalised baseline and cold-start fallback."""

    name = 'popularity'

    def fit(self, X: sp.csr_matrix, genome: np.ndarray):
        self.popularity = np.asarray(X.sum(axis=0)).ravel().astype(np.float32)
        return self

    def score(self, X_users: sp.csr_matrix) -> np.ndarray:
        return np.broadcast_to(self.popularity, (X_users.shape[0], len(self.popularity))).copy()


class ContentModel:
    """Tag Genome embeddings (standardised, reduced with TruncatedSVD). User profile = sum of liked items."""

    name = 'content'

    def __init__(self, n_components: int = 64, seed: int = 0):
        self.n_components = n_components
        self.seed = seed

    def fit(self, X: sp.csr_matrix, genome: np.ndarray):
        z = StandardScaler().fit_transform(genome)
        svd = TruncatedSVD(n_components=self.n_components, random_state=self.seed)
        self.embeddings = normalize(svd.fit_transform(z)).astype(np.float32)
        self.explained_variance = float(svd.explained_variance_ratio_.sum())
        return self

    def score(self, X_users: sp.csr_matrix) -> np.ndarray:
        profiles = normalize(np.asarray(X_users @ self.embeddings))
        return (profiles @ self.embeddings.T).astype(np.float32)


class ItemKNNModel:
    """Item-based collaborative filtering with shrunk cosine similarity, top-k neighbours kept sparse.

    Similarities are computed `block` items at a time, so peak memory is O(block x n_items)
    instead of the O(n_items^2) of a dense similarity matrix.
    """

    name = 'item_knn'

    def __init__(self, k: int = 50, shrink: float = 10.0, block: int = 500):
        self.k, self.shrink, self.block = k, shrink, block

    def fit(self, X: sp.csr_matrix, genome: np.ndarray):
        X = sp.csc_matrix(X, dtype=np.float32)
        n_items = X.shape[1]
        norms = np.sqrt(np.asarray(X.sum(axis=0)).ravel())
        XT = X.T.tocsr()
        rows, cols, vals = [], [], []
        for start in range(0, n_items, self.block):
            stop = min(start + self.block, n_items)
            co = (XT[start:stop] @ X).toarray()
            sim = co / (np.outer(norms[start:stop], norms) + self.shrink + 1e-9)
            sim[np.arange(stop - start), np.arange(start, stop)] = 0.0
            k = min(self.k, n_items - 1)
            top = np.argpartition(-sim, k, axis=1)[:, :k]
            top_vals = np.take_along_axis(sim, top, axis=1)
            keep = top_vals > 0
            rows.append(np.repeat(np.arange(start, stop), k)[keep.ravel()])
            cols.append(top.ravel()[keep.ravel()])
            vals.append(top_vals.ravel()[keep.ravel()])
        self.similarity = sp.csr_matrix(
            (np.concatenate(vals).astype(np.float32), (np.concatenate(rows), np.concatenate(cols))),
            shape=(n_items, n_items),
        )
        return self

    def score(self, X_users: sp.csr_matrix) -> np.ndarray:
        return np.asarray((X_users @ self.similarity).todense(), dtype=np.float32)


def _minmax_rows(s: np.ndarray) -> np.ndarray:
    lo = s.min(axis=1, keepdims=True)
    span = s.max(axis=1, keepdims=True) - lo
    return np.divide(s - lo, span, out=np.zeros_like(s), where=span > 0)


class HybridModel:
    """Blend of item-kNN, content and popularity.

    The collaborative weight grows with history size, n / (n + history_prior): users with a long
    history lean on item-kNN, users with one or two liked movies lean on content similarity.
    """

    name = 'hybrid'

    def __init__(self, knn: ItemKNNModel, content: ContentModel, popularity: PopularityModel,
                 history_prior: float = 10.0, popularity_weight: float = 0.1):
        self.knn, self.content, self.popularity = knn, content, popularity
        self.history_prior = history_prior
        self.popularity_weight = popularity_weight

    def fit(self, X: sp.csr_matrix, genome: np.ndarray):
        for m in (self.knn, self.content, self.popularity):
            m.fit(X, genome)
        return self

    def score(self, X_users: sp.csr_matrix) -> np.ndarray:
        n = np.asarray(X_users.sum(axis=1), dtype=np.float32)
        alpha = n / (n + self.history_prior)
        personal = alpha * _minmax_rows(self.knn.score(X_users)) + (1 - alpha) * _minmax_rows(
            self.content.score(X_users))
        pop = _minmax_rows(self.popularity.score(X_users))
        blended = (1 - self.popularity_weight) * personal + self.popularity_weight * pop
        # No history at all: fall back to popularity alone.
        return np.where(n > 0, blended, pop).astype(np.float32)


def mmr_rerank(candidates: np.ndarray, scores: np.ndarray, embeddings: np.ndarray, k: int,
               diversity: float) -> np.ndarray:
    """Maximal Marginal Relevance: trade relevance against similarity to items already picked."""
    if len(candidates) <= 1 or diversity <= 0:
        return candidates[np.argsort(-scores, kind='stable')[:k]]
    rel = _minmax_rows(scores[None, :])[0]
    emb = embeddings[candidates]
    chosen = [int(np.argmax(rel))]
    max_sim = emb @ emb[chosen[0]]
    while len(chosen) < min(k, len(candidates)):
        mmr = (1 - diversity) * rel - diversity * max_sim
        mmr[chosen] = -np.inf
        nxt = int(np.argmax(mmr))
        chosen.append(nxt)
        max_sim = np.maximum(max_sim, emb @ emb[nxt])
    return candidates[chosen]
