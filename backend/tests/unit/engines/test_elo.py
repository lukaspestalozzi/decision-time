"""Unit tests for the ELO tournament engine."""

import uuid
from typing import Any

import pytest

from app.engines.base import AlreadyVotedContext, CompletedContext, EloMatchupContext
from app.engines.elo import EloEngine, _apply_elo, _expected_score
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


def _voter_labels(n: int) -> list[str]:
    return [f"Voter {i + 1}" for i in range(n)]


def _seed_config(cfg: dict[str, Any], labels: list[str]) -> dict[str, Any]:
    """Inject deterministic shuffle seeds so tests don't depend on the service layer."""
    cfg = dict(cfg)
    cfg.setdefault("voter_shuffle_seeds", {label: i + 1 for i, label in enumerate(labels)})
    return cfg


def _vote_all(
    engine: EloEngine,
    state: dict[str, Any],
    voter_label: str,
    preference_order: list[str] | None = None,
) -> dict[str, Any]:
    """Vote through all matchups for a voter. If preference_order is given, prefer earlier entries."""
    while True:
        ctx = engine.get_vote_context(state, voter_label)
        if isinstance(ctx, AlreadyVotedContext | CompletedContext):
            break
        assert isinstance(ctx, EloMatchupContext)
        if preference_order:
            a_rank = preference_order.index(ctx.entry_a["id"])
            b_rank = preference_order.index(ctx.entry_b["id"])
            winner = ctx.entry_a["id"] if a_rank < b_rank else ctx.entry_b["id"]
        else:
            winner = ctx.entry_a["id"]
        state = engine.submit_vote(
            state,
            voter_label,
            {"matchup_id": ctx.matchup_id, "winner_entry_id": winner},
        )
    return state


class TestEloValidateConfig:
    def test_default_config_is_valid(self) -> None:
        assert EloEngine().validate_config({}) == []

    def test_custom_valid_config(self) -> None:
        cfg = {"rounds_per_pair": 5, "k_factor": 24.0, "initial_rating": 1200.0}
        assert EloEngine().validate_config(cfg) == []

    def test_rounds_per_pair_zero_rejected(self) -> None:
        assert EloEngine().validate_config({"rounds_per_pair": 0}) != []

    def test_rounds_per_pair_too_large_rejected(self) -> None:
        assert EloEngine().validate_config({"rounds_per_pair": 21}) != []

    def test_k_factor_zero_rejected(self) -> None:
        assert EloEngine().validate_config({"k_factor": 0}) != []

    def test_k_factor_negative_rejected(self) -> None:
        assert EloEngine().validate_config({"k_factor": -5}) != []

    def test_k_factor_too_large_rejected(self) -> None:
        assert EloEngine().validate_config({"k_factor": 500}) != []

    def test_negative_initial_rating_rejected(self) -> None:
        assert EloEngine().validate_config({"initial_rating": -1}) != []


class TestEloInitialize:
    def test_3_entries_1_round_creates_3_matchups(self) -> None:
        engine = EloEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, _seed_config({"rounds_per_pair": 1}, ["default"]))
        assert len(state["matchups"]) == 3

    def test_3_entries_3_rounds_creates_9_matchups(self) -> None:
        engine = EloEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, _seed_config({"rounds_per_pair": 3}, ["default"]))
        assert len(state["matchups"]) == 9

    def test_4_entries_2_rounds_creates_12_matchups(self) -> None:
        engine = EloEngine()
        entries = _make_entries(4)
        state = engine.initialize(entries, _seed_config({"rounds_per_pair": 2}, ["default"]))
        assert len(state["matchups"]) == 12

    def test_each_pair_appears_rounds_per_pair_times(self) -> None:
        engine = EloEngine()
        entries = _make_entries(4)
        state = engine.initialize(entries, _seed_config({"rounds_per_pair": 3}, ["default"]))
        pair_counts: dict[str, int] = {}
        for m in state["matchups"]:
            pair_counts[m["pair_id"]] = pair_counts.get(m["pair_id"], 0) + 1
        assert all(count == 3 for count in pair_counts.values())
        assert len(pair_counts) == 6  # C(4, 2)

    def test_voter_matchup_orders_cover_all_matchups(self) -> None:
        engine = EloEngine()
        entries = _make_entries(4)
        labels = _voter_labels(2)
        state = engine.initialize(entries, _seed_config({"voter_labels": labels, "rounds_per_pair": 2}, labels))
        matchup_ids = {m["matchup_id"] for m in state["matchups"]}
        for order in state["voter_matchup_orders"].values():
            assert set(order) == matchup_ids

    def test_unshuffled_order_is_round_interleaved(self) -> None:
        engine = EloEngine()
        entries = _make_entries(3)
        state = engine.initialize(
            entries,
            _seed_config({"rounds_per_pair": 2, "shuffle_order": False}, ["default"]),
        )
        order = state["voter_matchup_orders"]["default"]
        matchup_by_id = {m["matchup_id"]: m for m in state["matchups"]}
        rounds = [matchup_by_id[mid]["round_number"] for mid in order]
        # Round-interleaved: all round-1 matchups first, then all round-2
        assert rounds == [1, 1, 1, 2, 2, 2]

    def test_voter_ratings_initialized(self) -> None:
        engine = EloEngine()
        entries = _make_entries(3)
        labels = _voter_labels(2)
        state = engine.initialize(
            entries,
            _seed_config({"voter_labels": labels, "initial_rating": 1500.0}, labels),
        )
        for label in labels:
            ratings = state["voter_ratings"][label]
            assert len(ratings) == 3
            assert all(r == 1500.0 for r in ratings.values())

    def test_config_snapshot_populated(self) -> None:
        engine = EloEngine()
        entries = _make_entries(3)
        cfg = _seed_config({"rounds_per_pair": 5, "k_factor": 24.0, "initial_rating": 1200.0}, ["default"])
        state = engine.initialize(entries, cfg)
        snap = state["config_snapshot"]
        assert snap["rounds_per_pair"] == 5
        assert snap["k_factor"] == 24.0
        assert snap["initial_rating"] == 1200.0

    def test_voter_progress_initialized(self) -> None:
        engine = EloEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, _seed_config({"rounds_per_pair": 2}, ["default"]))
        prog = state["voter_progress"]["default"]
        assert prog["completed_matchups"] == 0
        assert prog["total_matchups"] == 6  # 3 pairs * 2 rounds

    def test_seeds_produce_deterministic_shuffles(self) -> None:
        engine = EloEngine()
        entries = _make_entries(4)
        labels = _voter_labels(2)
        cfg = _seed_config({"voter_labels": labels, "rounds_per_pair": 2}, labels)
        state1 = engine.initialize(entries, cfg)
        state2 = engine.initialize(entries, cfg)
        assert state1["voter_matchup_orders"] == state2["voter_matchup_orders"]


class TestEloMath:
    def test_expected_score_equal_ratings(self) -> None:
        assert _expected_score(1000.0, 1000.0) == pytest.approx(0.5)

    def test_expected_score_400_point_gap(self) -> None:
        # Classic Elo figure: a 400-point-higher rating expects ~0.909
        assert _expected_score(1400.0, 1000.0) == pytest.approx(0.909, abs=0.002)

    def test_apply_elo_equal_ratings_winner_a(self) -> None:
        new_a, new_b, da, db = _apply_elo(1000.0, 1000.0, winner_is_a=True, k=32.0)
        assert new_a == pytest.approx(1016.0)
        assert new_b == pytest.approx(984.0)
        assert da == pytest.approx(16.0)
        assert db == pytest.approx(-16.0)

    def test_apply_elo_equal_ratings_winner_b(self) -> None:
        new_a, new_b, _, _ = _apply_elo(1000.0, 1000.0, winner_is_a=False, k=32.0)
        assert new_a == pytest.approx(984.0)
        assert new_b == pytest.approx(1016.0)

    def test_apply_elo_upset_rewards_winner(self) -> None:
        # Low-rated B beats high-rated A — B should gain close to K
        _, _, da, db = _apply_elo(1500.0, 1000.0, winner_is_a=False, k=32.0)
        assert db > 28.0
        assert da < -28.0

    def test_apply_elo_sum_invariant(self) -> None:
        _, _, da, db = _apply_elo(1234.0, 987.0, winner_is_a=True, k=32.0)
        assert da + db == pytest.approx(0.0)


class TestEloVoting:
    def test_get_vote_context_exposes_current_ratings(self) -> None:
        engine = EloEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, _seed_config({}, ["default"]))
        ctx = engine.get_vote_context(state, "default")
        assert isinstance(ctx, EloMatchupContext)
        assert "rating" in ctx.entry_a
        assert "rating" in ctx.entry_b
        assert ctx.entry_a["rating"] == 1000.0
        assert ctx.entry_b["rating"] == 1000.0
        assert ctx.rounds_per_pair == 3
        assert ctx.round_number >= 1

    def test_submit_vote_updates_rating_table(self) -> None:
        engine = EloEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, _seed_config({}, ["default"]))
        ctx = engine.get_vote_context(state, "default")
        assert isinstance(ctx, EloMatchupContext)
        state = engine.submit_vote(
            state,
            "default",
            {"matchup_id": ctx.matchup_id, "winner_entry_id": ctx.entry_a["id"]},
        )
        ratings = state["voter_ratings"]["default"]
        assert ratings[ctx.entry_a["id"]] > 1000.0
        assert ratings[ctx.entry_b["id"]] < 1000.0

    def test_submit_vote_records_before_and_after(self) -> None:
        engine = EloEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, _seed_config({}, ["default"]))
        ctx = engine.get_vote_context(state, "default")
        assert isinstance(ctx, EloMatchupContext)
        state = engine.submit_vote(
            state,
            "default",
            {"matchup_id": ctx.matchup_id, "winner_entry_id": ctx.entry_a["id"]},
        )
        record = state["votes"][-1]
        assert record["voter_label"] == "default"
        assert record["matchup_id"] == ctx.matchup_id
        assert record["winner_entry_id"] == ctx.entry_a["id"]
        assert record["rating_before"][ctx.entry_a["id"]] == 1000.0
        assert record["rating_after"][ctx.entry_a["id"]] > 1000.0
        assert record["delta_a"] + record["delta_b"] == pytest.approx(0.0)

    def test_submit_vote_advances_progress(self) -> None:
        engine = EloEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, _seed_config({"rounds_per_pair": 2}, ["default"]))
        ctx = engine.get_vote_context(state, "default")
        assert isinstance(ctx, EloMatchupContext)
        state = engine.submit_vote(
            state,
            "default",
            {"matchup_id": ctx.matchup_id, "winner_entry_id": ctx.entry_a["id"]},
        )
        assert state["voter_progress"]["default"]["completed_matchups"] == 1

    def test_unknown_matchup_rejected(self) -> None:
        engine = EloEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, _seed_config({}, ["default"]))
        with pytest.raises(ValidationError, match="not found"):
            engine.submit_vote(
                state,
                "default",
                {"matchup_id": str(uuid.uuid4()), "winner_entry_id": str(uuid.uuid4())},
            )

    def test_invalid_winner_rejected(self) -> None:
        engine = EloEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, _seed_config({}, ["default"]))
        ctx = engine.get_vote_context(state, "default")
        assert isinstance(ctx, EloMatchupContext)
        with pytest.raises(ValidationError, match="participant"):
            engine.submit_vote(
                state,
                "default",
                {"matchup_id": ctx.matchup_id, "winner_entry_id": str(uuid.uuid4())},
            )

    def test_unknown_voter_rejected_on_submit(self) -> None:
        engine = EloEngine()
        entries = _make_entries(3)
        labels = ["Alice", "Bob"]
        state = engine.initialize(entries, _seed_config({"voter_labels": labels}, labels))
        ctx = engine.get_vote_context(state, "Alice")
        assert isinstance(ctx, EloMatchupContext)
        with pytest.raises(ValidationError, match="Unknown voter"):
            engine.submit_vote(
                state,
                "Charlie",
                {"matchup_id": ctx.matchup_id, "winner_entry_id": ctx.entry_a["id"]},
            )

    def test_unknown_voter_rejected_on_get_context(self) -> None:
        engine = EloEngine()
        entries = _make_entries(3)
        labels = ["Alice", "Bob"]
        state = engine.initialize(entries, _seed_config({"voter_labels": labels}, labels))
        with pytest.raises(ValidationError, match="Unknown voter"):
            engine.get_vote_context(state, "Charlie")

    def test_duplicate_vote_rejected(self) -> None:
        engine = EloEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, _seed_config({}, ["default"]))
        ctx = engine.get_vote_context(state, "default")
        assert isinstance(ctx, EloMatchupContext)
        state = engine.submit_vote(
            state,
            "default",
            {"matchup_id": ctx.matchup_id, "winner_entry_id": ctx.entry_a["id"]},
        )
        with pytest.raises(ValidationError, match="already"):
            engine.submit_vote(
                state,
                "default",
                {"matchup_id": ctx.matchup_id, "winner_entry_id": ctx.entry_a["id"]},
            )

    def test_finished_voter_sees_already_voted_until_others_done(self) -> None:
        engine = EloEngine()
        entries = _make_entries(3)
        labels = _voter_labels(2)
        state = engine.initialize(entries, _seed_config({"voter_labels": labels}, labels))
        state = _vote_all(engine, state, "Voter 1")
        ctx = engine.get_vote_context(state, "Voter 1")
        assert isinstance(ctx, AlreadyVotedContext)


class TestEloFullFlow:
    def test_single_voter_dominant_preference_produces_clear_winner(self) -> None:
        engine = EloEngine()
        entries = _make_entries(3)
        entry_ids = [str(e.id) for e in entries]
        state = engine.initialize(entries, _seed_config({"rounds_per_pair": 2}, ["default"]))
        state = _vote_all(engine, state, "default", preference_order=entry_ids)
        result = engine.compute_result(state, entries)
        assert len(result.winner_ids) == 1
        assert str(result.winner_ids[0]) == entry_ids[0]

    def test_two_entries_deterministic_rating_sequence(self) -> None:
        """2 entries, 1 voter, 3 rounds, K=32, A always wins.

        Round 1: 1000/1000 → A wins → 1016.00 / 984.00 (E_A = 0.5, delta = 16)
        Round 2: 1016/984 → A wins → E_A ≈ 0.5459, delta ≈ 14.53 → 1030.53 / 969.47
        Round 3: 1030.53/969.47 → A wins → E_A ≈ 0.5873, delta ≈ 13.20 → 1043.73 / 956.27
        """
        engine = EloEngine()
        entries = _make_entries(2)
        entry_ids = [str(e.id) for e in entries]
        state = engine.initialize(
            entries,
            _seed_config({"rounds_per_pair": 3, "shuffle_order": False}, ["default"]),
        )
        state = _vote_all(engine, state, "default", preference_order=entry_ids)
        ratings = state["voter_ratings"]["default"]
        assert ratings[entry_ids[0]] == pytest.approx(1043.73, abs=0.1)
        assert ratings[entry_ids[1]] == pytest.approx(956.27, abs=0.1)

    def test_multi_voter_aggregation_by_mean(self) -> None:
        engine = EloEngine()
        entries = _make_entries(3)
        entry_ids = [str(e.id) for e in entries]
        labels = _voter_labels(2)
        state = engine.initialize(entries, _seed_config({"voter_labels": labels, "rounds_per_pair": 2}, labels))
        # Both voters prefer entry 0
        state = _vote_all(engine, state, "Voter 1", preference_order=entry_ids)
        state = _vote_all(engine, state, "Voter 2", preference_order=entry_ids)
        assert engine.is_complete(state)
        result = engine.compute_result(state, entries)
        assert str(result.winner_ids[0]) == entry_ids[0]

    def test_completed_context_after_all_voters_finish(self) -> None:
        engine = EloEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, _seed_config({}, ["default"]))
        state = _vote_all(engine, state, "default")
        ctx = engine.get_vote_context(state, "Anyone")
        assert isinstance(ctx, CompletedContext)


class TestEloResult:
    def test_ranking_ordered_by_mean_rating(self) -> None:
        engine = EloEngine()
        entries = _make_entries(3)
        entry_ids = [str(e.id) for e in entries]
        state = engine.initialize(entries, _seed_config({"rounds_per_pair": 2}, ["default"]))
        state = _vote_all(engine, state, "default", preference_order=entry_ids)
        result = engine.compute_result(state, entries)
        # Ranking rows should be in descending mean_rating order
        ratings = [row["mean_rating"] for row in result.ranking]
        assert ratings == sorted(ratings, reverse=True)

    def test_ranking_contains_wins_losses_matches(self) -> None:
        engine = EloEngine()
        entries = _make_entries(3)
        entry_ids = [str(e.id) for e in entries]
        state = engine.initialize(entries, _seed_config({"rounds_per_pair": 2}, ["default"]))
        state = _vote_all(engine, state, "default", preference_order=entry_ids)
        result = engine.compute_result(state, entries)
        top = result.ranking[0]
        assert "wins" in top
        assert "losses" in top
        assert "matches_played" in top
        assert top["matches_played"] == top["wins"] + top["losses"]

    def test_metadata_contains_voter_ratings_and_pairwise(self) -> None:
        engine = EloEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, _seed_config({}, ["default"]))
        state = _vote_all(engine, state, "default")
        result = engine.compute_result(state, entries)
        assert "voter_ratings" in result.metadata
        assert "pairwise_records" in result.metadata
        assert "config" in result.metadata

    def test_rank_skipping_on_ties(self) -> None:
        """When no votes cast, all options have mean_rating == initial — all tied at rank 1."""
        engine = EloEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, _seed_config({}, ["default"]))
        result = engine.compute_result(state, entries)
        assert all(row["rank"] == 1 for row in result.ranking)
        assert len(result.winner_ids) == 3


class TestEloReplayDeterminism:
    def test_replay_preserves_matchup_orders_and_ratings(self) -> None:
        from app.schemas.tournament import Vote

        engine = EloEngine()
        entries = _make_entries(3)
        labels = _voter_labels(2)
        cfg = _seed_config({"voter_labels": labels, "rounds_per_pair": 2}, labels)
        state = engine.initialize(entries, cfg)

        # Play a few matchups
        votes: list[Vote] = []
        for label in labels:
            for _ in range(3):
                ctx = engine.get_vote_context(state, label)
                assert isinstance(ctx, EloMatchupContext)
                payload = {"matchup_id": ctx.matchup_id, "winner_entry_id": ctx.entry_a["id"]}
                state = engine.submit_vote(state, label, payload)
                votes.append(Vote(voter_label=label, payload=payload))

        replayed = engine.replay_state(entries, cfg, votes)
        assert replayed["voter_matchup_orders"] == state["voter_matchup_orders"]
        assert replayed["voter_ratings"] == state["voter_ratings"]
        assert replayed["voter_progress"] == state["voter_progress"]


class TestEloIsComplete:
    def test_not_complete_after_init(self) -> None:
        engine = EloEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, _seed_config({}, ["default"]))
        assert not engine.is_complete(state)

    def test_complete_after_all_voters_finish(self) -> None:
        engine = EloEngine()
        entries = _make_entries(3)
        state = engine.initialize(entries, _seed_config({}, ["default"]))
        state = _vote_all(engine, state, "default")
        assert engine.is_complete(state)
