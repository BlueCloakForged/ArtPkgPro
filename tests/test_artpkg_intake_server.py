import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))

import artpkg_intake_server as server


class IntakeServerTests(unittest.TestCase):
    def test_parse_multipart_markdown_upload(self):
        boundary = "----artpkg"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="pre.md"\r\n'
            "Content-Type: text/markdown\r\n\r\n"
            "# Pre-Artifacts Package\r\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")

        upload = server.parse_multipart_upload(f"multipart/form-data; boundary={boundary}", body)
        self.assertEqual("pre.md", upload.filename)
        self.assertIn(b"Pre-Artifacts", upload.content)

    def test_session_summary_excludes_full_document_payload(self):
        session = {
            "session_id": "S",
            "session_dir": "D:/tmp/S",
            "source": {"sha256": "abc"},
            "validation": {"status": "DRAFT"},
            "review_queues": {"needs_answer": [{"id": "PKG-003"}]},
            "document": {"answers": {"PKG-001": {"value": "Example"}}},
        }
        summary = server.session_summary(session)
        self.assertNotIn("document", summary)
        self.assertEqual("S", summary["session_id"])
        self.assertEqual(1, summary["queue_counts"]["needs_answer"])

    def test_resolve_session_dir_accepts_workspace_intake_session(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "workspace"
            session_dir = workspace / ".artpkg" / "intake_sessions" / "session-1"
            session_dir.mkdir(parents=True)

            resolved = server.resolve_session_dir(str(session_dir), workspace)

            self.assertEqual(session_dir.resolve(), resolved)

    def test_resolve_session_dir_rejects_path_outside_workspace_intake_sessions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "workspace"
            outside_session = Path(temp_dir) / "outside" / "session-1"
            outside_session.mkdir(parents=True)

            with self.assertRaisesRegex(ValueError, "outside the configured intake sessions directory"):
                server.resolve_session_dir(str(outside_session), workspace)

    def test_load_workspace_session_normalizes_malicious_session_dir_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "workspace"
            session_dir = workspace / ".artpkg" / "intake_sessions" / "session-1"
            malicious_session_dir = Path(temp_dir) / "outside" / "session-1"
            session_dir.mkdir(parents=True)
            questionnaire = server.artpkg_intake.questionnaire
            answers = {
                "schema_version": questionnaire.SCHEMA_VERSION,
                "answers": {},
                "records": {section: [] for section in questionnaire.ID_PREFIXES},
            }
            (session_dir / "answers.json").write_text(json.dumps(answers), encoding="utf-8")
            (session_dir / "seed.json").write_text(json.dumps({"answers": {}}), encoding="utf-8")
            (session_dir / "session.json").write_text(
                json.dumps({"session_id": "S", "session_dir": str(malicious_session_dir)}),
                encoding="utf-8",
            )

            session = server.load_workspace_session(str(session_dir), workspace)

            self.assertEqual(str(session_dir.resolve()), session["session_dir"])

    def test_build_projection_summary_runs_archify_receipts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ir_path = Path(temp_dir) / "artpkg-readiness.architecture.json"
            ir_path.write_text("{}", encoding="utf-8")
            projection = SimpleNamespace(
                ir_path=str(ir_path),
                mapping_path=str(Path(temp_dir) / "artpkg-readiness.mapping.json"),
                validation_path=str(Path(temp_dir) / "artpkg-readiness.projection-validation.json"),
            )
            def deliver_receipt(_config, _kind, _ir, html):
                Path(html).write_text("<html></html>", encoding="utf-8")
                return {"ok": True, "receipt_path": "deliver.json"}

            with patch("artpkg_intake_server.artpkg_archify_projection.build_readiness_projection", return_value=projection), \
                    patch("artpkg_intake_server.artpkg_archify_runner.run_archify_validate", return_value={"ok": True, "receipt_path": "validate.json"}) as validate, \
                    patch("artpkg_intake_server.artpkg_archify_runner.run_archify_deliver", side_effect=deliver_receipt) as deliver, \
                    patch("artpkg_intake_server.artpkg_archify_runner.run_archify_visual_check", return_value={"ok": True, "receipt_path": "visual.json"}) as visual:
                summary = server.build_projection_summary({"session_dir": temp_dir})

        self.assertEqual(str(ir_path), summary["ir_path"])
        self.assertEqual(str(ir_path.with_suffix(".html")), summary["html_path"])
        self.assertEqual("validate.json", summary["archify"]["validate"]["receipt_path"])
        self.assertEqual("deliver.json", summary["archify"]["deliver"]["receipt_path"])
        self.assertEqual("visual.json", summary["archify"]["visual_check"]["receipt_path"])
        validate.assert_called_once()
        deliver.assert_called_once()
        visual.assert_called_once()

    def test_build_projection_summary_does_not_visual_check_stale_html_after_failed_deliver(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ir_path = Path(temp_dir) / "artpkg-readiness.architecture.json"
            ir_path.write_text("{}", encoding="utf-8")
            stale_html = ir_path.with_suffix(".html")
            stale_html.write_text("<html>stale</html>", encoding="utf-8")
            projection = SimpleNamespace(
                ir_path=str(ir_path),
                mapping_path=str(Path(temp_dir) / "artpkg-readiness.mapping.json"),
                validation_path=str(Path(temp_dir) / "artpkg-readiness.projection-validation.json"),
            )
            with patch("artpkg_intake_server.artpkg_archify_projection.build_readiness_projection", return_value=projection), \
                    patch("artpkg_intake_server.artpkg_archify_runner.run_archify_validate", return_value={"ok": True}), \
                    patch("artpkg_intake_server.artpkg_archify_runner.run_archify_deliver", return_value={"ok": False, "receipt": {"error": "failed"}}), \
                    patch("artpkg_intake_server.artpkg_archify_runner.run_archify_visual_check") as visual:
                summary = server.build_projection_summary({"session_dir": temp_dir})

        self.assertFalse(Path(summary["html_path"]).exists())
        self.assertFalse(summary["archify"]["visual_check"]["ok"])
        self.assertEqual("Archify deliver did not create fresh HTML", summary["archify"]["visual_check"]["receipt"]["error"])
        visual.assert_not_called()

    def test_projection_html_response_serves_session_visualization_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "workspace"
            session_dir = workspace / ".artpkg" / "intake_sessions" / "session-1"
            session_dir.mkdir(parents=True)
            html_path = session_dir / "artpkg-readiness.architecture.html"
            html_path.write_text("<html><body>readiness</body></html>", encoding="utf-8")

            status, headers, body = server.projection_html_response(str(session_dir), workspace)

            self.assertEqual(200, status)
            self.assertEqual("text/html; charset=utf-8", headers["Content-Type"])
            self.assertIn(b"readiness", body)

    def test_projection_html_response_rejects_missing_visualization(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "workspace"
            session_dir = workspace / ".artpkg" / "intake_sessions" / "session-1"
            session_dir.mkdir(parents=True)

            with self.assertRaisesRegex(FileNotFoundError, "projection HTML has not been generated"):
                server.projection_html_response(str(session_dir), workspace)

    def test_ui_contains_upload_review_and_projection_controls(self):
        html_path = Path(__file__).parents[1] / "tools" / "artpkg_intake_ui.html"
        html = html_path.read_text(encoding="utf-8")
        self.assertIn('id="preArtifactsFile"', html)
        self.assertIn('id="restrictedAck"', html)
        self.assertIn('id="reviewQueues"', html)
        self.assertIn('dataset.action = "confirm"', html)
        self.assertIn('dataset.action = "reject"', html)
        self.assertIn('dataset.action = "answer"', html)
        self.assertIn('id="buildProjection"', html)
        self.assertIn("renderQuestionContext", html)
        self.assertIn("renderRecordContext", html)
        self.assertIn("Open visualization", html)
        self.assertIn("/api/session/projection-html", html)

    def test_ui_supports_answer_and_record_actions(self):
        html_path = Path(__file__).parents[1] / "tools" / "artpkg_intake_ui.html"
        html = html_path.read_text(encoding="utf-8")
        self.assertIn("/api/session/answer", html)
        self.assertIn('/api/session/record/${action}', html)
        self.assertNotIn("Record review is not yet answer-actionable in this slice.", html)
