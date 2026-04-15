"""Condorcet tournament engine with Schulze method resolution."""

import copy
import random
from itertools import combinations
from typing import Any
from uuid import UUID, uuid4

from app.engines.base import (
    AlreadyVotedContext,
    CompletedContext,
    CondorcetMatchupContext,
    TournamentEngine,
    VoteContext,
)
from app.exceptions import ValidationError
from app.schemas.common import CondorcetConfig
from app.schemas.tournament import Result, TournamentEntry


def _schulze(entry_ids: list[str], matchups: list[dict[str, Any]], votes: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute Schulze ranking from pairwise votes.

    Returns dict with 'ranking' (list of {entry_id, rank, wins}),
    'pairwise_matrix', and 'path_strengths'.
    """
    n = len(entry_ids)
    idx = {eid: i for i, eid in enumerate(entry_ids)}

    # Build matchup lookup: matchup_id -> (entry_a_id, entry_b_id)
    matchup_map = {m["matchup_id"]: (m["entry_a_id"], m["entry_b_id"]) for m in matchups}

    # Build preference matrix d[i][j] = voters who preferred i over j
    d = [[0] * n for _ in range(n)]
    for vote in votes:
        winner_id = vote["winner_entry_id"]
        a_id, b_id = matchup_map[vote["matchup_id"]]
        loser_id = b_id if winner_id == a_id else a_id
        d[idx[winner_id]][idx[loser_id]] += 1

    # Initialize strength matrix p
    p = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j and d[i][j] > d[j][i]:
                p[i][j] = d[i][j]

    # Floyd-Warshall: strongest paths
    for k in range(n):
        for i in range(n):
            if i == k:
                continue
            for j in range(n):
                if j in (i, k):
                    continue
                p[i][j] = max(p[i][j], min(p[i][k], p[k][j]))

    # Count wins: i beats j when p[i][j] > p[j][i]
    wins = [sum(1 for j in range(n) if i != j and p[i][j] > p[j][i]) for i in range(n)]

    # Sort by wins descending, derive ranking with ties
    indexed = sorted(range(n), key=lambda i: wins[i], reverse=True)
    ranking: list[dict[str, Any]] = []
    current_rank = 1
    for pos, i in enumerate(indexed):
        if pos > 0 and wins[i] < wins[indexed[pos - 1]]:
            current_rank = pos + 1
        ranking.append({"rank": current_rank, "entry_id": entry_ids[i], "wins": wins[i]})

    return {
        "ranking": ranking,
        "pairwise_matrix": d,
        "path_strengths": p,
    }


class CondorcetEngine(TournamentEngine):
    """Condorcet tournament with Schulze method resolution."""

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        try:
            CondorcetConfig(**config)
            return []
        except Exception as e:
            return [str(e)]

    def initialize(self, entries: list[TournamentEntry], config: dict[str, Any]) -> dict[str, Any]:
        cfg = CondorcetConfig(**config)
        entry_ids = [str(e.id) for e in entries]

        # Generate all N*(N-1)/2 pairwise matchups
        matchups: list[dict[str, str]] = []
        for a_id, b_id in combinations(entry_ids, 2):
            matchups.append(
                {
                    "matchup_id": str(uuid4()),
                    "entry_a_id": a_id,
                    "entry_b_id": b_id,
                }
            )

        matchup_ids = [m["matchup_id"] for m in matchups]
        total_matchups = len(matchups)

        # Pre-generate randomized matchup order per voter
        voter_matchup_orders: dict[str, list[str]] = {}
        voter_progress: dict[str, dict[str, int]] = {}
        rng = random.Random()

        for label in cfg.voter_labels:
            order = list(matchup_ids)
            rng.shuffle(order)
            voter_matchup_orders[label] = order
            voter_progress[label] = {
                "completed_matchups": 0,
                "total_matchups": total_matchups,
            }

        return {
            "voter_labels": list(cfg.voter_labels),
            "ballots_required": len(cfg.voter_labels),
            "ballots_submitted": 0,
            "entry_ids": entry_ids,
            "matchups": matchups,
            "voter_matchup_orders": voter_matchup_orders,
            "voter_progress": voter_progress,
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

        # Find next matchup for this voter
        order = state["voter_matchup_orders"][voter_label]
        next_idx = progress["completed_matchups"]
        next_matchup_id = order[next_idx]

        # Look up matchup details
        matchup_map = {m["matchup_id"]: m for m in state["matchups"]}
        matchup = matchup_map[next_matchup_id]

        return CondorcetMatchupContext(
            matchup_id=matchup["matchup_id"],
            entry_a={"id": matchup["entry_a_id"]},
            entry_b={"id": matchup["entry_b_id"]},
            matchup_number=next_idx + 1,
            total_matchups=progress["total_matchups"],
        )

    def submit_vote(self, state: dict[str, Any], voter_label: str, vote_payload: dict[str, Any]) -> dict[str, Any]:
        state = copy.deepcopy(state)

        if voter_label not in state["voter_labels"]:
            raise ValidationError(f"Unknown voter: '{voter_label}'")

        matchup_id = vote_payload.get("matchup_id")
        winner_entry_id = vote_payload.get("winner_entry_id")

        # Validate matchup exists
        matchup_map = {m["matchup_id"]: m for m in state["matchups"]}
        matchup = matchup_map.get(str(matchup_id))
        if matchup is None:
            raise ValidationError(f"Matchup {matchup_id} not found")

        # Validate winner is a participant
        if winner_entry_id not in (matchup["entry_a_id"], matchup["entry_b_id"]):
            raise ValidationError(f"Winner {winner_entry_id} is not a participant in this matchup")

        # Validate voter hasn't already voted this matchup
        for v in state["votes"]:
            if v["voter_label"] == voter_label and v["matchup_id"] == matchup_id:
                raise ValidationError(f"Voter '{voter_label}' has already voted on matchup {matchup_id}")

        state["votes"].append(
            {
                "voter_label": voter_label,
                "matchup_id": matchup_id,
                "winner_entry_id": winner_entry_id,
            }
        )

        # Update voter progress
        if voter_label in state["voter_progress"]:
            state["voter_progress"][voter_label]["completed_matchups"] += 1

        return state

    def is_complete(self, state: dict[str, Any]) -> bool:
        for progress in state["voter_progress"].values():
            if progress["completed_matchups"] < progress["total_matchups"]:
                return False
        return True

    def compute_result(self, state: dict[str, Any], entries: list[TournamentEntry]) -> Result:
        entry_ids = state["entry_ids"]
        schulze_result = _schulze(entry_ids, state["matchups"], state["votes"])

        ranking = schulze_result["ranking"]
        winner_ids = [r["entry_id"] for r in ranking if r["rank"] == 1]

        return Result(
            winner_ids=[UUID(wid) for wid in winner_ids],
            ranking=ranking,
            metadata={
                "pairwise_matrix": schulze_result["pairwise_matrix"],
                "path_strengths": schulze_result["path_strengths"],
            },
        )
