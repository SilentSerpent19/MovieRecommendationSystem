"""Build the processed dataset from raw sources.

Outputs in `processed_dir`:
  catalog.csv         one row per catalog movie (row order = index used by all arrays below)
  genome.npy          float32 (n_movies x n_tags) Tag Genome relevance
  genome_tags.json    tag names for genome.npy columns
  mood_scores.npy     float32 (n_movies x n_moods), columns ordered as moods.MOOD_TAGS
  interactions.npz    user, movie (MovieLens ids), rating, timestamp for the sampled users
  manifest.json       config, source checksums, and a data-quality report
"""
import json
import logging
import time
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from . import enrich, movielens, moods, sources
from .config import DataConfig

log = logging.getLogger(__name__)


def select_catalog(counts: np.ndarray, genome_ids: np.ndarray, n_movies: int) -> np.ndarray:
    """Top-n movie ids by rating count among movies with genome scores; ties broken by id."""
    eligible = genome_ids[genome_ids < len(counts)]
    eligible = eligible[counts[eligible] > 0]
    order = np.lexsort((eligible, -counts[eligible]))
    return np.sort(eligible[order[:n_movies]])


def sample_users(ratings: pd.DataFrame, n_users: int, min_ratings: int, seed: int) -> tuple[pd.DataFrame, dict]:
    """Keep users with >= min_ratings rows, then draw n_users of them at random (seeded)."""
    per_user = ratings.groupby('userId').size()
    eligible = np.sort(per_user[per_user >= min_ratings].index.to_numpy())
    rng = np.random.default_rng(seed)
    chosen = np.sort(rng.choice(eligible, size=min(n_users, len(eligible)), replace=False))
    stats = {'pool_users': int(len(per_user)), 'eligible_users': int(len(eligible)), 'sampled_users': int(len(chosen))}
    return ratings[ratings['userId'].isin(chosen)].reset_index(drop=True), stats


def run(cfg: DataConfig) -> dict:
    t0 = time.time()
    out = cfg.processed_dir
    out.mkdir(parents=True, exist_ok=True)
    ml_zip = sources.ensure_downloaded(sources.MOVIELENS_25M, cfg.raw_dir)
    imdb_path = sources.ensure_downloaded(sources.IMDB_RATINGS, cfg.raw_dir)

    log.info('Reading movies and links')
    movies = movielens.read_movies(ml_zip).set_index('movieId')
    log.info('Scanning genome movie ids')
    genome_ids = movielens.genome_movie_ids(ml_zip, cfg.chunksize)
    log.info('Scanning ratings (single streaming pass)')
    pool = movielens.user_pool(cfg.max_user_id, cfg.user_pool_fraction, cfg.seed)
    scan = movielens.scan_ratings(ml_zip, pool, cfg.max_user_id, cfg.chunksize)

    catalog_ids = select_catalog(scan.movie_counts, genome_ids, cfg.n_movies)
    counts = scan.movie_counts[catalog_ids]
    means = scan.movie_sums[catalog_ids] / counts
    global_mean = float(scan.movie_sums.sum() / scan.total_ratings)
    prior_count = float(np.quantile(counts, cfg.prior_quantile))

    cat = movies.loc[catalog_ids].reset_index()
    cat['ml_rating_count'] = counts
    cat['ml_rating_mean'] = means.round(4)
    cat['weighted_rating'] = enrich.bayesian_average(means, counts, global_mean, prior_count).round(4)

    log.info('Reading genome for %d catalog movies', len(catalog_ids))
    genome, tags = movielens.read_genome(ml_zip, catalog_ids, cfg.chunksize)
    mood_matrix = moods.mood_scores(genome, tags)

    log.info('Joining IMDb ratings')
    imdb = enrich.read_imdb_ratings(imdb_path, set(cat['imdb_id']), cfg.chunksize)
    cat = cat.merge(imdb, on='imdb_id', how='left')
    if cfg.fetch_wikidata:
        log.info('Fetching directors/runtime from Wikidata (cached)')
        wd = enrich.fetch_wikidata(cat['imdb_id'].tolist(), cfg.raw_dir / 'wikidata_cache.json')
        cat = cat.merge(wd, on='imdb_id', how='left')
    else:
        cat['directors'], cat['runtime'] = '', pd.NA

    in_catalog = scan.pool_ratings[scan.pool_ratings['movieId'].isin(catalog_ids)]
    interactions, user_stats = sample_users(in_catalog, cfg.n_users, cfg.min_user_ratings, cfg.seed)

    cat['genres'] = cat['genres'].map('|'.join)
    cat.to_csv(out / 'catalog.csv', index=False)
    np.save(out / 'genome.npy', genome)
    (out / 'genome_tags.json').write_text(json.dumps(tags))
    np.save(out / 'mood_scores.npy', mood_matrix)
    np.savez_compressed(
        out / 'interactions.npz',
        user=interactions['userId'].to_numpy(), movie=interactions['movieId'].to_numpy(),
        rating=interactions['rating'].to_numpy(), timestamp=interactions['timestamp'].to_numpy(),
    )

    manifest = {
        'created_at': datetime.now(UTC).isoformat(timespec='seconds'),
        'config': cfg.as_dict(),
        'mood_version': moods.MOOD_VERSION,
        'sources': {s.filename: {'url': s.url, 'md5': sources.md5sum(cfg.raw_dir / s.filename), 'license': s.license}
                    for s in sources.SOURCES},
        'quality': quality_report(scan, genome_ids, cat, prior_count, global_mean, interactions, user_stats,
                                  mood_matrix),
        'runtime_seconds': round(time.time() - t0, 1),
    }
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    return manifest


def quality_report(scan, genome_ids, cat, prior_count, global_mean, inter, user_stats, mood_matrix) -> dict:
    n_users = inter['userId'].nunique()
    n_items = inter['movieId'].nunique()
    per_user = inter.groupby('userId').size()
    per_item = inter.groupby('movieId').size()
    return {
        'ratings_total': int(scan.total_ratings),
        'movies_with_ratings': int((scan.movie_counts > 0).sum()),
        'movies_with_genome': int(len(genome_ids)),
        'catalog_movies': int(len(cat)),
        'catalog_min_rating_count': int(cat['ml_rating_count'].min()),
        'catalog_share_of_all_ratings': round(float(cat['ml_rating_count'].sum() / scan.total_ratings), 4),
        'catalog_year_range': [int(cat['year'].min()), int(cat['year'].max())],
        'catalog_missing_year': int(cat['year'].isna().sum()),
        'catalog_missing_imdb_rating': int(cat['imdb_rating'].isna().sum()),
        'catalog_missing_directors': int((cat['directors'].fillna('') == '').sum()),
        'catalog_missing_runtime': int(cat['runtime'].isna().sum()),
        'bayesian_prior': {'global_mean': round(global_mean, 4), 'prior_count': prior_count},
        'users': user_stats,
        'interactions': int(len(inter)),
        'interaction_users': int(n_users),
        'interaction_items': int(n_items),
        'catalog_items_without_interactions': int(len(cat) - n_items),
        'density': round(len(inter) / (n_users * n_items), 5) if n_users and n_items else 0.0,
        'ratings_per_user_median': float(per_user.median()),
        'ratings_per_item_median': float(per_item.median()),
        'rating_distribution': {str(k): int(v) for k, v in inter['rating'].value_counts().sort_index().items()},
        'timestamp_range': [datetime.fromtimestamp(int(inter['timestamp'].min()), UTC).date().isoformat(),
                            datetime.fromtimestamp(int(inter['timestamp'].max()), UTC).date().isoformat()],
        'mood_score_quantiles': {
            name: [round(float(q), 3) for q in np.quantile(mood_matrix[:, j], [0.5, 0.9, 0.99])]
            for j, name in enumerate(moods.MOOD_TAGS)
        },
    }
