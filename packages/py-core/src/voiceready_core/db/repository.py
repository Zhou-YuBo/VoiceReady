"""Small repository for core project facts."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

from .connection import Database
from .migrations import migrate


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id() -> str:
    return str(uuid.uuid4())


def _json(value: dict[str, Any] | None) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True)


class Repository:
    """Transactional access to the database's core entities."""

    def __init__(self, database: Database, *, auto_migrate: bool = True) -> None:
        self.database = database
        if auto_migrate:
            migrate(database)

    def create_project(
        self,
        name: str,
        root_uri: str,
        default_language: str | None = None,
    ) -> str:
        project_id = _id()
        now = _now()
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO project(id, name, root_uri, default_language, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (project_id, name, root_uri, default_language, now, now),
            )
        return project_id

    def get_project(self, project_id: str) -> sqlite3.Row | None:
        return self.database.connection.execute(
            "SELECT * FROM project WHERE id = ?", (project_id,)
        ).fetchone()

    def create_asset(
        self,
        project_id: str,
        *,
        asset_type: str,
        origin_type: str,
        uri: str,
        display_name: str,
        sha256: str | None = None,
        size_bytes: int | None = None,
        duration_ms: int | None = None,
        sample_rate: int | None = None,
        channels: int | None = None,
        language: str | None = None,
        speaker_id: str | None = None,
        is_readonly: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        asset_id = _id()
        now = _now()
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO asset(
                    id, project_id, asset_type, origin_type, uri, display_name,
                    sha256, size_bytes, duration_ms, sample_rate, channels,
                    language, speaker_id, is_readonly, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset_id,
                    project_id,
                    asset_type,
                    origin_type,
                    uri,
                    display_name,
                    sha256,
                    size_bytes,
                    duration_ms,
                    sample_rate,
                    channels,
                    language,
                    speaker_id,
                    int(is_readonly),
                    _json(metadata),
                    now,
                    now,
                ),
            )
        return asset_id

    def create_asset_relation(
        self,
        parent_asset_id: str,
        child_asset_id: str,
        relation_type: str,
        *,
        start_ms: int | None = None,
        end_ms: int | None = None,
        sequence_index: int | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> str:
        relation_id = _id()
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO asset_relation(
                    id, parent_asset_id, child_asset_id, relation_type,
                    start_ms, end_ms, sequence_index, parameters_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    relation_id,
                    parent_asset_id,
                    child_asset_id,
                    relation_type,
                    start_ms,
                    end_ms,
                    sequence_index,
                    _json(parameters),
                    _now(),
                ),
            )
        return relation_id

    def create_collection(
        self,
        project_id: str,
        *,
        name: str,
        purpose: str | None = None,
        language: str | None = None,
        speaker_id: str | None = None,
    ) -> str:
        collection_id = _id()
        now = _now()
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO collection(
                    id, project_id, name, purpose, language, speaker_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (collection_id, project_id, name, purpose, language, speaker_id, now, now),
            )
        return collection_id

    def add_to_collection(
        self,
        collection_id: str,
        asset_id: str,
        *,
        included: bool = True,
        inclusion_reason: str | None = None,
        exclusion_reason: str | None = None,
    ) -> None:
        now = _now()
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO collection_asset(
                    collection_id, asset_id, included, inclusion_reason,
                    exclusion_reason, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(collection_id, asset_id) DO UPDATE SET
                    included = excluded.included,
                    inclusion_reason = excluded.inclusion_reason,
                    exclusion_reason = excluded.exclusion_reason,
                    updated_at = excluded.updated_at
                """,
                (
                    collection_id,
                    asset_id,
                    int(included),
                    inclusion_reason,
                    exclusion_reason,
                    now,
                    now,
                ),
            )

    def create_text_source(
        self,
        project_id: str,
        *,
        source_type: str,
        name: str,
        uri: str | None = None,
        content_sha256: str | None = None,
        language: str | None = None,
        description: str | None = None,
    ) -> str:
        source_id = _id()
        now = _now()
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO text_source(
                    id, project_id, source_type, name, uri, content_sha256,
                    language, description, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    project_id,
                    source_type,
                    name,
                    uri,
                    content_sha256,
                    language,
                    description,
                    now,
                    now,
                ),
            )
        return source_id

    def create_text_unit(
        self,
        source_id: str,
        *,
        sequence_index: int,
        text: str,
        speaker_id: str | None = None,
        locator: dict[str, Any] | None = None,
    ) -> str:
        unit_id = _id()
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO text_unit(
                    id, source_id, sequence_index, text, speaker_id, locator_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (unit_id, source_id, sequence_index, text, speaker_id, _json(locator), _now()),
            )
        return unit_id

    def create_speech_unit(
        self,
        asset_id: str,
        *,
        sequence_index: int = 0,
        start_ms: int | None = None,
        end_ms: int | None = None,
        official_text: str | None = None,
        asr_text: str | None = None,
        final_text: str | None = None,
        official_text_unit_id: str | None = None,
        text_source_type: str | None = None,
    ) -> str:
        speech_id = _id()
        now = _now()
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO speech_unit(
                    id, asset_id, sequence_index, start_ms, end_ms,
                    official_text, asr_text, final_text, official_text_unit_id,
                    text_source_type, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    speech_id,
                    asset_id,
                    sequence_index,
                    start_ms,
                    end_ms,
                    official_text,
                    asr_text,
                    final_text,
                    official_text_unit_id,
                    text_source_type,
                    now,
                    now,
                ),
            )
        return speech_id

    def create_job(
        self,
        project_id: str,
        *,
        job_type: str,
        parameters: dict[str, Any] | None = None,
    ) -> str:
        job_id = _id()
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO job(id, project_id, job_type, parameters_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (job_id, project_id, job_type, _json(parameters), _now()),
            )
        return job_id

    def link_job_asset(
        self,
        job_id: str,
        asset_id: str,
        *,
        io_role: str,
        sequence_index: int = 0,
    ) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO job_asset(job_id, asset_id, io_role, sequence_index)
                VALUES (?, ?, ?, ?)
                """,
                (job_id, asset_id, io_role, sequence_index),
            )

    def update_job(
        self,
        job_id: str,
        *,
        status: str,
        error_message: str | None = None,
        log_uri: str | None = None,
    ) -> None:
        """Update a job and retain terminal failure details."""

        now = _now()
        with self.database.transaction() as connection:
            job = connection.execute(
                "SELECT started_at FROM job WHERE id = ?",
                (job_id,),
            ).fetchone()
            if job is None:
                raise ValueError(f"Unknown job: {job_id}")

            started_at = job["started_at"] or (now if status == "running" else None)
            finished_at = now if status in {"succeeded", "failed", "cancelled"} else None
            connection.execute(
                """
                UPDATE job
                SET status = ?, error_message = ?, log_uri = ?,
                    started_at = ?, finished_at = ?
                WHERE id = ?
                """,
                (status, error_message, log_uri, started_at, finished_at, job_id),
            )

    def get_job(self, job_id: str) -> sqlite3.Row | None:
        return self.database.connection.execute(
            "SELECT * FROM job WHERE id = ?", (job_id,)
        ).fetchone()

    def create_review_task(
        self,
        project_id: str,
        *,
        review_type: str,
        title: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        task_id = _id()
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO review_task(id, project_id, review_type, title, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (task_id, project_id, review_type, title, _json(metadata), _now()),
            )
        return task_id

    def create_review_item(
        self,
        review_task_id: str,
        asset_id: str,
        *,
        speech_unit_id: str | None = None,
        ai_suggestion: str | None = None,
        confidence: float | None = None,
    ) -> str:
        item_id = _id()
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO review_item(
                    id, review_task_id, asset_id, speech_unit_id,
                    ai_suggestion, confidence, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    review_task_id,
                    asset_id,
                    speech_unit_id,
                    ai_suggestion,
                    confidence,
                    _now(),
                    _now(),
                ),
            )
        return item_id

    def update_review_item(
        self,
        item_id: str,
        *,
        status: str,
        human_decision: str | None = None,
        reviewer: str | None = None,
        note: str | None = None,
    ) -> None:
        now = _now()
        with self.database.transaction() as connection:
            item = connection.execute(
                "SELECT speech_unit_id FROM review_item WHERE id = ?",
                (item_id,),
            ).fetchone()
            if item is None:
                raise ValueError(f"Unknown review item: {item_id}")
            if status == "human_approved" and human_decision != "approved":
                raise ValueError("human_approved requires human_decision='approved'")
            if status == "human_rejected" and human_decision != "rejected":
                raise ValueError("human_rejected requires human_decision='rejected'")

            connection.execute(
                """
                UPDATE review_item
                SET status = ?, human_decision = ?, reviewer = ?,
                    reviewed_at = ?, note = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, human_decision, reviewer, now, note, now, item_id),
            )
            speech_unit_id = item["speech_unit_id"]
            if speech_unit_id is not None:
                speech_status = {
                    "human_approved": "human_approved",
                    "human_rejected": "human_rejected",
                    "needs_revision": "needs_revision",
                    "ai_completed": "ai_completed",
                }.get(status)
                if speech_status is not None:
                    connection.execute(
                        """
                        UPDATE speech_unit
                        SET review_status = ?, review_note = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (speech_status, note, now, speech_unit_id),
                    )
            connection.execute(
                """
                INSERT INTO review_event(
                    id, review_item_id, actor_kind, event_type, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    _id(),
                    item_id,
                    "ai" if status == "ai_completed" else ("human" if reviewer else "system"),
                    status,
                    _json({"human_decision": human_decision, "note": note}),
                    now,
                ),
            )

    def list_exportable_speech_units(self, collection_id: str) -> list[sqlite3.Row]:
        """Return only human-approved speech units with final text."""

        return list(
            self.database.connection.execute(
                """
                SELECT su.*, a.uri, a.display_name
                FROM collection_asset ca
                JOIN asset a ON a.id = ca.asset_id
                JOIN speech_unit su ON su.asset_id = a.id
                WHERE ca.collection_id = ?
                  AND ca.included = 1
                  AND su.review_status = 'human_approved'
                  AND su.final_text IS NOT NULL
                  AND length(trim(su.final_text)) > 0
                ORDER BY a.display_name, su.sequence_index
                """,
                (collection_id,),
            )
        )

    def health_status(self) -> dict[str, Any]:
        schema_row = self.database.connection.execute(
            "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
        ).fetchone()
        integrity = self.database.connection.execute("PRAGMA integrity_check").fetchone()[0]
        project_count = self.database.connection.execute("SELECT COUNT(*) FROM project").fetchone()[0]
        return {
            "database": str(self.database.path),
            "schema_version": int(schema_row["version"]),
            "integrity": integrity,
            "project_count": int(project_count),
        }
