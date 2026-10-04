from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from voiceready_core import Repository, create_project, get_health_status, open_project
from voiceready_core.db import migrations as migration_api


class CoreDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name)
        self.database = open_project(self.project_root)
        self.repository = Repository(self.database)
        self.project_id = self.repository.create_project("测试项目", str(self.project_root), "zh")

    def tearDown(self) -> None:
        self.database.close()
        self.temp_dir.cleanup()

    def test_migration_is_idempotent_and_health_is_valid(self) -> None:
        status = self.repository.health_status()
        self.assertEqual(status["schema_version"], 1)
        self.assertEqual(status["integrity"], "ok")
        self.assertEqual(status["project_count"], 1)

        with open_project(self.project_root) as reopened:
            second = Repository(reopened).health_status()
            self.assertEqual(second["schema_version"], 1)
            self.assertEqual(second["project_count"], 1)

    def test_failed_migration_rolls_back_schema_changes(self) -> None:
        broken_root = Path(self.temp_dir.name) / "broken-migration"
        migration_dir = Path(self.temp_dir.name) / "migrations"
        migration_dir.mkdir()
        (migration_dir / "0002_broken.sql").write_text(
            "CREATE TABLE should_rollback (id INTEGER);\nTHIS IS NOT SQL;\n",
            encoding="utf-8",
        )
        original_path = migration_api.MIGRATIONS_PATH
        migration_api.MIGRATIONS_PATH = migration_dir
        try:
            with open_project(broken_root) as database:
                with self.assertRaises(sqlite3.Error):
                    migration_api.migrate(database)
                table = database.connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'should_rollback'"
                ).fetchone()
                applied = database.connection.execute(
                    "SELECT COUNT(*) FROM schema_migrations WHERE version = 2"
                ).fetchone()[0]
                self.assertIsNone(table)
                self.assertEqual(applied, 0)
        finally:
            migration_api.MIGRATIONS_PATH = original_path

    def test_asset_lineage_and_collection_membership(self) -> None:
        source = self.repository.create_asset(
            self.project_id,
            asset_type="voice_audio",
            origin_type="source",
            uri="media/voice/sources/source.wav",
            display_name="source.wav",
            duration_ms=10_000,
            is_readonly=True,
        )
        segment = self.repository.create_asset(
            self.project_id,
            asset_type="voice_audio",
            origin_type="segment",
            uri="media/voice/segments/source_0001.wav",
            display_name="source_0001.wav",
            duration_ms=2_000,
        )
        self.repository.create_asset_relation(
            source,
            segment,
            "segment_of",
            start_ms=0,
            end_ms=2_000,
            sequence_index=0,
        )
        collection = self.repository.create_collection(self.project_id, name="TTS", purpose="training")
        self.repository.add_to_collection(collection, segment)
        self.assertEqual(len(self.repository.list_exportable_speech_units(collection)), 0)

    def test_official_and_asr_text_are_separate_and_export_requires_human_approval(self) -> None:
        asset = self.repository.create_asset(
            self.project_id,
            asset_type="voice_audio",
            origin_type="source",
            uri="media/voice/sources/line.wav",
            display_name="line.wav",
        )
        speech = self.repository.create_speech_unit(
            asset,
            official_text="官方文本",
            asr_text="ASR 文本",
            final_text="官方文本",
            text_source_type="official",
        )
        collection = self.repository.create_collection(self.project_id, name="Approved")
        self.repository.add_to_collection(collection, asset)
        self.assertEqual(len(self.repository.list_exportable_speech_units(collection)), 0)

        task = self.repository.create_review_task(
            self.project_id,
            review_type="official_alignment",
            title="校对",
        )
        item = self.repository.create_review_item(
            task,
            asset,
            speech_unit_id=speech,
            ai_suggestion="使用官方文本",
        )
        self.repository.update_review_item(item, status="ai_completed", reviewer="ai")
        self.assertEqual(len(self.repository.list_exportable_speech_units(collection)), 0)
        self.repository.update_review_item(item, status="human_approved", human_decision="approved", reviewer="human")
        rows = self.repository.list_exportable_speech_units(collection)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["official_text"], "官方文本")
        self.assertEqual(rows[0]["asr_text"], "ASR 文本")

    def test_failed_job_keeps_error_details(self) -> None:
        job = self.repository.create_job(self.project_id, job_type="asr")
        self.repository.update_job(job, status="failed", error_message="模型进程退出")
        row = self.repository.get_job(job)
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["error_message"], "模型进程退出")
        self.assertIsNotNone(row["finished_at"])

    def test_public_project_helpers_use_the_standard_database_path(self) -> None:
        other_root = Path(self.temp_dir.name) / "other-project"
        project_id = create_project(other_root, "另一个项目", "en")
        status = get_health_status(other_root)
        self.assertTrue(project_id)
        self.assertEqual(status["project_count"], 1)
        self.assertEqual(
            status["database"],
            str(other_root.resolve() / "voiceready" / "db" / "project.sqlite"),
        )

    def test_invalid_segment_range_is_rejected(self) -> None:
        source = self.repository.create_asset(
            self.project_id,
            asset_type="voice_audio",
            origin_type="source",
            uri="source.wav",
            display_name="source.wav",
        )
        segment = self.repository.create_asset(
            self.project_id,
            asset_type="voice_audio",
            origin_type="segment",
            uri="segment.wav",
            display_name="segment.wav",
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.create_asset_relation(source, segment, "segment_of", start_ms=2000, end_ms=1000)

    def test_overlapping_segments_are_rejected(self) -> None:
        source = self.repository.create_asset(
            self.project_id,
            asset_type="voice_audio",
            origin_type="source",
            uri="source.wav",
            display_name="source.wav",
        )
        first = self.repository.create_asset(
            self.project_id,
            asset_type="voice_audio",
            origin_type="segment",
            uri="first.wav",
            display_name="first.wav",
        )
        second = self.repository.create_asset(
            self.project_id,
            asset_type="voice_audio",
            origin_type="segment",
            uri="second.wav",
            display_name="second.wav",
        )
        self.repository.create_asset_relation(
            source,
            first,
            "segment_of",
            start_ms=0,
            end_ms=1000,
            sequence_index=0,
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.create_asset_relation(
                source,
                second,
                "segment_of",
                start_ms=500,
                end_ms=1500,
                sequence_index=1,
            )

    def test_readonly_source_asset_cannot_be_updated(self) -> None:
        source = self.repository.create_asset(
            self.project_id,
            asset_type="voice_audio",
            origin_type="source",
            uri="source.wav",
            display_name="source.wav",
            is_readonly=True,
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.database.connection.execute(
                "UPDATE asset SET display_name = 'changed.wav' WHERE id = ?", (source,)
            )
        self.database.connection.rollback()


if __name__ == "__main__":
    unittest.main()
