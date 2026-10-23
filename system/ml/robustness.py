"""Robustness checks for the offline results, using the hyperparameters already selected by experiment.run.

1. Resampled users: the same per-user protocol on independent user samples drawn with other seeds.
   Does the ranking of models depend on which 10,000 users we happened to sample?
2. Global time split: a single cut-off date for everyone instead of a per-user split.
   Training then never contains interactions from after any test interaction, as in a real deployment.

Nothing is re-tuned here, so the checks cost one test evaluation each (about a minute).
"""
import logging

import numpy as np

from .data import POSITIVE_THRESHOLD, Dataset, temporal_split
from .experiment import ExperimentConfig, make_fold, sample_eval_users, test_models
from .models import ContentModel

log = logging.getLogger(__name__)


def _embeddings(ds: Dataset, selected: dict, cfg: ExperimentConfig) -> np.ndarray:
    # Content embeddings depend only on the genome, not on interactions.
    return ContentModel(selected['content']['n_components'], seed=cfg.seed).fit(None, ds.genome).embeddings


def per_user_split(ds: Dataset, selected: dict, cfg: ExperimentConfig) -> dict:
    """The main protocol's test evaluation (full history and leak-free cold start) with fixed hyperparameters."""
    folds = temporal_split(ds.users, ds.timestamps, cfg.val_frac, cfg.test_frac)
    _, cold_users = sample_eval_users(ds.n_users, cfg)
    test = make_fold(ds, folds <= 1, folds == 2)
    results, comparisons = test_models(
        ds, {'full': test, 'cold': test.cold_start(cold_users, cfg.cold_start_history)}, selected, cfg,
        _embeddings(ds, selected, cfg))
    return {'test_results': results['full'], 'test_results_cold_start': results['cold'],
            'paired_comparisons': comparisons}


def global_cutoff(timestamps: np.ndarray, test_frac: float) -> int:
    """The timestamp after which `test_frac` of all interactions fall."""
    return int(np.sort(timestamps)[int(len(timestamps) * (1 - test_frac))])


def global_time_split(ds: Dataset, selected: dict, cfg: ExperimentConfig) -> dict:
    """Train on everything before one cut-off date, test on everything after it.

    Only users with at least one like before the cut-off are evaluated: users who arrive after it have no
    history, and the app would serve them popularity. Items first liked after the cut-off cannot be learned by
    collaborative models; the report says how much of the test set they account for.
    """
    cut = global_cutoff(ds.timestamps, cfg.test_frac)
    history, target = ds.timestamps < cut, ds.timestamps >= cut
    likes = ds.ratings >= POSITIVE_THRESHOLD
    history_likes = np.bincount(ds.users[history & likes], minlength=ds.n_users)
    target_likes = np.bincount(ds.users[target & likes], minlength=ds.n_users)
    evaluated = np.flatnonzero((history_likes > 0) & (target_likes > 0))
    fold = make_fold(ds, history, target, users=evaluated)

    item_train_likes = np.bincount(ds.items[history & likes], minlength=ds.n_items)
    test_items = ds.items[target & likes & np.isin(ds.users, evaluated)]
    results, comparisons = test_models(ds, {'global': fold}, selected, cfg, _embeddings(ds, selected, cfg))
    return {
        'cutoff': int(cut),
        'interactions': {'train': int(history.sum()), 'test': int(target.sum())},
        # evaluated = likes on both sides of the cut-off; new_after_cutoff = no likes before it
        'users': {
            'with_test_likes': int((target_likes > 0).sum()),
            'evaluated': int(len(evaluated)),
            'new_after_cutoff': int(((history_likes == 0) & (target_likes > 0)).sum()),
        },
        'test_likes_on_items_without_training_likes': round(float((item_train_likes[test_items] == 0).mean()), 4),
        'test_results': results['global'],
        'paired_comparisons': comparisons,
    }
