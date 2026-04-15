"""FastAPI dependency injection factory functions."""

from app.config import load_config
from app.repositories.options import OptionRepository
from app.repositories.tournaments import TournamentRepository
from app.services.option_service import OptionService
from app.services.tournament_service import TournamentService

_config = load_config()


def get_option_service() -> OptionService:
    return OptionService(OptionRepository(_config.data_dir))


def get_tournament_service() -> TournamentService:
    return TournamentService(
        TournamentRepository(_config.data_dir),
        OptionRepository(_config.data_dir),
        cool_off_seconds=_config.undo_cool_off_seconds,
    )
