"""Tests for Vote status and config.allow_undo additions."""

from datetime import UTC, datetime

from app.schemas.common import (
    BracketConfig,
    CondorcetConfig,
    MultivoteConfig,
    ScoreConfig,
    TournamentConfig,
)
from app.schemas.tournament import Vote, VoteStatus


class TestVoteStatus:
    def test_default_status_is_active(self) -> None:
        vote = Vote(voter_label="Alice", payload={"foo": "bar"})
        assert vote.status == VoteStatus.ACTIVE

    def test_default_superseded_at_is_none(self) -> None:
        vote = Vote(voter_label="Alice", payload={})
        assert vote.superseded_at is None

    def test_explicit_superseded_status(self) -> None:
        vote = Vote(
            voter_label="Alice",
            payload={},
            status=VoteStatus.SUPERSEDED,
            superseded_at=datetime.now(UTC),
        )
        assert vote.status == VoteStatus.SUPERSEDED
        assert vote.superseded_at is not None

    def test_legacy_json_without_status_deserializes(self) -> None:
        """Existing tournament JSON files have no status field — should default to ACTIVE."""
        legacy = {"voter_label": "Alice", "payload": {"scores": [1, 2, 3]}}
        vote = Vote.model_validate(legacy)
        assert vote.status == VoteStatus.ACTIVE
        assert vote.superseded_at is None

    def test_status_serializes_as_string(self) -> None:
        vote = Vote(voter_label="Alice", payload={})
        dumped = vote.model_dump(mode="json")
        assert dumped["status"] == "active"


class TestAllowUndoConfig:
    def test_tournament_config_default_allow_undo_true(self) -> None:
        cfg = TournamentConfig()
        assert cfg.allow_undo is True

    def test_score_config_default_allow_undo_true(self) -> None:
        cfg = ScoreConfig()
        assert cfg.allow_undo is True

    def test_multivote_config_default_allow_undo_true(self) -> None:
        cfg = MultivoteConfig()
        assert cfg.allow_undo is True

    def test_condorcet_config_default_allow_undo_true(self) -> None:
        cfg = CondorcetConfig()
        assert cfg.allow_undo is True

    def test_bracket_config_default_allow_undo_true(self) -> None:
        cfg = BracketConfig()
        assert cfg.allow_undo is True

    def test_explicit_allow_undo_false(self) -> None:
        cfg = ScoreConfig(allow_undo=False)
        assert cfg.allow_undo is False

    def test_legacy_config_json_without_allow_undo_defaults_true(self) -> None:
        legacy = {"min_score": 1, "max_score": 5, "voter_labels": ["Alice"]}
        cfg = ScoreConfig.model_validate(legacy)
        assert cfg.allow_undo is True
