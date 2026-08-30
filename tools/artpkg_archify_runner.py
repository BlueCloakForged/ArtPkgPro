"""Local Archify command runner for ArtPkg review projections."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


@dataclass
class ArchifyConfig:
    node_executable: str = "node"
    archify_root: str = "D:/archify/archify"
    quality: str = "showcase"
    receipt_dir: str | None = None
    timeout_seconds: int = 60


def sha256_file(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _artifact_path(operation: str, args: list[str]) -> str | None:
    if operation in {"validate", "deliver"} and len(args) >= 3:
        return args[2]
    if operation == "visual-check" and len(args) >= 2:
        return args[1]
    return None


def _output_path(operation: str, args: list[str]) -> str | None:
    if operation == "deliver" and len(args) >= 4:
        return args[3]
    return None


def _write_receipt(config: ArchifyConfig, operation: str, result: dict[str, Any]) -> None:
    if not config.receipt_dir:
        return
    receipt_dir = Path(config.receipt_dir).expanduser().resolve()
    receipt_dir.mkdir(parents=True, exist_ok=True)
    path = receipt_dir / f"archify-{operation}.receipt.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    result["receipt_path"] = str(path)


def _run(config: ArchifyConfig, args: list[str]) -> dict[str, Any]:
    command = [config.node_executable, "bin/archify.mjs", *args, "--json"]
    operation = args[0] if args else "unknown"
    diagram_type = args[1] if operation in {"validate", "deliver"} and len(args) > 1 else None
    artifact_path = _artifact_path(operation, args)
    output_path = _output_path(operation, args)
    artifact_sha256 = sha256_file(artifact_path) if artifact_path and Path(artifact_path).exists() else None
    try:
        completed = subprocess.run(command, cwd=config.archify_root, text=True, capture_output=True, timeout=config.timeout_seconds)
        exit_code: int | str = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        try:
            receipt = json.loads(stdout or "{}")
        except json.JSONDecodeError:
            receipt = {"ok": False, "error": "Archify did not return JSON", "stdout": stdout}
        if not isinstance(receipt, dict):
            receipt = {"ok": False, "error": "Archify did not return a JSON object", "value": receipt}
        ok = completed.returncode == 0 and receipt.get("ok") is True
    except subprocess.TimeoutExpired as exc:
        exit_code = "TIMEOUT"
        stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        receipt = {"ok": False, "error": "Archify command timed out"}
        ok = False

    result = {
        "ok": ok,
        "operation": operation,
        "diagram_type": diagram_type,
        "exit_code": exit_code,
        "command": command,
        "cwd": config.archify_root,
        "artifact_path": artifact_path,
        "artifact_sha256": artifact_sha256,
        "output_path": output_path,
        "output_sha256": sha256_file(output_path) if output_path and Path(output_path).exists() else None,
        "timeout_seconds": config.timeout_seconds,
        "created": _now(),
        "receipt": receipt,
        "stderr": stderr,
    }
    _write_receipt(config, operation, result)
    return result


def run_archify_validate(config: ArchifyConfig, diagram_type: str, ir_path: str | Path) -> dict[str, Any]:
    return _run(config, ["validate", diagram_type, str(ir_path), "--quality", config.quality])


def run_archify_deliver(config: ArchifyConfig, diagram_type: str, ir_path: str | Path, html_path: str | Path) -> dict[str, Any]:
    return _run(config, ["deliver", diagram_type, str(ir_path), str(html_path), "--quality", config.quality])


def run_archify_visual_check(config: ArchifyConfig, html_path: str | Path) -> dict[str, Any]:
    return _run(config, ["visual-check", str(html_path)])
