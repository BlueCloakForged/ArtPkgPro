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
