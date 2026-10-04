"""Shared domain primitives and project services."""

__version__ = "0.1.0"

from .db import (
    Database,
    Repository,
    create_project,
    database_path,
    get_health_status,
    initialize_database,
    migrate,
    open_project,
    run_migrations,
)

__all__ = [
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
