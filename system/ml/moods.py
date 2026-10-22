"""Mood labels derived from the MovieLens Tag Genome.

Each mood is the mean relevance of a few genome tags. The genome itself is a published ML model
(Vig, Sen & Riedl 2012) trained on user tags, ratings and reviews, so moods reflect how people
describe a film rather than a guess from its genre. Labels are deterministic for a given genome.
"""
import numpy as np

MOOD_VERSION = 'genome-v1'

MOOD_TAGS: dict[str, tuple[str, ...]] = {
    'Funny': ('funny', 'hilarious', 'goofy', 'fun movie'),
    'Feel-Good': ('feel-good', 'feel good movie', 'heartwarming', 'happy ending'),
    'Romantic': ('romantic', 'love story'),
    'Dark': ('dark', 'bleak', 'disturbing', 'depressing'),
    'Scary': ('scary', 'creepy', 'horror'),
    'Suspenseful': ('suspense', 'suspenseful', 'tense', 'intense'),
    'Action-Packed': ('action packed', 'fast paced', 'action'),
    'Adventurous': ('adventure', 'epic'),
    'Thought-Provoking': ('thought-provoking', 'philosophical', 'cerebral'),
    'Emotional': ('emotional', 'touching', 'sad', 'sentimental'),
    'Inspiring': ('inspirational', 'inspiring'),
    'Mysterious': ('mystery', 'twist ending', 'mindfuck'),
    'Whimsical': ('whimsical', 'quirky', 'cute', 'light'),
    'Atmospheric': ('atmospheric', 'dreamlike', 'surreal', 'visually stunning'),
}


def mood_scores(genome: np.ndarray, tags: list[str]) -> np.ndarray:
    """(n_movies x n_moods) matrix of mean tag relevance in [0, 1], columns ordered as MOOD_TAGS."""
    col = {t: i for i, t in enumerate(tags)}
    missing = [t for ts in MOOD_TAGS.values() for t in ts if t not in col]
    if missing:
        raise KeyError(f'genome tags not found: {missing}')
    return np.stack(
        [genome[:, [col[t] for t in ts]].mean(axis=1) for ts in MOOD_TAGS.values()], axis=1
    ).astype(np.float32)


def assign_moods(scores: np.ndarray, threshold: float) -> list[list[tuple[int, float]]]:
    """For each movie, the (mood index, score) pairs at or above threshold, strongest first."""
    out = []
    for row in scores:
        idx = np.flatnonzero(row >= threshold)
        out.append(sorted(((int(i), float(row[i])) for i in idx), key=lambda p: -p[1]))
    return out
