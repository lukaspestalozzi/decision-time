"""Option domain model."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import Field, field_validator

from app.schemas.common import DecisionTimeModel, normalize_tag


class Option(DecisionTimeModel):
    """An option is something that can be chosen — the atomic unit of the system."""

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., max_length=256)
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("name must not be blank")
        return stripped

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, v: list[str]) -> list[str]:
        normalized = [normalize_tag(t) for t in v]
        return sorted(set(t for t in normalized if t is not None))


class BulkCreateResult(DecisionTimeModel):
    """Outcome of a bulk-create/import request.

    `created` holds freshly-created options; `updated` holds pre-existing options
    whose tag list was merged with the bulk tags (at least one new tag added).
    Options that already had every supplied tag are omitted entirely.
    """

    created: list[Option] = Field(default_factory=list)
    updated: list[Option] = Field(default_factory=list)
