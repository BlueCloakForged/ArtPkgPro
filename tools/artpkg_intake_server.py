"""Local ArtPkg intake web UI server."""
from __future__ import annotations

import argparse
import json
import tempfile
import webbrowser
from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import artpkg_intake
import artpkg_archify_projection


@dataclass
class UploadedFile:
    filename: str
    content: bytes
    content_type: str


def parse_multipart_upload(content_type: str, body: bytes) -> UploadedFile:
    headers = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
    message = BytesParser(policy=default).parsebytes(headers + body)
    for part in message.iter_parts():
        disposition = part.get_content_disposition()
        if disposition == "form-data" and part.get_param("name", header="content-disposition") == "file":
            filename = part.get_filename() or "pre-artifacts.md"
            return UploadedFile(filename=filename, content=part.get_payload(decode=True) or b"", content_type=part.get_content_type())
    raise ValueError("multipart upload did not include file")


def session_summary(session: dict[str, Any]) -> dict[str, Any]:
    queues = session.get("review_queues", {})
    return {
        "session_id": session.get("session_id"),
        "session_dir": session.get("session_dir"),
        "source": session.get("source"),
        "validation": session.get("validation"),
        "review_queues": queues,
        "queue_counts": {name: len(items) for name, items in queues.items()},
        "answers_path": session.get("answers_path"),
    }


def resolve_session_dir(session_dir: str, workspace: str | Path) -> Path:
    intake_sessions_dir = (Path(workspace).expanduser().resolve() / ".artpkg" / "intake_sessions").resolve()
    resolved_session_dir = Path(session_dir).expanduser().resolve()
    try:
        resolved_session_dir.relative_to(intake_sessions_dir)
    except ValueError as exc:
        raise ValueError("session directory is outside the configured intake sessions directory") from exc
    return resolved_session_dir


class IntakeHandler(BaseHTTPRequestHandler):
    workspace = Path.cwd()
    template_path: Path | None = None

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            html = (Path(__file__).with_name("artpkg_intake_ui.html")).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
            return
        if parsed.path == "/api/session":
            try:
                params = parse_qs(parsed.query)
                session_dir = resolve_session_dir(params.get("dir", [""])[0], self.workspace)
                session = artpkg_intake.load_intake_session(session_dir)
                self._json(200, session_summary(session))
            except Exception as exc:
                self._json(400, {"error": str(exc)})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            if parsed.path == "/api/intake":
                upload = parse_multipart_upload(self.headers.get("Content-Type", ""), body)
                if Path(upload.filename).suffix.lower() not in {".md", ".markdown", ".txt"}:
                    raise ValueError("unsupported upload type")
                upload_dir = Path(tempfile.mkdtemp(prefix="artpkg-upload-"))
                source = upload_dir / Path(upload.filename).name
                source.write_bytes(upload.content)
                session = artpkg_intake.create_intake_session(source, self.workspace, template_path=self.template_path)
                self._json(200, session_summary(session))
                return

            payload = json.loads(body.decode("utf-8") or "{}")
            session_dir = resolve_session_dir(payload["session_dir"], self.workspace)
            session = artpkg_intake.load_intake_session(session_dir)
            if parsed.path == "/api/session/confirm":
                artpkg_intake.confirm_answer(session, payload["question_id"], payload.get("reviewer", "UI reviewer"))
                self._json(200, session_summary(session))
                return
            if parsed.path == "/api/session/reject":
                artpkg_intake.reject_seeded_answer(session, payload["question_id"], payload.get("reason", "Rejected in UI"), payload.get("reviewer", "UI reviewer"))
                self._json(200, session_summary(session))
                return
            if parsed.path == "/api/session/project":
                result = artpkg_archify_projection.build_readiness_projection(session)
                summary = session_summary(session)
                summary["projection"] = {"ir_path": result.ir_path, "mapping_path": result.mapping_path, "validation_path": result.validation_path}
                self._json(200, summary)
                return
            self._json(404, {"error": "not found"})
        except Exception as exc:
            self._json(400, {"error": str(exc)})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local ArtPkg intake UI.")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--template", default=None)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args(argv)

    IntakeHandler.workspace = Path(args.workspace).expanduser().resolve()
    IntakeHandler.template_path = Path(args.template).expanduser().resolve() if args.template else None
    server = ThreadingHTTPServer((args.host, args.port), IntakeHandler)
    url = f"http://{args.host}:{args.port}/"
    print(f"ArtPkg intake UI running at {url}")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
