"""Integration tests for TournamentService with Swiss mode."""

from app.repositories.options import OptionRepository
from app.schemas.common import TournamentMode, TournamentStatus
from app.schemas.option import Option
from app.schemas.tournament import Tournament
from app.services.tournament_service import TournamentService


def _create_options(option_repo: OptionRepository, names: list[str]) -> list[Option]:
    return [option_repo.create(Option(name=n)) for n in names]


def _create_active_swiss(
    tournament_service: TournamentService,
    option_repo: OptionRepository,
    option_count: int,
    *,
    allow_draws: bool = True,
    total_rounds: int | None = None,
) -> Tournament:
    options = _create_options(option_repo, [f"Opt {i}" for i in range(option_count)])
    t = tournament_service.create_tournament("swiss test", TournamentMode.SWISS)
    t = tournament_service.update_tournament(
        t.id,
        version=t.version,
        selected_option_ids=[o.id for o in options],
        config={
            "allow_draws": allow_draws,
            "total_rounds": total_rounds,
            "shuffle_seed": False,
            "voter_labels": ["default"],
        },
    )
    return tournament_service.activate_tournament(t.id, version=t.version)


class TestSwissActivation:
    def test_activation_produces_swiss_state(
        self, tournament_service: TournamentService, option_repo: OptionRepository
    ) -> None:
        t = _create_active_swiss(tournament_service, option_repo, 4)
        assert t.status == TournamentStatus.ACTIVE
        assert t.state["total_rounds"] == 2
        assert len(t.state["rounds"]) == 1
        assert len(t.state["rounds"][0]["matchups"]) == 2

    def test_bye_applied_at_activation_for_odd_count(
        self, tournament_service: TournamentService, option_repo: OptionRepository
    ) -> None:
        t = _create_active_swiss(tournament_service, option_repo, 3)
        byes = [m for m in t.state["rounds"][0]["matchups"] if m["is_bye"]]
        assert len(byes) == 1


class TestSwissFullFlow:
    def test_complete_tournament_from_service(
        self, tournament_service: TournamentService, option_repo: OptionRepository
    ) -> None:
        t = _create_active_swiss(tournament_service, option_repo, 4)
        version = t.version
        # Vote through all matches until complete.
        while t.status == TournamentStatus.ACTIVE:
            ctx = tournament_service.get_vote_context(t.id, "default")
            if ctx.type == "completed":
                break
            assert ctx.type == "swiss_matchup"
            t = tournament_service.submit_vote(
                t.id,
                version,
                "default",
                {"matchup_id": ctx.matchup_id, "result": "a_wins"},
            )
            version = t.version
        assert t.status == TournamentStatus.COMPLETED
        assert t.result is not None
        assert len(t.result.ranking) == 4
        assert len(t.result.winner_ids) >= 1


class TestSwissUndo:
    def test_undo_replays_state_deterministically(
        self, tournament_service: TournamentService, option_repo: OptionRepository
    ) -> None:
        t = _create_active_swiss(tournament_service, option_repo, 4)
        ctx = tournament_service.get_vote_context(t.id, "default")
        assert ctx.type == "swiss_matchup"
        t = tournament_service.submit_vote(
            t.id, t.version, "default", {"matchup_id": ctx.matchup_id, "result": "a_wins"}
        )
        state_after_vote = t.state

        t = tournament_service.undo_vote(t.id, t.version, "default")
        # After undo, round 1 matchup should be back to result=None.
        original_matchup = next(m for m in t.state["rounds"][0]["matchups"] if m["matchup_id"] == ctx.matchup_id)
        assert original_matchup["result"] is None
        # Standings should be reset.
        assert t.state["standings"][ctx.entry_a["id"]]["points"] == 0.0
        # Re-submitting the same vote reproduces the same standings.
        t = tournament_service.submit_vote(
            t.id, t.version, "default", {"matchup_id": ctx.matchup_id, "result": "a_wins"}
        )
        assert t.state["standings"] == state_after_vote["standings"]
