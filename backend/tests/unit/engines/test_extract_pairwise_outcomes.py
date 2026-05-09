"""Per-engine tests of TournamentEngine.extract_pairwise_outcomes."""

import uuid
from typing import Any

from app.engines.bracket import BracketEngine
from app.engines.condorcet import CondorcetEngine
from app.engines.elo import EloEngine
from app.engines.multivote import MultivoteEngine
from app.engines.score import ScoreEngine
from app.engines.swiss import SwissEngine
from app.schemas.tournament import TournamentEntry


def _make_entries(n: int) -> list[TournamentEntry]:
    return [TournamentEntry(option_id=uuid.uuid4(), option_snapshot={"name": f"Option {i + 1}"}) for i in range(n)]


def _vote_until_complete(
    engine: Any,
    state: dict[str, Any],
    voter_label: str,
    payload_for_ctx: Any,
) -> dict[str, Any]:
    while not engine.is_complete(state):
        ctx = engine.get_vote_context(state, voter_label)
        if ctx.type in ("already_voted", "completed"):
            break
        state = engine.submit_vote(state, voter_label, payload_for_ctx(ctx))
    return state


class TestBracketExtraction:
    def test_emits_one_outcome_per_non_bye_matchup(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(4)
        state = engine.initialize(entries, {"shuffle_seed": False})

        # Vote through all matchups picking entry_a each time.
        state = _vote_until_complete(
            engine,
            state,
            "default",
            lambda ctx: {"matchup_id": ctx.matchup_id, "winner_entry_id": ctx.entry_a["id"]},
        )

        outcomes = engine.extract_pairwise_outcomes(state, entries)
        # 4-entry bracket: 2 round-1 matchups + 1 final = 3 outcomes.
        assert len(outcomes) == 3
        for o in outcomes:
            assert o["score_a"] == 1.0  # winner is always entry_a in this run

    def test_skips_bye_matchups(self) -> None:
        engine = BracketEngine()
        entries = _make_entries(3)  # 3 entries → bracket size 4 → 1 bye
        state = engine.initialize(entries, {"shuffle_seed": False})
        state = _vote_until_complete(
            engine,
            state,
            "default",
            lambda ctx: {"matchup_id": ctx.matchup_id, "winner_entry_id": ctx.entry_a["id"]},
        )
        outcomes = engine.extract_pairwise_outcomes(state, entries)
        # 3-entry bracket has 2 voted matchups (one round-1 + final). The bye is skipped.
        assert len(outcomes) == 2


class TestCondorcetExtraction:
    def test_one_outcome_per_vote_per_voter(self) -> None:
        engine = CondorcetEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"voter_labels": ["Alice", "Bob"]})
        for voter in ("Alice", "Bob"):
            state = _vote_until_complete(
                engine,
                state,
                voter,
                lambda ctx: {"matchup_id": ctx.matchup_id, "winner_entry_id": ctx.entry_a["id"]},
            )
        outcomes = engine.extract_pairwise_outcomes(state, entries)
        # 3 pairs x 2 voters = 6 outcomes.
        assert len(outcomes) == 6
        assert all(o["score_a"] == 1.0 for o in outcomes)


class TestEloExtraction:
    def test_one_outcome_per_vote(self) -> None:
        engine = EloEngine()
        entries = _make_entries(3)
        cfg = {
            "rounds_per_pair": 2,
            "voter_shuffle_seeds": {"default": 1},
        }
        state = engine.initialize(entries, cfg)
        state = _vote_until_complete(
            engine,
            state,
            "default",
            lambda ctx: {"matchup_id": ctx.matchup_id, "winner_entry_id": ctx.entry_a["id"]},
        )
        outcomes = engine.extract_pairwise_outcomes(state, entries)
        # 3 pairs x 2 rounds = 6 matchups.
        assert len(outcomes) == 6


class TestSwissExtraction:
    def test_emits_outcomes_with_correct_scores(self) -> None:
        engine = SwissEngine()
        entries = _make_entries(4)
        state = engine.initialize(entries, {"shuffle_seed": False})
        # Vote: a_wins on first matchup of each round, draw on second if possible.
        results_seen: list[float] = []
        while not engine.is_complete(state):
            ctx = engine.get_vote_context(state, "default")
            if ctx.type != "swiss_matchup":
                break
            # Always pick a_wins for simplicity.
            state = engine.submit_vote(
                state,
                "default",
                {"matchup_id": ctx.matchup_id, "result": "a_wins"},
            )
        outcomes = engine.extract_pairwise_outcomes(state, entries)
        assert len(outcomes) > 0
        for o in outcomes:
            assert o["score_a"] == 1.0
            results_seen.append(o["score_a"])

    def test_draw_emits_half_score(self) -> None:
        engine = SwissEngine()
        entries = _make_entries(4)
        state = engine.initialize(entries, {"shuffle_seed": False, "allow_draws": True})
        while not engine.is_complete(state):
            ctx = engine.get_vote_context(state, "default")
            if ctx.type != "swiss_matchup":
                break
            state = engine.submit_vote(
                state,
                "default",
                {"matchup_id": ctx.matchup_id, "result": "draw"},
            )
        outcomes = engine.extract_pairwise_outcomes(state, entries)
        assert all(o["score_a"] == 0.5 for o in outcomes)


class TestScoreExtraction:
    def test_per_voter_pairwise(self) -> None:
        engine = ScoreEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"voter_labels": ["Alice", "Bob"]})
        entry_ids = [str(e.id) for e in entries]
        # Alice: A=5, B=3, C=1 → A beats B beats C
        state = engine.submit_vote(
            state,
            "Alice",
            {
                "scores": [
                    {"entry_id": entry_ids[0], "score": 5},
                    {"entry_id": entry_ids[1], "score": 3},
                    {"entry_id": entry_ids[2], "score": 1},
                ]
            },
        )
        # Bob: A=4, B=4, C=4 → all draws.
        state = engine.submit_vote(
            state,
            "Bob",
            {
                "scores": [
                    {"entry_id": entry_ids[0], "score": 4},
                    {"entry_id": entry_ids[1], "score": 4},
                    {"entry_id": entry_ids[2], "score": 4},
                ]
            },
        )
        outcomes = engine.extract_pairwise_outcomes(state, entries)
        # 3 pairs x 2 voters = 6 outcomes.
        assert len(outcomes) == 6
        # Alice contributes 3 wins for the higher-scored entry.
        alice = [o for o in outcomes if o["source"].startswith("Alice:")]
        assert all(o["score_a"] == 1.0 for o in alice)
        # Bob: all draws.
        bob = [o for o in outcomes if o["source"].startswith("Bob:")]
        assert all(o["score_a"] == 0.5 for o in bob)


class TestMultivoteExtraction:
    def test_per_voter_pairwise(self) -> None:
        engine = MultivoteEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, {"voter_labels": ["Alice"], "total_votes": 6})
        entry_ids = [str(e.id) for e in entries]
        state = engine.submit_vote(
            state,
            "Alice",
            {
                "allocations": [
                    {"entry_id": entry_ids[0], "votes": 4},
                    {"entry_id": entry_ids[1], "votes": 2},
                    {"entry_id": entry_ids[2], "votes": 0},
                ]
            },
        )
        outcomes = engine.extract_pairwise_outcomes(state, entries)
        # 3 pairs x 1 voter = 3 outcomes.
        assert len(outcomes) == 3
        # All wins for the higher-allocated entry.
        assert all(o["score_a"] == 1.0 for o in outcomes)


class TestBaseDefault:
    def test_default_returns_empty(self) -> None:
        # The abstract base's default impl returns no outcomes — used by any engine
        # that doesn't override (none currently, but contract test).
        from app.engines.base import TournamentEngine

        # Build a minimal subclass that doesn't override anything except abstracts.
        class StubEngine(TournamentEngine):
            def validate_config(self, config: dict[str, Any]) -> list[str]:
                return []

            def initialize(self, entries: Any, config: dict[str, Any]) -> dict[str, Any]:
                return {}

            def get_vote_context(self, state: dict[str, Any], voter_label: str) -> Any:
                from app.engines.base import AlreadyVotedContext

                return AlreadyVotedContext()

            def submit_vote(
                self,
                state: dict[str, Any],
                voter_label: str,
                vote_payload: dict[str, Any],
            ) -> dict[str, Any]:
                return state

            def is_complete(self, state: dict[str, Any]) -> bool:
                return True

            def compute_result(self, state: dict[str, Any], entries: Any) -> Any:
                from app.schemas.tournament import Result

                return Result(winner_ids=[], ranking=[])

        assert StubEngine().extract_pairwise_outcomes({}, []) == []
