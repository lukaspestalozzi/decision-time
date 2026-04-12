"""Shared test fixtures for the decision-time backend."""

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_option_service, get_tournament_service
from app.repositories.options import OptionRepository
from app.repositories.tournaments import TournamentRepository
from app.schemas.common import TournamentMode
from app.schemas.option import Option
from app.schemas.tournament import Tournament
from app.services.option_service import OptionService
from app.services.tournament_service import TournamentService


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


@pytest.fixture
def client(data_dir: Path) -> Generator[TestClient, None, None]:
    """TestClient with dependency overrides pointing to tmp data dir."""
    from app.main import app

    option_repo = OptionRepository(data_dir)
    tournament_repo = TournamentRepository(data_dir)

    app.dependency_overrides[get_option_service] = lambda: OptionService(option_repo)
    app.dependency_overrides[get_tournament_service] = lambda: TournamentService(tournament_repo, option_repo)

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
