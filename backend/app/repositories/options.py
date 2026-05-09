"""Option repository — JSON file persistence for Options."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from app.exceptions import NotFoundError
from app.repositories.util import acquire_lock, list_dir, read_json, write_json
from app.schemas.option import Option

SortBy = Literal["created_at", "name", "elo_rating"]
SortOrder = Literal["asc", "desc"]


class OptionRepository:
    """Persists Option entities as JSON files on disk."""

    def __init__(self, data_dir: Path) -> None:
        self._dir = data_dir / "options"

    def _path(self, option_id: UUID) -> Path:
        return self._dir / f"{option_id}.json"

    def get(self, option_id: UUID) -> Option:
        """Get a single option by ID. Raises NotFoundError if not found."""
        data = read_json(self._path(option_id))
        return Option.model_validate(data)

    def list_all(
        self,
        q: str | None = None,
        tags_all: list[str] | None = None,
        tags_any: list[str] | None = None,
        sort_by: SortBy = "created_at",
        sort_order: SortOrder = "desc",
    ) -> list[Option]:
        """List options with optional filtering and sorting.

        q: case-insensitive substring match on name.
        tags_all: option must have ALL these tags (AND).
        tags_any: option must have at least ONE of these tags (OR).
        sort_by: one of "created_at", "name", "elo_rating".
        sort_order: "asc" or "desc".
        """
        options: list[Option] = []
        for path in list_dir(self._dir):
            data = read_json(path)
            option = Option.model_validate(data)
            if q and q.lower() not in option.name.lower():
                continue
            if tags_all and not set(tags_all).issubset(set(option.tags)):
                continue
            if tags_any and not set(tags_any) & set(option.tags):
                continue
            options.append(option)

        if sort_by == "name":
            options.sort(key=lambda o: o.name.lower(), reverse=(sort_order == "desc"))
        elif sort_by == "elo_rating":
            options.sort(key=lambda o: o.elo_rating, reverse=(sort_order == "desc"))
        else:
            options.sort(key=lambda o: o.created_at, reverse=(sort_order == "desc"))
        return options

    def create(self, option: Option) -> Option:
        """Persist a new option."""
        path = self._path(option.id)
        with acquire_lock(path):
            write_json(path, option.model_dump(mode="json"))
        return option

    def update(
        self,
        option_id: UUID,
        name: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> Option:
        """Update an existing option. Raises NotFoundError if not found."""
        path = self._path(option_id)
        with acquire_lock(path):
            data = read_json(path)
            option = Option.model_validate(data)
            updates: dict[str, str | list[str] | datetime] = {"updated_at": datetime.now(UTC)}
            if name is not None:
                updates["name"] = name
            if description is not None:
                updates["description"] = description
            if tags is not None:
                updates["tags"] = tags
            # Re-validate to trigger tag normalization and name stripping
            option = Option.model_validate(option.model_dump() | updates)
            write_json(path, option.model_dump(mode="json"))
        return option

    def bump_elo_rating(self, option_id: UUID, new_rating: float) -> Option:
        """Persist a new global Elo rating without touching ``updated_at``.

        Acquires the option's file lock, re-reads the JSON, sets ``elo_rating``,
        writes atomically, returns the updated Option. Raises NotFoundError if
        the option file is missing.
        """
        path = self._path(option_id)
        with acquire_lock(path):
            data = read_json(path)
            data["elo_rating"] = new_rating
            option = Option.model_validate(data)
            write_json(path, option.model_dump(mode="json"))
        return option

    def delete(self, option_id: UUID) -> None:
        """Delete an option file. Raises NotFoundError if not found."""
        path = self._path(option_id)
        if not path.exists():
            raise NotFoundError(f"Option {option_id} not found")
        path.unlink()

    def get_many(self, option_ids: list[UUID]) -> list[Option]:
        """Get multiple options by ID. Silently skips IDs that don't exist."""
        results: list[Option] = []
        for oid in option_ids:
            try:
                results.append(self.get(oid))
            except NotFoundError:
                continue
        return results

    def get_all_tags(self) -> list[str]:
        """Return sorted, deduplicated list of all tags across all options."""
        all_tags: set[str] = set()
        for path in list_dir(self._dir):
            data = read_json(path)
            option = Option.model_validate(data)
            all_tags.update(option.tags)
        return sorted(all_tags)
