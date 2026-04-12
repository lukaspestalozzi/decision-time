"""Tournament repository — JSON file persistence for Tournaments."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from app.exceptions import ConflictError, NotFoundError
from app.repositories.util import acquire_lock, list_dir, read_json, write_json
from app.schemas.common import TournamentStatus
from app.schemas.tournament import Tournament


class TournamentRepository:
    """Persists Tournament entities as JSON files on disk."""

    def __init__(self, data_dir: Path) -> None:
        self._dir = data_dir / "tournaments"

    def _path(self, tournament_id: UUID) -> Path:
        return self._dir / f"{tournament_id}.json"

    def get(self, tournament_id: UUID) -> Tournament:
        """Get a tournament by ID. Raises NotFoundError if not found."""
        data = read_json(self._path(tournament_id))
        return Tournament.model_validate(data)

    def list_all(self, status: list[TournamentStatus] | None = None) -> list[Tournament]:
        """List tournaments, optionally filtered by status.

        Returns sorted by created_at descending.
        """
        tournaments: list[Tournament] = []
        for path in list_dir(self._dir):
            data = read_json(path)
            tournament = Tournament.model_validate(data)
            if status and tournament.status not in status:
                continue
            tournaments.append(tournament)
        tournaments.sort(key=lambda t: t.created_at, reverse=True)
        return tournaments

    def create(self, tournament: Tournament) -> Tournament:
        """Persist a new tournament."""
        path = self._path(tournament.id)
        with acquire_lock(path):
            write_json(path, tournament.model_dump(mode="json"))
        return tournament

    def save(self, tournament: Tournament, expected_version: int) -> Tournament:
        """Save an updated tournament with optimistic concurrency check.

        Acquires lock, reads current version from disk, compares with expected_version.
        If mismatch, raises ConflictError. Otherwise increments version, sets updated_at, writes.
        """
        path = self._path(tournament.id)
        with acquire_lock(path):
            current_data = read_json(path)
            current_version = current_data.get("version", 1)
            if current_version != expected_version:
                raise ConflictError(f"Version conflict: expected {expected_version}, found {current_version}")
            tournament.version = current_version + 1
            tournament.updated_at = datetime.now(UTC)
            write_json(path, tournament.model_dump(mode="json"))
        return tournament

    def delete(self, tournament_id: UUID) -> None:
        """Delete a tournament file. Raises NotFoundError if not found."""
        path = self._path(tournament_id)
        if not path.exists():
            raise NotFoundError(f"Tournament {tournament_id} not found")
        path.unlink()
