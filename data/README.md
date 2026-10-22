# data/

Nothing in this folder is committed except this file. The data licences forbid redistribution.

| path | written by | contents |
|---|---|---|
| `raw/ml-25m.zip` | `prepare_data` (download, md5-verified) | MovieLens 25M, read directly from the zip |
| `raw/title.ratings.tsv.gz` | `prepare_data` | IMDb ratings (refreshed daily upstream) |
| `raw/wikidata_cache.json` | `prepare_data` | directors/runtime by IMDb id, so re-runs make no requests |
| `processed/` | `prepare_data` | `catalog.csv`, `genome.npy`, `genome_tags.json`, `mood_scores.npy`, `interactions.npz`, `manifest.json` |
| `models/<version>/` | `train_recommender` | `similarity.npz`, `embeddings.npy`, `popularity.npy`, `item_ids.npy`, `meta.json` |
| `models/LATEST` | `train_recommender` | the version the web app loads |

The row order of `processed/catalog.csv` is the item index used by every array in `processed/` and `models/`.
`processed/manifest.json` records the config, source checksums and the data-quality report for the run.

To rebuild from scratch:

```bash
rm -rf data/processed data/models && python manage.py prepare_data && python manage.py load_catalog \
  && python manage.py evaluate_recommenders && python manage.py train_recommender
```
