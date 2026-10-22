from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class DataConfig:
    """Every knob that shapes the processed dataset. Stored in the manifest for reproducibility."""

    raw_dir: Path
    processed_dir: Path
    # Catalog: the N most-rated MovieLens movies that also have Tag Genome scores.
    n_movies: int = 5000
    # Users: seeded random pool, then keep users with enough ratings inside the catalog,
    # then subsample to n_users. Keeps the interaction matrix small (~1M rows).
    user_pool_fraction: float = 0.125
    n_users: int = 10_000
    min_user_ratings: int = 20
    # Upper bound on MovieLens user ids (162,541 in ml-25m), used to draw a reproducible user pool.
    max_user_id: int = 200_000
    seed: int = 42
    chunksize: int = 2_000_000
    # Bayesian average prior strength = this quantile of catalog vote counts.
    prior_quantile: float = 0.5
    fetch_wikidata: bool = True
    extra: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        d = asdict(self)
        d['raw_dir'] = str(self.raw_dir)
        d['processed_dir'] = str(self.processed_dir)
        return d
