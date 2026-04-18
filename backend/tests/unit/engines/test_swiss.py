"""Unit tests for the Swiss tournament engine."""

import math
import uuid
from collections.abc import Callable
from typing import Any

import pytest

from app.engines.base import CompletedContext, SwissMatchupContext
from app.engines.swiss import SwissEngine
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


def _always_a_wins(ctx: SwissMatchupContext) -> dict[str, Any]:
    return {"matchup_id": ctx.matchup_id, "result": "a_wins"}


def _play_through(
    engine: SwissEngine,
    state: dict[str, Any],
    decision: Callable[[SwissMatchupContext], dict[str, Any]] = _always_a_wins,
) -> dict[str, Any]:
    """Advance the tournament by repeatedly fetching and submitting votes."""
    guard = 0
    while not engine.is_complete(state):
        ctx = engine.get_vote_context(state, "default")
        if isinstance(ctx, CompletedContext):
            break
        assert isinstance(ctx, SwissMatchupContext)
        state = engine.submit_vote(state, "default", decision(ctx))
        guard += 1
        assert guard < 1000, "infinite loop guard tripped"
    return state


class TestSwissValidateConfig:
    def test_default_config_is_valid(self) -> None:
        engine = SwissEngine()
        assert engine.validate_config({}) == []

    def test_custom_config_is_valid(self) -> None:
        engine = SwissEngine()
        assert engine.validate_config({"total_rounds": 5, "allow_draws": False, "shuffle_seed": False}) == []

    def test_multi_voter_rejected(self) -> None:
        engine = SwissEngine()
        errors = engine.validate_config({"voter_labels": ["Alice", "Bob"]})
        assert errors and "single voter" in errors[0]

    def test_zero_rounds_rejected(self) -> None:
        engine = SwissEngine()
        errors = engine.validate_config({"total_rounds": 0})
        assert errors and "total_rounds" in errors[0]


class TestSwissInitialize:
    def test_requires_at_least_2_entries(self) -> None:
        engine = SwissEngine()
        with pytest.raises(ValidationError):
            engine.initialize(_make_entries(1), {})

    @pytest.mark.parametrize(
        "n,expected_rounds",
        [(2, 1), (3, 2), (4, 2), (5, 3), (8, 3), (9, 4), (16, 4)],
    )
    def test_default_total_rounds_is_ceil_log2(self, n: int, expected_rounds: int) -> None:
        engine = SwissEngine()
        state = engine.initialize(_make_entries(n), {"shuffle_seed": False})
        assert state["total_rounds"] == expected_rounds
        assert state["total_rounds"] == max(1, math.ceil(math.log2(n)))

    def test_explicit_total_rounds_overrides(self) -> None:
        engine = SwissEngine()
        state = engine.initialize(_make_entries(8), {"total_rounds": 2, "shuffle_seed": False})
        assert state["total_rounds"] == 2

    def test_round_1_pairs_every_entry(self) -> None:
        engine = SwissEngine()
        entries = _make_entries(4)
        state = engine.initialize(entries, {"shuffle_seed": False})
        seen: set[str] = set()
        for m in state["rounds"][0]["matchups"]:
            seen.add(m["entry_a_id"])
            if m["entry_b_id"] is not None:
                seen.add(m["entry_b_id"])
        assert seen == {str(e.id) for e in entries}

    def test_odd_entries_produce_exactly_one_bye(self) -> None:
        engine = SwissEngine()
        state = engine.initialize(_make_entries(5), {"shuffle_seed": False})
        byes = [m for m in state["rounds"][0]["matchups"] if m["is_bye"]]
        assert len(byes) == 1
        assert byes[0]["entry_b_id"] is None
        assert byes[0]["result"] == "bye"

    def test_bye_entry_receives_point(self) -> None:
        engine = SwissEngine()
        state = engine.initialize(_make_entries(3), {"shuffle_seed": False})
        bye = next(m for m in state["rounds"][0]["matchups"] if m["is_bye"])
        assert state["standings"][bye["entry_a_id"]]["points"] == 1.0
        assert state["standings"][bye["entry_a_id"]]["byes"] == 1

    def test_even_entries_produce_no_byes(self) -> None:
        engine = SwissEngine()
        state = engine.initialize(_make_entries(8), {"shuffle_seed": False})
        assert all(not m["is_bye"] for m in state["rounds"][0]["matchups"])

    def test_shuffle_seed_is_deterministic(self) -> None:
        engine = SwissEngine()
        entries = _make_entries(8)
        state1 = engine.initialize(entries, {"shuffle_seed": True})
        state2 = engine.initialize(entries, {"shuffle_seed": True})
        pairs1 = [(m["entry_a_id"], m["entry_b_id"]) for m in state1["rounds"][0]["matchups"]]
        pairs2 = [(m["entry_a_id"], m["entry_b_id"]) for m in state2["rounds"][0]["matchups"]]
        assert pairs1 == pairs2


class TestSwissVoting:
    def test_vote_context_returns_first_undecided(self) -> None:
        engine = SwissEngine()
        state = engine.initialize(_make_entries(4), {"shuffle_seed": False})
        ctx = engine.get_vote_context(state, "default")
        assert isinstance(ctx, SwissMatchupContext)
        assert ctx.round == 1
        assert ctx.match_number == 1
        assert ctx.matches_in_round == 2
        assert ctx.allow_draws is True

    def test_vote_context_includes_standings_snapshot(self) -> None:
        engine = SwissEngine()
        state = engine.initialize(_make_entries(4), {"shuffle_seed": False})
        ctx = engine.get_vote_context(state, "default")
        assert isinstance(ctx, SwissMatchupContext)
        assert len(ctx.standings) == 4
        assert all("points" in s and "rank" in s for s in ctx.standings)

    def test_a_wins_updates_standings(self) -> None:
        engine = SwissEngine()
        state = engine.initialize(_make_entries(4), {"shuffle_seed": False})
        ctx = engine.get_vote_context(state, "default")
        assert isinstance(ctx, SwissMatchupContext)
        state = engine.submit_vote(state, "default", {"matchup_id": ctx.matchup_id, "result": "a_wins"})
        assert state["standings"][ctx.entry_a["id"]]["points"] == 1.0
        assert state["standings"][ctx.entry_a["id"]]["wins"] == 1
        assert state["standings"][ctx.entry_b["id"]]["losses"] == 1

    def test_draw_splits_half_point(self) -> None:
        engine = SwissEngine()
        state = engine.initialize(_make_entries(4), {"shuffle_seed": False})
        ctx = engine.get_vote_context(state, "default")
        assert isinstance(ctx, SwissMatchupContext)
        state = engine.submit_vote(state, "default", {"matchup_id": ctx.matchup_id, "result": "draw"})
        assert state["standings"][ctx.entry_a["id"]]["points"] == 0.5
        assert state["standings"][ctx.entry_b["id"]]["points"] == 0.5
        assert state["standings"][ctx.entry_a["id"]]["draws"] == 1

    def test_draw_rejected_when_disabled(self) -> None:
        engine = SwissEngine()
        state = engine.initialize(_make_entries(4), {"allow_draws": False, "shuffle_seed": False})
        ctx = engine.get_vote_context(state, "default")
        assert isinstance(ctx, SwissMatchupContext)
        assert ctx.allow_draws is False
        with pytest.raises(ValidationError, match="draws are not allowed"):
            engine.submit_vote(state, "default", {"matchup_id": ctx.matchup_id, "result": "draw"})

    def test_invalid_result_rejected(self) -> None:
        engine = SwissEngine()
        state = engine.initialize(_make_entries(4), {"shuffle_seed": False})
        ctx = engine.get_vote_context(state, "default")
        assert isinstance(ctx, SwissMatchupContext)
        with pytest.raises(ValidationError, match="Invalid result"):
            engine.submit_vote(state, "default", {"matchup_id": ctx.matchup_id, "result": "tie"})

    def test_unknown_matchup_rejected(self) -> None:
        engine = SwissEngine()
        state = engine.initialize(_make_entries(4), {"shuffle_seed": False})
        with pytest.raises(ValidationError, match="not found"):
            engine.submit_vote(state, "default", {"matchup_id": str(uuid.uuid4()), "result": "a_wins"})

    def test_already_decided_matchup_rejected(self) -> None:
        engine = SwissEngine()
        state = engine.initialize(_make_entries(4), {"shuffle_seed": False})
        ctx = engine.get_vote_context(state, "default")
        assert isinstance(ctx, SwissMatchupContext)
        state = engine.submit_vote(state, "default", {"matchup_id": ctx.matchup_id, "result": "a_wins"})
        with pytest.raises(ValidationError, match="already decided"):
            engine.submit_vote(state, "default", {"matchup_id": ctx.matchup_id, "result": "b_wins"})

    def test_voting_on_bye_rejected(self) -> None:
        engine = SwissEngine()
        state = engine.initialize(_make_entries(3), {"shuffle_seed": False})
        bye = next(m for m in state["rounds"][0]["matchups"] if m["is_bye"])
        with pytest.raises(ValidationError, match="bye"):
            engine.submit_vote(state, "default", {"matchup_id": bye["matchup_id"], "result": "a_wins"})


class TestSwissRoundAdvancement:
    def test_round_advances_when_all_decided(self) -> None:
        engine = SwissEngine()
        state = engine.initialize(_make_entries(4), {"shuffle_seed": False})
        assert state["current_round"] == 1
        assert len(state["rounds"]) == 1
        # Resolve both round-1 matchups.
        for _ in range(2):
            ctx = engine.get_vote_context(state, "default")
            assert isinstance(ctx, SwissMatchupContext)
            state = engine.submit_vote(state, "default", _always_a_wins(ctx))
        assert state["current_round"] == 2
        assert len(state["rounds"]) == 2

    def test_no_rematches_when_possible(self) -> None:
        engine = SwissEngine()
        state = engine.initialize(_make_entries(4), {"shuffle_seed": False})
        state = _play_through(engine, state)
        # Aggregate every pairing across every round (excluding byes).
        seen: list[tuple[str, str]] = []
        for rnd in state["rounds"]:
            for m in rnd["matchups"]:
                if m["is_bye"]:
                    continue
                pair = tuple(sorted([m["entry_a_id"], m["entry_b_id"]]))
                seen.append(pair)  # type: ignore[arg-type]
        # 4 entries over 2 rounds = 4 matchups; no duplicates (Swiss avoids rematches here).
        assert len(seen) == len(set(seen))

    def test_byes_rotate_to_new_entry(self) -> None:
        engine = SwissEngine()
        # 3 entries, 2 rounds → each round has exactly one bye.
        state = engine.initialize(_make_entries(3), {"shuffle_seed": False})
        ctx = engine.get_vote_context(state, "default")
        assert isinstance(ctx, SwissMatchupContext)
        state = engine.submit_vote(state, "default", _always_a_wins(ctx))
        # Round 2 bye must be a different entry.
        bye_r1 = next(m for m in state["rounds"][0]["matchups"] if m["is_bye"])
        bye_r2 = next(m for m in state["rounds"][1]["matchups"] if m["is_bye"])
        assert bye_r1["entry_a_id"] != bye_r2["entry_a_id"]


class TestSwissCompletion:
    def test_not_complete_after_init(self) -> None:
        engine = SwissEngine()
        state = engine.initialize(_make_entries(4), {"shuffle_seed": False})
        assert not engine.is_complete(state)

    def test_is_complete_after_all_rounds(self) -> None:
        engine = SwissEngine()
        state = engine.initialize(_make_entries(4), {"shuffle_seed": False})
        state = _play_through(engine, state)
        assert engine.is_complete(state)

    def test_vote_context_after_completion_returns_completed(self) -> None:
        engine = SwissEngine()
        entries = _make_entries(4)
        state = engine.initialize(entries, {"shuffle_seed": False})
        state = _play_through(engine, state)
        ctx = engine.get_vote_context(state, "default")
        assert isinstance(ctx, CompletedContext)


class TestSwissResult:
    def test_ranking_covers_every_entry(self) -> None:
        engine = SwissEngine()
        entries = _make_entries(8)
        state = engine.initialize(entries, {"shuffle_seed": False})
        state = _play_through(engine, state)
        result = engine.compute_result(state, entries)
        assert len(result.ranking) == 8
        ranked_ids = {r["entry_id"] for r in result.ranking}
        assert ranked_ids == {str(e.id) for e in entries}

    def test_winner_has_most_points(self) -> None:
        engine = SwissEngine()
        entries = _make_entries(4)
        state = engine.initialize(entries, {"shuffle_seed": False})
        state = _play_through(engine, state)
        result = engine.compute_result(state, entries)
        top = max(state["standings"].values(), key=lambda s: s["points"])["points"]
        winner_points = {r["points"] for r in result.ranking if r["rank"] == 1}
        assert winner_points == {top}

    def test_rank_respects_points_order(self) -> None:
        engine = SwissEngine()
        entries = _make_entries(8)
        state = engine.initialize(entries, {"shuffle_seed": False})
        state = _play_through(engine, state)
        result = engine.compute_result(state, entries)
        for i in range(1, len(result.ranking)):
            assert result.ranking[i]["rank"] >= result.ranking[i - 1]["rank"]
            assert result.ranking[i]["points"] <= result.ranking[i - 1]["points"]

    def test_metadata_records_tiebreakers(self) -> None:
        engine = SwissEngine()
        entries = _make_entries(4)
        state = engine.initialize(entries, {"shuffle_seed": False})
        state = _play_through(engine, state)
        result = engine.compute_result(state, entries)
        assert result.metadata["total_rounds"] == state["total_rounds"]
        assert "buchholz" in result.metadata["tiebreakers"]


class TestSwissTiebreakers:
    def test_buchholz_included_in_ranking(self) -> None:
        engine = SwissEngine()
        entries = _make_entries(4)
        state = engine.initialize(entries, {"shuffle_seed": False})
        state = _play_through(engine, state)
        result = engine.compute_result(state, entries)
        assert all("buchholz" in r for r in result.ranking)

    def test_all_draws_produces_tied_winner(self) -> None:
        """If every matchup is a draw, every entry has equal points.

        With equal Buchholz and equal head-to-head, all are rank-1 winners.
        """
        engine = SwissEngine()
        entries = _make_entries(4)
        state = engine.initialize(entries, {"shuffle_seed": False})
        state = _play_through(
            engine,
            state,
            decision=lambda ctx: {"matchup_id": ctx.matchup_id, "result": "draw"},
        )
        result = engine.compute_result(state, entries)
        assert all(r["rank"] == 1 for r in result.ranking)
        assert len(result.winner_ids) == 4


class TestSwissReplay:
    def test_deterministic_initialization(self) -> None:
        """Two initializations with the same entries produce identical round-1 pairings."""
        engine = SwissEngine()
        entries = _make_entries(8)
        s1 = engine.initialize(entries, {"shuffle_seed": True})
        s2 = engine.initialize(entries, {"shuffle_seed": True})
        pairs1 = [(m["entry_a_id"], m["entry_b_id"]) for m in s1["rounds"][0]["matchups"]]
        pairs2 = [(m["entry_a_id"], m["entry_b_id"]) for m in s2["rounds"][0]["matchups"]]
        assert pairs1 == pairs2

    def test_default_replay_matches_direct_play(self) -> None:
        """The base-engine replay (initialize + replay each active vote) equals live state."""
        from app.schemas.tournament import Vote

        engine = SwissEngine()
        entries = _make_entries(4)
        state_live = engine.initialize(entries, {"shuffle_seed": False})

        votes: list[Vote] = []
        while not engine.is_complete(state_live):
            ctx = engine.get_vote_context(state_live, "default")
            assert isinstance(ctx, SwissMatchupContext)
            payload = {"matchup_id": ctx.matchup_id, "result": "a_wins"}
            votes.append(Vote(voter_label="default", payload=payload))
            state_live = engine.submit_vote(state_live, "default", payload)

        state_replay = engine.replay_state(entries, {"shuffle_seed": False}, votes)
        # Compare the same externally visible signals.
        assert state_replay["current_round"] == state_live["current_round"]
        assert state_replay["standings"] == state_live["standings"]
        assert len(state_replay["rounds"]) == len(state_live["rounds"])
