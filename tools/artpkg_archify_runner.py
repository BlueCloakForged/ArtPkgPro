"""Local Archify command runner for ArtPkg review projections."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ArchifyConfig:
    node_executable: str = "node"
    archify_root: str = "D:/archify/archify"
    quality: str = "showcase"


def _run(config: ArchifyConfig, args: list[str]) -> dict[str, Any]:
    command = [config.node_executable, "bin/archify.mjs", *args, "--json"]
    completed = subprocess.run(command, cwd=config.archify_root, text=True, capture_output=True)
    try:
        receipt = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        receipt = {"ok": False, "error": "Archify did not return JSON", "stdout": completed.stdout}
    if not isinstance(receipt, dict):
        receipt = {"ok": False, "error": "Archify did not return a JSON object", "value": receipt}
    return {
        "ok": completed.returncode == 0 and receipt.get("ok") is True,
        "exit_code": completed.returncode,
        "command": command,
        "cwd": config.archify_root,
        "receipt": receipt,
        "stderr": completed.stderr,
    }


def run_archify_validate(config: ArchifyConfig, diagram_type: str, ir_path: str | Path) -> dict[str, Any]:
    return _run(config, ["validate", diagram_type, str(ir_path), "--quality", config.quality])


def run_archify_deliver(config: ArchifyConfig, diagram_type: str, ir_path: str | Path, html_path: str | Path) -> dict[str, Any]:
    return _run(config, ["deliver", diagram_type, str(ir_path), str(html_path), "--quality", config.quality])


def run_archify_visual_check(config: ArchifyConfig, html_path: str | Path) -> dict[str, Any]:
    return _run(config, ["visual-check", str(html_path)])
