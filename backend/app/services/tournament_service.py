"""Tournament service — lifecycle orchestration between repos and engines."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.engines.base import TournamentEngine, VoteContext
from app.engines.bracket import BracketEngine
from app.engines.condorcet import CondorcetEngine
from app.engines.multivote import MultivoteEngine
from app.engines.score import ScoreEngine
from app.exceptions import InvalidStateError, ValidationError
from app.repositories.options import OptionRepository
from app.repositories.tournaments import TournamentRepository
from app.schemas.common import TournamentMode, TournamentStatus, get_default_config, normalize_config
from app.schemas.tournament import Result, Tournament, TournamentEntry, Vote, VoteStatus


class TournamentService:
    """Orchestrates tournament lifecycle: creation, activation, voting, completion."""

    def __init__(
        self,
        tournament_repo: TournamentRepository,
        option_repo: OptionRepository,
    ) -> None:
        self._repo = tournament_repo
        self._option_repo = option_repo

    def _get_engine(self, mode: TournamentMode) -> TournamentEngine:
        engines: dict[TournamentMode, TournamentEngine] = {
            TournamentMode.BRACKET: BracketEngine(),
            TournamentMode.SCORE: ScoreEngine(),
            TournamentMode.MULTIVOTE: MultivoteEngine(),
            TournamentMode.CONDORCET: CondorcetEngine(),
        }
        engine = engines.get(mode)
        if engine is None:
            raise ValidationError(f"Mode '{mode}' is not yet implemented")
        return engine

    def list_tournaments(self, status: list[TournamentStatus] | None = None) -> list[Tournament]:
        return self._repo.list_all(status=status)

    def get_tournament(self, tournament_id: UUID) -> Tournament:
        return self._repo.get(tournament_id)

    def create_tournament(self, name: str, mode: TournamentMode, description: str = "") -> Tournament:
        tournament = Tournament(
            name=name,
            mode=mode,
            description=description,
            config=get_default_config(mode),
        )
        return self._repo.create(tournament)

    def update_tournament(
        self,
        tournament_id: UUID,
        version: int,
        name: str | None = None,
        description: str | None = None,
        mode: TournamentMode | None = None,
        selected_option_ids: list[UUID] | None = None,
        config: dict[str, Any] | None = None,
    ) -> Tournament:
        tournament = self._repo.get(tournament_id)
        if tournament.status != TournamentStatus.DRAFT:
            raise InvalidStateError("Tournament can only be updated in draft status")
        if name is not None:
            tournament.name = name
        if description is not None:
            tournament.description = description
        if selected_option_ids is not None:
            tournament.selected_option_ids = selected_option_ids
        mode_changed = mode is not None and mode != tournament.mode
        if mode_changed:
            assert mode is not None
            tournament.mode = mode
            # Config is mode-specific. When mode changes, any supplied config is
            # ignored and we reset to the new mode's defaults to avoid cross-mode
            # validation landmines (e.g. bracket enforces exactly one voter).
            tournament.config = get_default_config(mode)
        elif config is not None:
            try:
                tournament.config = normalize_config(tournament.mode, config)
            except Exception as e:
                raise ValidationError(str(e)) from e
        return self._repo.save(tournament, expected_version=version)

    def delete_tournament(self, tournament_id: UUID) -> None:
        self._repo.delete(tournament_id)

    def activate_tournament(self, tournament_id: UUID, version: int) -> Tournament:
        tournament = self._repo.get(tournament_id)
        if tournament.status != TournamentStatus.DRAFT:
            raise InvalidStateError("Only draft tournaments can be activated")

        # Resolve options — silently skip missing/deleted
        options = self._option_repo.get_many(tournament.selected_option_ids)
        if len(options) < 2:
            raise ValidationError("Tournament requires at least 2 valid options to activate")

        # Snapshot options into entries
        entries = [
            TournamentEntry(
                option_id=opt.id,
                option_snapshot=opt.model_dump(mode="json"),
            )
            for opt in options
        ]

        # Initialize engine
        engine = self._get_engine(tournament.mode)
        errors = engine.validate_config(tournament.config)
        if errors:
            raise ValidationError(f"Invalid config: {'; '.join(errors)}")

        initial_state = engine.initialize(entries, tournament.config)

        tournament.status = TournamentStatus.ACTIVE
        tournament.entries = entries
        tournament.state = initial_state
        return self._repo.save(tournament, expected_version=version)

    def cancel_tournament(self, tournament_id: UUID, version: int) -> Tournament:
        tournament = self._repo.get(tournament_id)
        if tournament.status not in (TournamentStatus.DRAFT, TournamentStatus.ACTIVE):
            raise InvalidStateError("Only draft or active tournaments can be cancelled")
        tournament.status = TournamentStatus.CANCELLED
        return self._repo.save(tournament, expected_version=version)

    def clone_tournament(self, tournament_id: UUID) -> Tournament:
        original = self._repo.get(tournament_id)
        clone = Tournament(
            name=f"{original.name} (copy)",
            mode=original.mode,
            description=original.description,
            config=original.config,
            selected_option_ids=list(original.selected_option_ids),
        )
        return self._repo.create(clone)

    def get_vote_context(self, tournament_id: UUID, voter_label: str) -> VoteContext:
        tournament = self._repo.get(tournament_id)
        if tournament.status == TournamentStatus.COMPLETED:
            engine = self._get_engine(tournament.mode)
            return engine.get_vote_context(tournament.state, voter_label)
        if tournament.status != TournamentStatus.ACTIVE:
            raise InvalidStateError("Voting is only available on active tournaments")
        engine = self._get_engine(tournament.mode)
        return engine.get_vote_context(tournament.state, voter_label)

    def submit_vote(
        self,
        tournament_id: UUID,
        version: int,
        voter_label: str,
        payload: dict[str, Any],
    ) -> Tournament:
        tournament = self._repo.get(tournament_id)
        if tournament.status != TournamentStatus.ACTIVE:
            raise InvalidStateError("Voting is only available on active tournaments")

        engine = self._get_engine(tournament.mode)
        new_state = engine.submit_vote(tournament.state, voter_label, payload)

        # Create vote record
        vote = Vote(voter_label=voter_label, payload=payload)
        tournament.votes.append(vote)
        tournament.state = new_state

        # When the last required vote arrives, finalize immediately.
        if engine.is_complete(new_state):
            tournament.status = TournamentStatus.COMPLETED
            tournament.completed_at = datetime.now(UTC)
            tournament.result = engine.compute_result(new_state, tournament.entries)

        return self._repo.save(tournament, expected_version=version)

    def undo_vote(self, tournament_id: UUID, version: int, voter_label: str) -> Tournament:
        """Soft-supersede the latest active vote for `voter_label` and replay state.

        Rejected if: tournament not active, allow_undo is False, voter unknown,
        or no active vote exists for this voter.
        """
        tournament = self._repo.get(tournament_id)
        if tournament.status != TournamentStatus.ACTIVE:
            raise InvalidStateError("Undo is only available on active tournaments")

        allow_undo = tournament.config.get("allow_undo", True)
        if not allow_undo:
            raise InvalidStateError("Undo is disabled for this tournament")

        voter_labels = tournament.config.get("voter_labels", [])
        if voter_label not in voter_labels:
            raise ValidationError(f"Unknown voter: '{voter_label}'")

        # Find the latest active vote for this voter
        active_votes_for_voter = [
            v for v in tournament.votes if v.voter_label == voter_label and v.status == VoteStatus.ACTIVE
        ]
        if not active_votes_for_voter:
            raise ValidationError(f"No vote to undo for voter '{voter_label}'")

        latest = max(active_votes_for_voter, key=lambda v: v.submitted_at)
        latest.status = VoteStatus.SUPERSEDED
        latest.superseded_at = datetime.now(UTC)

        # Replay state from remaining active votes
        engine = self._get_engine(tournament.mode)
        active_votes = [v for v in tournament.votes if v.status == VoteStatus.ACTIVE]
        tournament.state = engine.replay_state(tournament.entries, tournament.config, active_votes)

        return self._repo.save(tournament, expected_version=version)

    def get_result(self, tournament_id: UUID) -> Result:
        tournament = self._repo.get(tournament_id)
        if tournament.status != TournamentStatus.COMPLETED or tournament.result is None:
            raise InvalidStateError("Result is only available for completed tournaments")
        return tournament.result

    def get_state(self, tournament_id: UUID) -> dict[str, Any]:
        tournament = self._repo.get(tournament_id)
        return tournament.state
