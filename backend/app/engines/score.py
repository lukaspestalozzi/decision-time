"""Score / Rating tournament engine."""

import copy
from typing import Any

from app.engines.base import AlreadyVotedContext, BallotContext, CompletedContext, TournamentEngine, VoteContext
from app.exceptions import ValidationError
from app.schemas.common import ScoreConfig
from app.schemas.tournament import Result, TournamentEntry


class ScoreEngine(TournamentEngine):
    """Score tournament: each option rated on an integer scale, highest average wins."""

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        try:
            cfg = ScoreConfig(**config)
            if cfg.min_score >= cfg.max_score:
                return ["min_score must be less than max_score"]
            return []
        except Exception as e:
            return [str(e)]

    def initialize(self, entries: list[TournamentEntry], config: dict[str, Any]) -> dict[str, Any]:
        cfg = ScoreConfig(**config)
        return {
            "ballots_required": cfg.voter_count,
            "ballots_submitted": 0,
            "min_score": cfg.min_score,
            "max_score": cfg.max_score,
            "entry_ids": [str(e.id) for e in entries],
            "votes": [],
        }

    def get_vote_context(self, state: dict[str, Any], voter_label: str) -> VoteContext:
        if self.is_complete(state):
            result = self.compute_result(state, [])
            return CompletedContext(result=result.model_dump(mode="json"))

        voted_labels = {v["voter_label"] for v in state["votes"]}
        if voter_label in voted_labels:
            return AlreadyVotedContext()

        return BallotContext(
            entries=[{"id": eid} for eid in state["entry_ids"]],
            ballot_type="score",
            ballots_submitted=state["ballots_submitted"],
            ballots_required=state["ballots_required"],
        )

    def submit_vote(self, state: dict[str, Any], voter_label: str, vote_payload: dict[str, Any]) -> dict[str, Any]:
        state = copy.deepcopy(state)

        voted_labels = {v["voter_label"] for v in state["votes"]}
        if voter_label in voted_labels:
            raise ValidationError(f"Voter '{voter_label}' has already submitted a ballot")

        scores = vote_payload.get("scores", [])
        entry_ids = set(state["entry_ids"])
        scored_ids = {s["entry_id"] for s in scores}

        if scored_ids != entry_ids:
            missing = entry_ids - scored_ids
            raise ValidationError(f"Every entry must have a score. Missing: {missing}")

        min_s = state["min_score"]
        max_s = state["max_score"]
        for s in scores:
            if not isinstance(s["score"], int) or s["score"] < min_s or s["score"] > max_s:
                raise ValidationError(f"Score {s['score']} out of range [{min_s}, {max_s}]")

        state["votes"].append({"voter_label": voter_label, "scores": scores})
        state["ballots_submitted"] += 1
        return state

    def is_complete(self, state: dict[str, Any]) -> bool:
        return bool(state["ballots_submitted"] >= state["ballots_required"])

    def compute_result(self, state: dict[str, Any], entries: list[TournamentEntry]) -> Result:
        entry_ids = state["entry_ids"]
        totals: dict[str, float] = {eid: 0.0 for eid in entry_ids}
        count = state["ballots_submitted"]

        for vote in state["votes"]:
            for s in vote["scores"]:
                totals[s["entry_id"]] += s["score"]

        averages = {eid: totals[eid] / count if count > 0 else 0.0 for eid in entry_ids}
        sorted_entries = sorted(entry_ids, key=lambda eid: averages[eid], reverse=True)

        ranking: list[dict[str, Any]] = []
        current_rank = 1
        for i, eid in enumerate(sorted_entries):
            if i > 0 and averages[eid] < averages[sorted_entries[i - 1]]:
                current_rank = i + 1
            ranking.append({"rank": current_rank, "entry_id": eid, "average_score": averages[eid]})

        winner_ids = [r["entry_id"] for r in ranking if r["rank"] == 1]

        from uuid import UUID

        return Result(
            winner_ids=[UUID(wid) for wid in winner_ids],
            ranking=ranking,
            metadata={"total_ballots": count, "min_score": state["min_score"], "max_score": state["max_score"]},
        )
