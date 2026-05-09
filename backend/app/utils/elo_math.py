"""Shared chess-style Elo math.

Used by both the in-tournament ELO mode (per-voter ratings, no draws) and
the global option-popularity tracker (single rating per Option, draws via
swiss/derived pairwise).
"""

GLOBAL_INITIAL_RATING: float = 1000.0
GLOBAL_K_FACTOR: float = 24.0


def expected_score(rating_a: float, rating_b: float) -> float:
    """Elo expected score for A given the two ratings."""
    return float(1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0)))


def apply_elo(rating_a: float, rating_b: float, score_a: float, k: float) -> tuple[float, float, float, float]:
    """Apply an Elo update.

    `score_a` is the actual outcome from A's perspective: 1.0 win, 0.0 loss,
    0.5 draw. The function does not constrain to {0, 0.5, 1} so callers can
    pass any value in [0, 1] if a future feature wants partial credit.

    Returns (new_a, new_b, delta_a, delta_b). Sum of deltas is exactly zero.
    """
    expected_a = expected_score(rating_a, rating_b)
    delta_a = k * (score_a - expected_a)
    return rating_a + delta_a, rating_b - delta_a, delta_a, -delta_a
