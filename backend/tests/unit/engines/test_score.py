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


class TestScoreValidateConfig:
    def test_default_config_is_valid(self) -> None:
        engine = ScoreEngine()
        assert engine.validate_config({}) == []

    def test_custom_config_is_valid(self) -> None:
        engine = ScoreEngine()
        assert engine.validate_config({"min_score": 0, "max_score": 10, "voter_count": 3}) == []


class TestScoreInitialize:
    def test_correct_state_structure(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"voter_count": 2})
        assert state["ballots_required"] == 2
        assert state["ballots_submitted"] == 0
        assert state["min_score"] == 1
        assert state["max_score"] == 5
        assert len(state["entry_ids"]) == 3

    def test_default_voter_count_is_1(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {})
        assert state["ballots_required"] == 1


class TestScoreVoting:
    def test_valid_ballot_accepted(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {})
        payload = _make_scores(entries, [5, 3, 1])
        state = engine.submit_vote(state, "Voter 1", payload)
        assert state["ballots_submitted"] == 1

    def test_missing_entry_raises(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {})
        # Only score 2 of 3 entries
        payload = {"scores": [{"entry_id": str(entries[0].id), "score": 3}]}
        with pytest.raises(ValidationError, match="score"):
            engine.submit_vote(state, "Voter 1", payload)

    def test_out_of_range_score_raises(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"min_score": 1, "max_score": 5})
        payload = _make_scores(entries, [6, 3, 1])  # 6 > max of 5
        with pytest.raises(ValidationError, match="range"):
            engine.submit_vote(state, "Voter 1", payload)

    def test_duplicate_voter_raises(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"voter_count": 2})
        payload = _make_scores(entries, [5, 3, 1])
        state = engine.submit_vote(state, "Voter 1", payload)
        with pytest.raises(ValidationError, match="already"):
            engine.submit_vote(state, "Voter 1", payload)

    def test_already_voted_context(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"voter_count": 2})
        payload = _make_scores(entries, [5, 3, 1])
        state = engine.submit_vote(state, "Voter 1", payload)
        ctx = engine.get_vote_context(state, "Voter 1")
        assert isinstance(ctx, AlreadyVotedContext)

    def test_ballot_context_for_new_voter(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"voter_count": 2})
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
        state = engine.submit_vote(state, "Voter 1", payload)
        assert engine.is_complete(state)
        result = engine.compute_result(state, entries)
        assert len(result.winner_ids) == 1
        assert len(result.ranking) == 3

    def test_multi_voter_flow(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"voter_count": 3})
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
        state = engine.submit_vote(state, "Voter 1", payload)
        ctx = engine.get_vote_context(state, "Voter 2")
        assert isinstance(ctx, CompletedContext)


class TestScoreResult:
    def test_correct_averages(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"voter_count": 2})
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
        state = engine.submit_vote(state, "Voter 1", _make_scores(entries, [3, 3, 3]))
        result = engine.compute_result(state, entries)
        assert len(result.winner_ids) == 3
        ranks = [r["rank"] for r in result.ranking]
        assert all(r == 1 for r in ranks)

    def test_ordering_by_average_desc(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {})
        state = engine.submit_vote(state, "Voter 1", _make_scores(entries, [1, 5, 3]))
        result = engine.compute_result(state, entries)
        # Entry 1 (score 5) should be rank 1
        rank_1 = [r for r in result.ranking if r["rank"] == 1]
        assert len(rank_1) == 1
        assert rank_1[0]["entry_id"] == str(entries[1].id)
