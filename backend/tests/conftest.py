"""Shared test fixtures for the decision-time backend."""

from pathlib import Path

import pytest

from app.repositories.options import OptionRepository
from app.repositories.tournaments import TournamentRepository
from app.schemas.common import TournamentMode
from app.schemas.option import Option
from app.schemas.tournament import Tournament


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Provides a temporary data directory for tests."""
    return tmp_path / "data"


@pytest.fixture
def option_repo(data_dir: Path) -> OptionRepository:
    return OptionRepository(data_dir)


@pytest.fixture
def tournament_repo(data_dir: Path) -> TournamentRepository:
    return TournamentRepository(data_dir)


@pytest.fixture
def sample_option() -> Option:
    """A pre-built Option for tests that need one."""
    return Option(name="Test Option", description="A test option", tags=["test", "sample"])


@pytest.fixture
def sample_tournament() -> Tournament:
    """A pre-built Tournament in draft status."""
    return Tournament(name="Test Tournament", mode=TournamentMode.BRACKET)
