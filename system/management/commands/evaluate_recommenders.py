import json
import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from system.ml import experiment
from system.ml.data import load_dataset


def to_markdown(report: dict) -> str:
    k = report['protocol']['k']
    cols = [f'ndcg@{k}', f'recall@{k}', f'precision@{k}', f'hit_rate@{k}', 'coverage', f'popularity_percentile@{k}']
    lines = ['# Offline evaluation', '',
             f"Protocol: {report['protocol']['split']} split "
             f"({report['protocol']['val_frac']:.0%} validation, {report['protocol']['test_frac']:.0%} test per user), "
             f"positives = rating >= {report['protocol']['positive_threshold']}, k = {k}. "
             f"Hyperparameters selected on validation; test evaluated once.", '']
    for title, key in (('Test: full user history', 'test_results'),
                       (f"Test: cold start (each user's {report['protocol']['cold_start_history']} most recent likes)",
                        'test_results_cold_start')):
        lines += [f'## {title}', '', '| model | ' + ' | '.join(cols) + ' | NDCG 95% CI |',
                  '|---' * (len(cols) + 2) + '|']
        for name, r in report[key].items():
            ci = r[f'ndcg@{k}_ci95']
            lines.append(f'| {name} | ' + ' | '.join(f'{r[c]:.4f}' for c in cols) + f' | [{ci[0]:.4f}, {ci[1]:.4f}] |')
        lines.append('')
    lines += ['## Paired differences in NDCG (bootstrap 95% CI)', '', '| comparison | mean diff | 95% CI |',
              '|---|---|---|']
    for name, c in report['paired_comparisons'].items():
        lines.append(f"| {name} | {c[f'mean_ndcg@{k}_diff']:+.4f} | [{c['ci95'][0]:+.4f}, {c['ci95'][1]:+.4f}] |")
    lines += ['', '## Selected hyperparameters', '', '```json', json.dumps(report['selected_params'], indent=2), '```',
              '', f"Data: {report['data']}. Runtime: {report['runtime_seconds']}s.", '']
    return '\n'.join(lines)


class Command(BaseCommand):
    help = 'Tune models on a validation split and evaluate them once on held-out future interactions.'

    def handle(self, *args, **opts):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
        ds = load_dataset(settings.PROCESSED_DATA_DIR)
        report = experiment.run(ds, experiment.ExperimentConfig())
        out = settings.BASE_DIR / 'reports'
        out.mkdir(exist_ok=True)
        (out / 'evaluation.json').write_text(json.dumps(report, indent=2))
        (out / 'evaluation.md').write_text(to_markdown(report))
        self.stdout.write(to_markdown(report))
        self.stdout.write(self.style.SUCCESS(f'Report written to {out}/evaluation.{{json,md}}'))
