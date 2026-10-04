from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from voiceready_kernel.stdio import handle_request


class KernelProtocolTests(unittest.TestCase):
    def request(self, method: str, project_root: Path, request_id: str = "test-1"):
        return handle_request(
            {
                "protocol_version": 1,
                "request_id": request_id,
                "method": method,
                "params": {"project_root": str(project_root)},
            }
        )

    def test_create_open_and_duplicate_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "demo"
            created, should_stop = self.request("create_project", root)
            self.assertTrue(created["ok"])
            self.assertFalse(should_stop)
            self.assertTrue((root / "voiceready/db/project.sqlite").exists())

            opened, _ = self.request("open_project", root, "test-2")
            self.assertTrue(opened["ok"])
            self.assertEqual(opened["result"]["schema_version"], 1)
            self.assertTrue(opened["result"]["integrity_ok"])

            duplicate, _ = self.request("create_project", root, "test-3")
            self.assertFalse(duplicate["ok"])
            self.assertEqual(duplicate["error"]["code"], "PROJECT_ALREADY_EXISTS")

    def test_missing_project_and_invalid_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing, _ = self.request("open_project", Path(directory) / "missing")
            self.assertFalse(missing["ok"])
            self.assertEqual(missing["error"]["code"], "PROJECT_NOT_FOUND")

        invalid, should_stop = handle_request({"protocol_version": 1, "request_id": "bad"})
        self.assertFalse(invalid["ok"])
        self.assertFalse(should_stop)
        self.assertEqual(invalid["error"]["code"], "INVALID_REQUEST")

    def test_shutdown_is_successful(self) -> None:
        response, should_stop = handle_request(
            {"protocol_version": 1, "request_id": "shutdown", "method": "shutdown", "params": {}}
        )
        self.assertTrue(response["ok"])
        self.assertTrue(should_stop)


if __name__ == "__main__":
    unittest.main()