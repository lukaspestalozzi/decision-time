"""Repository utility functions: read_json, write_json, list_dir, acquire_lock."""

import contextlib
import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from filelock import FileLock

from app.exceptions import NotFoundError


def read_json(path: Path) -> dict[str, Any]:
    """Read and parse a JSON file.

    Raises NotFoundError if the file does not exist.
    """
    try:
        with open(path) as f:
            return json.load(f)  # type: ignore[no-any-return]
    except FileNotFoundError:
        raise NotFoundError(f"File not found: {path}") from None


def write_json(path: Path, data: dict[str, Any]) -> None:
    """Atomically write data as JSON to path.

    Writes to a temp file in the same directory, then renames.
    Creates parent directories if they don't exist.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, default=str)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


def list_dir(directory: Path) -> list[Path]:
    """List all .json files in a directory.

    Returns an empty list if the directory doesn't exist.
    """
    if not directory.exists():
        return []
    return sorted(p for p in directory.iterdir() if p.suffix == ".json")


@contextmanager
def acquire_lock(path: Path, timeout: float = 10.0) -> Iterator[None]:
    """Context manager that acquires a file lock for the given path.

    Lock file is placed at {path}.lock.
    """
    lock_path = Path(str(path) + ".lock")
    lock = FileLock(str(lock_path), timeout=timeout)
    with lock:
        yield
