"""Single elimination bracket tournament engine."""

import copy
import math
import random
from typing import Any
from uuid import uuid4

from app.engines.base import BracketMatchupContext, CompletedContext, TournamentEngine, VoteContext
from app.exceptions import ValidationError
from app.schemas.common import BracketConfig
from app.schemas.tournament import Result, TournamentEntry


def _round_name(round_number: int, total_rounds: int) -> str:
    """Generate a human-readable round name."""
    rounds_from_end = total_rounds - round_number
    match rounds_from_end:
        case 0:
            return "Final"
        case 1:
            return "Semi-finals"
        case 2:
            return "Quarter-finals"
        case _:
            return f"Round of {2 ** (rounds_from_end + 1)}"


class BracketEngine(TournamentEngine):
    """Single elimination bracket tournament."""

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        try:
            BracketConfig(**config)
            return []
        except Exception as e:
            return [str(e)]

    def initialize(self, entries: list[TournamentEntry], config: dict[str, Any]) -> dict[str, Any]:
        cfg = BracketConfig(**config)
        n = len(entries)
        bracket_size = 1
        while bracket_size < n:
            bracket_size *= 2
        total_rounds = int(math.log2(bracket_size))

        # Shuffle entries
        shuffled = list(entries)
        if cfg.shuffle_seed:
            random.shuffle(shuffled)

        # Build seeds array: real entries + None byes
        seeds: list[TournamentEntry | None] = list(shuffled) + [None] * (bracket_size - n)

        # Pair: seed[i] vs seed[bracket_size - 1 - i]
        matchups: list[dict[str, Any]] = []
        for i in range(bracket_size // 2):
            a = seeds[i]
            b = seeds[bracket_size - 1 - i]
            assert a is not None  # top seeds are always real entries
            is_bye = b is None
            matchups.append(
                {
                    "matchup_id": str(uuid4()),
                    "entry_a_id": str(a.id),
                    "entry_b_id": str(b.id) if b else None,
                    "winner_id": str(a.id) if is_bye else None,
                    "is_bye": is_bye,
                }
            )

        round_1: dict[str, Any] = {
            "round_number": 1,
            "name": _round_name(1, total_rounds),
            "matchups": matchups,
        }

        state: dict[str, Any] = {
            "rounds": [round_1],
            "current_round": 1,
            "total_rounds": total_rounds,
            "bracket_size": bracket_size,
        }

        return self._try_advance_round(state)

    def get_vote_context(self, state: dict[str, Any], voter_label: str) -> VoteContext:
        if self.is_complete(state):
            result = self.compute_result(state, [])
            return CompletedContext(result=result.model_dump(mode="json"))

        current_round = state["current_round"]
        round_data = state["rounds"][current_round - 1]
        non_bye_matchups = [m for m in round_data["matchups"] if not m["is_bye"]]

        for i, matchup in enumerate(non_bye_matchups):
            if matchup["winner_id"] is None:
                return BracketMatchupContext(
                    matchup_id=matchup["matchup_id"],
                    entry_a={"id": matchup["entry_a_id"]},
                    entry_b={"id": matchup["entry_b_id"]},
                    round=current_round,
                    round_name=round_data["name"],
                    match_number=i + 1,
                    matches_in_round=len(non_bye_matchups),
                )

        # Should not reach here — _try_advance_round handles round completion
        result = self.compute_result(state, [])
        return CompletedContext(result=result.model_dump(mode="json"))

    def submit_vote(self, state: dict[str, Any], voter_label: str, vote_payload: dict[str, Any]) -> dict[str, Any]:
        state = copy.deepcopy(state)
        matchup_id = vote_payload.get("matchup_id")
        winner_entry_id = vote_payload.get("winner_entry_id")

        current_round = state["current_round"]
        round_data = state["rounds"][current_round - 1]

        # Find the matchup
        target = None
        for matchup in round_data["matchups"]:
            if matchup["matchup_id"] == matchup_id:
                target = matchup
                break

        if target is None:
            raise ValidationError(f"Matchup {matchup_id} not found in current round")

        if target["winner_id"] is not None:
            raise ValidationError(f"Matchup {matchup_id} already decided")

        if winner_entry_id not in (target["entry_a_id"], target["entry_b_id"]):
            raise ValidationError(f"Winner {winner_entry_id} is not a participant in this matchup")

        target["winner_id"] = winner_entry_id
        return self._try_advance_round(state)

    def is_complete(self, state: dict[str, Any]) -> bool:
        total_rounds = state["total_rounds"]
        if len(state["rounds"]) < total_rounds:
            return False
        final_round = state["rounds"][-1]
        return all(m["winner_id"] is not None for m in final_round["matchups"])

    def compute_result(self, state: dict[str, Any], entries: list[TournamentEntry]) -> Result:
        ranking: list[dict[str, Any]] = []
        ranked_count = 0

        for round_data in reversed(state["rounds"]):
            if round_data["round_number"] == state["total_rounds"]:
                # Final round
                final = round_data["matchups"][0]
                winner_id = final["winner_id"]
                loser_id = final["entry_a_id"] if final["winner_id"] == final["entry_b_id"] else final["entry_b_id"]
                ranking.append({"rank": 1, "entry_id": winner_id})
                ranking.append({"rank": 2, "entry_id": loser_id})
                ranked_count = 2
            else:
                rank = ranked_count + 1
                for matchup in round_data["matchups"]:
                    if matchup["is_bye"]:
                        continue
                    loser_id = (
                        matchup["entry_a_id"]
                        if matchup["winner_id"] == matchup["entry_b_id"]
                        else matchup["entry_b_id"]
                    )
                    ranking.append({"rank": rank, "entry_id": loser_id})
                    ranked_count += 1

        winner_id_str = ranking[0]["entry_id"]
        # Map back to UUID if entries are provided
        if entries:
            entry_map = {str(e.id): e for e in entries}
            winner_entry = entry_map.get(winner_id_str)
            winner_uuid = winner_entry.id if winner_entry else uuid4()
        else:
            from uuid import UUID

            winner_uuid = UUID(winner_id_str)

        return Result(
            winner_ids=[winner_uuid],
            ranking=ranking,
            metadata={"bracket_size": state["bracket_size"], "total_rounds": state["total_rounds"]},
        )

    def _try_advance_round(self, state: dict[str, Any]) -> dict[str, Any]:
        """If current round is fully decided, create next round and advance."""
        while True:
            current = state["current_round"]
            total = state["total_rounds"]
            if current > total:
                break
            round_data = state["rounds"][current - 1]
            if any(m["winner_id"] is None for m in round_data["matchups"]):
                break
            if current == total:
                break  # Final round complete — tournament done
            # Create next round from winners
            winners = [m["winner_id"] for m in round_data["matchups"]]
            next_matchups: list[dict[str, Any]] = []
            for i in range(0, len(winners), 2):
                next_matchups.append(
                    {
                        "matchup_id": str(uuid4()),
                        "entry_a_id": winners[i],
                        "entry_b_id": winners[i + 1],
                        "winner_id": None,
                        "is_bye": False,
                    }
                )
            state["rounds"].append(
                {
                    "round_number": current + 1,
                    "name": _round_name(current + 1, total),
                    "matchups": next_matchups,
                }
            )
            state["current_round"] = current + 1
        return state
