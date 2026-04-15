"""Unit tests for the multivote tournament engine."""

import uuid

import pytest

from app.engines.base import AlreadyVotedContext, BallotContext
from app.engines.multivote import MultivoteEngine
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


def _make_allocations(entries: list[TournamentEntry], votes: list[int]) -> dict:
    return {"allocations": [{"entry_id": str(e.id), "votes": v} for e, v in zip(entries, votes, strict=True)]}


def _voter_labels(n: int) -> list[str]:
    return [f"Voter {i + 1}" for i in range(n)]


class TestMultivoteValidateConfig:
    def test_default_config_is_valid(self) -> None:
        engine = MultivoteEngine()
        assert engine.validate_config({}) == []

    def test_custom_config_is_valid(self) -> None:
        engine = MultivoteEngine()
        assert engine.validate_config({"total_votes": 20, "max_per_option": 5, "voter_labels": _voter_labels(3)}) == []


class TestMultivoteInitialize:
    def test_total_votes_computed_when_null(self) -> None:
        engine = MultivoteEngine()
        entries = _make_entries(5)
        state = engine.initialize(entries, {})
        assert state["total_votes"] == 10  # 5 entries * 2

    def test_total_votes_from_config(self) -> None:
        engine = MultivoteEngine()
        entries = _make_entries(5)
        state = engine.initialize(entries, {"total_votes": 20})
        assert state["total_votes"] == 20

    def test_correct_state_structure(self) -> None:
        engine = MultivoteEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"voter_labels": _voter_labels(2)})
        assert state["voter_labels"] == ["Voter 1", "Voter 2"]
        assert state["ballots_required"] == 2
        assert state["ballots_submitted"] == 0
        assert state["total_votes"] == 6  # 3 * 2
        assert state["max_per_option"] is None
        assert len(state["entry_ids"]) == 3

    def test_default_single_voter(self) -> None:
        engine = MultivoteEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {})
        assert state["voter_labels"] == ["default"]
        assert state["ballots_required"] == 1

    def test_custom_voter_labels_preserved(self) -> None:
        engine = MultivoteEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"voter_labels": ["Alice", "Bob"]})
        assert state["voter_labels"] == ["Alice", "Bob"]
        assert state["ballots_required"] == 2


class TestMultivoteVoting:
    def test_valid_allocation_accepted(self) -> None:
        engine = MultivoteEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {})  # total_votes = 6
        payload = _make_allocations(entries, [3, 2, 1])
        state = engine.submit_vote(state, "default", payload)
        assert state["ballots_submitted"] == 1

    def test_wrong_sum_raises(self) -> None:
        engine = MultivoteEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {})  # total_votes = 6
        payload = _make_allocations(entries, [3, 2, 0])  # sum = 5, not 6
        with pytest.raises(ValidationError, match="total_votes"):
            engine.submit_vote(state, "default", payload)

    def test_exceeds_max_per_option_raises(self) -> None:
        engine = MultivoteEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"max_per_option": 3})  # total_votes = 6, max = 3
        payload = _make_allocations(entries, [4, 1, 1])  # 4 > max of 3
        with pytest.raises(ValidationError, match="max_per_option"):
            engine.submit_vote(state, "default", payload)

    def test_duplicate_voter_raises(self) -> None:
        engine = MultivoteEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"voter_labels": _voter_labels(2)})
        payload = _make_allocations(entries, [2, 2, 2])
        state = engine.submit_vote(state, "Voter 1", payload)
        with pytest.raises(ValidationError, match="already"):
            engine.submit_vote(state, "Voter 1", payload)

    def test_unknown_voter_rejected(self) -> None:
        engine = MultivoteEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"voter_labels": ["Alice", "Bob"]})
        payload = _make_allocations(entries, [2, 2, 2])
        with pytest.raises(ValidationError, match="Unknown voter"):
            engine.submit_vote(state, "Charlie", payload)

    def test_get_vote_context_unknown_voter_rejected(self) -> None:
        engine = MultivoteEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"voter_labels": ["Alice", "Bob"]})
        with pytest.raises(ValidationError, match="Unknown voter"):
            engine.get_vote_context(state, "Charlie")

    def test_partial_allocation_ok(self) -> None:
        """Can vote for subset of entries — unlisted get 0 implicitly."""
        engine = MultivoteEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {})  # total_votes = 6
        # Only allocate to 2 of 3 entries
        payload = {
            "allocations": [
                {"entry_id": str(entries[0].id), "votes": 4},
                {"entry_id": str(entries[1].id), "votes": 2},
            ]
        }
        state = engine.submit_vote(state, "default", payload)
        assert state["ballots_submitted"] == 1

    def test_ballot_context_for_new_voter(self) -> None:
        engine = MultivoteEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"voter_labels": _voter_labels(2)})
        ctx = engine.get_vote_context(state, "Voter 1")
        assert isinstance(ctx, BallotContext)
        assert ctx.ballot_type == "multivote"
        assert ctx.ballots_required == 2

    def test_already_voted_context(self) -> None:
        engine = MultivoteEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"voter_labels": _voter_labels(2)})
        payload = _make_allocations(entries, [2, 2, 2])
        state = engine.submit_vote(state, "Voter 1", payload)
        ctx = engine.get_vote_context(state, "Voter 1")
        assert isinstance(ctx, AlreadyVotedContext)


class TestMultivoteFullFlow:
    def test_single_voter_flow(self) -> None:
        engine = MultivoteEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {})
        payload = _make_allocations(entries, [3, 2, 1])
        state = engine.submit_vote(state, "default", payload)
        assert engine.is_complete(state)
        result = engine.compute_result(state, entries)
        assert len(result.winner_ids) == 1

    def test_multi_voter_flow(self) -> None:
        engine = MultivoteEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"voter_labels": _voter_labels(2)})
        state = engine.submit_vote(state, "Voter 1", _make_allocations(entries, [3, 2, 1]))
        assert not engine.is_complete(state)
        state = engine.submit_vote(state, "Voter 2", _make_allocations(entries, [1, 2, 3]))
        assert engine.is_complete(state)


class TestMultivoteResult:
    def test_correct_totals(self) -> None:
        engine = MultivoteEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"voter_labels": _voter_labels(2)})
        # V1: [3,2,1], V2: [1,2,3] → totals: [4,4,4]
        state = engine.submit_vote(state, "Voter 1", _make_allocations(entries, [3, 2, 1]))
        state = engine.submit_vote(state, "Voter 2", _make_allocations(entries, [1, 2, 3]))
        result = engine.compute_result(state, entries)
        # All tied
        assert len(result.winner_ids) == 3
        ranks = [r["rank"] for r in result.ranking]
        assert all(r == 1 for r in ranks)

    def test_ordering_by_total_desc(self) -> None:
        engine = MultivoteEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {})
        state = engine.submit_vote(state, "default", _make_allocations(entries, [1, 4, 1]))
        result = engine.compute_result(state, entries)
        rank_1 = [r for r in result.ranking if r["rank"] == 1]
        assert len(rank_1) == 1
        assert rank_1[0]["entry_id"] == str(entries[1].id)
