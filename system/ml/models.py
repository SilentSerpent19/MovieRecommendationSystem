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
        self.rng = np.random.default_rng(self.seed)  # one stream, so batches get independent draws
        return self

    def score(self, X_users: sp.csr_matrix) -> np.ndarray:
        return self.rng.random((X_users.shape[0], self.n_items), dtype=np.float32)


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


class ALSModel:
    """Implicit-feedback matrix factorisation (Hu, Koren & Volinsky 2008) fitted by alternating least squares.

    Each observed positive gets confidence 1 + alpha and every unobserved pair confidence 1 (preference 0).
    Only item factors are kept: users are folded in from their history at scoring time (one exact
    least-squares solve each), so cold-start and app users need no retraining. Memory is
    O((n_users + n_items) x factors) plus one chunk of factors x factors systems.
    """

    name = 'als'

    def __init__(self, factors: int = 64, reg: float = 1.0, alpha: float = 20.0, iterations: int = 10,
                 seed: int = 0, chunk: int = 2000):
        self.factors, self.reg, self.alpha = factors, reg, alpha
        self.iterations, self.seed, self.chunk = iterations, seed, chunk

    def fit(self, X: sp.csr_matrix, genome: np.ndarray):
        X = sp.csr_matrix(X, dtype=np.float32)
        XT = X.T.tocsr()
        rng = np.random.default_rng(self.seed)
        items = rng.normal(0, 0.01, (X.shape[1], self.factors)).astype(np.float32)
        for _ in range(self.iterations):
            users = self._solve(X, items)
            items = self._solve(XT, users)
        self.item_factors = items
        return self

    def _solve(self, R: sp.csr_matrix, F: np.ndarray) -> np.ndarray:
        """Row-wise argmin_x sum_j c_rj (p_rj - x.F_j)^2 + reg |x|^2 for a binary CSR matrix R.

        Uses the identity sum_j c_rj F_j F_j^T = F^T F + alpha * sum_{j in row} F_j F_j^T, so only each row's
        non-zeros are touched. Rows with no positives get the zero vector (their exact solution).
        """
        F64 = F.astype(np.float64)
        base = F64.T @ F64 + self.reg * np.eye(self.factors)
        out = np.zeros((R.shape[0], self.factors), np.float32)
        rows = np.flatnonzero(np.diff(R.indptr))
        for chunk in np.array_split(rows, len(rows) // self.chunk + 1):
            A = np.empty((len(chunk), self.factors, self.factors))
            b = np.empty((len(chunk), self.factors))
            for i, r in enumerate(chunk):
                Fj = F64[R.indices[R.indptr[r]:R.indptr[r + 1]]]
                A[i] = base + self.alpha * (Fj.T @ Fj)
                b[i] = (1 + self.alpha) * Fj.sum(axis=0)
            if len(chunk):
                out[chunk] = np.linalg.solve(A, b[..., None])[..., 0]
        return out

    def score(self, X_users: sp.csr_matrix) -> np.ndarray:
        users = self._solve(sp.csr_matrix(X_users, dtype=np.float32), self.item_factors)
        return users @ self.item_factors.T


def _minmax_rows(s: np.ndarray) -> np.ndarray:
    lo = s.min(axis=1, keepdims=True)
    span = s.max(axis=1, keepdims=True) - lo
    return np.divide(s - lo, span, out=np.zeros_like(s), where=span > 0)


class HybridModel:
    """Blend of a collaborative model (ALS or item-kNN), content similarity and popularity.

    The collaborative weight grows with history size, n / (n + history_prior): users with a long
    history lean on collaborative filtering, users with one or two liked movies lean on content similarity.
    """

    name = 'hybrid'

    def __init__(self, cf: 'ALSModel | ItemKNNModel', content: ContentModel, popularity: PopularityModel,
                 history_prior: float = 10.0, popularity_weight: float = 0.1):
        self.cf, self.content, self.popularity = cf, content, popularity
        self.history_prior = history_prior
        self.popularity_weight = popularity_weight

    def fit(self, X: sp.csr_matrix, genome: np.ndarray):
        for m in (self.cf, self.content, self.popularity):
            m.fit(X, genome)
        return self

    def score(self, X_users: sp.csr_matrix) -> np.ndarray:
        n = np.asarray(X_users.sum(axis=1), dtype=np.float32)
        alpha = n / (n + self.history_prior)
        personal = alpha * _minmax_rows(self.cf.score(X_users)) + (1 - alpha) * _minmax_rows(
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
