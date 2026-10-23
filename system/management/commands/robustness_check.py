import json
import logging
from datetime import UTC, datetime

import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from system.ml import prepare, robustness
from system.ml.config import DataConfig
from system.ml.data import load_dataset
from system.ml.experiment import ExperimentConfig

MODELS = ('popularity', 'item_knn', 'als', 'hybrid')
KEY_COMPARISONS = ('als - item_knn', 'hybrid - als', 'hybrid - item_knn', 'item_knn - popularity')


def _sample_users(processed_dir) -> np.ndarray:
    return np.unique(np.load(processed_dir / 'interactions.npz')['user'])


def _ci(c: dict) -> str:
    diff, (lo, hi) = c['mean_ndcg@10_diff'], c['ci95']
    mark = '' if lo <= 0 <= hi else ' *'
    return f'{diff:+.4f} [{lo:+.4f}, {hi:+.4f}]{mark}'


def to_markdown(report: dict) -> str:
    samples = report['resampled_users']['samples']
    lines = ['# Robustness checks', '',
             'Hyperparameters are fixed to those selected in `reports/evaluation.json`; nothing is re-tuned. '
             'NDCG@10 on the test fold. `*` = the paired bootstrap 95% CI excludes 0.', '',
             '## 1. Resampled users', '',
             'The same per-user chronological protocol (70/10/20, leak-free cold start) on independent samples of '
             '10,000 users, drawn with different seeds. The catalog is identical in every sample.', '']
    for setting, key in (('full history', 'test_results'), ('cold start (3 likes)', 'test_results_cold_start')):
        lines += [f'### NDCG@10, {setting}', '', '| sample | users evaluated | ' + ' | '.join(MODELS) + ' |',
                  '|---' * (len(MODELS) + 2) + '|']
        for name, s in samples.items():
            r = s[key]
            lines.append(f"| {name} | {r['hybrid']['users_evaluated']:,} | "
                         + ' | '.join(f"{r[m]['ndcg@10']:.4f}" for m in MODELS) + ' |')
        vals = np.array([[s[key][m]['ndcg@10'] for m in MODELS] for s in samples.values()])
        lines.append('| **mean ± sd** | | ' + ' | '.join(f'**{m:.4f}** ± {sd:.4f}' for m, sd in
                                                        zip(vals.mean(0), vals.std(0, ddof=1), strict=True)) + ' |')
        lines.append('')
    lines += ['### Paired differences per sample', '', '| sample | ' + ' | '.join(
        f'{c} ({s})' for c in KEY_COMPARISONS for s in ('full', 'cold')) + ' |',
        '|---' * (2 * len(KEY_COMPARISONS) + 1) + '|']
    for name, s in samples.items():
        lines.append(f'| {name} | ' + ' | '.join(
            _ci(s['paired_comparisons'][f'{c} ({st})']) for c in KEY_COMPARISONS for st in ('full', 'cold')) + ' |')
    lines += ['', f"User overlap with the main sample: {report['resampled_users']['overlap_with_main']}.", '']

    g = report['global_time_split']
    lines += ['## 2. Global time split', '',
              f"One cut-off for everyone at **{g['cutoff_date']}**: the newest 20% of all interactions are test, "
              'everything before is training.', '',
              f"- Users evaluated (likes on both sides of the cut-off): {g['users']['evaluated']:,} "
              f"of {g['users']['with_test_likes']:,} with test likes; "
              f"{g['users']['new_after_cutoff']:,} users only appear after the cut-off.",
              f"- Test likes on movies with no training likes (unlearnable for CF): "
              f"{g['test_likes_on_items_without_training_likes']:.1%}.", '',
              '| model | NDCG@10 | 95% CI | recall@10 | coverage | popularity percentile |',
              '|---|---|---|---|---|---|']
    for m, r in g['test_results'].items():
        ci = r['ndcg@10_ci95']
        lines.append(f"| {m} | {r['ndcg@10']:.4f} | [{ci[0]:.4f}, {ci[1]:.4f}] | {r['recall@10']:.4f} | "
                     f"{r['coverage']:.4f} | {r['popularity_percentile@10']:.4f} |")
    lines += ['', '| comparison | mean diff [95% CI] |', '|---|---|']
    for c in KEY_COMPARISONS + ('hybrid - popularity',):
        lines.append(f"| {c} | {_ci(g['paired_comparisons'][f'{c} (global)'])} |")
    lines += ['', f"Runtime: {report['runtime_seconds']}s.", '']
    return '\n'.join(lines)


class Command(BaseCommand):
    help = ('Check that the offline conclusions hold on independent user samples and under a global time split, '
            'using the hyperparameters selected by evaluate_recommenders.')

    def add_arguments(self, parser):
        parser.add_argument('--seeds', type=int, nargs='+', default=[1, 2, 3],
                            help='Extra user-sample seeds (each is ~85 s and ~30 MB under data/robustness/)')

    def handle(self, *args, **opts):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
        t0 = datetime.now(UTC)
        reports = settings.BASE_DIR / 'reports'
        try:
            main_report = json.loads((reports / 'evaluation.json').read_text())
        except FileNotFoundError as e:
            raise CommandError('Run evaluate_recommenders first: it selects the hyperparameters.') from e
        selected = main_report['selected_params']
        cfg = ExperimentConfig()
        main_seed = json.loads((settings.PROCESSED_DATA_DIR / 'manifest.json').read_text())['config']['seed']

        samples = {f'seed {main_seed} (main)': {k: main_report[k] for k in
                                                ('test_results', 'test_results_cold_start', 'paired_comparisons')}}
        main_users = _sample_users(settings.PROCESSED_DATA_DIR)
        overlap = {}
        for seed in opts['seeds']:
            out = settings.DATA_DIR / 'robustness' / f'seed_{seed}'
            if not (out / 'manifest.json').exists():
                prepare.run(DataConfig(raw_dir=settings.RAW_DATA_DIR, processed_dir=out, seed=seed,
                                       fetch_wikidata=False))
            ds = load_dataset(out)
            self.stdout.write(f'Evaluating user sample seed {seed} ({ds.n_users} users)')
            samples[f'seed {seed}'] = robustness.per_user_split(ds, selected, cfg)
            overlap[f'seed {seed}'] = f'{np.isin(_sample_users(out), main_users).mean():.1%}'

        self.stdout.write('Global time split on the main sample')
        g = robustness.global_time_split(load_dataset(settings.PROCESSED_DATA_DIR), selected, cfg)
        g['cutoff_date'] = datetime.fromtimestamp(g['cutoff'], UTC).strftime('%Y-%m-%d')

        report = {'selected_params': selected,
                  'resampled_users': {'samples': samples, 'overlap_with_main': overlap},
                  'global_time_split': g,
                  'runtime_seconds': round((datetime.now(UTC) - t0).total_seconds(), 1)}
        (reports / 'robustness.json').write_text(json.dumps(report, indent=2))
        (reports / 'robustness.md').write_text(to_markdown(report))
        self.stdout.write(to_markdown(report))
        self.stdout.write(self.style.SUCCESS(f'Report written to {reports}/robustness.{{json,md}}'))
