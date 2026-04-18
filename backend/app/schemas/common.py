"""Shared types, enums, mode configs, and utilities used across schemas."""

import re
from datetime import datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

MAX_VOTER_LABELS = 50
MAX_VOTER_LABEL_LENGTH = 50


def normalize_tag(raw: str) -> str | None:
    """Normalize a tag per Section 2.1.1 rules.

    Steps: lowercase → replace whitespace with hyphens → strip non-[a-z0-9-]
    → collapse consecutive hyphens → strip leading/trailing hyphens.
    Returns None if empty after normalization.
    """
    result = raw.lower()
    result = re.sub(r"\s+", "-", result)
    result = re.sub(r"[^a-z0-9-]", "", result)
    result = re.sub(r"-{2,}", "-", result)
    result = result.strip("-")
    return result if result else None


class TournamentMode(StrEnum):
    BRACKET = "bracket"
    SCORE = "score"
    MULTIVOTE = "multivote"
    CONDORCET = "condorcet"
    SWISS = "swiss"


class TournamentStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DecisionTimeModel(BaseModel):
    """Base model with shared config for all domain models."""

    model_config = ConfigDict(populate_by_name=True)

    @field_serializer(
        "created_at",
        "updated_at",
        "completed_at",
        "submitted_at",
        "computed_at",
        "superseded_at",
        check_fields=False,
    )
    @classmethod
    def serialize_utc_datetime(cls, v: datetime | None) -> str | None:
        if v is None:
            return None
        return v.strftime("%Y-%m-%dT%H:%M:%SZ")


class TournamentConfig(DecisionTimeModel):
    """Base config shared by all tournament modes.

    Owns `voter_labels`: the list of voter identities for the tournament.
    Count is always `len(voter_labels)`.
    Owns `allow_undo`: whether voters may undo/revise their votes.
    """

    voter_labels: list[str] = Field(default_factory=lambda: ["default"])
    allow_undo: bool = True

    @model_validator(mode="after")
    def _validate_voter_labels(self) -> Self:
        trimmed = [label.strip() for label in self.voter_labels]
        if len(trimmed) < 1:
            raise ValueError("at least one voter label is required")
        if len(trimmed) > MAX_VOTER_LABELS:
            raise ValueError(f"at most {MAX_VOTER_LABELS} voter labels allowed")
        for label in trimmed:
            if not label:
                raise ValueError("voter labels cannot be empty or whitespace-only")
            if len(label) > MAX_VOTER_LABEL_LENGTH:
                raise ValueError(f"voter labels must be at most {MAX_VOTER_LABEL_LENGTH} characters")
        if len(set(trimmed)) != len(trimmed):
            raise ValueError("voter labels must be unique")
        self.voter_labels = trimmed
        return self


class BracketConfig(TournamentConfig):
    shuffle_seed: bool = True
    third_place_match: bool = False

    @model_validator(mode="after")
    def _validate_bracket_single_voter(self) -> Self:
        if len(self.voter_labels) != 1:
            raise ValueError("bracket mode supports only a single voter")
        return self


class ScoreConfig(TournamentConfig):
    min_score: int = 1
    max_score: int = 5


class MultivoteConfig(TournamentConfig):
    total_votes: int | None = None
    max_per_option: int | None = None


class CondorcetConfig(TournamentConfig):
    pass


class SwissConfig(TournamentConfig):
    total_rounds: int | None = None
    allow_draws: bool = True
    shuffle_seed: bool = True

    @model_validator(mode="after")
    def _validate_swiss_single_voter(self) -> Self:
        if len(self.voter_labels) != 1:
            raise ValueError("swiss mode supports only a single voter")
        return self

    @model_validator(mode="after")
    def _validate_rounds(self) -> Self:
        if self.total_rounds is not None and self.total_rounds < 1:
            raise ValueError("total_rounds must be >= 1")
        return self


CONFIG_CLASSES: dict[TournamentMode, type[TournamentConfig]] = {
    TournamentMode.BRACKET: BracketConfig,
    TournamentMode.SCORE: ScoreConfig,
    TournamentMode.MULTIVOTE: MultivoteConfig,
    TournamentMode.CONDORCET: CondorcetConfig,
    TournamentMode.SWISS: SwissConfig,
}


def get_default_config(mode: TournamentMode) -> dict[str, Any]:
    """Return the default config dict for a tournament mode."""
    return CONFIG_CLASSES[mode]().model_dump()


def normalize_config(mode: TournamentMode, config: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a config dict for a tournament mode.

    Raises pydantic.ValidationError on invalid input.
    """
    return CONFIG_CLASSES[mode](**config).model_dump()
