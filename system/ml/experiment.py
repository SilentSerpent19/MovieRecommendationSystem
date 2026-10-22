"""Model selection and final evaluation.

1. Per-user chronological split: 70% train / 10% validation / 20% test.
2. Tune each model's hyperparameters on validation (fit on train only).
3. Refit the chosen configurations on train+validation and evaluate once on test,
   against random and popularity baselines.
"""
import logging
import time
from dataclasses import dataclass, field

import numpy as np
import scipy.sparse as sp

from .data import POSITIVE_THRESHOLD, Dataset, interaction_matrix, temporal_split
from .evaluation import bootstrap_ci, evaluate, truncate_history
from .models import ContentModel, HybridModel, ItemKNNModel, PopularityModel, RandomModel

log = logging.getLogger(__name__)


@dataclass
class ExperimentConfig:
    val_frac: float = 0.1
    test_frac: float = 0.2
    k: int = 10
    seed: int = 42
    tuning_users: int = 3000  # validation metrics on a seeded subsample keep tuning fast
    cold_start_history: int = 3  # profile length for the cold-start evaluation
    knn_k: tuple = (25, 50, 100, 200)
    knn_shrink: tuple = (0.0, 10.0, 50.0)
    content_components: tuple = (32, 64, 128)
    history_prior: tuple = (2.0, 10.0, 50.0)
    popularity_weight: tuple = (0.0, 0.1, 0.3)
    extra: dict = field(default_factory=dict)


@dataclass
class Fold:
    train: object
    seen: object
    relevant: object
    popularity: np.ndarray
    order: object  # timestamps of history positives, for building cold-start profiles

    def cold_start(self, n: int) -> 'Fold':
        return Fold(truncate_history(self.train, self.order, n), self.seen, self.relevant, self.popularity, self.order)


def make_fold(ds: Dataset, history_mask: np.ndarray, target_mask: np.ndarray, users=None) -> Fold:
    pos = ds.ratings >= POSITIVE_THRESHOLD
    shape = (ds.n_users, ds.n_items)
    hp = history_mask & pos
    train = interaction_matrix(ds.users[hp], ds.items[hp], *shape)
    order = sp.csr_matrix((ds.timestamps[hp].astype(np.float64), (ds.users[hp], ds.items[hp])), shape=shape)
    seen = interaction_matrix(ds.users[history_mask], ds.items[history_mask], *shape)
    relevant = interaction_matrix(ds.users[target_mask & pos], ds.items[target_mask & pos], *shape)
    if users is not None:  # restrict evaluation to a subset of users (history is kept for all)
        keep = np.zeros(ds.n_users, bool)
        keep[users] = True
        relevant = relevant.multiply(keep[:, None]).tocsr()
    return Fold(train, seen, relevant, np.asarray(train.sum(axis=0)).ravel(), order)


def _eval(model, fold: Fold, k: int, per_user: bool = False) -> dict:
    return evaluate(model, fold.train, fold.seen, fold.relevant, fold.popularity, k=k, per_user=per_user)


def run(ds: Dataset, cfg: ExperimentConfig) -> dict:
    t0 = time.time()
    folds = temporal_split(ds.users, ds.timestamps, cfg.val_frac, cfg.test_frac)
    rng = np.random.default_rng(cfg.seed)
    tune_users = rng.choice(ds.n_users, size=min(cfg.tuning_users, ds.n_users), replace=False)
    val = make_fold(ds, folds == 0, folds == 1, users=tune_users)
    tuning = {}

    log.info('Tuning item-kNN')
    knn_results = {}
    for k in cfg.knn_k:
        for shrink in cfg.knn_shrink:
            m = ItemKNNModel(k=k, shrink=shrink).fit(val.train, ds.genome)
            knn_results[(k, shrink)] = _eval(m, val, cfg.k)
    best_knn = max(knn_results, key=lambda p: knn_results[p][f'ndcg@{cfg.k}'])
    tuning['item_knn'] = [{'k': p[0], 'shrink': p[1], **r} for p, r in knn_results.items()]

    log.info('Tuning content model')
    content_results = {}
    for n in cfg.content_components:
        m = ContentModel(n_components=n, seed=cfg.seed).fit(val.train, ds.genome)
        content_results[n] = {**_eval(m, val, cfg.k), 'explained_variance': round(m.explained_variance, 3)}
    best_content = max(content_results, key=lambda n: content_results[n][f'ndcg@{cfg.k}'])
    tuning['content'] = [{'n_components': n, **r} for n, r in content_results.items()]

    log.info('Tuning hybrid blend (objective: mean of full-history and cold-start validation NDCG)')
    val_cold = val.cold_start(cfg.cold_start_history)
    knn = ItemKNNModel(*best_knn).fit(val.train, ds.genome)
    content = ContentModel(best_content, seed=cfg.seed).fit(val.train, ds.genome)
    pop = PopularityModel().fit(val.train, ds.genome)
    hybrid_results = {}
    for prior in cfg.history_prior:
        for pw in cfg.popularity_weight:
            m = HybridModel(knn, content, pop, history_prior=prior, popularity_weight=pw)
            full, cold = _eval(m, val, cfg.k), _eval(m, val_cold, cfg.k)
            hybrid_results[(prior, pw)] = {**full, f'cold_start_ndcg@{cfg.k}': cold[f'ndcg@{cfg.k}'],
                                           'objective': round((full[f'ndcg@{cfg.k}'] + cold[f'ndcg@{cfg.k}']) / 2, 4)}
    best_hybrid = max(hybrid_results, key=lambda p: hybrid_results[p]['objective'])
    tuning['hybrid'] = [{'history_prior': p[0], 'popularity_weight': p[1], **r} for p, r in hybrid_results.items()]

    log.info('Final evaluation on the test fold')
    test = make_fold(ds, folds <= 1, folds == 2)
    final_models = [
        RandomModel(seed=cfg.seed),
        PopularityModel(),
        ContentModel(best_content, seed=cfg.seed),
        ItemKNNModel(*best_knn),
        HybridModel(ItemKNNModel(*best_knn), ContentModel(best_content, seed=cfg.seed), PopularityModel(),
                    history_prior=best_hybrid[0], popularity_weight=best_hybrid[1]),
    ]
    test_cold = test.cold_start(cfg.cold_start_history)
    results, cold_results, per_user = {}, {}, {}
    for m in final_models:
        m.fit(test.train, ds.genome)
        for name, fold, out in (('full', test, results), ('cold', test_cold, cold_results)):
            r = _eval(m, fold, cfg.k, per_user=True)
            per_user[(m.name, name)] = r.pop('_ndcg')
            r[f'ndcg@{cfg.k}_ci95'] = bootstrap_ci(per_user[(m.name, name)], seed=cfg.seed)
            out[m.name] = r
        log.info('%s: full %s | cold-start %s', m.name, results[m.name][f'ndcg@{cfg.k}'],
                 cold_results[m.name][f'ndcg@{cfg.k}'])
    comparisons = {}
    for a, b in (('item_knn', 'popularity'), ('hybrid', 'popularity'), ('hybrid', 'item_knn'),
                 ('hybrid', 'content')):
        for setting in ('full', 'cold'):
            diff = per_user[(a, setting)] - per_user[(b, setting)]
            comparisons[f'{a} - {b} ({setting})'] = {
                f'mean_ndcg@{cfg.k}_diff': round(float(diff.mean()), 4),
                'ci95': bootstrap_ci(diff, seed=cfg.seed)}

    split_sizes = {name: int((folds == i).sum()) for i, name in enumerate(['train', 'validation', 'test'])}
    return {
        'protocol': {
            'split': 'per-user chronological', 'val_frac': cfg.val_frac, 'test_frac': cfg.test_frac,
            'positive_threshold': POSITIVE_THRESHOLD, 'k': cfg.k, 'seed': cfg.seed,
            'tuning_users': len(tune_users), 'selection_metric': f'ndcg@{cfg.k} on validation',
            'cold_start_history': cfg.cold_start_history,
            'interactions_per_fold': split_sizes,
        },
        'selected_params': {
            'item_knn': {'k': best_knn[0], 'shrink': best_knn[1]},
            'content': {'n_components': best_content},
            'hybrid': {'history_prior': best_hybrid[0], 'popularity_weight': best_hybrid[1]},
        },
        'test_results': results,
        'test_results_cold_start': cold_results,
        'paired_comparisons': comparisons,
        'tuning': tuning,
        'data': {'created_at': ds.manifest.get('created_at'), 'n_users': ds.n_users, 'n_items': ds.n_items,
                 'n_interactions': len(ds.users)},
        'runtime_seconds': round(time.time() - t0, 1),
    }
