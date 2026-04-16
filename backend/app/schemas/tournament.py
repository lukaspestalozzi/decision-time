"""Tournament domain models: Tournament, TournamentEntry, Vote, Result."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, field_validator

from app.schemas.common import DecisionTimeModel, TournamentMode, TournamentStatus


class TournamentEntry(DecisionTimeModel):
    """Snapshot of an Option as it entered a Tournament. Created on activation."""

    id: UUID = Field(default_factory=uuid4)
    option_id: UUID
    seed: int | None = None
    option_snapshot: dict[str, Any]


class VoteStatus(StrEnum):
    """Lifecycle status of a Vote record.

    Votes are append-only — undo/revise marks them SUPERSEDED rather than deleting.
    """

    ACTIVE = "active"
    SUPERSEDED = "superseded"


class Vote(DecisionTimeModel):
    """A vote or judgment submitted during a tournament.

    Votes are never mutated or deleted. When undone, `status` is flipped to
    SUPERSEDED and `superseded_at` is set; state is recomputed by replaying
    only ACTIVE votes.
    """

    id: UUID = Field(default_factory=uuid4)
    voter_label: str
    round: int | None = None
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any]
    status: VoteStatus = VoteStatus.ACTIVE
    superseded_at: datetime | None = None


class Result(DecisionTimeModel):
    """Computed result of a completed tournament."""

    winner_ids: list[UUID]
    ranking: list[dict[str, Any]]
    metadata: dict[str, Any] = Field(default_factory=dict)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Tournament(DecisionTimeModel):
    """A tournament is a decision process applied to a set of Options."""

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., max_length=256)
    description: str = ""
    mode: TournamentMode
    status: TournamentStatus = TournamentStatus.DRAFT
    config: dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    selected_option_ids: list[UUID] = Field(default_factory=list)
    entries: list[TournamentEntry] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)
    votes: list[Vote] = Field(default_factory=list)
    result: Result | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    cool_off_ends_at: datetime | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("name must not be blank")
        return stripped
