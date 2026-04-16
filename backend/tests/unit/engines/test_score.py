"""Unit tests for the score tournament engine."""

import uuid

import pytest

from app.engines.base import AlreadyVotedContext, BallotContext, CompletedContext
from app.engines.score import ScoreEngine
from app.exceptions import ValidationError
from app.schemas.tournament import TournamentEntry


def _make_entries(n: int) -> list[TournamentEntry]:
    return [
        TournamentEntry(
            option_id=uuid.uuid4(),
            option_snapshot={"name": f"Option {i + 1}", "id": str(uuid.uuid4())},
        )
        for i in range(n)
    ]


def _make_scores(entries: list[TournamentEntry], scores: list[int]) -> dict:
    return {"scores": [{"entry_id": str(e.id), "score": s} for e, s in zip(entries, scores, strict=True)]}


def _voter_labels(n: int) -> list[str]:
    return [f"Voter {i + 1}" for i in range(n)]


class TestScoreValidateConfig:
    def test_default_config_is_valid(self) -> None:
        engine = ScoreEngine()
        assert engine.validate_config({}) == []

    def test_custom_config_is_valid(self) -> None:
        engine = ScoreEngine()
        assert engine.validate_config({"min_score": 0, "max_score": 10, "voter_labels": _voter_labels(3)}) == []


class TestScoreInitialize:
    def test_correct_state_structure(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"voter_labels": _voter_labels(2)})
        assert state["voter_labels"] == ["Voter 1", "Voter 2"]
        assert state["ballots_required"] == 2
        assert state["ballots_submitted"] == 0
        assert state["min_score"] == 1
        assert state["max_score"] == 5
        assert len(state["entry_ids"]) == 3

    def test_default_single_voter(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {})
        assert state["voter_labels"] == ["default"]
        assert state["ballots_required"] == 1

    def test_custom_voter_labels_preserved(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"voter_labels": ["Alice", "Bob"]})
        assert state["voter_labels"] == ["Alice", "Bob"]
        assert state["ballots_required"] == 2


class TestScoreVoting:
    def test_valid_ballot_accepted(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {})
        payload = _make_scores(entries, [5, 3, 1])
        state = engine.submit_vote(state, "default", payload)
        assert state["ballots_submitted"] == 1

    def test_missing_entry_raises(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {})
        # Only score 2 of 3 entries
        payload = {"scores": [{"entry_id": str(entries[0].id), "score": 3}]}
        with pytest.raises(ValidationError, match="score"):
            engine.submit_vote(state, "default", payload)

    def test_out_of_range_score_raises(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"min_score": 1, "max_score": 5})
        payload = _make_scores(entries, [6, 3, 1])  # 6 > max of 5
        with pytest.raises(ValidationError, match="range"):
            engine.submit_vote(state, "default", payload)

    def test_duplicate_voter_raises(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"voter_labels": _voter_labels(2)})
        payload = _make_scores(entries, [5, 3, 1])
        state = engine.submit_vote(state, "Voter 1", payload)
        with pytest.raises(ValidationError, match="already"):
            engine.submit_vote(state, "Voter 1", payload)

    def test_unknown_voter_rejected(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"voter_labels": ["Alice", "Bob"]})
        payload = _make_scores(entries, [5, 3, 1])
        with pytest.raises(ValidationError, match="Unknown voter"):
            engine.submit_vote(state, "Charlie", payload)

    def test_get_vote_context_unknown_voter_rejected(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"voter_labels": ["Alice", "Bob"]})
        with pytest.raises(ValidationError, match="Unknown voter"):
            engine.get_vote_context(state, "Charlie")

    def test_already_voted_context(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"voter_labels": _voter_labels(2)})
        payload = _make_scores(entries, [5, 3, 1])
        state = engine.submit_vote(state, "Voter 1", payload)
        ctx = engine.get_vote_context(state, "Voter 1")
        assert isinstance(ctx, AlreadyVotedContext)

    def test_ballot_context_for_new_voter(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"voter_labels": _voter_labels(2)})
        ctx = engine.get_vote_context(state, "Voter 1")
        assert isinstance(ctx, BallotContext)
        assert ctx.ballot_type == "score"
        assert ctx.ballots_submitted == 0
        assert ctx.ballots_required == 2
        assert len(ctx.entries) == 3


class TestScoreFullFlow:
    def test_single_voter_flow(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {})
        assert not engine.is_complete(state)
        payload = _make_scores(entries, [5, 3, 1])
        state = engine.submit_vote(state, "default", payload)
        assert engine.is_complete(state)
        result = engine.compute_result(state, entries)
        assert len(result.winner_ids) == 1
        assert len(result.ranking) == 3

    def test_multi_voter_flow(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"voter_labels": _voter_labels(3)})
        for i in range(3):
            assert not engine.is_complete(state)
            payload = _make_scores(entries, [5, 3, 1])
            state = engine.submit_vote(state, f"Voter {i + 1}", payload)
        assert engine.is_complete(state)

    def test_completed_context_after_all_votes(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {})
        payload = _make_scores(entries, [5, 3, 1])
        state = engine.submit_vote(state, "default", payload)
        # Once complete, get_vote_context returns CompletedContext for any voter
        ctx = engine.get_vote_context(state, "default")
        assert isinstance(ctx, CompletedContext)


class TestScoreResult:
    def test_correct_averages(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"voter_labels": _voter_labels(2)})
        # Voter 1: [5, 3, 1], Voter 2: [3, 5, 1] → averages: [4.0, 4.0, 1.0]
        state = engine.submit_vote(state, "Voter 1", _make_scores(entries, [5, 3, 1]))
        state = engine.submit_vote(state, "Voter 2", _make_scores(entries, [3, 5, 1]))
        result = engine.compute_result(state, entries)
        # Entries 0 and 1 tied at avg 4.0, entry 2 at 1.0
        ranks = sorted(r["rank"] for r in result.ranking)
        assert ranks == [1, 1, 3]

    def test_tied_entries_share_rank(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {})
        # All same score → all tied at rank 1
        state = engine.submit_vote(state, "default", _make_scores(entries, [3, 3, 3]))
        result = engine.compute_result(state, entries)
        assert len(result.winner_ids) == 3
        ranks = [r["rank"] for r in result.ranking]
        assert all(r == 1 for r in ranks)

    def test_ordering_by_average_desc(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {})
        state = engine.submit_vote(state, "default", _make_scores(entries, [1, 5, 3]))
        result = engine.compute_result(state, entries)
        # Entry 1 (score 5) should be rank 1
        rank_1 = [r for r in result.ranking if r["rank"] == 1]
        assert len(rank_1) == 1
        assert rank_1[0]["entry_id"] == str(entries[1].id)


class TestScoreReplayState:
    def test_replay_with_no_votes_equals_initialize(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        config = {"voter_labels": _voter_labels(2)}
        initial = engine.initialize(entries, config)
        replayed = engine.replay_state(entries, config, [])
        assert replayed == initial

    def test_replay_with_single_vote_equals_sequential_submit(self) -> None:
        from app.schemas.tournament import Vote

        engine = ScoreEngine()
        entries = _make_entries(3)
        config = {"voter_labels": _voter_labels(2)}
        sequential = engine.submit_vote(
            engine.initialize(entries, config),
            "Voter 1",
            _make_scores(entries, [5, 3, 1]),
        )
        votes = [Vote(voter_label="Voter 1", payload=_make_scores(entries, [5, 3, 1]))]
        replayed = engine.replay_state(entries, config, votes)
        assert replayed == sequential

    def test_replay_with_subset_of_votes_is_not_complete(self) -> None:
        from app.schemas.tournament import Vote

        engine = ScoreEngine()
        entries = _make_entries(3)
        config = {"voter_labels": _voter_labels(3)}
        votes = [
            Vote(voter_label="Voter 1", payload=_make_scores(entries, [5, 3, 1])),
            Vote(voter_label="Voter 2", payload=_make_scores(entries, [3, 5, 1])),
        ]
        state = engine.replay_state(entries, config, votes)
        assert not engine.is_complete(state)
        assert state["ballots_submitted"] == 2

    def test_replay_omitting_a_vote_allows_resubmit(self) -> None:
        """If voter's vote is filtered out of active_votes, they can submit again."""
        from app.schemas.tournament import Vote

        engine = ScoreEngine()
        entries = _make_entries(3)
        config = {"voter_labels": _voter_labels(2)}
        # Submit both votes, then replay with only one
        votes = [
            Vote(voter_label="Voter 1", payload=_make_scores(entries, [5, 3, 1])),
            Vote(voter_label="Voter 2", payload=_make_scores(entries, [3, 5, 1])),
        ]
        full_state = engine.replay_state(entries, config, votes)
        assert engine.is_complete(full_state)

        # Now replay with only Voter 1's vote — Voter 2 should be able to vote
        partial_state = engine.replay_state(entries, config, votes[:1])
        assert not engine.is_complete(partial_state)
        # Re-submit Voter 2 on top of the partial state
        new_state = engine.submit_vote(
            partial_state,
            "Voter 2",
            _make_scores(entries, [1, 1, 5]),
        )
        assert engine.is_complete(new_state)

    def test_replay_sorts_votes_by_submitted_at(self) -> None:
        """Votes passed out of chronological order are replayed in submission order."""
        from datetime import UTC, datetime

        from app.schemas.tournament import Vote

        engine = ScoreEngine()
        entries = _make_entries(2)
        config = {"voter_labels": _voter_labels(2)}
        early = Vote(
            voter_label="Voter 1",
            submitted_at=datetime(2026, 4, 15, 10, 0, 0, tzinfo=UTC),
            payload=_make_scores(entries, [5, 1]),
        )
        late = Vote(
            voter_label="Voter 2",
            submitted_at=datetime(2026, 4, 15, 11, 0, 0, tzinfo=UTC),
            payload=_make_scores(entries, [1, 5]),
        )
        # Pass in reverse order — replay should still work
        state = engine.replay_state(entries, config, [late, early])
        assert engine.is_complete(state)
        # Both voters recorded
        voted = {v["voter_label"] for v in state["votes"]}
        assert voted == {"Voter 1", "Voter 2"}
