import json
import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from system.ml import prepare
from system.ml.config import DataConfig


class Command(BaseCommand):
    help = ('Download MovieLens 25M + IMDb ratings (if missing), stream them into a small processed '
            'dataset under data/processed/, and write a data-quality manifest.')

    def add_arguments(self, parser):
        defaults = DataConfig(raw_dir=settings.RAW_DATA_DIR, processed_dir=settings.PROCESSED_DATA_DIR)
        parser.add_argument('--movies', type=int, default=defaults.n_movies)
        parser.add_argument('--users', type=int, default=defaults.n_users)
        parser.add_argument('--min-user-ratings', type=int, default=defaults.min_user_ratings)
        parser.add_argument('--seed', type=int, default=defaults.seed)
        parser.add_argument('--skip-wikidata', action='store_true', help='Do not fetch directors/runtime')

    def handle(self, *args, **opts):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
        cfg = DataConfig(
            raw_dir=settings.RAW_DATA_DIR,
            processed_dir=settings.PROCESSED_DATA_DIR,
            n_movies=opts['movies'],
            n_users=opts['users'],
            min_user_ratings=opts['min_user_ratings'],
            seed=opts['seed'],
            fetch_wikidata=not opts['skip_wikidata'],
        )
        manifest = prepare.run(cfg)
        self.stdout.write(json.dumps(manifest['quality'], indent=2))
        self.stdout.write(self.style.SUCCESS(
            f"Processed dataset written to {cfg.processed_dir} in {manifest['runtime_seconds']}s"))
