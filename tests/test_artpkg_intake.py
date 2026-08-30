import json
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))

import artpkg_intake as intake


class IntakeSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.template = self.root / "reusable_artifacts_package_template.md"
        self.template.write_text("# Package\n", encoding="utf-8")
        self.pre = self.root / "pre.md"
        self.pre.write_text(
            "# Pre-Artifacts Package\n\n"
            "## 1. Project Summary\n"
            "- Project name: Example Intake\n"
            "- Primary goal: Produce a reviewable package.\n\n"
            "## 16. Authority and Decision Boundaries\n"
            "- This file is discovery context; it is not an approved implementation contract.\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_create_intake_session_persists_seed_and_answers(self):
        session = intake.create_intake_session(
            self.pre,
            self.root,
            template_path=self.template,
            respondent="Reviewer",
        )

        session_dir = Path(session["session_dir"])
        self.assertTrue((session_dir / "source_pre_artifacts.md").exists())
        self.assertTrue((session_dir / "seed.json").exists())
        self.assertTrue((session_dir / "answers.json").exists())
        self.assertEqual(intake.sha256_file(self.pre), session["source"]["sha256"])
        self.assertEqual("Example Intake", session["document"]["answers"]["PKG-001"]["value"])
        self.assertEqual("SOURCE_ARTIFACT", session["document"]["answers"]["PKG-001"]["source_type"])

    def test_gitignore_excludes_local_artpkg_sessions(self):
        gitignore = (Path(__file__).parents[1] / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".artpkg/", gitignore)

    def test_rejected_seeded_answer_persists_and_needs_replacement(self):
        session = intake.create_intake_session(
            self.pre,
            self.root,
            template_path=self.template,
            respondent="Reviewer",
        )

        rejected = intake.reject_seeded_answer(session, "PKG-001", "Project name needs correction", "Reviewer")
        reloaded = intake.load_intake_session(session["session_dir"])
        queued_ids = {item["id"] for item in reloaded["review_queues"]["needs_answer"]}

        self.assertEqual("Example Intake", rejected["value"])
        self.assertEqual("HUMAN_REJECTED", reloaded["document"]["answers"]["PKG-001"]["review_disposition"])
        self.assertEqual("Example Intake", reloaded["document"]["answers"]["PKG-001"]["value"])
        self.assertIn("PKG-001", queued_ids)
