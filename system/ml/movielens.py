"""Streaming readers for the MovieLens 25M zip. Nothing here loads a full file into memory."""
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

PREFIX = 'ml-25m/'
RATING_DTYPES = {'userId': np.int32, 'movieId': np.int32, 'rating': np.float32, 'timestamp': np.int64}
YEAR_RE = re.compile(r'\s*\((\d{4})\)\s*$')


@dataclass
class RatingScan:
    """Result of one pass over ratings.csv."""

    movie_counts: np.ndarray  # index = movieId
    movie_sums: np.ndarray
    total_ratings: int
    pool_ratings: pd.DataFrame  # every rating made by a user in the sampled pool


def _accumulate(acc: np.ndarray, add: np.ndarray) -> np.ndarray:
    if len(add) > len(acc):
        acc = np.pad(acc, (0, len(add) - len(acc)))
    acc[: len(add)] += add
    return acc


def user_pool(max_user_id: int, fraction: float, seed: int) -> np.ndarray:
    """Reproducible random subset of user ids, drawn without knowing which ids exist."""
    keys = np.random.default_rng(seed).random(max_user_id + 1)
    return np.flatnonzero(keys < fraction).astype(np.int32)


def scan_ratings(zip_path: Path, pool: np.ndarray, max_user_id: int, chunksize: int) -> RatingScan:
    """Single chunked pass: per-movie rating counts/sums over ALL users, plus the raw rows of `pool` users."""
    counts = np.zeros(0, np.int64)
    sums = np.zeros(0, np.float64)
    total = 0
    parts = []
    with zipfile.ZipFile(zip_path) as zf, zf.open(PREFIX + 'ratings.csv') as f:
        for chunk in pd.read_csv(f, dtype=RATING_DTYPES, chunksize=chunksize):
            movies = chunk['movieId'].to_numpy()
            counts = _accumulate(counts, np.bincount(movies))
            sums = _accumulate(sums, np.bincount(movies, weights=chunk['rating'].to_numpy()))
            total += len(chunk)
            users = chunk['userId'].to_numpy()
            if users.max() > max_user_id:
                raise ValueError(f'user id {users.max()} exceeds max_user_id={max_user_id}')
            parts.append(chunk[np.isin(users, pool)])
    return RatingScan(counts, sums, total, pd.concat(parts, ignore_index=True))


def genome_movie_ids(zip_path: Path, chunksize: int) -> np.ndarray:
    """Movie ids that have Tag Genome scores (reads only the movieId column)."""
    ids = set()
    with zipfile.ZipFile(zip_path) as zf, zf.open(PREFIX + 'genome-scores.csv') as f:
        for chunk in pd.read_csv(f, usecols=['movieId'], dtype=np.int32, chunksize=chunksize):
            ids.update(np.unique(chunk['movieId'].to_numpy()).tolist())
    return np.array(sorted(ids), dtype=np.int32)


def read_genome(zip_path: Path, movie_ids: np.ndarray, chunksize: int) -> tuple[np.ndarray, list[str]]:
    """Dense (len(movie_ids) x n_tags) float32 relevance matrix for the given movies only."""
    with zipfile.ZipFile(zip_path) as zf:
        tags = pd.read_csv(zf.open(PREFIX + 'genome-tags.csv')).sort_values('tagId')
        tag_index = {tid: i for i, tid in enumerate(tags['tagId'])}
        row_of = {int(m): i for i, m in enumerate(movie_ids)}
        out = np.full((len(movie_ids), len(tags)), np.nan, dtype=np.float32)
        dtypes = {'movieId': np.int32, 'tagId': np.int32, 'relevance': np.float32}
        with zf.open(PREFIX + 'genome-scores.csv') as f:
            for chunk in pd.read_csv(f, dtype=dtypes, chunksize=chunksize):
                chunk = chunk[chunk['movieId'].isin(row_of)]
                rows = chunk['movieId'].map(row_of).to_numpy()
                cols = chunk['tagId'].map(tag_index).to_numpy()
                out[rows, cols] = chunk['relevance'].to_numpy()
    if np.isnan(out).any():
        raise ValueError('incomplete genome rows for some catalog movies')
    return out, tags['tag'].tolist()


def read_movies(zip_path: Path) -> pd.DataFrame:
    """movies.csv joined with links.csv; title split into clean title + year; genres as a list."""
    with zipfile.ZipFile(zip_path) as zf:
        movies = pd.read_csv(zf.open(PREFIX + 'movies.csv'))
        links = pd.read_csv(zf.open(PREFIX + 'links.csv'), dtype={'imdbId': str})
    df = movies.merge(links, on='movieId', how='left')
    years = df['title'].str.extract(YEAR_RE)[0]
    df['year'] = pd.to_numeric(years, errors='coerce').astype('Int16')
    df['title'] = df['title'].str.replace(YEAR_RE, '', regex=True).str.strip()
    df['title'] = df['title'].map(_unflip_article)
    df['genres'] = df['genres'].map(lambda g: [] if g == '(no genres listed)' else g.split('|'))
    df['imdb_id'] = 'tt' + df['imdbId'].str.zfill(7)
    df['tmdb_id'] = df['tmdbId'].astype('Int64')
    return df[['movieId', 'title', 'year', 'genres', 'imdb_id', 'tmdb_id']]


_ARTICLE_RE = re.compile(r'^(.*), (The|A|An)$')


def _unflip_article(title: str) -> str:
    """'Matrix, The' -> 'The Matrix' (MovieLens stores titles with a trailing article)."""
    m = _ARTICLE_RE.match(title)
    return f'{m.group(2)} {m.group(1)}' if m else title
