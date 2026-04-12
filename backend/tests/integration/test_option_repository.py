"""Tests for OptionRepository: CRUD, filtering, tags."""

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.exceptions import NotFoundError
from app.repositories.options import OptionRepository
from app.schemas.option import Option


class TestOptionCRUD:
    def test_create_persists_to_disk(self, option_repo: OptionRepository, data_dir: Path) -> None:
        option = Option(name="Luna")
        created = option_repo.create(option)
        file_path = data_dir / "options" / f"{created.id}.json"
        assert file_path.exists()

    def test_create_returns_option_with_id(self, option_repo: OptionRepository) -> None:
        option = Option(name="Luna")
        created = option_repo.create(option)
        assert created.id is not None
        assert created.name == "Luna"

    def test_get_returns_created_option(self, option_repo: OptionRepository) -> None:
        option = Option(name="Mira", description="A star", tags=["space"])
        created = option_repo.create(option)
        fetched = option_repo.get(created.id)
        assert fetched.id == created.id
        assert fetched.name == "Mira"
        assert fetched.description == "A star"
        assert fetched.tags == ["space"]

    def test_get_not_found_raises_error(self, option_repo: OptionRepository) -> None:
        with pytest.raises(NotFoundError):
            option_repo.get(uuid.uuid4())

    def test_update_changes_name(self, option_repo: OptionRepository) -> None:
        created = option_repo.create(Option(name="Old Name"))
        updated = option_repo.update(created.id, name="New Name")
        assert updated.name == "New Name"
        fetched = option_repo.get(created.id)
        assert fetched.name == "New Name"

    def test_update_changes_tags_with_normalization(self, option_repo: OptionRepository) -> None:
        created = option_repo.create(Option(name="Test"))
        updated = option_repo.update(created.id, tags=["Baby Name!", "ITALIAN"])
        assert updated.tags == ["baby-name", "italian"]

    def test_update_sets_updated_at(self, option_repo: OptionRepository) -> None:
        created = option_repo.create(Option(name="Test"))
        original_updated_at = created.updated_at
        updated = option_repo.update(created.id, name="Changed")
        assert updated.updated_at > original_updated_at

    def test_update_not_found_raises_error(self, option_repo: OptionRepository) -> None:
        with pytest.raises(NotFoundError):
            option_repo.update(uuid.uuid4(), name="New")

    def test_update_preserves_unchanged_fields(self, option_repo: OptionRepository) -> None:
        created = option_repo.create(Option(name="Original", description="Desc", tags=["tag1"]))
        updated = option_repo.update(created.id, name="Changed")
        assert updated.description == "Desc"
        assert updated.tags == ["tag1"]

    def test_delete_removes_file(self, option_repo: OptionRepository, data_dir: Path) -> None:
        created = option_repo.create(Option(name="ToDelete"))
        option_repo.delete(created.id)
        file_path = data_dir / "options" / f"{created.id}.json"
        assert not file_path.exists()

    def test_delete_not_found_raises_error(self, option_repo: OptionRepository) -> None:
        with pytest.raises(NotFoundError):
            option_repo.delete(uuid.uuid4())


class TestOptionList:
    def test_list_all_returns_all_options(self, option_repo: OptionRepository) -> None:
        option_repo.create(Option(name="A"))
        option_repo.create(Option(name="B"))
        option_repo.create(Option(name="C"))
        result = option_repo.list_all()
        assert len(result) == 3

    def test_list_all_empty_returns_empty_list(self, option_repo: OptionRepository) -> None:
        result = option_repo.list_all()
        assert result == []

    def test_list_all_sorted_by_created_at_desc(self, option_repo: OptionRepository) -> None:
        now = datetime.now(UTC)
        option_repo.create(Option(name="First", created_at=now - timedelta(hours=2)))
        option_repo.create(Option(name="Second", created_at=now - timedelta(hours=1)))
        option_repo.create(Option(name="Third", created_at=now))
        result = option_repo.list_all()
        # Most recently created should be first
        assert result[0].name == "Third"
        assert result[-1].name == "First"


class TestOptionFiltering:
    def test_filter_by_q_substring_match(self, option_repo: OptionRepository) -> None:
        option_repo.create(Option(name="Luna"))
        option_repo.create(Option(name="Mira"))
        option_repo.create(Option(name="Lunar Eclipse"))
        result = option_repo.list_all(q="lun")
        assert len(result) == 2
        names = {o.name for o in result}
        assert names == {"Luna", "Lunar Eclipse"}

    def test_filter_by_q_case_insensitive(self, option_repo: OptionRepository) -> None:
        option_repo.create(Option(name="Luna"))
        result = option_repo.list_all(q="LUNA")
        assert len(result) == 1
        assert result[0].name == "Luna"

    def test_filter_by_tags_all_and_logic(self, option_repo: OptionRepository) -> None:
        option_repo.create(Option(name="A", tags=["italian", "short"]))
        option_repo.create(Option(name="B", tags=["italian"]))
        option_repo.create(Option(name="C", tags=["short"]))
        result = option_repo.list_all(tags_all=["italian", "short"])
        assert len(result) == 1
        assert result[0].name == "A"

    def test_filter_by_tags_any_or_logic(self, option_repo: OptionRepository) -> None:
        option_repo.create(Option(name="A", tags=["italian"]))
        option_repo.create(Option(name="B", tags=["german"]))
        option_repo.create(Option(name="C", tags=["french"]))
        result = option_repo.list_all(tags_any=["italian", "german"])
        assert len(result) == 2
        names = {o.name for o in result}
        assert names == {"A", "B"}

    def test_filter_combined_q_and_tags(self, option_repo: OptionRepository) -> None:
        option_repo.create(Option(name="Luna", tags=["italian"]))
        option_repo.create(Option(name="Lucia", tags=["italian"]))
        option_repo.create(Option(name="Luna Rosa", tags=["spanish"]))
        result = option_repo.list_all(q="luna", tags_any=["italian"])
        assert len(result) == 1
        assert result[0].name == "Luna"

    def test_filter_no_matches_returns_empty(self, option_repo: OptionRepository) -> None:
        option_repo.create(Option(name="Luna", tags=["italian"]))
        result = option_repo.list_all(q="xyz")
        assert result == []


class TestOptionBulkAndTags:
    def test_get_many_returns_existing_skips_missing(self, option_repo: OptionRepository) -> None:
        a = option_repo.create(Option(name="A"))
        b = option_repo.create(Option(name="B"))
        missing_id = uuid.uuid4()
        result = option_repo.get_many([a.id, missing_id, b.id])
        assert len(result) == 2
        names = {o.name for o in result}
        assert names == {"A", "B"}

    def test_get_all_tags_returns_sorted_deduplicated(self, option_repo: OptionRepository) -> None:
        option_repo.create(Option(name="A", tags=["zebra", "apple"]))
        option_repo.create(Option(name="B", tags=["apple", "mango"]))
        tags = option_repo.get_all_tags()
        assert tags == ["apple", "mango", "zebra"]

    def test_get_all_tags_empty_when_no_options(self, option_repo: OptionRepository) -> None:
        tags = option_repo.get_all_tags()
        assert tags == []


class TestTagNormalization:
    def test_strips_special_chars(self) -> None:
        option = Option(name="Test", tags=["Baby Name!"])
        assert option.tags == ["baby-name"]

    def test_collapses_hyphens(self) -> None:
        option = Option(name="Test", tags=["a---b"])
        assert option.tags == ["a-b"]

    def test_discards_empty_after_normalization(self) -> None:
        option = Option(name="Test", tags=["!!!", "valid"])
        assert option.tags == ["valid"]

    def test_deduplicates_tags(self) -> None:
        option = Option(name="Test", tags=["hello", "HELLO", "Hello"])
        assert option.tags == ["hello"]

    def test_sorts_tags(self) -> None:
        option = Option(name="Test", tags=["zebra", "apple", "mango"])
        assert option.tags == ["apple", "mango", "zebra"]
