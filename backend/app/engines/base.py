"""Abstract tournament engine interface and VoteContext models."""

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel

from app.schemas.tournament import Result, TournamentEntry

# --- VoteContext models (tagged union) ---


class BracketMatchupContext(BaseModel):
    type: Literal["bracket_matchup"] = "bracket_matchup"
    matchup_id: str
    entry_a: dict[str, Any]
    entry_b: dict[str, Any]
    round: int
    round_name: str
    match_number: int
    matches_in_round: int


class CondorcetMatchupContext(BaseModel):
    type: Literal["condorcet_matchup"] = "condorcet_matchup"
    matchup_id: str
    entry_a: dict[str, Any]
    entry_b: dict[str, Any]
    matchup_number: int
    total_matchups: int


class BallotContext(BaseModel):
    type: Literal["ballot"] = "ballot"
    entries: list[dict[str, Any]]
    ballot_type: str
    ballots_submitted: int
    ballots_required: int


class AlreadyVotedContext(BaseModel):
    type: Literal["already_voted"] = "already_voted"


class CompletedContext(BaseModel):
    type: Literal["completed"] = "completed"
    result: dict[str, Any]


VoteContext = BracketMatchupContext | CondorcetMatchupContext | BallotContext | AlreadyVotedContext | CompletedContext


# --- Abstract Engine ---


class TournamentEngine(ABC):
    """Abstract base for tournament mode engines.

    Engines are pure logic — no I/O, no side effects. They take state in
    and return state out.
    """

    @abstractmethod
    def validate_config(self, config: dict[str, Any]) -> list[str]:
        """Validate mode-specific config. Returns list of errors (empty = valid)."""

    @abstractmethod
    def initialize(self, entries: list[TournamentEntry], config: dict[str, Any]) -> dict[str, Any]:
        """Create initial state from entries and config."""

    @abstractmethod
    def get_vote_context(self, state: dict[str, Any], voter_label: str) -> VoteContext:
        """Return the current voting context for a voter."""

    @abstractmethod
    def submit_vote(self, state: dict[str, Any], voter_label: str, vote_payload: dict[str, Any]) -> dict[str, Any]:
        """Process a vote and return updated state."""

    @abstractmethod
    def is_complete(self, state: dict[str, Any]) -> bool:
        """Check if all voting is done."""

    @abstractmethod
    def compute_result(self, state: dict[str, Any], entries: list[TournamentEntry]) -> Result:
        """Compute final ranking and winner(s)."""
