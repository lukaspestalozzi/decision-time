"""Option service — business logic for options and tags."""

from uuid import UUID

from app.repositories.options import OptionRepository
from app.schemas.option import Option


class OptionService:
    """Orchestrates option operations between the router and repository layers."""

    def __init__(self, option_repo: OptionRepository) -> None:
        self._repo = option_repo

    def list_options(
        self,
        q: str | None = None,
        tags_all: list[str] | None = None,
        tags_any: list[str] | None = None,
    ) -> list[Option]:
        return self._repo.list_all(q=q, tags_all=tags_all, tags_any=tags_any)

    def get_option(self, option_id: UUID) -> Option:
        return self._repo.get(option_id)

    def create_option(self, name: str, description: str = "", tags: list[str] | None = None) -> Option:
        option = Option(name=name, description=description, tags=tags or [])
        return self._repo.create(option)

    def update_option(
        self,
        option_id: UUID,
        name: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> Option:
        return self._repo.update(option_id, name=name, description=description, tags=tags)

    def delete_option(self, option_id: UUID) -> None:
        self._repo.delete(option_id)

    def bulk_create(self, names: list[str], tags: list[str] | None = None) -> list[Option]:
        """Create multiple options from a list of names.

        Skips blank names, duplicates within the request, and names matching existing options.
        """
        existing = {o.name for o in self._repo.list_all()}
        seen: set[str] = set()
        created: list[Option] = []
        for raw_name in names:
            name = raw_name.strip()
            if not name or name in seen or name in existing:
                continue
            seen.add(name)
            option = Option(name=name, tags=tags or [])
            created.append(self._repo.create(option))
        return created

    def bulk_update_tags(
        self,
        option_ids: list[UUID],
        add_tags: list[str] | None = None,
        remove_tags: list[str] | None = None,
    ) -> list[Option]:
        """Add/remove tags on multiple options. Additive/subtractive, not replacement."""
        updated: list[Option] = []
        for oid in option_ids:
            option = self._repo.get(oid)
            current_tags = set(option.tags)
            if add_tags:
                current_tags.update(add_tags)
            if remove_tags:
                current_tags -= set(remove_tags)
            result = self._repo.update(oid, tags=sorted(current_tags))
            updated.append(result)
        return updated

    def get_all_tags(self) -> list[str]:
        return self._repo.get_all_tags()
