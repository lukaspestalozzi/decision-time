"""Tests for repository utility functions: read_json, write_json, list_dir, acquire_lock."""

import json
import threading
import time
from pathlib import Path

import pytest

from app.exceptions import NotFoundError
from app.repositories.util import acquire_lock, list_dir, read_json, write_json


class TestReadJson:
    def test_returns_parsed_dict(self, tmp_path: Path) -> None:
        path = tmp_path / "test.json"
        path.write_text(json.dumps({"key": "value"}))
        result = read_json(path)
        assert result == {"key": "value"}

    def test_not_found_raises_not_found_error(self, tmp_path: Path) -> None:
        path = tmp_path / "nonexistent.json"
        with pytest.raises(NotFoundError):
            read_json(path)

    def test_invalid_json_raises_error(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("{not valid json")
        with pytest.raises(json.JSONDecodeError):
            read_json(path)


class TestWriteJson:
    def test_creates_file_with_content(self, tmp_path: Path) -> None:
        path = tmp_path / "out.json"
        write_json(path, {"name": "test"})
        assert path.exists()
        content = json.loads(path.read_text())
        assert content == {"name": "test"}

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        path = tmp_path / "nested" / "deep" / "file.json"
        write_json(path, {"nested": True})
        assert path.exists()
        content = json.loads(path.read_text())
        assert content == {"nested": True}

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        path = tmp_path / "overwrite.json"
        write_json(path, {"version": 1})
        write_json(path, {"version": 2})
        content = json.loads(path.read_text())
        assert content == {"version": 2}

    def test_pretty_prints_with_indent(self, tmp_path: Path) -> None:
        path = tmp_path / "pretty.json"
        write_json(path, {"key": "value"})
        raw = path.read_text()
        assert "\n" in raw
        assert "  " in raw


class TestListDir:
    def test_returns_json_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.json").write_text("{}")
        (tmp_path / "b.json").write_text("{}")
        result = list_dir(tmp_path)
        names = sorted(p.name for p in result)
        assert names == ["a.json", "b.json"]

    def test_ignores_non_json_files(self, tmp_path: Path) -> None:
        (tmp_path / "data.json").write_text("{}")
        (tmp_path / "data.json.lock").write_text("")
        (tmp_path / "temp.tmp").write_text("")
        result = list_dir(tmp_path)
        assert len(result) == 1
        assert result[0].name == "data.json"

    def test_returns_empty_for_nonexistent_dir(self, tmp_path: Path) -> None:
        result = list_dir(tmp_path / "nonexistent")
        assert result == []

    def test_returns_empty_for_empty_dir(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        result = list_dir(empty)
        assert result == []


class TestAcquireLock:
    def test_creates_lock_file(self, tmp_path: Path) -> None:
        path = tmp_path / "target.json"
        path.write_text("{}")
        with acquire_lock(path):
            lock_path = Path(str(path) + ".lock")
            assert lock_path.exists()

    def test_releases_on_exit(self, tmp_path: Path) -> None:
        path = tmp_path / "target.json"
        path.write_text("{}")
        with acquire_lock(path):
            pass
        # Should be able to acquire again immediately
        with acquire_lock(path):
            pass

    def test_blocks_concurrent_access(self, tmp_path: Path) -> None:
        path = tmp_path / "target.json"
        path.write_text("{}")
        order: list[str] = []

        def worker(name: str, delay: float) -> None:
            with acquire_lock(path, timeout=5.0):
                order.append(f"{name}_start")
                time.sleep(delay)
                order.append(f"{name}_end")

        t1 = threading.Thread(target=worker, args=("first", 0.2))
        t2 = threading.Thread(target=worker, args=("second", 0.0))
        t1.start()
        time.sleep(0.05)  # Ensure t1 acquires lock first
        t2.start()
        t1.join()
        t2.join()
        # first must complete before second starts
        assert order.index("first_end") < order.index("second_start")

    def test_timeout_raises_error(self, tmp_path: Path) -> None:
        from filelock import Timeout

        path = tmp_path / "target.json"
        path.write_text("{}")

        lock_acquired = threading.Event()
        release_lock = threading.Event()

        def hold_lock() -> None:
            with acquire_lock(path, timeout=5.0):
                lock_acquired.set()
                release_lock.wait(timeout=5.0)

        holder = threading.Thread(target=hold_lock)
        holder.start()
        lock_acquired.wait(timeout=2.0)

        with pytest.raises(Timeout), acquire_lock(path, timeout=0.1):
            pass

        release_lock.set()
        holder.join()
