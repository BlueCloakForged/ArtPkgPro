"""Local ArtPkg intake web UI server."""
from __future__ import annotations

import argparse
import json
import os
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
import artpkg_archify_runner


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


def load_workspace_session(session_dir: str, workspace: str | Path) -> dict[str, Any]:
    resolved_session_dir = resolve_session_dir(session_dir, workspace)
    session = artpkg_intake.load_intake_session(resolved_session_dir)
    session["session_dir"] = str(resolved_session_dir)
    return session


def projection_html_response(session_dir: str, workspace: str | Path) -> tuple[int, dict[str, str], bytes]:
    resolved_session_dir = resolve_session_dir(session_dir, workspace)
    html_path = resolved_session_dir / "artpkg-readiness.architecture.html"
    if not html_path.exists():
        raise FileNotFoundError("projection HTML has not been generated")
    body = html_path.read_bytes()
    return 200, {"Content-Type": "text/html; charset=utf-8", "Content-Length": str(len(body))}, body


def decorate_projection_html(html_path: str | Path, mapping_path: str | Path) -> None:
    target = Path(html_path)
    mapping = json.loads(Path(mapping_path).read_text(encoding="utf-8"))
    payload = {
        "session_dir": mapping.get("session_dir"),
        "nodes": {
            node.get("archify_id"): node.get("artpkg_review_action")
            for node in mapping.get("nodes", [])
            if node.get("archify_id") and node.get("artpkg_review_action")
        },
    }
    if not payload["nodes"]:
        return
    page = target.read_text(encoding="utf-8")
    if "artpkg-review-actions-data" in page:
        return
    data = json.dumps(payload, ensure_ascii=True).replace("</", "<\\/")
    injection = f"""
<style id="artpkg-review-actions-style">
  .artpkg-review-panel {{ border-top:1px solid rgba(125, 211, 252, .35); margin-top:12px; padding-top:10px; display:grid; gap:7px; }}
  .artpkg-review-panel[hidden] {{ display:none; }}
  .artpkg-review-eyebrow {{ color:#7dd3fc; font-size:10px; font-weight:800; letter-spacing:.09em; text-transform:uppercase; }}
  .artpkg-review-panel p {{ margin:0; color:#c8d7e3; font-size:12px; line-height:1.35; }}
  .artpkg-review-panel a {{ display:inline-flex; width:max-content; border:1px solid #7dd3fc; border-radius:4px; padding:6px 8px; color:#e8f7ff; text-decoration:none; font-size:12px; font-weight:800; }}
</style>
<script id="artpkg-review-actions-data" type="application/json">{data}</script>
<script>
(function () {{
  var dataElement = document.getElementById('artpkg-review-actions-data');
  if (!dataElement) return;
  var data = JSON.parse(dataElement.textContent || '{{}}');
  var chip = document.getElementById('focus-chip');
  if (!chip) return;
  var panel = document.createElement('div');
  panel.className = 'artpkg-review-panel';
  panel.setAttribute('data-artpkg-review-panel', '');
  panel.hidden = true;
  chip.appendChild(panel);
  function hrefFor(action) {{
    var query = new URLSearchParams();
    if (data.session_dir) query.set('dir', data.session_dir);
    if (action.queue) query.set('queue', action.queue);
    if (action.focus) query.set('focus', action.focus);
    return '/?' + query.toString();
  }}
  function render(nodeId) {{
    var action = data.nodes && data.nodes[nodeId];
    panel.textContent = '';
    if (!action) {{ panel.hidden = true; return; }}
    panel.hidden = false;
    var eyebrow = document.createElement('span');
    eyebrow.className = 'artpkg-review-eyebrow';
    eyebrow.textContent = 'ArtPkg review';
    var summary = document.createElement('p');
    summary.textContent = action.summary || 'Open the related ArtPkg review item.';
    var impact = document.createElement('p');
    impact.textContent = action.impact || 'Review this before changing downstream readiness.';
    var link = document.createElement('a');
    var href = hrefFor(action);
    link.href = href;
    link.target = '_blank';
    link.rel = 'noopener';
    link.textContent = action.label || 'Open in ArtPkg';
    link.addEventListener('click', function (event) {{
      event.preventDefault();
      window.open(href, '_blank', 'noopener');
    }});
    panel.appendChild(eyebrow);
    panel.appendChild(summary);
    panel.appendChild(impact);
    panel.appendChild(link);
  }}
  document.addEventListener('click', function (event) {{
    var node = event.target.closest && event.target.closest('[data-node-id]');
    if (node) setTimeout(function () {{ render(node.getAttribute('data-node-id')); }}, 0);
  }}, true);
  document.addEventListener('keyup', function (event) {{
    if (event.key !== 'Enter' && event.key !== ' ') return;
    var node = event.target.closest && event.target.closest('[data-node-id]');
    if (node) setTimeout(function () {{ render(node.getAttribute('data-node-id')); }}, 0);
  }}, true);
  window.addEventListener('hashchange', function () {{
    var match = String(location.hash || '').match(/focus=([^&]+)/);
    if (match) render(decodeURIComponent(match[1]));
  }});
}}());
</script>
"""
    marker = "</body>"
    if marker in page:
        page = page.replace(marker, injection + "\n" + marker, 1)
    else:
        page += injection
    target.write_text(page, encoding="utf-8")


def archify_config_for_session(session: dict[str, Any]) -> artpkg_archify_runner.ArchifyConfig:
    return artpkg_archify_runner.ArchifyConfig(
        node_executable=os.environ.get("ARTPKG_NODE", "node"),
        archify_root=os.environ.get("ARTPKG_ARCHIFY_ROOT", "D:/archify/archify"),
        quality=os.environ.get("ARTPKG_ARCHIFY_QUALITY", "showcase"),
        receipt_dir=session["session_dir"],
    )


def build_projection_summary(session: dict[str, Any]) -> dict[str, Any]:
    result = artpkg_archify_projection.build_readiness_projection(session)
    config = archify_config_for_session(session)
    html_path = str(Path(result.ir_path).with_suffix(".html"))
    validate = artpkg_archify_runner.run_archify_validate(config, "architecture", result.ir_path)
    Path(html_path).unlink(missing_ok=True)
    deliver = artpkg_archify_runner.run_archify_deliver(config, "architecture", result.ir_path, html_path)
    if deliver.get("ok") is True and Path(html_path).exists():
        decorate_projection_html(html_path, result.mapping_path)
    visual = artpkg_archify_runner.run_archify_visual_check(config, html_path) if deliver.get("ok") is True and Path(html_path).exists() else {
        "ok": False,
        "operation": "visual-check",
        "receipt": {"ok": False, "error": "Archify deliver did not create fresh HTML"},
    }
    return {
        "ir_path": result.ir_path,
        "mapping_path": result.mapping_path,
        "validation_path": result.validation_path,
        "html_path": html_path,
        "archify": {
            "validate": validate,
            "deliver": deliver,
            "visual_check": visual,
        },
    }


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
                session = load_workspace_session(params.get("dir", [""])[0], self.workspace)
                self._json(200, session_summary(session))
            except Exception as exc:
                self._json(400, {"error": str(exc)})
            return
        if parsed.path == "/api/session/projection-html":
            try:
                params = parse_qs(parsed.query)
                status, headers, body = projection_html_response(params.get("dir", [""])[0], self.workspace)
                self.send_response(status)
                for name, value in headers.items():
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(body)
            except Exception as exc:
                self._json(404, {"error": str(exc)})
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
            session = load_workspace_session(payload["session_dir"], self.workspace)
            if parsed.path == "/api/session/confirm":
                artpkg_intake.confirm_answer(session, payload["question_id"], payload.get("reviewer", "UI reviewer"))
                self._json(200, session_summary(session))
                return
            if parsed.path == "/api/session/answer":
                artpkg_intake.provide_answer(
                    session,
                    payload["question_id"],
                    payload.get("value"),
                    payload.get("reviewer", "UI reviewer"),
                    payload.get("state", "PROVIDED"),
                )
                self._json(200, session_summary(session))
                return
            if parsed.path == "/api/session/reject":
                artpkg_intake.reject_seeded_answer(session, payload["question_id"], payload.get("reason", "Rejected in UI"), payload.get("reviewer", "UI reviewer"))
                self._json(200, session_summary(session))
                return
            if parsed.path == "/api/session/record/confirm":
                artpkg_intake.confirm_record(session, payload["record_id"], payload.get("reviewer", "UI reviewer"))
                self._json(200, session_summary(session))
                return
            if parsed.path == "/api/session/record/reject":
                artpkg_intake.reject_seeded_record(session, payload["record_id"], payload.get("reason", "Rejected in UI"), payload.get("reviewer", "UI reviewer"))
                self._json(200, session_summary(session))
                return
            if parsed.path == "/api/session/project":
                summary = session_summary(session)
                summary["projection"] = build_projection_summary(session)
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
