"""Option service — business logic for options and tags."""

from uuid import UUID

from app.repositories.options import OptionRepository
from app.schemas.common import normalize_tag
from app.schemas.option import BulkCreateResult, Option


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

    def bulk_create(self, names: list[str], tags: list[str] | None = None) -> BulkCreateResult:
        """Create options from names; merge supplied tags into any existing matches.

        - Blank names and in-request duplicates are skipped.
        - Unknown names produce fresh options with the supplied tags.
        - Names matching an existing option: the supplied tags are unioned into
          that option's tag list (duplicates ignored). Options whose tags are
          unchanged afterwards are reported in neither `created` nor `updated`.
        - If multiple existing options share the same name (permitted by the
          domain model), the merge is applied to each of them.
        """
        supplied_tags = {nt for nt in (normalize_tag(t) for t in tags or []) if nt is not None}

        existing_by_name: dict[str, list[Option]] = {}
        for opt in self._repo.list_all():
            existing_by_name.setdefault(opt.name, []).append(opt)

        seen: set[str] = set()
        created: list[Option] = []
        updated: list[Option] = []

        for raw_name in names:
            name = raw_name.strip()
            if not name or name in seen:
                continue
            seen.add(name)

            matches = existing_by_name.get(name)
            if matches:
                for existing_opt in matches:
                    current = set(existing_opt.tags)
                    union = current | supplied_tags
                    if union != current:
                        updated.append(self._repo.update(existing_opt.id, tags=sorted(union)))
                continue

            option = Option(name=name, tags=sorted(supplied_tags))
            created.append(self._repo.create(option))

        return BulkCreateResult(created=created, updated=updated)

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
