import json
import logging
from datetime import UTC, datetime

import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand

from system.ml import artifacts
from system.ml.data import POSITIVE_THRESHOLD, interaction_matrix, load_dataset
from system.ml.models import ContentModel, HybridModel, ItemKNNModel, PopularityModel

DEFAULT_PARAMS = {'item_knn': {'k': 200, 'shrink': 0.0}, 'content': {'n_components': 128},
                  'hybrid': {'history_prior': 10.0, 'popularity_weight': 0.0}}


class Command(BaseCommand):
    help = ('Fit the hybrid recommender on all sampled interactions with the hyperparameters selected by '
            'evaluate_recommenders, and save a versioned artifact the web app loads.')

    def handle(self, *args, **opts):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
        report_path = settings.BASE_DIR / 'reports' / 'evaluation.json'
        report = json.loads(report_path.read_text()) if report_path.exists() else None
        params = report['selected_params'] if report else DEFAULT_PARAMS
        if report is None:
            self.stdout.write(self.style.WARNING('No reports/evaluation.json; using default hyperparameters.'))

        ds = load_dataset(settings.PROCESSED_DATA_DIR)
        pos = ds.ratings >= POSITIVE_THRESHOLD
        X = interaction_matrix(ds.users[pos], ds.items[pos], ds.n_users, ds.n_items)
        model = HybridModel(
            ItemKNNModel(**params['item_knn']),
            ContentModel(n_components=params['content']['n_components'], seed=42),
            PopularityModel(),
            **params['hybrid'],
        ).fit(X, ds.genome)

        version = datetime.now(UTC).strftime('%Y%m%d-%H%M%S')
        meta = {
            'trained_at': datetime.now(UTC).isoformat(timespec='seconds'),
            'data_created_at': ds.manifest.get('created_at'),
            'n_users': ds.n_users, 'n_items': ds.n_items, 'n_positive_interactions': int(X.nnz),
            'similarity_nnz': int(model.knn.similarity.nnz),
            'params_source': 'reports/evaluation.json' if report else 'defaults',
            # Offline metrics come from the same configuration refit on train+validation and scored on the
            # held-out test period; this artifact is then refit on all interactions, so it has no test score.
            'offline_evaluation': {
                'evaluated_model': 'same hyperparameters, fit on train+validation (see reports/evaluation.json)',
                'test_results': report['test_results'] if report else None,
                'test_results_cold_start': report['test_results_cold_start'] if report else None,
            },
        }
        out = artifacts.save(model, ds.item_ids, settings.MODEL_DIR, version, meta)
        size_mb = sum(f.stat().st_size for f in out.iterdir()) / 1e6
        self.stdout.write(self.style.SUCCESS(
            f'Saved model {version} to {out} ({size_mb:.1f} MB, {model.knn.similarity.nnz} similarity entries, '
            f'{int(np.count_nonzero(model.popularity.popularity))} items with likes).'))
