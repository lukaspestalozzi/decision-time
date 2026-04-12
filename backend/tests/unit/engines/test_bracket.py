"""Unit tests for the bracket tournament engine."""

import uuid
from typing import Any

import pytest

from app.engines.base import BracketMatchupContext, CompletedContext
from app.engines.bracket import BracketEngine
from app.exceptions import ValidationError
from app.schemas.tournament import TournamentEntry


def _make_entries(n: int) -> list[TournamentEntry]:
    """Create n TournamentEntry objects with unique IDs."""
    return [
        TournamentEntry(
            option_id=uuid.uuid4(),
            option_snapshot={"name": f"Option {i + 1}", "id": str(uuid.uuid4())},
        )
        for i in range(n)
    ]


def _vote_through(engine: BracketEngine, state: dict[str, Any], matchups_to_vote: int) -> dict[str, Any]:
    """Vote through the given number of matchups, always picking entry_a as winner."""
    for _ in range(matchups_to_vote):
        ctx = engine.get_vote_context(state, "default")
        assert isinstance(ctx, BracketMatchupContext)
        state = engine.submit_vote(
            state,
            "default",
            {"matchup_id": ctx.matchup_id, "winner_entry_id": ctx.entry_a["id"]},
        )
    return state


class TestBracketValidateConfig:
    def test_default_config_is_valid(self) -> None:
        engine = BracketEngine()
        errors = engine.validate_config({})
        assert errors == []

    def test_custom_config_is_valid(self) -> None:
        engine = BracketEngine()
        errors = engine.validate_config({"shuffle_seed": False, "third_place_match": False})
        assert errors == []


class TestBracketInitialize:
    def test_2_entries_creates_1_round_1_matchup(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(2)
        state = engine.initialize(entries, {"shuffle_seed": False})
        assert state["bracket_size"] == 2
        assert state["total_rounds"] == 1
        assert len(state["rounds"]) == 1
        assert len(state["rounds"][0]["matchups"]) == 1
        assert state["rounds"][0]["name"] == "Final"

    def test_3_entries_creates_bracket_of_4_with_1_bye(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"shuffle_seed": False})
        assert state["bracket_size"] == 4
        assert state["total_rounds"] == 2
        matchups = state["rounds"][0]["matchups"]
        assert len(matchups) == 2
        byes = [m for m in matchups if m["is_bye"]]
        assert len(byes) == 1

    def test_4_entries_creates_2_rounds_no_byes(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(4)
        state = engine.initialize(entries, {"shuffle_seed": False})
        assert state["bracket_size"] == 4
        assert state["total_rounds"] == 2
        matchups = state["rounds"][0]["matchups"]
        assert len(matchups) == 2
        assert all(not m["is_bye"] for m in matchups)

    def test_5_entries_creates_bracket_of_8_with_3_byes(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(5)
        state = engine.initialize(entries, {"shuffle_seed": False})
        assert state["bracket_size"] == 8
        assert state["total_rounds"] == 3
        matchups = state["rounds"][0]["matchups"]
        assert len(matchups) == 4
        byes = [m for m in matchups if m["is_bye"]]
        assert len(byes) == 3

    def test_8_entries_creates_3_rounds_no_byes(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(8)
        state = engine.initialize(entries, {"shuffle_seed": False})
        assert state["bracket_size"] == 8
        assert state["total_rounds"] == 3
        matchups = state["rounds"][0]["matchups"]
        assert len(matchups) == 4
        assert all(not m["is_bye"] for m in matchups)

    def test_byes_have_winner_preset(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"shuffle_seed": False})
        matchups = state["rounds"][0]["matchups"]
        for m in matchups:
            if m["is_bye"]:
                assert m["winner_id"] is not None
                assert m["entry_b_id"] is None
                assert m["winner_id"] == m["entry_a_id"]

    def test_all_entries_appear_exactly_once_in_round_1(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(5)
        state = engine.initialize(entries, {"shuffle_seed": False})
        entry_ids = {str(e.id) for e in entries}
        found_ids: set[str] = set()
        for m in state["rounds"][0]["matchups"]:
            found_ids.add(m["entry_a_id"])
            if m["entry_b_id"] is not None:
                found_ids.add(m["entry_b_id"])
        assert found_ids == entry_ids

    def test_round_names_for_8_entry_bracket(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(8)
        state = engine.initialize(entries, {"shuffle_seed": False})
        # Vote through all to generate all rounds
        state = _vote_through(engine, state, 4 + 2 + 1)
        round_names = [r["name"] for r in state["rounds"]]
        assert round_names == ["Quarter-finals", "Semi-finals", "Final"]

    def test_round_names_for_16_entry_bracket(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(16)
        state = engine.initialize(entries, {"shuffle_seed": False})
        state = _vote_through(engine, state, 8 + 4 + 2 + 1)
        round_names = [r["name"] for r in state["rounds"]]
        assert round_names == ["Round of 16", "Quarter-finals", "Semi-finals", "Final"]

    def test_shuffle_seed_true_randomizes_order(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(8)
        # Run multiple times — at least one should differ from the natural order
        orders: set[tuple[str, ...]] = set()
        for _ in range(10):
            state = engine.initialize(entries, {"shuffle_seed": True})
            first_round_a_ids = tuple(m["entry_a_id"] for m in state["rounds"][0]["matchups"])
            orders.add(first_round_a_ids)
        # With 8 entries, probability of getting the same order 10 times is negligible
        assert len(orders) > 1


class TestBracketVoting:
    def test_get_vote_context_returns_first_undecided_matchup(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(4)
        state = engine.initialize(entries, {"shuffle_seed": False})
        ctx = engine.get_vote_context(state, "default")
        assert isinstance(ctx, BracketMatchupContext)
        assert ctx.round == 1
        assert ctx.match_number == 1
        assert ctx.matches_in_round == 2

    def test_submit_vote_sets_winner(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(4)
        state = engine.initialize(entries, {"shuffle_seed": False})
        ctx = engine.get_vote_context(state, "default")
        assert isinstance(ctx, BracketMatchupContext)
        state = engine.submit_vote(
            state,
            "default",
            {"matchup_id": ctx.matchup_id, "winner_entry_id": ctx.entry_a["id"]},
        )
        matchup = state["rounds"][0]["matchups"][0]
        assert matchup["winner_id"] == ctx.entry_a["id"]

    def test_submit_vote_wrong_matchup_id_raises(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(4)
        state = engine.initialize(entries, {"shuffle_seed": False})
        with pytest.raises(ValidationError):
            engine.submit_vote(
                state,
                "default",
                {"matchup_id": str(uuid.uuid4()), "winner_entry_id": str(uuid.uuid4())},
            )

    def test_submit_vote_invalid_winner_raises(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(4)
        state = engine.initialize(entries, {"shuffle_seed": False})
        ctx = engine.get_vote_context(state, "default")
        assert isinstance(ctx, BracketMatchupContext)
        with pytest.raises(ValidationError):
            engine.submit_vote(
                state,
                "default",
                {"matchup_id": ctx.matchup_id, "winner_entry_id": str(uuid.uuid4())},
            )

    def test_submit_vote_already_decided_raises(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(4)
        state = engine.initialize(entries, {"shuffle_seed": False})
        ctx = engine.get_vote_context(state, "default")
        assert isinstance(ctx, BracketMatchupContext)
        state = engine.submit_vote(
            state,
            "default",
            {"matchup_id": ctx.matchup_id, "winner_entry_id": ctx.entry_a["id"]},
        )
        # Try to vote on the same matchup again
        with pytest.raises(ValidationError):
            engine.submit_vote(
                state,
                "default",
                {"matchup_id": ctx.matchup_id, "winner_entry_id": ctx.entry_a["id"]},
            )

    def test_round_advances_when_all_matchups_decided(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(4)
        state = engine.initialize(entries, {"shuffle_seed": False})
        assert state["current_round"] == 1
        # Vote both matchups in round 1
        state = _vote_through(engine, state, 2)
        assert state["current_round"] == 2
        assert len(state["rounds"]) == 2

    def test_next_round_has_correct_winners(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(4)
        state = engine.initialize(entries, {"shuffle_seed": False})
        # Get the matchups and vote for entry_a in both
        r1_winners = []
        for _ in range(2):
            ctx = engine.get_vote_context(state, "default")
            assert isinstance(ctx, BracketMatchupContext)
            r1_winners.append(ctx.entry_a["id"])
            state = engine.submit_vote(
                state,
                "default",
                {"matchup_id": ctx.matchup_id, "winner_entry_id": ctx.entry_a["id"]},
            )
        # Round 2 matchup should have the two winners
        r2_matchup = state["rounds"][1]["matchups"][0]
        assert r2_matchup["entry_a_id"] in r1_winners
        assert r2_matchup["entry_b_id"] in r1_winners

    def test_vote_context_after_completion_returns_completed(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(2)
        state = engine.initialize(entries, {"shuffle_seed": False})
        state = _vote_through(engine, state, 1)
        ctx = engine.get_vote_context(state, "default")
        assert isinstance(ctx, CompletedContext)


class TestBracketFullFlow:
    def test_2_entry_bracket_single_matchup(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(2)
        state = engine.initialize(entries, {"shuffle_seed": False})
        assert not engine.is_complete(state)
        state = _vote_through(engine, state, 1)
        assert engine.is_complete(state)
        result = engine.compute_result(state, entries)
        assert len(result.winner_ids) == 1
        assert len(result.ranking) == 2

    def test_4_entry_bracket_two_rounds(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(4)
        state = engine.initialize(entries, {"shuffle_seed": False})
        # Round 1: 2 matchups
        state = _vote_through(engine, state, 2)
        assert not engine.is_complete(state)
        # Round 2 (Final): 1 matchup
        state = _vote_through(engine, state, 1)
        assert engine.is_complete(state)
        result = engine.compute_result(state, entries)
        assert len(result.winner_ids) == 1
        assert len(result.ranking) == 4
        ranks = sorted(r["rank"] for r in result.ranking)
        assert ranks == [1, 2, 3, 3]

    def test_5_entry_bracket_with_byes(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(5)
        state = engine.initialize(entries, {"shuffle_seed": False})
        # Round 1: 4 matchups, 3 are byes, 1 real
        real_matchups_r1 = [m for m in state["rounds"][0]["matchups"] if not m["is_bye"]]
        assert len(real_matchups_r1) == 1
        # Vote the 1 real matchup
        state = _vote_through(engine, state, 1)
        assert not engine.is_complete(state)
        # Round 2: 2 matchups, all real
        assert state["current_round"] == 2
        state = _vote_through(engine, state, 2)
        assert not engine.is_complete(state)
        # Round 3 (Final): 1 matchup
        state = _vote_through(engine, state, 1)
        assert engine.is_complete(state)
        result = engine.compute_result(state, entries)
        assert len(result.winner_ids) == 1
        assert len(result.ranking) == 5


class TestBracketResult:
    def test_result_has_single_winner(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(4)
        state = engine.initialize(entries, {"shuffle_seed": False})
        state = _vote_through(engine, state, 3)
        result = engine.compute_result(state, entries)
        assert len(result.winner_ids) == 1

    def test_ranking_4_entries_correct_ranks(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(4)
        state = engine.initialize(entries, {"shuffle_seed": False})
        state = _vote_through(engine, state, 3)
        result = engine.compute_result(state, entries)
        ranks = sorted(r["rank"] for r in result.ranking)
        assert ranks == [1, 2, 3, 3]

    def test_ranking_8_entries_correct_ranks(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(8)
        state = engine.initialize(entries, {"shuffle_seed": False})
        state = _vote_through(engine, state, 7)
        result = engine.compute_result(state, entries)
        ranks = sorted(r["rank"] for r in result.ranking)
        assert ranks == [1, 2, 3, 3, 5, 5, 5, 5]

    def test_byes_do_not_appear_as_losers_in_ranking(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"shuffle_seed": False})
        # 1 bye + 1 real in round 1, then 1 final
        state = _vote_through(engine, state, 1 + 1)
        result = engine.compute_result(state, entries)
        # Only 3 real entries should appear in ranking
        assert len(result.ranking) == 3
        entry_ids = {str(e.id) for e in entries}
        ranked_ids = {r["entry_id"] for r in result.ranking}
        assert ranked_ids == entry_ids


class TestBracketIsComplete:
    def test_not_complete_after_initialization(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(4)
        state = engine.initialize(entries, {"shuffle_seed": False})
        assert not engine.is_complete(state)

    def test_complete_after_final_decided(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(4)
        state = engine.initialize(entries, {"shuffle_seed": False})
        state = _vote_through(engine, state, 3)
        assert engine.is_complete(state)
