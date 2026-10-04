"""Command-line entry point for the VoiceReady application kernel."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import __version__
from .stdio import serve_stdio
from voiceready_core import Repository, open_project


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="voiceready-kernel")
    parser.add_argument("--version", action="version", version=f"voiceready-kernel {__version__}")
    parser.add_argument("--stdio", action="store_true", help="Run the persistent JSONL protocol server")
    parser.add_argument("--project", type=Path, help="VoiceReady project root")
    parser.add_argument("command", nargs="?", choices=("health", "migrate"))
    return parser


def _run(command: str, project_root: Path) -> dict[str, object]:
    with open_project(project_root) as database:
        repository = Repository(database)
        status = repository.health_status()
        status["command"] = command
        return status


def main() -> None:
    args = _parser().parse_args()
    if args.stdio:
        serve_stdio()
        return
    if args.project is None or args.command is None:
        raise SystemExit("--project and command are required unless --stdio is used")
    print(json.dumps(_run(args.command, args.project), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
