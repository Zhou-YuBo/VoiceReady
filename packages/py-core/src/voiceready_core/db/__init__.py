"""SQLite project storage for VoiceReady."""

from pathlib import Path

from .connection import Database, database_path, open_project
from .migrations import CURRENT_SCHEMA_VERSION, migrate
from .repository import Repository


def initialize_database(project_root: str | Path) -> Database:
    """Open a project database and apply all available migrations."""

    database = open_project(project_root)
    migrate(database)
    return database


def run_migrations(database: Database | str | Path) -> int:
    """Apply migrations to an open database or a project root."""

    if isinstance(database, Database):
        return migrate(database)
    with open_project(database) as opened:
        return migrate(opened)


def get_health_status(project_root: str | Path) -> dict[str, object]:
    """Return the health summary for a project database."""

    with initialize_database(project_root) as database:
        return Repository(database).health_status()


def create_project(
    project_root: str | Path,
    name: str,
    default_language: str | None = None,
) -> str:
    """Create the root project record in its own database."""

    root = Path(project_root).expanduser().resolve()
    with initialize_database(root) as database:
        return Repository(database).create_project(name, str(root), default_language)

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "Database",
    "Repository",
    "create_project",
    "database_path",
    "get_health_status",
    "initialize_database",
    "migrate",
    "open_project",
    "run_migrations",
]
