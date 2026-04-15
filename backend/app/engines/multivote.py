"""Multivoting tournament engine."""

import copy
from typing import Any

from app.engines.base import AlreadyVotedContext, BallotContext, CompletedContext, TournamentEngine, VoteContext
from app.exceptions import ValidationError
from app.schemas.common import MultivoteConfig
from app.schemas.tournament import Result, TournamentEntry


class MultivoteEngine(TournamentEngine):
    """Multivote tournament: distribute a vote budget across options."""

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        try:
            MultivoteConfig(**config)
            return []
        except Exception as e:
            return [str(e)]

    def initialize(self, entries: list[TournamentEntry], config: dict[str, Any]) -> dict[str, Any]:
        cfg = MultivoteConfig(**config)
        total_votes = cfg.total_votes if cfg.total_votes is not None else len(entries) * 2
        return {
            "voter_labels": list(cfg.voter_labels),
            "ballots_required": len(cfg.voter_labels),
            "ballots_submitted": 0,
            "total_votes": total_votes,
            "max_per_option": cfg.max_per_option,
            "entry_ids": [str(e.id) for e in entries],
            "votes": [],
        }

    def get_vote_context(self, state: dict[str, Any], voter_label: str) -> VoteContext:
        if self.is_complete(state):
            result = self.compute_result(state, [])
            return CompletedContext(result=result.model_dump(mode="json"))

        if voter_label not in state["voter_labels"]:
            raise ValidationError(f"Unknown voter: '{voter_label}'")

        voted_labels = {v["voter_label"] for v in state["votes"]}
        if voter_label in voted_labels:
            return AlreadyVotedContext()

        return BallotContext(
            entries=[{"id": eid} for eid in state["entry_ids"]],
            ballot_type="multivote",
            ballots_submitted=state["ballots_submitted"],
            ballots_required=state["ballots_required"],
        )

    def submit_vote(self, state: dict[str, Any], voter_label: str, vote_payload: dict[str, Any]) -> dict[str, Any]:
        state = copy.deepcopy(state)

        if voter_label not in state["voter_labels"]:
            raise ValidationError(f"Unknown voter: '{voter_label}'")

        voted_labels = {v["voter_label"] for v in state["votes"]}
        if voter_label in voted_labels:
            raise ValidationError(f"Voter '{voter_label}' has already submitted a ballot")

        allocations = vote_payload.get("allocations", [])
        total_votes = state["total_votes"]
        max_per = state["max_per_option"]
        entry_ids = set(state["entry_ids"])

        # Validate entry_ids
        for a in allocations:
            if a["entry_id"] not in entry_ids:
                raise ValidationError(f"Unknown entry_id: {a['entry_id']}")

        # Validate sum
        vote_sum = sum(a["votes"] for a in allocations)
        if vote_sum != total_votes:
            raise ValidationError(f"Allocations sum to {vote_sum}, must equal total_votes ({total_votes})")

        # Validate per-option cap
        if max_per is not None:
            for a in allocations:
                if a["votes"] > max_per:
                    raise ValidationError(
                        f"Allocation {a['votes']} for {a['entry_id']} exceeds max_per_option ({max_per})"
                    )

        # Validate non-negative
        for a in allocations:
            if a["votes"] < 0:
                raise ValidationError(f"Allocation cannot be negative: {a['votes']}")

        state["votes"].append({"voter_label": voter_label, "allocations": allocations})
        state["ballots_submitted"] += 1
        return state

    def is_complete(self, state: dict[str, Any]) -> bool:
        return bool(state["ballots_submitted"] >= state["ballots_required"])

    def compute_result(self, state: dict[str, Any], entries: list[TournamentEntry]) -> Result:
        entry_ids = state["entry_ids"]
        totals: dict[str, int] = {eid: 0 for eid in entry_ids}

        for vote in state["votes"]:
            for a in vote["allocations"]:
                totals[a["entry_id"]] += a["votes"]

        sorted_entries = sorted(entry_ids, key=lambda eid: totals[eid], reverse=True)

        ranking: list[dict[str, Any]] = []
        current_rank = 1
        for i, eid in enumerate(sorted_entries):
            if i > 0 and totals[eid] < totals[sorted_entries[i - 1]]:
                current_rank = i + 1
            ranking.append({"rank": current_rank, "entry_id": eid, "total_votes": totals[eid]})

        winner_ids = [r["entry_id"] for r in ranking if r["rank"] == 1]

        from uuid import UUID

        return Result(
            winner_ids=[UUID(wid) for wid in winner_ids],
            ranking=ranking,
            metadata={"total_ballots": state["ballots_submitted"], "total_votes_per_ballot": state["total_votes"]},
        )
