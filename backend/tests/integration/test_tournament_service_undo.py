"""Tests for TournamentService.undo_vote."""

import pytest

from app.exceptions import ConflictError, InvalidStateError, ValidationError
from app.repositories.options import OptionRepository
from app.schemas.common import TournamentMode, TournamentStatus
from app.schemas.option import Option
from app.schemas.tournament import Tournament, VoteStatus
from app.services.tournament_service import TournamentService


def _create_score_options(option_repo: OptionRepository, names: list[str]) -> list[Option]:
    return [option_repo.create(Option(name=n)) for n in names]


def _create_active_score(
    tournament_service: TournamentService,
    option_repo: OptionRepository,
    voter_labels: list[str],
    *,
    allow_undo: bool = True,
) -> Tournament:
    """Create + activate a score tournament with the given voters. 3 options each."""
    options = _create_score_options(option_repo, ["A", "B", "C"])
    t = tournament_service.create_tournament("test", TournamentMode.SCORE)
    t = tournament_service.update_tournament(
        t.id,
        version=t.version,
        selected_option_ids=[o.id for o in options],
        config={
            "min_score": 1,
            "max_score": 5,
            "voter_labels": voter_labels,
            "allow_undo": allow_undo,
        },
    )
    return tournament_service.activate_tournament(t.id, version=t.version)


def _score_payload(t: Tournament, scores: list[int]) -> dict:
    return {"scores": [{"entry_id": str(e.id), "score": s} for e, s in zip(t.entries, scores, strict=True)]}


class TestUndoVoteBasic:
    def test_undo_marks_vote_superseded(
        self, tournament_service: TournamentService, option_repo: OptionRepository
    ) -> None:
        t = _create_active_score(tournament_service, option_repo, ["Alice", "Bob"])
        t = tournament_service.submit_vote(t.id, t.version, "Alice", _score_payload(t, [5, 3, 1]))
        assert len(t.votes) == 1
        assert t.votes[0].status == VoteStatus.ACTIVE

        t = tournament_service.undo_vote(t.id, t.version, "Alice")

        # Vote record preserved but marked superseded
        assert len(t.votes) == 1
        assert t.votes[0].status == VoteStatus.SUPERSEDED
        assert t.votes[0].superseded_at is not None

    def test_undo_replays_state(self, tournament_service: TournamentService, option_repo: OptionRepository) -> None:
        t = _create_active_score(tournament_service, option_repo, ["Alice", "Bob"])
        t = tournament_service.submit_vote(t.id, t.version, "Alice", _score_payload(t, [5, 3, 1]))
        assert t.state["ballots_submitted"] == 1

        t = tournament_service.undo_vote(t.id, t.version, "Alice")

        assert t.state["ballots_submitted"] == 0
        # State's inner votes list only contains ACTIVE votes after replay
        assert t.state["votes"] == []

    def test_undo_bumps_version(self, tournament_service: TournamentService, option_repo: OptionRepository) -> None:
        t = _create_active_score(tournament_service, option_repo, ["Alice", "Bob"])
        t = tournament_service.submit_vote(t.id, t.version, "Alice", _score_payload(t, [5, 3, 1]))
        version_before_undo = t.version

        t = tournament_service.undo_vote(t.id, t.version, "Alice")
        assert t.version == version_before_undo + 1

    def test_undo_allows_resubmit(self, tournament_service: TournamentService, option_repo: OptionRepository) -> None:
        t = _create_active_score(tournament_service, option_repo, ["Alice", "Bob"])
        t = tournament_service.submit_vote(t.id, t.version, "Alice", _score_payload(t, [5, 3, 1]))
        t = tournament_service.undo_vote(t.id, t.version, "Alice")

        # Alice can now submit a different ballot
        t = tournament_service.submit_vote(t.id, t.version, "Alice", _score_payload(t, [1, 3, 5]))
        active_votes = [v for v in t.votes if v.status == VoteStatus.ACTIVE]
        assert len(active_votes) == 1
        assert active_votes[0].payload["scores"][0]["score"] == 1

    def test_undo_only_affects_calling_voter(
        self, tournament_service: TournamentService, option_repo: OptionRepository
    ) -> None:
        t = _create_active_score(tournament_service, option_repo, ["Alice", "Bob", "Carol"])
        t = tournament_service.submit_vote(t.id, t.version, "Alice", _score_payload(t, [5, 3, 1]))
        t = tournament_service.submit_vote(t.id, t.version, "Bob", _score_payload(t, [1, 5, 3]))

        t = tournament_service.undo_vote(t.id, t.version, "Alice")

        active = [v for v in t.votes if v.status == VoteStatus.ACTIVE]
        assert len(active) == 1
        assert active[0].voter_label == "Bob"


class TestUndoVoteErrors:
    def test_undo_with_no_active_vote_raises(
        self, tournament_service: TournamentService, option_repo: OptionRepository
    ) -> None:
        t = _create_active_score(tournament_service, option_repo, ["Alice", "Bob"])
        with pytest.raises(ValidationError, match="No vote to undo"):
            tournament_service.undo_vote(t.id, t.version, "Alice")

    def test_undo_already_undone_vote_raises(
        self, tournament_service: TournamentService, option_repo: OptionRepository
    ) -> None:
        t = _create_active_score(tournament_service, option_repo, ["Alice", "Bob"])
        t = tournament_service.submit_vote(t.id, t.version, "Alice", _score_payload(t, [5, 3, 1]))
        t = tournament_service.undo_vote(t.id, t.version, "Alice")
        with pytest.raises(ValidationError, match="No vote to undo"):
            tournament_service.undo_vote(t.id, t.version, "Alice")

    def test_undo_on_draft_raises_invalid_state(
        self, tournament_service: TournamentService, option_repo: OptionRepository
    ) -> None:
        options = _create_score_options(option_repo, ["A", "B"])
        t = tournament_service.create_tournament("t", TournamentMode.SCORE)
        t = tournament_service.update_tournament(
            t.id,
            version=t.version,
            selected_option_ids=[o.id for o in options],
            config={"voter_labels": ["Alice"]},
        )
        with pytest.raises(InvalidStateError):
            tournament_service.undo_vote(t.id, t.version, "Alice")

    def test_undo_on_cancelled_raises_invalid_state(
        self, tournament_service: TournamentService, option_repo: OptionRepository
    ) -> None:
        t = _create_active_score(tournament_service, option_repo, ["Alice", "Bob"])
        t = tournament_service.submit_vote(t.id, t.version, "Alice", _score_payload(t, [5, 3, 1]))
        t = tournament_service.cancel_tournament(t.id, t.version)
        with pytest.raises(InvalidStateError):
            tournament_service.undo_vote(t.id, t.version, "Alice")

    def test_undo_with_allow_undo_false_raises(
        self, tournament_service: TournamentService, option_repo: OptionRepository
    ) -> None:
        t = _create_active_score(tournament_service, option_repo, ["Alice", "Bob"], allow_undo=False)
        t = tournament_service.submit_vote(t.id, t.version, "Alice", _score_payload(t, [5, 3, 1]))
        with pytest.raises(InvalidStateError, match=r"[Uu]ndo is disabled"):
            tournament_service.undo_vote(t.id, t.version, "Alice")

    def test_undo_with_stale_version_raises_conflict(
        self, tournament_service: TournamentService, option_repo: OptionRepository
    ) -> None:
        t = _create_active_score(tournament_service, option_repo, ["Alice", "Bob"])
        t = tournament_service.submit_vote(t.id, t.version, "Alice", _score_payload(t, [5, 3, 1]))
        stale_version = t.version - 1
        with pytest.raises(ConflictError):
            tournament_service.undo_vote(t.id, stale_version, "Alice")

    def test_undo_unknown_voter_raises(
        self, tournament_service: TournamentService, option_repo: OptionRepository
    ) -> None:
        t = _create_active_score(tournament_service, option_repo, ["Alice", "Bob"])
        t = tournament_service.submit_vote(t.id, t.version, "Alice", _score_payload(t, [5, 3, 1]))
        with pytest.raises(ValidationError):
            tournament_service.undo_vote(t.id, t.version, "Charlie")


class TestUndoVoteContextAfterUndo:
    def test_vote_context_returns_ballot_after_undo(
        self, tournament_service: TournamentService, option_repo: OptionRepository
    ) -> None:
        t = _create_active_score(tournament_service, option_repo, ["Alice", "Bob"])
        t = tournament_service.submit_vote(t.id, t.version, "Alice", _score_payload(t, [5, 3, 1]))
        # Before undo: already voted
        ctx = tournament_service.get_vote_context(t.id, "Alice")
        assert ctx.type == "already_voted"
        # After undo: ballot context returned again
        tournament_service.undo_vote(t.id, t.version, "Alice")
        ctx = tournament_service.get_vote_context(t.id, "Alice")
        assert ctx.type == "ballot"


class TestUndoOnCompletedTournament:
    def test_last_vote_completes_tournament_immediately(
        self, tournament_service: TournamentService, option_repo: OptionRepository
    ) -> None:
        t = _create_active_score(tournament_service, option_repo, ["Alice", "Bob"])
        t = tournament_service.submit_vote(t.id, t.version, "Alice", _score_payload(t, [5, 3, 1]))
        assert t.status == TournamentStatus.ACTIVE

        t = tournament_service.submit_vote(t.id, t.version, "Bob", _score_payload(t, [1, 3, 5]))
        assert t.status == TournamentStatus.COMPLETED
        assert t.completed_at is not None
        assert t.result is not None

    def test_undo_on_completed_tournament_raises(
        self, tournament_service: TournamentService, option_repo: OptionRepository
    ) -> None:
        t = _create_active_score(tournament_service, option_repo, ["Alice"])
        t = tournament_service.submit_vote(t.id, t.version, "Alice", _score_payload(t, [5, 3, 1]))
        assert t.status == TournamentStatus.COMPLETED

        with pytest.raises(InvalidStateError):
            tournament_service.undo_vote(t.id, t.version, "Alice")
