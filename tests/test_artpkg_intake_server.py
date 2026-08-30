import json
import tempfile
import unittest
from pathlib import Path

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
