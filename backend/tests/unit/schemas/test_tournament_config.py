"""Tests for TournamentConfig base and mode-specific configs (voter_labels)."""

import pytest
from pydantic import ValidationError

from app.schemas.common import (
    BracketConfig,
    CondorcetConfig,
    MultivoteConfig,
    ScoreConfig,
    TournamentConfig,
)


class TestTournamentConfigBase:
    def test_default_voter_labels(self) -> None:
        cfg = TournamentConfig()
        assert cfg.voter_labels == ["default"]

    def test_custom_labels_preserved(self) -> None:
        cfg = TournamentConfig(voter_labels=["Alice", "Bob"])
        assert cfg.voter_labels == ["Alice", "Bob"]

    def test_empty_labels_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TournamentConfig(voter_labels=[])

    def test_too_many_labels_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TournamentConfig(voter_labels=[f"V{i}" for i in range(51)])

    def test_exactly_fifty_labels_accepted(self) -> None:
        labels = [f"V{i}" for i in range(50)]
        cfg = TournamentConfig(voter_labels=labels)
        assert len(cfg.voter_labels) == 50

    def test_empty_string_label_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TournamentConfig(voter_labels=["Alice", ""])

    def test_whitespace_only_label_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TournamentConfig(voter_labels=["Alice", "   "])

    def test_duplicate_labels_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TournamentConfig(voter_labels=["Alice", "Alice"])

    def test_duplicate_labels_case_sensitive(self) -> None:
        # "alice" and "Alice" are considered distinct
        cfg = TournamentConfig(voter_labels=["alice", "Alice"])
        assert cfg.voter_labels == ["alice", "Alice"]

    def test_labels_are_trimmed(self) -> None:
        cfg = TournamentConfig(voter_labels=["  Alice  ", "Bob "])
        assert cfg.voter_labels == ["Alice", "Bob"]

    def test_trimmed_duplicate_rejected(self) -> None:
        # After trim, "Alice" and " Alice " collide
        with pytest.raises(ValidationError):
            TournamentConfig(voter_labels=["Alice", " Alice "])

    def test_label_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TournamentConfig(voter_labels=["A" * 51])

    def test_label_exactly_fifty_chars_accepted(self) -> None:
        cfg = TournamentConfig(voter_labels=["A" * 50])
        assert cfg.voter_labels == ["A" * 50]


class TestScoreConfig:
    def test_defaults(self) -> None:
        cfg = ScoreConfig()
        assert cfg.min_score == 1
        assert cfg.max_score == 5
        assert cfg.voter_labels == ["default"]

    def test_custom_labels(self) -> None:
        cfg = ScoreConfig(voter_labels=["Alice", "Bob", "Charlie"])
        assert cfg.voter_labels == ["Alice", "Bob", "Charlie"]


class TestMultivoteConfig:
    def test_defaults(self) -> None:
        cfg = MultivoteConfig()
        assert cfg.total_votes is None
        assert cfg.max_per_option is None
        assert cfg.voter_labels == ["default"]

    def test_custom_labels(self) -> None:
        cfg = MultivoteConfig(voter_labels=["Alice", "Bob"])
        assert cfg.voter_labels == ["Alice", "Bob"]


class TestCondorcetConfig:
    def test_defaults(self) -> None:
        cfg = CondorcetConfig()
        assert cfg.voter_labels == ["default"]

    def test_custom_labels(self) -> None:
        cfg = CondorcetConfig(voter_labels=["Alice", "Bob"])
        assert cfg.voter_labels == ["Alice", "Bob"]


class TestBracketConfig:
    def test_defaults(self) -> None:
        cfg = BracketConfig()
        assert cfg.shuffle_seed is True
        assert cfg.third_place_match is False
        assert cfg.voter_labels == ["default"]

    def test_rejects_multiple_voters(self) -> None:
        with pytest.raises(ValidationError):
            BracketConfig(voter_labels=["Alice", "Bob"])

    def test_accepts_single_custom_voter(self) -> None:
        cfg = BracketConfig(voter_labels=["Alice"])
        assert cfg.voter_labels == ["Alice"]
