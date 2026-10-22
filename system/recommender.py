"""Serving layer: filters + the user's history -> a ranked, diversified, logged recommendation list.

Pipeline: candidates (filters, relaxed one at a time if too few match) -> exclude already-seen
-> score with the trained hybrid model -> MMR diversity re-rank -> explain -> log impressions.
"""
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from django.conf import settings

from .ml import artifacts
from .ml.models import mmr_rerank
from .models import Feedback, Impression, Movie, RecommendationRequest, Watchlist

log = logging.getLogger(__name__)

ERAS = {
    'pre-1970': (None, 1969),
    '1970s': (1970, 1979),
    '1980s': (1980, 1989),
    '1990s': (1990, 1999),
    '2000s': (2000, 2009),
    '2010s': (2010, 2019),
}
# Order in which filters are dropped when too few movies match: least to most important.
RELAX_ORDER = ('mood', 'min_rating', 'era', 'genre')
CANDIDATE_POOL = 200  # top-scored candidates handed to the diversity re-ranker
DIVERSITY = 0.3  # used only for model artifacts that predate the diversity sweep


@dataclass(frozen=True)
class Filters:
    genre: str = ''
    era: str = ''
    min_rating: float | None = None
    mood: str = ''

    def active(self) -> list[str]:
        return [f for f in RELAX_ORDER if getattr(self, f) not in ('', None)]

    def as_dict(self) -> dict:
        return {f: getattr(self, f) for f in self.active()}


@dataclass
class Recommendation:
    movie: Movie
    score: float
    reason: str


@dataclass
class Result:
    items: list[Recommendation]
    relaxed: list[str] = field(default_factory=list)
    strategy: str = ''
    model_version: str = ''
    request_id: str = ''


@dataclass
class LoadedModel:
    model: object
    index_of: dict  # movielens_id -> item index
    item_ids: np.ndarray
    version: str
    diversity: float  # MMR trade-off selected offline (reports/evaluation.md)


def load_model() -> LoadedModel | None:
    """The model named in MODEL_DIR/LATEST. Re-checked per call, so retraining needs no server restart."""
    version = artifacts.latest_version(settings.MODEL_DIR)
    if version is None:
        log.warning('No trained model in %s; falling back to weighted rating.', settings.MODEL_DIR)
        return None
    return _load_version(str(settings.MODEL_DIR), version)


@lru_cache(maxsize=2)
def _load_version(model_dir: str, version: str) -> LoadedModel:
    model, item_ids, meta = artifacts.load(Path(model_dir), version)
    return LoadedModel(model, {int(m): i for i, m in enumerate(item_ids)}, item_ids, version,
                       meta['params'].get('diversity', DIVERSITY))


def candidate_queryset(filters: Filters, dropped: set[str]):
    qs = Movie.objects.all()
    if filters.genre and 'genre' not in dropped:
        qs = qs.filter(genres__name=filters.genre)
    if filters.era in ERAS and 'era' not in dropped:
        lo, hi = ERAS[filters.era]
        qs = qs.filter(year__lte=hi) if lo is None else qs.filter(year__gte=lo, year__lte=hi)
    if filters.min_rating is not None and 'min_rating' not in dropped:
        qs = qs.filter(imdb_rating__gte=filters.min_rating)
    if filters.mood and 'mood' not in dropped:
        qs = qs.filter(moods__name=filters.mood)
    return qs


def user_history(user) -> tuple[list[int], set[int]]:
    """(liked movie pks, pks to exclude). Liked = watchlist + likes; excluded also includes dislikes."""
    if not user.is_authenticated:
        return [], set()
    watch = set(Watchlist.objects.filter(user=user).values_list('movie_id', flat=True))
    fb = dict(Feedback.objects.filter(user=user).values_list('movie_id', 'value'))
    liked = watch | {m for m, v in fb.items() if v == Feedback.LIKE}
    return sorted(liked), liked | set(fb)


def recommend(user, filters: Filters, k: int = 10, session_key: str = '', log_request: bool = True) -> Result:
    liked, exclude = user_history(user)
    relaxed: list[str] = []
    to_relax = filters.active()
    while True:
        rows = list(candidate_queryset(filters, set(relaxed)).exclude(pk__in=exclude)
                    .values_list('pk', 'movielens_id').distinct())
        if len(rows) >= k or not to_relax:
            break
        relaxed.append(to_relax.pop(0))

    loaded = load_model()
    result = _rank_with_model(loaded, rows, liked, k) if loaded and rows else None
    if result is None or not result.items:  # no model, or no candidate known to the model
        result = _rank_by_weighted_rating([pk for pk, _ in rows], k)
    result.relaxed = relaxed
    if log_request and result.items:
        _log(result, user, session_key, filters, len(liked))
    return result


def _rank_by_weighted_rating(pks: list[int], k: int) -> Result:
    movies = Movie.objects.filter(pk__in=pks).prefetch_related('genres', 'moods').order_by('-weighted_rating')[:k]
    items = [Recommendation(m, m.weighted_rating, 'Highly rated by MovieLens users') for m in movies]
    return Result(items, strategy='weighted_rating')


def _rank_with_model(loaded: LoadedModel, rows: list[tuple[int, int]], liked: list[int], k: int) -> Result:
    pk_of = {loaded.index_of[ml]: pk for pk, ml in rows if ml in loaded.index_of}
    if not pk_of:
        return Result([])
    candidates = np.fromiter(pk_of, dtype=np.int64)
    liked_ml = dict(Movie.objects.filter(pk__in=liked).values_list('movielens_id', 'title'))
    history = [loaded.index_of[m] for m in liked_ml if m in loaded.index_of]
    X = sp.csr_matrix((np.ones(len(history), np.float32), ([0] * len(history), history)),
                      shape=(1, len(loaded.item_ids)))
    scores = loaded.model.score(X)[0]
    pool = candidates[np.argsort(-scores[candidates], kind='stable')[:CANDIDATE_POOL]]
    embeddings = loaded.model.content.embeddings
    chosen = mmr_rerank(pool, scores[pool], embeddings, k, loaded.diversity)

    reasons = _explain(chosen, history, embeddings, [liked_ml[int(loaded.item_ids[h])] for h in history])
    movies = Movie.objects.prefetch_related('genres', 'moods').in_bulk([pk_of[i] for i in chosen])
    items = [Recommendation(movies[pk_of[i]], float(scores[i]), r) for i, r in zip(chosen, reasons, strict=True)]
    return Result(items, strategy='hybrid' if history else 'popularity', model_version=loaded.version)


def _explain(chosen: np.ndarray, history: list[int], embeddings: np.ndarray, history_titles: list[str]) -> list[str]:
    if not history:
        return ['Popular with MovieLens users'] * len(chosen)
    sims = embeddings[chosen] @ embeddings[history].T
    return [f'Because you liked {history_titles[j]}' for j in sims.argmax(axis=1)]


def _log(result: Result, user, session_key: str, filters: Filters, history_size: int) -> None:
    req = RecommendationRequest.objects.create(
        user=user if user.is_authenticated else None, session_key=session_key or '',
        filters=filters.as_dict(), relaxed=result.relaxed, strategy=result.strategy,
        model_version=result.model_version, history_size=history_size,
    )
    Impression.objects.bulk_create([
        Impression(request=req, movie=r.movie, rank=i, score=r.score) for i, r in enumerate(result.items, 1)
    ])
    result.request_id = str(req.id)
