"""Optional metadata joined onto the catalog by IMDb id: IMDb ratings and Wikidata directors/runtime."""
import json
import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

log = logging.getLogger(__name__)

WIKIDATA_URL = 'https://query.wikidata.org/sparql'
WIKIDATA_UA = 'MovieRecommendationSystem/1.0 (non-commercial learning project)'
WIKIDATA_QUERY = """
SELECT ?imdb (GROUP_CONCAT(DISTINCT ?dirLabel; separator="|") AS ?directors) (SAMPLE(?dur) AS ?runtime)
WHERE {
  VALUES ?imdb { %s }
  ?film wdt:P345 ?imdb .
  OPTIONAL { ?film wdt:P57 ?dir . ?dir rdfs:label ?dirLabel FILTER(LANG(?dirLabel) = "en") }
  OPTIONAL { ?film wdt:P2047 ?dur }
}
GROUP BY ?imdb
"""


def read_imdb_ratings(path: Path, imdb_ids: set[str], chunksize: int) -> pd.DataFrame:
    """averageRating/numVotes for the given tconsts only, read in chunks."""
    parts = []
    for chunk in pd.read_csv(path, sep='\t', chunksize=chunksize, dtype={'tconst': str},
                             na_values='\\N'):
        parts.append(chunk[chunk['tconst'].isin(imdb_ids)])
    df = pd.concat(parts, ignore_index=True)
    return df.rename(columns={'tconst': 'imdb_id', 'averageRating': 'imdb_rating', 'numVotes': 'imdb_votes'})


def fetch_wikidata(imdb_ids: list[str], cache_path: Path, batch: int = 200) -> pd.DataFrame:
    """Directors and runtime from Wikidata (CC0). Results are cached so re-runs make no requests."""
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    todo = [i for i in imdb_ids if i not in cache]
    for start in range(0, len(todo), batch):
        ids = todo[start: start + batch]
        values = ' '.join(f'"{i}"' for i in ids)
        resp = requests.get(WIKIDATA_URL, params={'query': WIKIDATA_QUERY % values},
                            headers={'Accept': 'application/sparql-results+json', 'User-Agent': WIKIDATA_UA},
                            timeout=120)
        resp.raise_for_status()
        for i in ids:
            cache[i] = {}
        for b in resp.json()['results']['bindings']:
            cache[b['imdb']['value']] = {
                'directors': b.get('directors', {}).get('value', ''),
                'runtime': b.get('runtime', {}).get('value'),
            }
        cache_path.write_text(json.dumps(cache))
        log.info('Wikidata: %d/%d', min(start + batch, len(todo)), len(todo))
        time.sleep(1)  # be polite to the public endpoint
    rows = [{'imdb_id': i, **cache.get(i, {})} for i in imdb_ids]
    df = pd.DataFrame(rows, columns=['imdb_id', 'directors', 'runtime'])
    df['directors'] = df['directors'].fillna('').str.replace('|', ', ', regex=False)
    runtime = pd.to_numeric(df['runtime'], errors='coerce')
    df['runtime'] = runtime.where((runtime > 0) & (runtime < 1000)).round().astype('Int16')
    return df


def bayesian_average(mean: np.ndarray, count: np.ndarray, prior_mean: float, prior_count: float) -> np.ndarray:
    """Shrink each item's mean towards the global mean; items with few votes move the most."""
    return (count * mean + prior_count * prior_mean) / (count + prior_count)
