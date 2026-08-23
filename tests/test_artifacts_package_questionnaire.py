import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import artifacts_package_questionnaire as q


class QuestionnaireTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.template = self.root / "reusable_artifacts_package_template.md"
        self.template.write_text("# Package\n\nProject: `<name>`\nStatus: `<DRAFT / READY_FOR_REVIEW / ACCEPTED / SUPERSEDED / BLOCKED>`\n", encoding="utf-8")
        self.document = q.new_answers(str(self.template), str(self.root), "Tester")

    def tearDown(self):
        self.temp.cleanup()

    def test_stable_ids_survive_delete_and_resume(self):
        first = q.add_record(self.document, "actors", {"name": "One"})
        second = q.add_record(self.document, "actors", {"name": "Two"})
        q.edit_record(self.document, first, {"name": "Changed"})
        q.delete_record(self.document, first)
        path = self.root / "answers.json"
        q.save_answers(self.document, str(path))
        loaded = q.load_answers(str(path))
        self.assertEqual("ACT-003", q.add_record(loaded, "actors", {"name": "Three"}))
        self.assertIn(second, {record["id"] for record in loaded["records"]["actors"]})
        self.assertIn(first, loaded["deleted_ids"])

    def test_unknown_is_not_none(self):
        q.set_answer(self.document, "PKG-006", None, "UNKNOWN")
        q.set_answer(self.document, "AUT-007", "NONE")
        self.assertEqual("UNKNOWN", self.document["answers"]["PKG-006"]["state"])
        self.assertEqual("NONE", self.document["answers"]["AUT-007"]["value"])

    def test_unsupported_authority_and_attestation_block(self):
        q.set_answer(self.document, "AUT-001", "IMPLEMENTATION_WITHIN_EXACT_SCOPE")
        result = q.validate_answers(self.document)
        self.assertEqual("BLOCKED", result["status"])
        self.assertIn("AUT-002", result["blocking_ids"])
        self.assertIn("FIN-003", result["blocking_ids"])
        self.assertEqual("HUMAN_REVIEW_ONLY", result["next_permitted_action"])

    def test_claims_need_evidence_and_conflicts_block(self):
        requirement = q.add_record(self.document, "functional_requirements", {"status": "VERIFIED", "requirement": "x"})
        criterion = q.add_record(self.document, "acceptance_criteria", {"status": "PASSED", "requirement_ids": [requirement], "evidence_ids": ["EVD-404"]})
        conflict = q.add_record(self.document, "conflicts", {"status": "OPEN", "conflict": "x"})
        result = q.validate_answers(self.document)
        self.assertIn(requirement, result["blocking_ids"])
        self.assertIn(criterion, result["blocking_ids"])
        self.assertIn(conflict, result["blocking_ids"])

    def test_inspection_provenance_does_not_grant_authority(self):
        q.set_answer(self.document, "AUT-001", "NONE", source_type="REPOSITORY_OBSERVATION")
        q.set_answer(self.document, "PKG-001", "Observed", source_type="REPOSITORY_OBSERVATION")
        result = q.validate_answers(self.document)
        self.assertNotIn("ACCEPTED", result["status"])

    def test_commands_are_disabled_and_destructive_is_rejected(self):
        self.assertEqual("NOT_RUN", q.run_validated_command("python -c pass", str(self.root))["result"])
        self.assertEqual("REJECTED", q.run_validated_command("rm -rf x", str(self.root), True)["result"])

    def test_restricted_fields_redact_with_reason_code(self):
        rendered = q.redact_fields({"payload": "secret", "purpose": "safe"}, True)
        self.assertEqual("[REDACTED:RESTRICTED_CONTENT]", rendered["payload"])
        self.assertEqual("safe", rendered["purpose"])

    def test_generation_is_deterministic_and_requires_overwrite(self):
        q.set_answer(self.document, "PKG-001", "Demo")
        q.set_answer(self.document, "FIN-001", "YES"); q.set_answer(self.document, "FIN-002", "YES"); q.set_answer(self.document, "FIN-003", "YES")
        paths = q.generate(self.document)
        first = (self.root / "artifacts_package.md").read_text(encoding="utf-8")
        with self.assertRaises(FileExistsError): q.generate(self.document)
        q.generate(self.document, overwrite=True)
        self.assertEqual(first, (self.root / "artifacts_package.md").read_text(encoding="utf-8"))
        self.assertTrue((self.root / "artifacts_package_validation.md").exists())
        self.assertEqual(3, len(paths))

    def test_standard_multi_file_generation(self):
        self.document["setup"]["shape"] = "STANDARD_MULTI_FILE"
        paths = q.generate(self.document)
        self.assertEqual(8, len(paths))
        self.assertTrue((self.root / "00-overview-and-current-state.md").exists())
        self.assertTrue((self.root / "05-artifact-index-and-evidence-ledger.md").exists())

    def test_corrupt_answers_are_rejected(self):
        path = self.root / "bad.json"; path.write_text("{bad", encoding="utf-8")
        with self.assertRaises(ValueError): q.load_answers(str(path))

    def test_incompatible_schema_and_record_id_are_rejected(self):
        path = self.root / "incompatible.json"
        q.save_answers(self.document, str(path))
        payload = json.loads(path.read_text(encoding="utf-8")); payload["schema_version"] = "9.9"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(ValueError): q.load_answers(str(path))
        self.document["schema_version"] = "0.1"
        self.document["records"]["actors"].append({"id": "bad", "fields": {}})
        with self.assertRaises(ValueError): q.save_answers(self.document, str(self.root / "bad-id.json"))

    def test_atomic_save_leaves_a_valid_document(self):
        path = self.root / "atomic.json"
        q.save_answers(self.document, str(path))
        self.assertEqual(q.SCHEMA_VERSION, q.load_answers(str(path))["schema_version"])

    def test_invalid_cross_reference_is_reported(self):
        record_id = q.add_record(self.document, "phases", {"status": "PROPOSED", "requirement_ids": ["FR-999"]})
        result = q.validate_answers(self.document)
        self.assertIn(record_id, result["blocking_ids"])
        self.assertTrue(any("FR-999" in error for error in result["errors"]))

    def test_gate_report_has_explanations_and_ids(self):
        q.set_answer(self.document, "OVR-001", "problem")
        q.set_answer(self.document, "BND-001", "inside")
        q.set_answer(self.document, "BND-002", "outside")
        q.set_answer(self.document, "OUT-001", "good")
        q.set_answer(self.document, "OUT-002", "bad")
        result = q.validate_answers(self.document)
        self.assertEqual({"A", "B", "C", "D"}, set(result["gates"]))
        self.assertTrue(all("human_decision_or_evidence" in gate for gate in result["gates"].values()))

    def test_none_action_remains_human_review_only(self):
        q.set_answer(self.document, "AUT-001", "NONE")
        result = q.validate_answers(self.document)
        self.assertEqual("HUMAN_REVIEW_ONLY", result["next_permitted_action"])

    def test_final_attestation_failure_blocks_ready_status(self):
        q.set_answer(self.document, "FIN-001", "YES")
        q.set_answer(self.document, "FIN-002", "NO")
        q.set_answer(self.document, "FIN-003", "YES")
        result = q.validate_answers(self.document)
        self.assertEqual("BLOCKED", result["status"])
        self.assertIn("FIN-002", result["blocking_ids"])

    def test_source_provenance_is_retained(self):
        q.set_answer(self.document, "PKG-006", "snap", source_type="REPOSITORY_OBSERVATION", source_reference="snapshot")
        item = self.document["answers"]["PKG-006"]
        self.assertEqual("REPOSITORY_OBSERVATION", item["source_type"])
        self.assertEqual("snapshot", item["source_reference"])

    def test_unknown_answers_create_a_warning(self):
        q.set_answer(self.document, "PKG-006", None, "UNKNOWN")
        self.assertTrue(q.validate_answers(self.document)["warnings"])

    def test_catalog_contains_repeated_and_conditional_questions(self):
        for question_id in ("ACT-SET", "FR-SET", "EVD-SET", "XFR-SET", "VAL-004", "AUT-007-SCOPE"):
            self.assertIn(question_id, q.QUESTION_CATALOG)

    def test_field_by_field_record_done_and_cancel(self):
        values = iter(["add", "Ada", "OWNER", "maintains package", "scope", "done"])
        ids = q.collect_repeated(self.document, "actors", input_fn=lambda _prompt: next(values), output_fn=lambda _text: None)
        self.assertEqual(["ACT-001"], ids)
        cancelled = iter(["cancel"])
        self.assertEqual([], q.collect_repeated(self.document, "actors", input_fn=lambda _prompt: next(cancelled), output_fn=lambda _text: None))

    def test_record_field_back_and_edit_are_supported(self):
        values = iter(["add", "Ada", "OWNER", "maintains package", "edit name", "Ada Lovelace", "OWNER", "maintains package", "scope", "done"])
        ids = q.collect_repeated(self.document, "actors", input_fn=lambda _prompt: next(values), output_fn=lambda _text: None)
        self.assertEqual(["ACT-001"], ids)
        self.assertEqual("Ada Lovelace", self.document["records"]["actors"][0]["fields"]["name"])

    def test_conditional_harness_answers_are_not_applicable_when_disabled(self):
        self.assertEqual("NOT_APPLICABLE", self.document["answers"]["HAR-001"]["state"])
        self.assertEqual("DERIVED_BY_SCRIPT", self.document["answers"]["HAR-001"]["source_type"])
        q.set_harness_mode(self.document, True)
        q.set_answer(self.document, "HAR-001", "INTAKE")
        self.assertEqual("INTAKE", self.document["answers"]["HAR-001"]["value"])
        q.set_harness_mode(self.document, False)
        self.assertEqual("NOT_APPLICABLE", self.document["answers"]["HAR-001"]["state"])
        self.assertTrue(self.document["answer_history"])

    def test_interactive_harness_controller_activates_followups(self):
        q.set_harness_mode(self.document, True)
        self.assertEqual("YES", self.document["answers"]["HAR-000"]["value"])
        self.assertNotIn("HAR-001", self.document["answers"])

    def test_v01_migrates_without_losing_records(self):
        legacy = q.new_answers(str(self.template), str(self.root))
        actor_id = q.add_record(legacy, "actors", {"name": "Legacy"})
        legacy["schema_version"] = "0.1"
        for key in ("package_id", "parent_package_id", "answer_history", "repository_observations", "harness"):
            legacy.pop(key, None)
        legacy["setup"].pop("harness_enabled", None)
        path = self.root / "legacy.json"; path.write_text(json.dumps(legacy), encoding="utf-8")
        migrated = q.load_answers(str(path))
        self.assertEqual("0.2", migrated["schema_version"])
        self.assertEqual(actor_id, migrated["records"]["actors"][0]["id"])

    def test_read_only_inspection_is_disabled_and_captures_git_metadata(self):
        with self.assertRaises(PermissionError): q.inspect_repository(self.document, str(self.root))
        git_env = dict(os.environ, HOME=str(self.root), GIT_CONFIG_NOSYSTEM="1")
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True, env=git_env)
        self.document["setup"]["inspection"] = "READ_ONLY_INSPECTION"
        result = q.inspect_repository(self.document, str(self.root))
        self.assertTrue(result["observations"])
        self.assertTrue(all(item["source_type"] == "REPOSITORY_OBSERVATION" for item in result["observations"]))
        self.assertIn("status_short", {item["field"] for item in result["observations"]})

    def test_harness_reconciliation_and_snapshot_blockers(self):
        q.set_harness_mode(self.document, True)
        q.set_answer(self.document, "HAR-008", {"result": "FAIL", "discrepancy": 2})
        q.mark_snapshot_drift(self.document)
        result = q.validate_answers(self.document)
        self.assertIn("HAR-008", result["blocking_ids"])
        self.assertIn("HAR-021", result["blocking_ids"])

    def test_harness_partial_discovery_requires_fallback(self):
        q.set_harness_mode(self.document, True)
        q.set_answer(self.document, "HAR-011", "PARTIAL")
        result = q.validate_answers(self.document)
        self.assertIn("HAR-013", result["blocking_ids"])
        q.set_answer(self.document, "HAR-013", "HUMAN_REVIEW_ONLY")
        self.assertNotIn("HAR-013", q.validate_answers(self.document)["blocking_ids"])

    def test_harness_output_contains_all_state_fields(self):
        q.set_harness_mode(self.document, True)
        q.generate(self.document)
        text = (self.root / "artifacts_package.md").read_text(encoding="utf-8")
        for field in q.HARNESS_STATE_FIELDS:
            self.assertIn(field.replace("_", " ").title(), text)
        self.document["setup"]["shape"] = "STANDARD_MULTI_FILE"
        q.generate(self.document, overwrite=True)
        self.assertTrue((self.root / "06-sdlc-harness-pipeline.md").exists())

    def test_harness_discovery_defaults_are_safe(self):
        q.set_harness_mode(self.document, True)
        q.set_answer(self.document, "HAR-001", "DISCOVERY")
        q.set_answer(self.document, "HAR-011", "EMPTY")
        q.set_answer(self.document, "HAR-013", "HUMAN_REVIEW_ONLY")
        q.validate_answers(self.document)
        self.assertEqual("NONE", self.document["harness"]["state"]["active_bec"])
        self.assertEqual("NONE", self.document["harness"]["state"]["implementation_authorization"])
        self.assertEqual("NONE", self.document["harness"]["state"]["execution_authorization"])
        self.assertEqual("NOT_EVALUATED", self.document["harness"]["state"]["checkpoint_acceptance"])
        self.assertEqual("HUMAN_REVIEW_ONLY", self.document["harness"]["state"]["next_permitted_action"])

    def test_gortex_and_unallowlisted_commands_are_rejected(self):
        self.assertEqual("LIVE_GORTEX_PROHIBITED", q.run_validated_command("gortex inspect", str(self.root), True)["reason_code"])
        self.assertEqual("COMMAND_NOT_ALLOWLISTED", q.run_validated_command("python -V", str(self.root), True)["reason_code"])

    def test_coverage_matrix_is_complete_without_fallbacks(self):
        matrix = q.coverage_matrix()
        self.assertEqual(set(q.RECORD_FIELDS), {row["specification_record"] for row in matrix})
        self.assertTrue(all(row["required_fields"] and row["required_fields"] == row["interactive_fields"] == row["schema_fields"] == row["rendered_fields"] and row["tests"] for row in matrix))

    def test_harness_transition_jump_is_blocked(self):
        q.set_harness_mode(self.document, True)
        q.set_harness_transition(self.document, "implementation_authorization", "AUTHORIZED", evidence="EVD-1", authorizer="A", source="S", scope="P", phase="PH-1", expiry_or_checkpoint="C", stop_condition="STOP")
        result = q.validate_answers(self.document)
        self.assertIn("implementation_authorization", result["blocking_ids"])

    def test_harness_transitions_require_separate_authority(self):
        q.set_harness_mode(self.document, True)
        support = {"evidence": "EVD-1", "authorizer": "A", "source": "S", "scope": "P", "phase": "PH-1", "expiry_or_checkpoint": "C", "stop_condition": "STOP"}
        q.set_harness_transition(self.document, "bec_candidate", "PROPOSED")
        q.set_harness_transition(self.document, "bec_drafting_authorization", "AUTHORIZED", **support)
        q.set_harness_transition(self.document, "bec_drafted", "DRAFTED", evidence="EVD-1", source="S")
        q.set_harness_transition(self.document, "bec_acceptance", "ACCEPTED", **support)
        q.set_harness_transition(self.document, "bec_activation", "ACTIVE", **support)
        q.set_harness_transition(self.document, "implementation_authorization", "AUTHORIZED", **support)
        q.set_harness_transition(self.document, "execution_authorization", "AUTHORIZED", **support)
        q.set_harness_transition(self.document, "verification_status", "VERIFIED", evidence="EVD-1", source="S")
        q.set_harness_transition(self.document, "checkpoint_acceptance", "ACCEPTED", evidence="EVD-1", authorizer="A", source="S")
        q.set_harness_transition(self.document, "next_phase_authorization", "AUTHORIZED", separate_authorizer="B", evidence="EVD-2", authorizer="B", source="S", scope="NEXT", phase="PH-2", expiry_or_checkpoint="C", stop_condition="STOP")
        result = q.validate_answers(self.document)
        self.assertNotIn("implementation_authorization", result["blocking_ids"])
        self.assertNotIn("next_phase_authorization", result["blocking_ids"])

    def test_markdown_escapes_and_template_is_used(self):
        q.set_answer(self.document, "PKG-001", "A | <b>")
        text = q.render_package(self.document, str(self.template), q.validate_answers(self.document))
        self.assertIn("A \\| &lt;b&gt;", text)
        self.assertIn("# Package", text)


if __name__ == "__main__":
    unittest.main()