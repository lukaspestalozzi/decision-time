"""Swiss system tournament engine.

Pairs entries over a fixed number of rounds. Each round uses Dutch-style
score-group pairing with rematch avoidance. Final ranking is by points, with
Buchholz and head-to-head tiebreakers.
"""

import copy
import math
import random
from typing import Any
from uuid import UUID, uuid5

from app.engines.base import CompletedContext, SwissMatchupContext, TournamentEngine, VoteContext
from app.exceptions import ValidationError
from app.schemas.common import SwissConfig
from app.schemas.tournament import Result, TournamentEntry

_WIN_POINTS = 1.0
_DRAW_POINTS = 0.5
_BYE_POINTS = 1.0

# Namespace for deterministic matchup IDs — stable IDs allow replay to rebuild state
# from recorded votes without mismatching freshly generated UUIDs.
_SWISS_NAMESPACE = UUID("8f4a6c3d-2e1b-4f5a-9c8d-7e6f5a4b3c2d")


def _matchup_id(round_number: int, entry_a_id: str, entry_b_id: str | None) -> str:
    b = entry_b_id if entry_b_id is not None else "bye"
    return str(uuid5(_SWISS_NAMESPACE, f"{round_number}:{entry_a_id}:{b}"))


def _empty_standing() -> dict[str, Any]:
    return {
        "points": 0.0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "byes": 0,
        "opponents": [],
        "results_vs": {},
    }


def _deterministic_seed(entries: list[TournamentEntry]) -> int:
    """Seed derived from entry IDs so shuffling is reproducible across replays."""
    ids = sorted(str(e.id) for e in entries)
    return hash(tuple(ids)) & 0xFFFFFFFF


def _apply_bye(standings: dict[str, dict[str, Any]], entry_id: str) -> None:
    s = standings[entry_id]
    s["points"] += _BYE_POINTS
    s["byes"] += 1


def _select_bye_entry(entry_ids: list[str], standings: dict[str, dict[str, Any]]) -> str:
    """Pick the entry that should receive a bye: lowest-scored without a prior bye.

    Falls back to absolute lowest-scored if everyone has already had a bye.
    Tiebreak on entry_id for determinism.
    """
    return min(
        entry_ids,
        key=lambda eid: (standings[eid]["byes"], standings[eid]["points"], eid),
    )


def _pair_round(
    round_number: int,
    entry_ids: list[str],
    standings: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Score-group Dutch pairing with rematch avoidance.

    Sorts entries by points descending (stable on entry_id), walks from the top
    and greedily pairs each unpaired entry with the next candidate who hasn't
    already been an opponent. Falls back to a forced rematch if no unpaired
    non-opponent remains. Assumes even `entry_ids` count — bye selection must
    happen upstream.
    """
    ordered = sorted(entry_ids, key=lambda eid: (-standings[eid]["points"], eid))
    unpaired = list(ordered)
    matchups: list[dict[str, Any]] = []
    while unpaired:
        a = unpaired.pop(0)
        prior_opponents = set(standings[a]["opponents"])
        partner_idx: int | None = None
        for i, candidate in enumerate(unpaired):
            if candidate not in prior_opponents:
                partner_idx = i
                break
        if partner_idx is None:
            partner_idx = 0  # forced rematch
        partner = unpaired.pop(partner_idx)
        matchups.append(
            {
                "matchup_id": _matchup_id(round_number, a, partner),
                "entry_a_id": a,
                "entry_b_id": partner,
                "result": None,
                "is_bye": False,
            }
        )
    return matchups


def _build_round(
    round_number: int,
    entry_ids: list[str],
    standings: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build a round, inserting a bye matchup for the selected entry if needed."""
    playing = list(entry_ids)
    bye_matchup: dict[str, Any] | None = None
    if len(playing) % 2 == 1:
        bye_id = _select_bye_entry(playing, standings)
        playing.remove(bye_id)
        _apply_bye(standings, bye_id)
        bye_matchup = {
            "matchup_id": _matchup_id(round_number, bye_id, None),
            "entry_a_id": bye_id,
            "entry_b_id": None,
            "result": "bye",
            "is_bye": True,
        }
    matchups = _pair_round(round_number, playing, standings)
    if bye_matchup is not None:
        matchups.append(bye_matchup)
    return {"round_number": round_number, "matchups": matchups}


def _apply_result(
    standings: dict[str, dict[str, Any]],
    entry_a_id: str,
    entry_b_id: str,
    result: str,
) -> None:
    """Mutate standings to reflect a matchup result."""
    sa = standings[entry_a_id]
    sb = standings[entry_b_id]
    sa["opponents"].append(entry_b_id)
    sb["opponents"].append(entry_a_id)
    if result == "a_wins":
        sa["points"] += _WIN_POINTS
        sa["wins"] += 1
        sb["losses"] += 1
        sa["results_vs"][entry_b_id] = "win"
        sb["results_vs"][entry_a_id] = "loss"
    elif result == "b_wins":
        sb["points"] += _WIN_POINTS
        sb["wins"] += 1
        sa["losses"] += 1
        sa["results_vs"][entry_b_id] = "loss"
        sb["results_vs"][entry_a_id] = "win"
    elif result == "draw":
        sa["points"] += _DRAW_POINTS
        sb["points"] += _DRAW_POINTS
        sa["draws"] += 1
        sb["draws"] += 1
        sa["results_vs"][entry_b_id] = "draw"
        sb["results_vs"][entry_a_id] = "draw"
    else:  # pragma: no cover - guarded by submit_vote
        raise ValidationError(f"Unknown result '{result}'")


def _buchholz(entry_id: str, standings: dict[str, dict[str, Any]]) -> float:
    return float(sum(standings[opp]["points"] for opp in standings[entry_id]["opponents"]))


def _h2h_points(entry_id: str, tied_group: list[str], standings: dict[str, dict[str, Any]]) -> float:
    """Points earned against other entries in a tied group (head-to-head)."""
    results = standings[entry_id]["results_vs"]
    total = 0.0
    for other in tied_group:
        if other == entry_id:
            continue
        r = results.get(other)
        if r == "win":
            total += _WIN_POINTS
        elif r == "draw":
            total += _DRAW_POINTS
    return total


class SwissEngine(TournamentEngine):
    """Swiss system tournament with point-based ranking."""

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        try:
            SwissConfig(**config)
            return []
        except Exception as e:
            return [str(e)]

    def initialize(self, entries: list[TournamentEntry], config: dict[str, Any]) -> dict[str, Any]:
        cfg = SwissConfig(**config)
        if len(entries) < 2:
            raise ValidationError("swiss mode requires at least 2 entries")

        entry_ids = [str(e.id) for e in entries]
        total_rounds = cfg.total_rounds if cfg.total_rounds is not None else max(1, math.ceil(math.log2(len(entries))))

        # Deterministic shuffle for round-1 pairing (so replay reproduces identical bracket).
        round1_ids = list(entry_ids)
        if cfg.shuffle_seed:
            rng = random.Random(_deterministic_seed(entries))
            rng.shuffle(round1_ids)

        standings: dict[str, dict[str, Any]] = {eid: _empty_standing() for eid in entry_ids}

        round_1 = _build_round(1, round1_ids, standings)

        state: dict[str, Any] = {
            "entry_ids": entry_ids,
            "current_round": 1,
            "total_rounds": total_rounds,
            "allow_draws": cfg.allow_draws,
            "rounds": [round_1],
            "standings": standings,
        }
        return self._try_advance_round(state)

    def get_vote_context(self, state: dict[str, Any], voter_label: str) -> VoteContext:
        if self.is_complete(state):
            result = self.compute_result(state, [])
            return CompletedContext(result=result.model_dump(mode="json"))

        current_round = state["current_round"]
        round_data = state["rounds"][current_round - 1]
        non_bye = [m for m in round_data["matchups"] if not m["is_bye"]]

        for i, matchup in enumerate(non_bye):
            if matchup["result"] is None:
                return SwissMatchupContext(
                    matchup_id=matchup["matchup_id"],
                    entry_a={"id": matchup["entry_a_id"]},
                    entry_b={"id": matchup["entry_b_id"]},
                    round=current_round,
                    total_rounds=state["total_rounds"],
                    match_number=i + 1,
                    matches_in_round=len(non_bye),
                    allow_draws=state["allow_draws"],
                    standings=self._standings_snapshot(state),
                )

        # Should not reach here — _try_advance_round handles round completion.
        result = self.compute_result(state, [])
        return CompletedContext(result=result.model_dump(mode="json"))

    def submit_vote(self, state: dict[str, Any], voter_label: str, vote_payload: dict[str, Any]) -> dict[str, Any]:
        state = copy.deepcopy(state)
        matchup_id = vote_payload.get("matchup_id")
        result = vote_payload.get("result")

        if result not in ("a_wins", "b_wins", "draw"):
            raise ValidationError(f"Invalid result '{result}' (expected a_wins, b_wins, or draw)")
        if result == "draw" and not state["allow_draws"]:
            raise ValidationError("draws are not allowed in this tournament")

        current_round = state["current_round"]
        round_data = state["rounds"][current_round - 1]

        target: dict[str, Any] | None = None
        for matchup in round_data["matchups"]:
            if matchup["matchup_id"] == matchup_id:
                target = matchup
                break

        if target is None:
            raise ValidationError(f"Matchup {matchup_id} not found in current round")
        if target["is_bye"]:
            raise ValidationError(f"Matchup {matchup_id} is a bye and cannot be voted on")
        if target["result"] is not None:
            raise ValidationError(f"Matchup {matchup_id} already decided")

        target["result"] = result
        _apply_result(state["standings"], target["entry_a_id"], target["entry_b_id"], result)
        return self._try_advance_round(state)

    def is_complete(self, state: dict[str, Any]) -> bool:
        total_rounds = state["total_rounds"]
        if len(state["rounds"]) < total_rounds:
            return False
        final_round = state["rounds"][-1]
        return all(m["result"] is not None for m in final_round["matchups"])

    def compute_result(self, state: dict[str, Any], entries: list[TournamentEntry]) -> Result:
        standings = state["standings"]
        entry_ids = state["entry_ids"]

        buchholz = {eid: _buchholz(eid, standings) for eid in entry_ids}

        # Pre-sort by (points, buchholz) to identify tied groups for h2h.
        prelim = sorted(
            entry_ids,
            key=lambda eid: (-standings[eid]["points"], -buchholz[eid], eid),
        )

        # Compute head-to-head points within each (points, buchholz) group.
        h2h: dict[str, float] = {}
        i = 0
        while i < len(prelim):
            j = i
            key = (standings[prelim[i]]["points"], buchholz[prelim[i]])
            while j < len(prelim) and (standings[prelim[j]]["points"], buchholz[prelim[j]]) == key:
                j += 1
            group = prelim[i:j]
            for eid in group:
                h2h[eid] = _h2h_points(eid, group, standings)
            i = j

        # Final sort.
        final = sorted(
            entry_ids,
            key=lambda eid: (-standings[eid]["points"], -buchholz[eid], -h2h[eid], eid),
        )

        ranking: list[dict[str, Any]] = []
        current_rank = 1
        for pos, eid in enumerate(final):
            if pos > 0:
                prev = final[pos - 1]
                same_metrics = (
                    standings[eid]["points"] == standings[prev]["points"]
                    and buchholz[eid] == buchholz[prev]
                    and h2h[eid] == h2h[prev]
                )
                if not same_metrics:
                    current_rank = pos + 1
            s = standings[eid]
            ranking.append(
                {
                    "rank": current_rank,
                    "entry_id": eid,
                    "points": s["points"],
                    "wins": s["wins"],
                    "draws": s["draws"],
                    "losses": s["losses"],
                    "byes": s["byes"],
                    "buchholz": buchholz[eid],
                }
            )

        winner_ids = [UUID(r["entry_id"]) for r in ranking if r["rank"] == 1]

        return Result(
            winner_ids=winner_ids,
            ranking=ranking,
            metadata={
                "total_rounds": state["total_rounds"],
                "tiebreakers": ["points", "buchholz", "head_to_head"],
            },
        )

    def _standings_snapshot(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        """Sorted snapshot used by the vote context so the UI can render a live table."""
        standings = state["standings"]
        ordered = sorted(
            state["entry_ids"],
            key=lambda eid: (-standings[eid]["points"], eid),
        )
        snapshot: list[dict[str, Any]] = []
        current_rank = 1
        prev_points: float | None = None
        for pos, eid in enumerate(ordered):
            s = standings[eid]
            if prev_points is not None and s["points"] != prev_points:
                current_rank = pos + 1
            prev_points = s["points"]
            snapshot.append(
                {
                    "rank": current_rank,
                    "entry_id": eid,
                    "points": s["points"],
                    "wins": s["wins"],
                    "draws": s["draws"],
                    "losses": s["losses"],
                }
            )
        return snapshot

    def _try_advance_round(self, state: dict[str, Any]) -> dict[str, Any]:
        """Advance to the next round when the current one is fully resolved."""
        while True:
            current = state["current_round"]
            total = state["total_rounds"]
            round_data = state["rounds"][current - 1]
            if any(m["result"] is None for m in round_data["matchups"]):
                break
            if current >= total:
                break
            next_round = _build_round(current + 1, state["entry_ids"], state["standings"])
            state["rounds"].append(next_round)
            state["current_round"] = current + 1
        return state
