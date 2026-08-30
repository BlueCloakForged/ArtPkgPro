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
            "- This file is discovery context; it is not an approved implementation contract.\n"
            "## 14. Evidence and Validation\n"
            "- What is still unverified? Runtime behavior has not been validated.\n\n"
            "## 7. Requirements\n"
            "### Functional Requirements\n"
            "- FR-01: The intake UI shall let reviewers resolve seeded questionnaire gaps.\n\n"
            "## 19. Sensitive or Restricted Content\n"
            "- Does this project involve sensitive data, credentials, regulated information, or restricted content? Yes\n"
            "- If yes, what safeguards are required? Local-only handling and redaction.\n"
            "- Are any redaction or access controls needed? Yes, redact customer payloads.\n\n",
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
        self.assertEqual("seeded answer was rejected and needs replacement", next(
            item["reason"] for item in reloaded["review_queues"]["needs_answer"] if item["id"] == "PKG-001"
        ))

    def test_review_queues_separate_unknown_authority_and_evidence_items(self):
        session = intake.create_intake_session(
            self.pre,
            self.root,
            template_path=self.template,
            respondent="Reviewer",
        )
        queues = session["review_queues"]

        need_ids = {item["id"] for item in queues["needs_answer"]}
        authority_ids = {item["id"] for item in queues["authority_sensitive"]}
        evidence_ids = {item["id"] for item in queues["evidence_sensitive"]}

        self.assertIn("PKG-003", need_ids)
        self.assertIn("AUT-001", authority_ids)
        self.assertIn("SEC-001", authority_ids)
        self.assertIn("OVR-007", evidence_ids)

    def test_answer_queue_items_include_question_context_for_human_review(self):
        session = intake.create_intake_session(
            self.pre,
            self.root,
            template_path=self.template,
            respondent="Reviewer",
        )
        bnd_item = next(item for item in session["review_queues"]["needs_answer"] if item["id"] == "BND-001")

        self.assertEqual("Scope boundary", bnd_item["question"]["group"])
        self.assertEqual("Make the included and excluded work explicit before it is handed off.", bnd_item["question"]["group_description"])
        self.assertEqual("In scope", bnd_item["question"]["prompt"])
        self.assertEqual("LONG_TEXT", bnd_item["question"]["answer_type"])
        self.assertEqual(
            "Name the behavior, components, or decisions this package is allowed to discuss or change.",
            bnd_item["question"]["meaning"],
        )
        self.assertEqual("Order validation and its public API contract.", bnd_item["question"]["example"])
        self.assertEqual([], bnd_item["question"]["choices"])

    def test_answer_queue_items_include_project_agnostic_review_guidance(self):
        session = intake.create_intake_session(
            self.pre,
            self.root,
            template_path=self.template,
            respondent="Reviewer",
        )
        bnd_item = next(item for item in session["review_queues"]["needs_answer"] if item["id"] == "BND-001")

        self.assertEqual(
            "What work this artifact package is allowed to cover.",
            bnd_item["question"]["decision_prompt"],
        )
        self.assertIn("This package is in scope for:", bnd_item["question"]["answer_scaffold"])
        self.assertIn("It may make decisions about:", bnd_item["question"]["answer_scaffold"])
        self.assertIn("It does not authorize:", bnd_item["question"]["answer_scaffold"])
        self.assertIn("scope expansion", " ".join(bnd_item["question"]["downstream_effects"]))

    def test_question_guidance_scales_by_question_family(self):
        aut_context = intake._question_context("AUT-001")
        ac_context = intake._question_context("AC-SET")
        generic_context = intake._question_context("FUT-001")

        self.assertIn("who granted permission", aut_context["decision_prompt"])
        self.assertIn("Authority granted by:", aut_context["answer_scaffold"])
        self.assertIn("What must be true", ac_context["decision_prompt"])
        self.assertIn("Pass condition:", ac_context["answer_scaffold"])
        self.assertIn("What human-owned answer", generic_context["decision_prompt"])
        self.assertIn("Source basis:", generic_context["answer_scaffold"])

    def test_answer_queue_items_explain_unknown_source_attribution_and_confidence(self):
        session = intake.create_intake_session(
            self.pre,
            self.root,
            template_path=self.template,
            respondent="Reviewer",
        )
        bnd_item = next(item for item in session["review_queues"]["needs_answer"] if item["id"] == "BND-001")

        self.assertEqual("UNKNOWN", bnd_item["source_context"]["answer_status"])
        self.assertEqual("missing_in_source", bnd_item["source_context"]["source_status"])
        self.assertIn("No explicit in-scope statement", bnd_item["source_context"]["summary"])
        self.assertEqual("Classification confidence", bnd_item["confidence_context"]["label"])
        self.assertIn("missing or seeded", bnd_item["confidence_context"]["meaning"])

    def test_missing_answer_queue_items_recommend_human_provided_state(self):
        session = intake.create_intake_session(
            self.pre,
            self.root,
            template_path=self.template,
            respondent="Reviewer",
        )
        bnd_item = next(item for item in session["review_queues"]["needs_answer"] if item["id"] == "BND-001")

        recommendation = bnd_item["state_recommendation"]
        self.assertEqual("PROVIDED", recommendation["suggested_state"])
        self.assertEqual("write_human_answer", recommendation["action"])
        self.assertIn("scope-sensitive downstream decisions", recommendation["reason"])
        self.assertIn("Use TO_BE_INSPECTED", recommendation["fallback"])
        self.assertFalse(recommendation["can_auto_apply"])

    def test_seeded_authority_answers_recommend_human_confirmation(self):
        item = {
            "state": "PROVIDED",
            "value": "ArtPkg intake UI",
            "source_type": "SOURCE_ARTIFACT",
            "source_reference": "ArtPkg intake UI",
        }

        recommendation = intake._state_recommendation("AUT-002", item)

        self.assertEqual("PROVIDED", recommendation["suggested_state"])
        self.assertEqual("confirm_seeded_answer", recommendation["action"])
        self.assertIn("authority-sensitive", recommendation["reason"])
        self.assertIn("does not broaden authority", recommendation["checklist"])
        self.assertFalse(recommendation["can_auto_apply"])

    def test_record_queue_items_include_schema_context_for_human_review(self):
        session = intake.create_intake_session(
            self.pre,
            self.root,
            template_path=self.template,
            respondent="Reviewer",
        )
        record_id = next(iter(session["created_records"].values()))[0]
        record_item = next(item for item in session["review_queues"]["needs_confirmation"] if item["id"] == record_id)

        self.assertEqual("Functional Requirements", record_item["record_context"]["label"])
        self.assertEqual("Functional requirements", record_item["record_context"]["group"])
        self.assertEqual(
            "Record a human-owned behavior the project must provide.",
            record_item["record_context"]["group_description"],
        )
        fields = {field["name"]: field for field in record_item["record_schema"]}
        self.assertEqual("Requirement text", fields["requirement"]["label"])
        self.assertEqual("Provide the requirement text for this functional requirements record.", fields["requirement"]["meaning"])
        self.assertEqual(["ACCEPTED", "IMPLEMENTED", "PROPOSED", "VERIFIED"], fields["status"]["choices"])

    def test_confirm_and_reject_seeded_answers_are_durable(self):
        session = intake.create_intake_session(
            self.pre,
            self.root,
            template_path=self.template,
            respondent="Reviewer",
        )

        intake.confirm_answer(session, "PKG-001", reviewer="Reviewer")
        intake.reject_seeded_answer(session, "PKG-003", reason="Owner must be named by human", reviewer="Reviewer")

        reloaded = intake.load_intake_session(session["session_dir"])
        self.assertEqual("HUMAN_CONFIRMED", reloaded["document"]["answers"]["PKG-001"]["review_disposition"])
        self.assertEqual("HUMAN_REJECTED", reloaded["document"]["answers"]["PKG-003"]["review_disposition"])
        self.assertEqual("Owner must be named by human", reloaded["document"]["answers"]["PKG-003"]["rejection_reason"])

    def test_provide_answer_replaces_rejected_seed_with_human_declaration(self):
        session = intake.create_intake_session(
            self.pre,
            self.root,
            template_path=self.template,
            respondent="Reviewer",
        )

        intake.reject_seeded_answer(session, "PKG-003", reason="Owner must be named by human", reviewer="Reviewer")
        updated = intake.provide_answer(session, "PKG-003", "Vin", reviewer="Reviewer")
        reloaded = intake.load_intake_session(session["session_dir"])
        needs_answer_ids = {item["id"] for item in reloaded["review_queues"]["needs_answer"]}

        self.assertEqual("Vin", updated["value"])
        self.assertEqual("PROVIDED", updated["state"])
        self.assertEqual("HUMAN_DECLARATION", updated["source_type"])
        self.assertEqual("HUMAN_CONFIRMED", updated["review_disposition"])
        self.assertNotIn("PKG-003", needs_answer_ids)

    def test_confirm_and_reject_seeded_records_are_durable(self):
        session = intake.create_intake_session(
            self.pre,
            self.root,
            template_path=self.template,
            respondent="Reviewer",
        )
        record_id = next(iter(session["created_records"].values()))[0]

        confirmed = intake.confirm_record(session, record_id, reviewer="Reviewer")
        self.assertEqual("HUMAN_CONFIRMED", confirmed["review_disposition"])

        rejected = intake.reject_seeded_record(session, record_id, "Record needs replacement", reviewer="Reviewer")
        reloaded = intake.load_intake_session(session["session_dir"])
        needs_answer_ids = {item["id"] for item in reloaded["review_queues"]["needs_answer"]}

        self.assertEqual("HUMAN_REJECTED", rejected["review_disposition"])
        self.assertEqual("Record needs replacement", rejected["rejection_reason"])
        self.assertEqual("HUMAN_REJECTED", intake.questionnaire.find_record(reloaded["document"], record_id)["review_disposition"])
        self.assertIn(record_id, needs_answer_ids)

    def test_rejected_sensitive_answers_remain_in_specialist_queues(self):
        session = intake.create_intake_session(
            self.pre,
            self.root,
            template_path=self.template,
            respondent="Reviewer",
        )

        intake.reject_seeded_answer(session, "SEC-001", "Restricted-content answer needs review", "Reviewer")
        intake.reject_seeded_answer(session, "OVR-007", "Unverified claim needs review", "Reviewer")

        reloaded = intake.load_intake_session(session["session_dir"])
        authority_ids = {item["id"] for item in reloaded["review_queues"]["authority_sensitive"]}
        evidence_ids = {item["id"] for item in reloaded["review_queues"]["evidence_sensitive"]}

        self.assertIn("SEC-001", authority_ids)
        self.assertIn("OVR-007", evidence_ids)
