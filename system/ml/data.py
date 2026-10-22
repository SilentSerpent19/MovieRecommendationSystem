"""Load the processed dataset as index-aligned arrays and build sparse interaction matrices."""
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

# Ratings at or above this are treated as positive implicit feedback ("liked").
POSITIVE_THRESHOLD = 4.0


@dataclass
class Dataset:
    item_ids: np.ndarray  # MovieLens movieId per item index (catalog order)
    genome: np.ndarray  # (n_items x n_tags) side information
    users: np.ndarray  # per interaction: user index
    items: np.ndarray  # per interaction: item index
    ratings: np.ndarray
    timestamps: np.ndarray
    n_users: int
    manifest: dict

    @property
    def n_items(self) -> int:
        return len(self.item_ids)


def load_dataset(processed_dir: Path) -> Dataset:
    item_ids = pd.read_csv(processed_dir / 'catalog.csv', usecols=['movieId'])['movieId'].to_numpy()
    z = np.load(processed_dir / 'interactions.npz')
    items = pd.Index(item_ids).get_indexer(z['movie'])
    if (items < 0).any():
        raise ValueError('interactions reference movies outside the catalog')
    users, _ = pd.factorize(z['user'], sort=True)
    manifest_path = processed_dir / 'manifest.json'
    return Dataset(
        item_ids=item_ids,
        genome=np.load(processed_dir / 'genome.npy'),
        users=users.astype(np.int32),
        items=items.astype(np.int32),
        ratings=z['rating'],
        timestamps=z['timestamp'],
        n_users=int(users.max()) + 1,
        manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {},
    )


def interaction_matrix(users, items, n_users: int, n_items: int) -> sp.csr_matrix:
    """Binary users x items CSR matrix (duplicates collapse to 1)."""
    m = sp.csr_matrix((np.ones(len(users), np.float32), (users, items)), shape=(n_users, n_items))
    m.data[:] = 1.0
    return m


def temporal_split(users: np.ndarray, timestamps: np.ndarray, val_frac: float, test_frac: float) -> np.ndarray:
    """Per-user chronological split. Returns 0 (train), 1 (validation) or 2 (test) per interaction.

    Each user's most recent `test_frac` of interactions is test and the `val_frac` before that is
    validation, so every model is evaluated on predicting a user's *future* from their past. Interactions
    sharing the boundary timestamp all go to the later fold, so folds are strictly ordered in time.
    """
    df = pd.DataFrame({'u': users, 't': timestamps, 'i': np.arange(len(users))})
    df = df.sort_values(['u', 't', 'i'], kind='stable')
    pos = df.groupby('u').cumcount().to_numpy()
    n = df.groupby('u')['u'].transform('size').to_numpy()
    n_test = np.ceil(n * test_frac).astype(int)
    n_val = np.ceil(n * val_frac).astype(int)
    # Cut at the timestamp found at the boundary position, so interactions made in the same second never
    # straddle two folds (all ties go to the later fold).
    t = df['t'].to_numpy()
    start = np.flatnonzero(pos == 0).repeat(np.bincount(np.cumsum(pos == 0) - 1))
    test_cut = t[start + np.maximum(n - n_test, 0)]
    val_cut = t[start + np.maximum(n - n_test - n_val, 0)]
    fold = np.zeros(len(df), np.int8)
    fold[t >= val_cut] = 1
    fold[t >= test_cut] = 2
    out = np.empty(len(df), np.int8)
    out[df['i'].to_numpy()] = fold
    return out
