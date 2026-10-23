"""Raw data sources, their checksums, and a verified downloader."""
import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

import requests

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Source:
    filename: str
    url: str
    md5: str | None  # None = upstream publishes no fixed checksum (file is refreshed daily)
    license: str


MOVIELENS_25M = Source(
    filename='ml-25m.zip',
    url='https://files.grouplens.org/datasets/movielens/ml-25m.zip',
    md5='6b51fb2759a8657d3bfcbfc42b592ada',
    license='GroupLens research license: non-commercial, no redistribution, cite Harper & Konstan 2015.',
)
IMDB_RATINGS = Source(
    filename='title.ratings.tsv.gz',
    url='https://datasets.imdbws.com/title.ratings.tsv.gz',
    md5=None,
    license='IMDb non-commercial datasets: personal and non-commercial use only.',
)
SOURCES = (MOVIELENS_25M, IMDB_RATINGS)


def md5sum(path: Path, block: int = 1 << 20) -> str:
    h = hashlib.md5()
    with open(path, 'rb') as f:
        while chunk := f.read(block):
            h.update(chunk)
    return h.hexdigest()


def use_system_certificates() -> None:
    """Verify HTTPS against the operating system's trust store instead of certifi's bundle.

    files.grouplens.org chains to a root CA (emSign) that macOS and Windows trust but certifi does not ship,
    so plain `requests` fails with CERTIFICATE_VERIFY_FAILED where curl and browsers succeed.
    """
    import truststore
    truststore.inject_into_ssl()


def ensure_downloaded(source: Source, raw_dir: Path) -> Path:
    """Download `source` into raw_dir unless already present; verify its checksum when one is known."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / source.filename
    if not path.exists():
        log.info('Downloading %s', source.url)
        tmp = path.with_suffix(path.suffix + '.part')
        with requests.get(source.url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(tmp, 'wb') as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        tmp.rename(path)
    if source.md5 and md5sum(path) != source.md5:
        raise ValueError(f'Checksum mismatch for {path}; delete it and re-run.')
    return path
