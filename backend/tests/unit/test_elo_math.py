"""Unit tests for the shared Elo math module."""

import pytest

from app.utils.elo_math import (
    GLOBAL_INITIAL_RATING,
    GLOBAL_K_FACTOR,
    apply_elo,
    expected_score,
)


class TestConstants:
    def test_default_global_constants(self) -> None:
        assert GLOBAL_INITIAL_RATING == 1000.0
        assert GLOBAL_K_FACTOR == 24.0


class TestExpectedScore:
    def test_equal_ratings_yields_half(self) -> None:
        assert expected_score(1000.0, 1000.0) == pytest.approx(0.5)

    def test_400_point_gap_canonical(self) -> None:
        # Classic Elo figure: a 400-point-higher rating expects ~0.909.
        assert expected_score(1400.0, 1000.0) == pytest.approx(0.909, abs=0.002)
        assert expected_score(1000.0, 1400.0) == pytest.approx(0.091, abs=0.002)

    def test_symmetry(self) -> None:
        # P(A) + P(B) == 1 always.
        for r_a, r_b in [(1000, 1500), (1234, 987), (800, 800), (2000, 500)]:
            assert expected_score(r_a, r_b) + expected_score(r_b, r_a) == pytest.approx(1.0)


class TestApplyElo:
    def test_a_wins_equal_ratings_with_k32(self) -> None:
        new_a, new_b, da, db = apply_elo(1000.0, 1000.0, score_a=1.0, k=32.0)
        assert new_a == pytest.approx(1016.0)
        assert new_b == pytest.approx(984.0)
        assert da == pytest.approx(16.0)
        assert db == pytest.approx(-16.0)

    def test_b_wins_equal_ratings(self) -> None:
        new_a, new_b, _, _ = apply_elo(1000.0, 1000.0, score_a=0.0, k=32.0)
        assert new_a == pytest.approx(984.0)
        assert new_b == pytest.approx(1016.0)

    def test_draw_equal_ratings_no_change(self) -> None:
        new_a, new_b, da, db = apply_elo(1000.0, 1000.0, score_a=0.5, k=32.0)
        assert new_a == pytest.approx(1000.0)
        assert new_b == pytest.approx(1000.0)
        assert da == pytest.approx(0.0)
        assert db == pytest.approx(0.0)

    def test_draw_unequal_ratings_pulls_them_together(self) -> None:
        # Higher-rated A drawing against lower-rated B → A loses points, B gains.
        new_a, new_b, da, db = apply_elo(1500.0, 1000.0, score_a=0.5, k=32.0)
        assert da < 0
        assert db > 0
        assert da + db == pytest.approx(0.0)
        assert new_a < 1500.0 < new_b + 500  # A came down, B went up

    def test_upset_winner_gets_close_to_full_k(self) -> None:
        # Low-rated B beats high-rated A.
        _, _, da, db = apply_elo(1500.0, 1000.0, score_a=0.0, k=32.0)
        assert db > 28.0
        assert da < -28.0

    def test_sum_of_deltas_is_zero(self) -> None:
        for r_a, r_b, s_a, k in [
            (1234.0, 987.0, 1.0, 32.0),
            (800.0, 1600.0, 0.5, 24.0),
            (1100.0, 1050.0, 0.0, 16.0),
            (2000.0, 500.0, 0.5, 32.0),
        ]:
            _, _, da, db = apply_elo(r_a, r_b, score_a=s_a, k=k)
            assert da + db == pytest.approx(0.0)

    def test_zero_k_means_no_change(self) -> None:
        new_a, new_b, da, db = apply_elo(1234.0, 987.0, score_a=1.0, k=0.0)
        assert new_a == 1234.0
        assert new_b == 987.0
        assert da == 0.0
        assert db == 0.0
