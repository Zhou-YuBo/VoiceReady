"""SQL migration runner for the VoiceReady project database."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from .connection import Database


MIGRATIONS_PATH = Path(__file__).with_name("migrations")
MIGRATION_PATTERN = re.compile(r"^(?P<version>\d{4})_(?P<name>[a-z0-9_]+)\.sql$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _available_migrations() -> list[tuple[int, str, Path]]:
    migrations: list[tuple[int, str, Path]] = []
    for path in sorted(MIGRATIONS_PATH.glob("*.sql")):
        match = MIGRATION_PATTERN.match(path.name)
        if match is None:
            raise ValueError(f"Invalid migration filename: {path.name}")
        migrations.append((int(match.group("version")), match.group("name"), path))
    versions = [version for version, _, _ in migrations]
    if len(versions) != len(set(versions)):
        raise ValueError("Duplicate migration version")
    return migrations


CURRENT_SCHEMA_VERSION = max(
    (version for version, _, _ in _available_migrations()),
    default=0,
)


def migrate(database: Database) -> int:
    """Apply all pending migrations and return the resulting schema version."""

    database.connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )
    database.connection.commit()

    applied = {
        int(row["version"])
        for row in database.connection.execute("SELECT version FROM schema_migrations")
    }
    for version, name, path in _available_migrations():
        if version in applied:
            continue
        sql = path.read_text(encoding="utf-8")
        # ``executescript`` commits any transaction that is already open.
        # Put the migration and its version record in one explicit script
        # transaction so a failed migration cannot leave half a schema.
        applied_at = _utc_now().replace("'", "''")
        escaped_name = name.replace("'", "''")
        script = (
            "BEGIN;\n"
            f"{sql.rstrip()};\n"
            "INSERT INTO schema_migrations(version, name, applied_at) "
            f"VALUES ({version}, '{escaped_name}', '{applied_at}');\n"
            "COMMIT;"
        )
        try:
            database.connection.executescript(script)
        except Exception:
            database.connection.rollback()
            raise
    row = database.connection.execute(
        "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
    ).fetchone()
    return int(row["version"])
