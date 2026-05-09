"""Global option-popularity Elo tracker.

Listens for tournament completions and folds the head-to-head outcomes into a
per-Option global Elo rating. Idempotent via Tournament.elo_applied. The
tournament must already have status=COMPLETED and elo_applied=True (set and
persisted by the caller) before this is invoked — see "save-first ordering"
in the implementation plan.
"""

import logging

from app.engines.base import PairwiseOutcome, TournamentEngine
from app.exceptions import NotFoundError
from app.repositories.options import OptionRepository
from app.schemas.tournament import Tournament
from app.utils.elo_math import GLOBAL_K_FACTOR, apply_elo

logger = logging.getLogger(__name__)


class GlobalEloService:
    """Apply pairwise outcomes from a completed tournament to global Option ratings."""

    def __init__(self, option_repo: OptionRepository) -> None:
        self._options = option_repo

    def apply_tournament_completion(
        self,
        tournament: Tournament,
        engine: TournamentEngine,
    ) -> None:
        """Bump per-option Elo for every pairwise outcome from this tournament.

        Save-first contract: caller has already persisted ``tournament.elo_applied=True``
        before invoking this. On failure, partial bumps may be left applied; the
        idempotency flag prevents replays.
        """
        outcomes: list[PairwiseOutcome] = engine.extract_pairwise_outcomes(tournament.state, tournament.entries)
        if not outcomes:
            return

        # Map entry_id (str) -> option_id (UUID).
        entry_to_option = {str(e.id): e.option_id for e in tournament.entries}

        for outcome in outcomes:
            option_a_id = entry_to_option.get(outcome["entry_a_id"])
            option_b_id = entry_to_option.get(outcome["entry_b_id"])
            if option_a_id is None or option_b_id is None:
                # Unknown entry id; skip.
                continue
            try:
                option_a = self._options.get(option_a_id)
                option_b = self._options.get(option_b_id)
            except NotFoundError as exc:
                logger.warning(
                    "Skipping global Elo bump for tournament %s outcome %s: %s",
                    tournament.id,
                    outcome["source"],
                    exc,
                )
                continue

            new_a, new_b, _, _ = apply_elo(
                option_a.elo_rating,
                option_b.elo_rating,
                score_a=outcome["score_a"],
                k=GLOBAL_K_FACTOR,
            )
            try:
                self._options.bump_elo_rating(option_a_id, new_a)
                self._options.bump_elo_rating(option_b_id, new_b)
            except NotFoundError as exc:
                logger.warning(
                    "Failed to bump global Elo for tournament %s outcome %s: %s",
                    tournament.id,
                    outcome["source"],
                    exc,
                )
                continue
