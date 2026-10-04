"""JSONL protocol server for the VoiceReady application kernel."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from voiceready_core import Repository, create_project, database_path, initialize_database, open_project

PROTOCOL_VERSION = 1


class KernelError(Exception):
    """An expected error that can be returned to the desktop client."""

    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _error_response(request_id: str | None, code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "request_id": request_id,
        "ok": False,
        "error": {"code": code, "message": message, "details": details or {}},
    }


def _success_response(request_id: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "request_id": request_id,
        "ok": True,
        "result": result,
    }


def _project_root(params: dict[str, Any]) -> Path:
    value = params.get("project_root")
    if not isinstance(value, str) or not value.strip():
        raise KernelError("INVALID_PROJECT_ROOT", "project_root 必须是非空路径。")
    return Path(value).expanduser().resolve()


def _health(project_root: Path) -> dict[str, Any]:
    expected = database_path(project_root)
    if not expected.exists():
        raise KernelError(
            "PROJECT_NOT_FOUND",
            "找不到 VoiceReady 项目数据库。",
            details={"database_path": str(expected)},
        )
    with initialize_database(project_root) as database:
        status = Repository(database).health_status()
    return {
        "project_root": str(project_root),
        "database_path": status["database"],
        "schema_version": status["schema_version"],
        "integrity_ok": status["integrity"] == "ok",
        "project_count": status["project_count"],
    }


def _create(params: dict[str, Any]) -> dict[str, Any]:
    project_root = _project_root(params)
    expected = database_path(project_root)
    if expected.exists():
        raise KernelError(
            "PROJECT_ALREADY_EXISTS",
            "目标目录已经包含 VoiceReady 项目。",
            details={"database_path": str(expected)},
        )
    project_root.mkdir(parents=True, exist_ok=True)
    name = project_root.name or "VoiceReady 项目"
    with initialize_database(project_root) as database:
        Repository(database).create_project(name, str(project_root), "zh-CN")
    return _health(project_root)


def _dispatch(method: str, params: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    if method == "health":
        return _health(_project_root(params)), False
    if method == "create_project":
        return _create(params), False
    if method == "open_project":
        return _health(_project_root(params)), False
    if method == "shutdown":
        return {"message": "Kernel 已关闭。"}, True
    raise KernelError("METHOD_NOT_FOUND", f"不支持的方法：{method}")


def handle_request(request: Any) -> tuple[dict[str, Any], bool]:
    if not isinstance(request, dict):
        return _error_response(None, "INVALID_REQUEST", "请求必须是 JSON 对象。"), False
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip():
        return _error_response(None, "INVALID_REQUEST_ID", "request_id 必须是非空字符串。"), False
    if request.get("protocol_version") != PROTOCOL_VERSION:
        return _error_response(request_id, "UNSUPPORTED_PROTOCOL", "不支持的协议版本。"), False
    method = request.get("method")
    params = request.get("params", {})
    if not isinstance(method, str) or not isinstance(params, dict):
        return _error_response(request_id, "INVALID_REQUEST", "method 和 params 格式无效。"), False
    try:
        result, should_stop = _dispatch(method, params)
    except KernelError as error:
        return _error_response(request_id, error.code, error.message, error.details), False
    except Exception as error:  # noqa: BLE001 - convert worker failures to protocol errors
        print(f"kernel request failed: {error!r}", file=sys.stderr, flush=True)
        return _error_response(request_id, "INTERNAL_ERROR", "Kernel 处理请求失败。"), False
    return _success_response(request_id, result), should_stop


def serve_stdio() -> None:
    """Read one JSON request per line and write one JSON response per line."""

    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as error:
            response, should_stop = _error_response(None, "INVALID_JSON", "请求不是合法 JSON。", {"position": error.pos}), False
        else:
            response, should_stop = handle_request(request)
        print(json.dumps(response, ensure_ascii=False, separators=(",", ":")), flush=True)
        if should_stop:
            break
