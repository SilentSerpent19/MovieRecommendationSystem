"""Persist and load a trained HybridModel as a small versioned directory of numpy files."""
import json
from pathlib import Path

import numpy as np
import scipy.sparse as sp

from .models import ALSModel, ContentModel, HybridModel, ItemKNNModel, PopularityModel

LATEST = 'LATEST'


def save(model: HybridModel, item_ids: np.ndarray, model_dir: Path, version: str, meta: dict,
         diversity: float = 0.3) -> Path:
    out = model_dir / version
    out.mkdir(parents=True, exist_ok=False)
    np.save(out / 'item_ids.npy', item_ids)
    np.save(out / 'embeddings.npy', model.content.embeddings)
    np.save(out / 'popularity.npy', model.popularity.popularity)
    params = {'history_prior': model.history_prior, 'popularity_weight': model.popularity_weight,
              'content_components': model.content.n_components, 'diversity': diversity}
    if isinstance(model.cf, ALSModel):
        np.save(out / 'item_factors.npy', model.cf.item_factors)
        params.update(cf='als', als_factors=model.cf.factors, als_reg=model.cf.reg, als_alpha=model.cf.alpha)
    else:
        sp.save_npz(out / 'similarity.npz', model.cf.similarity)
        params.update(cf='item_knn', knn_k=model.cf.k, knn_shrink=model.cf.shrink)
    (out / 'meta.json').write_text(json.dumps({'version': version, 'params': params, **meta}, indent=2))
    (model_dir / LATEST).write_text(version)
    return out


def latest_version(model_dir: Path) -> str | None:
    path = model_dir / LATEST
    return path.read_text().strip() if path.exists() else None


def load(model_dir: Path, version: str) -> tuple[HybridModel, np.ndarray, dict]:
    src = model_dir / version
    meta = json.loads((src / 'meta.json').read_text())
    p = meta['params']
    if p.get('cf', 'item_knn') == 'als':  # artifacts saved before ALS have no 'cf' key and are item-kNN
        cf = ALSModel(factors=p['als_factors'], reg=p['als_reg'], alpha=p['als_alpha'])
        cf.item_factors = np.load(src / 'item_factors.npy')
    else:
        cf = ItemKNNModel(k=p['knn_k'], shrink=p['knn_shrink'])
        cf.similarity = sp.load_npz(src / 'similarity.npz').tocsr()
    content = ContentModel(n_components=p['content_components'])
    content.embeddings = np.load(src / 'embeddings.npy')
    pop = PopularityModel()
    pop.popularity = np.load(src / 'popularity.npy')
    model = HybridModel(cf, content, pop, history_prior=p['history_prior'],
                        popularity_weight=p['popularity_weight'])
    return model, np.load(src / 'item_ids.npy'), meta
