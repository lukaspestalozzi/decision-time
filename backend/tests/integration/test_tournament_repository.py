"""Tests for TournamentRepository: CRUD, optimistic concurrency, status filtering, serialization."""

import threading
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.exceptions import ConflictError, NotFoundError
from app.repositories.tournaments import TournamentRepository
from app.schemas.common import TournamentMode, TournamentStatus
from app.schemas.tournament import Result, Tournament, TournamentEntry, Vote


class TestTournamentCRUD:
    def test_create_persists_to_disk(self, tournament_repo: TournamentRepository, data_dir: Path) -> None:
        t = Tournament(name="Test", mode=TournamentMode.BRACKET)
        created = tournament_repo.create(t)
        file_path = data_dir / "tournaments" / f"{created.id}.json"
        assert file_path.exists()

    def test_create_starts_at_version_1(self, tournament_repo: TournamentRepository) -> None:
        t = Tournament(name="Test", mode=TournamentMode.BRACKET)
        created = tournament_repo.create(t)
        assert created.version == 1

    def test_create_has_draft_status(self, tournament_repo: TournamentRepository) -> None:
        t = Tournament(name="Test", mode=TournamentMode.SCORE)
        created = tournament_repo.create(t)
        assert created.status == TournamentStatus.DRAFT

    def test_get_returns_created_tournament(self, tournament_repo: TournamentRepository) -> None:
        t = Tournament(name="Decision", mode=TournamentMode.CONDORCET, description="Big choice")
        created = tournament_repo.create(t)
        fetched = tournament_repo.get(created.id)
        assert fetched.id == created.id
        assert fetched.name == "Decision"
        assert fetched.mode == TournamentMode.CONDORCET
        assert fetched.description == "Big choice"

    def test_get_not_found_raises_error(self, tournament_repo: TournamentRepository) -> None:
        with pytest.raises(NotFoundError):
            tournament_repo.get(uuid.uuid4())

    def test_delete_removes_file(self, tournament_repo: TournamentRepository, data_dir: Path) -> None:
        t = Tournament(name="ToDelete", mode=TournamentMode.BRACKET)
        created = tournament_repo.create(t)
        tournament_repo.delete(created.id)
        file_path = data_dir / "tournaments" / f"{created.id}.json"
        assert not file_path.exists()

    def test_delete_not_found_raises_error(self, tournament_repo: TournamentRepository) -> None:
        with pytest.raises(NotFoundError):
            tournament_repo.delete(uuid.uuid4())


class TestTournamentVersioning:
    def test_save_increments_version(self, tournament_repo: TournamentRepository) -> None:
        t = Tournament(name="Test", mode=TournamentMode.BRACKET)
        created = tournament_repo.create(t)
        assert created.version == 1
        created.name = "Updated"
        saved = tournament_repo.save(created, expected_version=1)
        assert saved.version == 2

    def test_save_updates_updated_at(self, tournament_repo: TournamentRepository) -> None:
        t = Tournament(name="Test", mode=TournamentMode.BRACKET)
        created = tournament_repo.create(t)
        original_updated_at = created.updated_at
        created.name = "Changed"
        saved = tournament_repo.save(created, expected_version=1)
        assert saved.updated_at > original_updated_at

    def test_save_with_wrong_version_raises_conflict(self, tournament_repo: TournamentRepository) -> None:
        t = Tournament(name="Test", mode=TournamentMode.BRACKET)
        created = tournament_repo.create(t)
        # First save succeeds
        created.name = "V2"
        tournament_repo.save(created, expected_version=1)
        # Second save with stale version fails
        created.name = "V3"
        with pytest.raises(ConflictError):
            tournament_repo.save(created, expected_version=1)

    def test_save_concurrent_writes_one_fails(self, tournament_repo: TournamentRepository) -> None:
        t = Tournament(name="Test", mode=TournamentMode.BRACKET)
        created = tournament_repo.create(t)
        results: list[str] = []

        def save_with_label(label: str) -> None:
            try:
                copy = tournament_repo.get(created.id)
                copy.name = label
                tournament_repo.save(copy, expected_version=1)
                results.append(f"{label}_ok")
            except ConflictError:
                results.append(f"{label}_conflict")

        t1 = threading.Thread(target=save_with_label, args=("A",))
        t2 = threading.Thread(target=save_with_label, args=("B",))
        t1.start()
        t1.join()  # Let first complete before second
        t2.start()
        t2.join()
        assert sorted(results) == sorted(["A_ok", "B_conflict"])

    def test_save_preserves_all_fields(self, tournament_repo: TournamentRepository) -> None:
        entry = TournamentEntry(
            option_id=uuid.uuid4(),
            seed=1,
            option_snapshot={"name": "Test Option", "id": str(uuid.uuid4())},
        )
        vote = Vote(
            voter_label="default",
            round=1,
            payload={"matchup_id": str(uuid.uuid4()), "winner_entry_id": str(uuid.uuid4())},
        )
        t = Tournament(
            name="Full",
            mode=TournamentMode.BRACKET,
            description="Full test",
            config={"shuffle_seed": True},
            selected_option_ids=[uuid.uuid4(), uuid.uuid4()],
            entries=[entry],
            votes=[vote],
            state={"rounds": [], "current_round": 1},
        )
        created = tournament_repo.create(t)
        # Modify and save
        created.status = TournamentStatus.ACTIVE
        saved = tournament_repo.save(created, expected_version=1)
        # Read back and verify all fields preserved
        fetched = tournament_repo.get(saved.id)
        assert fetched.description == "Full test"
        assert fetched.config == {"shuffle_seed": True}
        assert len(fetched.entries) == 1
        assert fetched.entries[0].seed == 1
        assert len(fetched.votes) == 1
        assert fetched.votes[0].voter_label == "default"
        assert fetched.state == {"rounds": [], "current_round": 1}
        assert fetched.status == TournamentStatus.ACTIVE


class TestTournamentListAndFilter:
    def test_list_all_returns_all(self, tournament_repo: TournamentRepository) -> None:
        tournament_repo.create(Tournament(name="A", mode=TournamentMode.BRACKET))
        tournament_repo.create(Tournament(name="B", mode=TournamentMode.SCORE))
        result = tournament_repo.list_all()
        assert len(result) == 2

    def test_list_all_filter_by_single_status(self, tournament_repo: TournamentRepository) -> None:
        t1 = Tournament(name="Draft", mode=TournamentMode.BRACKET)
        tournament_repo.create(t1)
        t2 = Tournament(name="Active", mode=TournamentMode.SCORE, status=TournamentStatus.ACTIVE)
        tournament_repo.create(t2)
        result = tournament_repo.list_all(status=[TournamentStatus.DRAFT])
        assert len(result) == 1
        assert result[0].name == "Draft"

    def test_list_all_filter_by_multiple_statuses(self, tournament_repo: TournamentRepository) -> None:
        tournament_repo.create(Tournament(name="Draft", mode=TournamentMode.BRACKET))
        tournament_repo.create(Tournament(name="Active", mode=TournamentMode.SCORE, status=TournamentStatus.ACTIVE))
        tournament_repo.create(
            Tournament(name="Done", mode=TournamentMode.MULTIVOTE, status=TournamentStatus.COMPLETED)
        )
        result = tournament_repo.list_all(status=[TournamentStatus.DRAFT, TournamentStatus.ACTIVE])
        assert len(result) == 2
        names = {t.name for t in result}
        assert names == {"Draft", "Active"}

    def test_list_all_no_filter_returns_all(self, tournament_repo: TournamentRepository) -> None:
        tournament_repo.create(Tournament(name="A", mode=TournamentMode.BRACKET))
        tournament_repo.create(Tournament(name="B", mode=TournamentMode.SCORE, status=TournamentStatus.ACTIVE))
        result = tournament_repo.list_all()
        assert len(result) == 2

    def test_list_all_sorted_by_created_at_desc(self, tournament_repo: TournamentRepository) -> None:
        now = datetime.now(UTC)
        tournament_repo.create(Tournament(name="Old", mode=TournamentMode.BRACKET, created_at=now - timedelta(hours=2)))
        tournament_repo.create(Tournament(name="New", mode=TournamentMode.SCORE, created_at=now))
        result = tournament_repo.list_all()
        assert result[0].name == "New"
        assert result[1].name == "Old"


class TestTournamentSerialization:
    def test_tournament_with_entries_round_trips(self, tournament_repo: TournamentRepository) -> None:
        entry = TournamentEntry(
            option_id=uuid.uuid4(),
            option_snapshot={"name": "Option A"},
        )
        t = Tournament(name="Test", mode=TournamentMode.BRACKET, entries=[entry])
        created = tournament_repo.create(t)
        fetched = tournament_repo.get(created.id)
        assert len(fetched.entries) == 1
        assert fetched.entries[0].option_snapshot == {"name": "Option A"}

    def test_tournament_with_votes_round_trips(self, tournament_repo: TournamentRepository) -> None:
        vote = Vote(
            voter_label="Voter 1",
            payload={"scores": [{"entry_id": str(uuid.uuid4()), "score": 4}]},
        )
        t = Tournament(name="Test", mode=TournamentMode.SCORE, votes=[vote])
        created = tournament_repo.create(t)
        fetched = tournament_repo.get(created.id)
        assert len(fetched.votes) == 1
        assert fetched.votes[0].voter_label == "Voter 1"

    def test_tournament_with_result_round_trips(self, tournament_repo: TournamentRepository) -> None:
        winner_id = uuid.uuid4()
        result = Result(
            winner_ids=[winner_id],
            ranking=[{"entry_id": str(winner_id), "rank": 1, "score": 4.5}],
            metadata={"total_votes": 3},
        )
        t = Tournament(
            name="Test",
            mode=TournamentMode.SCORE,
            status=TournamentStatus.COMPLETED,
            result=result,
        )
        created = tournament_repo.create(t)
        fetched = tournament_repo.get(created.id)
        assert fetched.result is not None
        assert fetched.result.winner_ids == [winner_id]
        assert fetched.result.metadata == {"total_votes": 3}

    def test_tournament_datetime_uses_z_suffix(self, tournament_repo: TournamentRepository, data_dir: Path) -> None:
        t = Tournament(name="Test", mode=TournamentMode.BRACKET)
        created = tournament_repo.create(t)
        import json

        file_path = data_dir / "tournaments" / f"{created.id}.json"
        raw = json.loads(file_path.read_text())
        assert raw["created_at"].endswith("Z")
        assert "+00:00" not in raw["created_at"]
