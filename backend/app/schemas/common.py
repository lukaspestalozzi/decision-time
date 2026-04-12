"""Shared types, enums, mode configs, and utilities used across schemas."""

import re
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer


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
        check_fields=False,
    )
    @classmethod
    def serialize_utc_datetime(cls, v: datetime | None) -> str | None:
        if v is None:
            return None
        return v.strftime("%Y-%m-%dT%H:%M:%SZ")


class BracketConfig(BaseModel):
    shuffle_seed: bool = True
    third_place_match: bool = False


class ScoreConfig(BaseModel):
    min_score: int = 1
    max_score: int = 5
    voter_count: int = 1


class MultivoteConfig(BaseModel):
    total_votes: int | None = None
    max_per_option: int | None = None
    voter_count: int = 1


class CondorcetConfig(BaseModel):
    voter_count: int = 1


DEFAULT_CONFIGS: dict[TournamentMode, BaseModel] = {
    TournamentMode.BRACKET: BracketConfig(),
    TournamentMode.SCORE: ScoreConfig(),
    TournamentMode.MULTIVOTE: MultivoteConfig(),
    TournamentMode.CONDORCET: CondorcetConfig(),
}


def get_default_config(mode: TournamentMode) -> dict[str, Any]:
    """Return the default config dict for a tournament mode."""
    return DEFAULT_CONFIGS[mode].model_dump()
