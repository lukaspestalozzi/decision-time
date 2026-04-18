"""ELO tournament engine with chess-style rating updates."""

import copy
import random
from itertools import combinations
from typing import Any
from uuid import UUID, uuid5

from app.engines.base import (
    AlreadyVotedContext,
    CompletedContext,
    EloMatchupContext,
    TournamentEngine,
    VoteContext,
)
from app.exceptions import ValidationError
from app.schemas.common import EloConfig
from app.schemas.tournament import Result, TournamentEntry

# Fixed namespace so pair_ids/matchup_ids derive deterministically from entry_ids.
# This keeps replay_state reproducible without threading a seed through the engine.
_ELO_NAMESPACE = UUID("6b0d4d9f-8e2a-4b1f-9c3d-1a2b3c4d5e6f")


def _expected_score(rating_a: float, rating_b: float) -> float:
    """Chess-style Elo expected score for A given ratings of A and B."""
    return float(1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0)))


def _apply_elo(rating_a: float, rating_b: float, winner_is_a: bool, k: float) -> tuple[float, float, float, float]:
    """Apply an Elo update for a matchup with no draws.

    Returns (new_a, new_b, delta_a, delta_b). Sum of deltas is zero.
    """
    expected_a = _expected_score(rating_a, rating_b)
    score_a = 1.0 if winner_is_a else 0.0
    delta_a = k * (score_a - expected_a)
    return rating_a + delta_a, rating_b - delta_a, delta_a, -delta_a


class EloEngine(TournamentEngine):
    """ELO tournament: all pairs play `rounds_per_pair` matchups, ratings rank options."""

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        try:
            EloConfig(**config)
            return []
        except Exception as e:
            return [str(e)]

    def initialize(self, entries: list[TournamentEntry], config: dict[str, Any]) -> dict[str, Any]:
        cfg = EloConfig(**config)
        entry_ids = [str(e.id) for e in entries]

        # Build unique unordered pairs. pair_id is derived from the entry ids
        # so it survives a replay_state().
        pairs: list[dict[str, str]] = [
            {
                "pair_id": str(uuid5(_ELO_NAMESPACE, f"pair:{a_id}:{b_id}")),
                "entry_a_id": a_id,
                "entry_b_id": b_id,
            }
            for a_id, b_id in combinations(entry_ids, 2)
        ]

        # Expand into matchups: one per (pair, round). Round-interleaved order
        # (all round-1 matchups first, then round-2, ...) — this is the base
        # order used directly when shuffle_order=False, and as the seed input
        # when shuffle_order=True. matchup_id is deterministic for replay.
        matchups: list[dict[str, Any]] = []
        for round_number in range(1, cfg.rounds_per_pair + 1):
            for pair in pairs:
                matchups.append(
                    {
                        "matchup_id": str(uuid5(_ELO_NAMESPACE, f"matchup:{pair['pair_id']}:{round_number}")),
                        "pair_id": pair["pair_id"],
                        "round_number": round_number,
                        "entry_a_id": pair["entry_a_id"],
                        "entry_b_id": pair["entry_b_id"],
                    }
                )

        base_order = [m["matchup_id"] for m in matchups]

        voter_matchup_orders: dict[str, list[str]] = {}
        voter_progress: dict[str, dict[str, int]] = {}
        voter_ratings: dict[str, dict[str, float]] = {}

        seeds = cfg.voter_shuffle_seeds or {}

        for label in cfg.voter_labels:
            order = list(base_order)
            if cfg.shuffle_order:
                seed = seeds.get(label)
                rng = random.Random(seed) if seed is not None else random.Random()
                rng.shuffle(order)
            voter_matchup_orders[label] = order
            voter_progress[label] = {
                "completed_matchups": 0,
                "total_matchups": len(matchups),
            }
            voter_ratings[label] = {eid: cfg.initial_rating for eid in entry_ids}

        return {
            "voter_labels": list(cfg.voter_labels),
            "ballots_required": len(cfg.voter_labels),
            "ballots_submitted": 0,
            "entry_ids": entry_ids,
            "config_snapshot": {
                "rounds_per_pair": cfg.rounds_per_pair,
                "k_factor": cfg.k_factor,
                "initial_rating": cfg.initial_rating,
            },
            "pairs": pairs,
            "matchups": matchups,
            "voter_matchup_orders": voter_matchup_orders,
            "voter_progress": voter_progress,
            "voter_ratings": voter_ratings,
            "votes": [],
        }

    def get_vote_context(self, state: dict[str, Any], voter_label: str) -> VoteContext:
        if self.is_complete(state):
            result = self.compute_result(state, [])
            return CompletedContext(result=result.model_dump(mode="json"))

        if voter_label not in state["voter_labels"]:
            raise ValidationError(f"Unknown voter: '{voter_label}'")

        progress = state["voter_progress"].get(voter_label)
        if progress is None or progress["completed_matchups"] >= progress["total_matchups"]:
            return AlreadyVotedContext()

        order = state["voter_matchup_orders"][voter_label]
        next_idx = progress["completed_matchups"]
        next_matchup_id = order[next_idx]

        matchup_map = {m["matchup_id"]: m for m in state["matchups"]}
        matchup = matchup_map[next_matchup_id]

        ratings = state["voter_ratings"][voter_label]
        return EloMatchupContext(
            matchup_id=matchup["matchup_id"],
            entry_a={"id": matchup["entry_a_id"], "rating": ratings[matchup["entry_a_id"]]},
            entry_b={"id": matchup["entry_b_id"], "rating": ratings[matchup["entry_b_id"]]},
            matchup_number=next_idx + 1,
            total_matchups=progress["total_matchups"],
            round_number=matchup["round_number"],
            rounds_per_pair=state["config_snapshot"]["rounds_per_pair"],
        )

    def submit_vote(self, state: dict[str, Any], voter_label: str, vote_payload: dict[str, Any]) -> dict[str, Any]:
        state = copy.deepcopy(state)

        if voter_label not in state["voter_labels"]:
            raise ValidationError(f"Unknown voter: '{voter_label}'")

        matchup_id = str(vote_payload.get("matchup_id"))
        winner_entry_id = vote_payload.get("winner_entry_id")

        matchup_map = {m["matchup_id"]: m for m in state["matchups"]}
        matchup = matchup_map.get(matchup_id)
        if matchup is None:
            raise ValidationError(f"Matchup {matchup_id} not found")

        a_id = matchup["entry_a_id"]
        b_id = matchup["entry_b_id"]
        if winner_entry_id not in (a_id, b_id):
            raise ValidationError(f"Winner {winner_entry_id} is not a participant in this matchup")

        for v in state["votes"]:
            if v["voter_label"] == voter_label and v["matchup_id"] == matchup_id:
                raise ValidationError(f"Voter '{voter_label}' has already voted on matchup {matchup_id}")

        ratings = state["voter_ratings"][voter_label]
        k = float(state["config_snapshot"]["k_factor"])
        rating_a = ratings[a_id]
        rating_b = ratings[b_id]
        new_a, new_b, delta_a, delta_b = _apply_elo(rating_a, rating_b, winner_is_a=(winner_entry_id == a_id), k=k)
        ratings[a_id] = new_a
        ratings[b_id] = new_b

        state["votes"].append(
            {
                "voter_label": voter_label,
                "matchup_id": matchup_id,
                "winner_entry_id": winner_entry_id,
                "rating_before": {a_id: rating_a, b_id: rating_b},
                "rating_after": {a_id: new_a, b_id: new_b},
                "delta_a": delta_a,
                "delta_b": delta_b,
            }
        )

        progress = state["voter_progress"][voter_label]
        progress["completed_matchups"] += 1
        if progress["completed_matchups"] == progress["total_matchups"]:
            state["ballots_submitted"] += 1

        return state

    def is_complete(self, state: dict[str, Any]) -> bool:
        for progress in state["voter_progress"].values():
            if progress["completed_matchups"] < progress["total_matchups"]:
                return False
        return True

    def compute_result(self, state: dict[str, Any], entries: list[TournamentEntry]) -> Result:
        entry_ids: list[str] = state["entry_ids"]
        voter_labels: list[str] = state["voter_labels"]
        voter_ratings: dict[str, dict[str, float]] = state["voter_ratings"]

        mean_ratings: dict[str, float] = {}
        for eid in entry_ids:
            ratings = [voter_ratings[v][eid] for v in voter_labels]
            mean_ratings[eid] = sum(ratings) / len(ratings) if ratings else 0.0

        # Aggregate wins/losses per entry across all votes and voters.
        wins: dict[str, int] = {eid: 0 for eid in entry_ids}
        losses: dict[str, int] = {eid: 0 for eid in entry_ids}
        pairwise: dict[str, dict[str, int]] = {eid: {} for eid in entry_ids}

        matchup_map = {m["matchup_id"]: m for m in state["matchups"]}
        for vote in state["votes"]:
            matchup = matchup_map[vote["matchup_id"]]
            winner = vote["winner_entry_id"]
            loser = matchup["entry_b_id"] if winner == matchup["entry_a_id"] else matchup["entry_a_id"]
            wins[winner] += 1
            losses[loser] += 1
            pairwise[winner][loser] = pairwise[winner].get(loser, 0) + 1

        ordered = sorted(entry_ids, key=lambda eid: mean_ratings[eid], reverse=True)
        ranking: list[dict[str, Any]] = []
        current_rank = 1
        for pos, eid in enumerate(ordered):
            if pos > 0 and mean_ratings[eid] < mean_ratings[ordered[pos - 1]]:
                current_rank = pos + 1
            ranking.append(
                {
                    "rank": current_rank,
                    "entry_id": eid,
                    "mean_rating": mean_ratings[eid],
                    "wins": wins[eid],
                    "losses": losses[eid],
                    "matches_played": wins[eid] + losses[eid],
                }
            )

        winner_ids = [UUID(row["entry_id"]) for row in ranking if row["rank"] == 1]

        return Result(
            winner_ids=winner_ids,
            ranking=ranking,
            metadata={
                "voter_ratings": voter_ratings,
                "pairwise_records": pairwise,
                "config": state["config_snapshot"],
            },
        )
