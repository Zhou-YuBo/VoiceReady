"""SQLite connection and project path helpers."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


DATABASE_RELATIVE_PATH = Path("voiceready") / "db" / "project.sqlite"
BUSY_TIMEOUT_MS = 5_000


def database_path(project_root: str | Path) -> Path:
    """Return the database path for a VoiceReady project."""

    return Path(project_root).expanduser().resolve() / DATABASE_RELATIVE_PATH


class Database:
    """A short-lived, thread-affine SQLite connection."""

    def __init__(self, path: Path, connection: sqlite3.Connection) -> None:
        self.path = path
        self.connection = connection

    @classmethod
    def connect(cls, path: str | Path, *, create_parent: bool = True) -> "Database":
        database = Path(path).expanduser().resolve()
        if create_parent:
            database.parent.mkdir(parents=True, exist_ok=True)

        connection = sqlite3.connect(
            database,
            timeout=BUSY_TIMEOUT_MS / 1000,
            check_same_thread=True,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        connection.execute("PRAGMA journal_mode = WAL")
        return cls(database, connection)

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Run a transaction and roll it back on any exception."""

        try:
            yield self.connection
        except Exception:
            self.connection.rollback()
            raise
        else:
            self.connection.commit()


def open_project(project_root: str | Path) -> Database:
    """Open the SQLite database belonging to a project root."""

    return Database.connect(database_path(project_root))
