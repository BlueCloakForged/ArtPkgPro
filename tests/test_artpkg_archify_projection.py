import json
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))

import artpkg_archify_projection as projection
import artpkg_intake as intake


class ArchifyProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.template = self.root / "reusable_artifacts_package_template.md"
        self.template.write_text("# Package\n", encoding="utf-8")
        self.pre = self.root / "pre.md"
        self.pre.write_text(
            "# Pre-Artifacts Package\n\n"
            "## 1. Project Summary\n"
            "- Project name: Example Projection\n"
            "- Primary goal: Produce a reviewable package.\n\n"
            "## 14. Evidence and Validation\n"
            "- Existing evidence: Source discussion only.\n"
            "- What is still unverified? Runtime behavior has not been validated.\n\n"
            "## 16. Authority and Decision Boundaries\n"
            "- This file is discovery context; it is not an approved implementation contract.\n",
            encoding="utf-8",
        )
        self.session = intake.create_intake_session(self.pre, self.root, template_path=self.template, respondent="Reviewer")

    def tearDown(self):
        self.temp.cleanup()

    def test_build_readiness_projection_writes_archify_ir_and_mapping(self):
        result = projection.build_readiness_projection(self.session)

        self.assertTrue(Path(result.ir_path).exists())
        self.assertTrue(Path(result.mapping_path).exists())
        self.assertTrue(Path(result.validation_path).exists())
        self.assertEqual("architecture", result.ir["diagram_type"])
        self.assertEqual("ARTPKG_ARCHIFY_MAPPING_SIDECAR", result.mapping["artifact_type"])

        component_ids = {component["id"] for component in result.ir["components"]}
        mapped_node_ids = {node["archify_id"] for node in result.mapping["nodes"]}
        self.assertLessEqual(len(component_ids), 12)
        self.assertEqual(component_ids, mapped_node_ids)
        self.assertIn("authorityState", component_ids)
        self.assertIn("reviewQueues", component_ids)

    def test_projection_rejects_unmapped_node(self):
        result = projection.build_readiness_projection(self.session)
        result.mapping["nodes"] = [node for node in result.mapping["nodes"] if node["archify_id"] != "authorityState"]

        checked = projection.validate_projection_mapping(result.ir, result.mapping, self.session["validation"])
        self.assertEqual("BLOCKED", checked["status"])
        self.assertIn("UNMAPPED_NODE", {issue["code"] for issue in checked["issues"]})

    def test_projection_rejects_authority_elevation(self):
        result = projection.build_readiness_projection(self.session)
        for node in result.mapping["nodes"]:
            if node["archify_id"] == "authorityState":
                node["authority_state"] = "IMPLEMENTATION_AUTHORIZED"

        checked = projection.validate_projection_mapping(result.ir, result.mapping, self.session["validation"])
        self.assertEqual("BLOCKED", checked["status"])
        self.assertIn("AUTHORITY_ELEVATION", {issue["code"] for issue in checked["issues"]})

    def test_projection_rejects_missing_digest(self):
        result = projection.build_readiness_projection(self.session)
        result.mapping["inputs"][0]["sha256"] = None
        for node in result.mapping["nodes"]:
            node["source_artifact_sha256"] = None

        checked = projection.validate_projection_mapping(result.ir, result.mapping, self.session["validation"])
        self.assertEqual("BLOCKED", checked["status"])
        self.assertIn("SOURCE_DIGEST_MISSING", {issue["code"] for issue in checked["issues"]})

    def test_projection_rejects_empty_and_unknown_record_mapping(self):
        result = projection.build_readiness_projection(self.session)
        for node in result.mapping["nodes"]:
            if node["archify_id"] == "authorityState":
                node["artpkg_records"] = []
            if node["archify_id"] == "preArtifacts":
                node["artpkg_records"] = ["PKG-999"]

        checked = projection.validate_projection_mapping(result.ir, result.mapping, self.session["validation"])
        self.assertEqual("BLOCKED", checked["status"])
        self.assertIn("EMPTY_RECORD_MAPPING", {issue["code"] for issue in checked["issues"]})
        self.assertIn("UNKNOWN_RECORD_MAPPING", {issue["code"] for issue in checked["issues"]})

    def test_projection_requires_explicit_aggregation_metadata(self):
        result = projection.build_readiness_projection(self.session)
        for node in result.mapping["nodes"]:
            if node["archify_id"] == "acceptanceCriteria":
                self.assertEqual("aggregation", node["mapping_type"])
                self.assertEqual("AC-SET", node["aggregation"]["record_set"])
                self.assertIn("acceptance_criteria", node["aggregation"]["sections"])
                del node["aggregation"]

        checked = projection.validate_projection_mapping(result.ir, result.mapping, self.session["validation"])
        self.assertEqual("BLOCKED", checked["status"])
        self.assertIn("AGGREGATION_METADATA_MISSING", {issue["code"] for issue in checked["issues"]})

    def test_projection_rejects_invalid_edge_rule(self):
        result = projection.build_readiness_projection(self.session)
        result.mapping["edges"][0]["rule"] = "LLM-INFERRED-LINK"
        result.mapping["edges"][0]["relation_type"] = "arbitrary"

        checked = projection.validate_projection_mapping(result.ir, result.mapping, self.session["validation"])
        self.assertEqual("BLOCKED", checked["status"])
        self.assertIn("INVALID_EDGE_RULE", {issue["code"] for issue in checked["issues"]})

    def test_build_recomputes_stale_validation(self):
        self.session["validation"] = {"status": "PASS", "gates": {"X": {"result": "PASS"}}, "next_permitted_action": "IMPLEMENT"}

        result = projection.build_readiness_projection(self.session)

        self.assertEqual("BLOCKED", result.projection_validation["artpkg_validation_status"])
        self.assertEqual("BLOCKED", self.session["validation"]["status"])
        self.assertEqual("HUMAN_REVIEW_ONLY", self.session["validation"]["next_permitted_action"])
        self.assertNotIn("X:PASS", result.ir["components"][6]["sublabel"])

    def test_projection_rejects_evidence_elevation(self):
        result = projection.build_readiness_projection(self.session)
        for node in result.mapping["nodes"]:
            if node["archify_id"] == "evidenceState":
                node["source_answers"]["VAL-002"]["state"] = "VERIFIED"
                node["source_answers"]["VAL-002"]["value"] = "Runtime proof exists"
        for component in result.ir["components"]:
            if component["id"] == "evidenceState":
                component["tag"] = "VERIFIED"

        checked = projection.validate_projection_mapping(result.ir, result.mapping, self.session["validation"])
        self.assertEqual("BLOCKED", checked["status"])
        self.assertIn("EVIDENCE_ELEVATION", {issue["code"] for issue in checked["issues"]})

    def test_mapping_preserves_distinct_source_sentinel_states(self):
        intake.questionnaire.set_answer(self.session["document"], "AUT-001", "NONE", state="PROVIDED", source_type="SOURCE_ARTIFACT")
        intake.questionnaire.set_answer(self.session["document"], "AUT-008", "NOT_APPLICABLE", state="NOT_APPLICABLE", source_type="DERIVED_BY_SCRIPT")
        intake.questionnaire.set_answer(self.session["document"], "VAL-001", "TO_BE_INSPECTED", state="TO_BE_INSPECTED", source_type="SOURCE_ARTIFACT")
        intake.questionnaire.set_answer(self.session["document"], "VAL-002", "DEFERRED", state="DEFERRED", source_type="SOURCE_ARTIFACT")
        intake.questionnaire.save_answers(self.session["document"], self.session["answers_path"])

        result = projection.build_readiness_projection(self.session)
        source_answers = {node["archify_id"]: node["source_answers"] for node in result.mapping["nodes"]}

        self.assertEqual({"value": "NONE", "state": "PROVIDED"}, {key: source_answers["authorityState"]["AUT-001"][key] for key in ("value", "state")})
        self.assertEqual({"value": "NOT_APPLICABLE", "state": "NOT_APPLICABLE"}, {key: source_answers["authorityState"]["AUT-008"][key] for key in ("value", "state")})
        self.assertEqual({"value": "TO_BE_INSPECTED", "state": "TO_BE_INSPECTED"}, {key: source_answers["evidenceState"]["VAL-001"][key] for key in ("value", "state")})
        self.assertEqual({"value": "DEFERRED", "state": "DEFERRED"}, {key: source_answers["evidenceState"]["VAL-002"][key] for key in ("value", "state")})

    def test_projection_rejects_malformed_digest(self):
        result = projection.build_readiness_projection(self.session)
        result.mapping["inputs"][0]["sha256"] = "not-a-sha256"
        for node in result.mapping["nodes"]:
            node["source_artifact_sha256"] = "not-a-sha256"

        checked = projection.validate_projection_mapping(result.ir, result.mapping, self.session["validation"])
        self.assertEqual("BLOCKED", checked["status"])
        self.assertIn("SOURCE_DIGEST_MALFORMED", {issue["code"] for issue in checked["issues"]})

    def test_projection_rejects_self_consistent_authority_tampering(self):
        result = projection.build_readiness_projection(self.session)
        for node in result.mapping["nodes"]:
            if node["archify_id"] == "authorityState":
                node["authority_state"] = "IMPLEMENTATION_WITHIN_EXACT_SCOPE"
                node["source_answers"]["AUT-001"]["value"] = "IMPLEMENTATION_WITHIN_EXACT_SCOPE"

        checked = projection.validate_projection_mapping(result.ir, result.mapping, self.session["validation"])
        self.assertEqual("BLOCKED", checked["status"])
        self.assertIn("AUTHORITY_ELEVATION", {issue["code"] for issue in checked["issues"]})

    def test_projection_rejects_evidence_answer_state_elevation(self):
        result = projection.build_readiness_projection(self.session)
        for node in result.mapping["nodes"]:
            if node["archify_id"] == "evidenceState":
                node["answer_state"] = "VERIFIED"

        checked = projection.validate_projection_mapping(result.ir, result.mapping, self.session["validation"])
        self.assertEqual("BLOCKED", checked["status"])
        self.assertIn("EVIDENCE_ELEVATION", {issue["code"] for issue in checked["issues"]})

    def test_projection_rejects_synchronized_forged_digest(self):
        result = projection.build_readiness_projection(self.session)
        forged = "a" * 64
        result.ir["meta"]["projection_expectations"]["source_artifact_sha256"] = forged
        result.mapping["inputs"][0]["sha256"] = forged
        for node in result.mapping["nodes"]:
            node["source_artifact_sha256"] = forged

        checked = projection.validate_projection_mapping(result.ir, result.mapping, self.session["validation"])
        self.assertEqual("BLOCKED", checked["status"])
        self.assertIn("SOURCE_DIGEST_MISMATCH", {issue["code"] for issue in checked["issues"]})

    def test_projection_rejects_synchronized_authority_tampering(self):
        result = projection.build_readiness_projection(self.session)
        forged_authority = {
            "value": "IMPLEMENTATION_WITHIN_EXACT_SCOPE",
            "state": "PROVIDED",
            "source_type": "SOURCE_ARTIFACT",
            "source_reference": result.mapping["inputs"][0]["stored_path"],
        }
        result.ir["meta"]["projection_expectations"]["authority"] = forged_authority
        for node in result.mapping["nodes"]:
            if node["archify_id"] == "authorityState":
                node["authority_state"] = "IMPLEMENTATION_WITHIN_EXACT_SCOPE"
                node["source_answers"]["AUT-001"] = forged_authority

        checked = projection.validate_projection_mapping(result.ir, result.mapping, self.session["validation"])
        self.assertEqual("BLOCKED", checked["status"])
        self.assertIn("AUTHORITY_ELEVATION", {issue["code"] for issue in checked["issues"]})

    def test_projection_rejects_synchronized_evidence_support_tampering(self):
        result = projection.build_readiness_projection(self.session)
        result.ir["meta"]["projection_expectations"]["evidence_verified_supported"] = True
        for node in result.mapping["nodes"]:
            if node["archify_id"] == "evidenceState":
                node["answer_state"] = "VERIFIED"

        checked = projection.validate_projection_mapping(result.ir, result.mapping, self.session["validation"])
        self.assertEqual("BLOCKED", checked["status"])
        self.assertIn("EVIDENCE_ELEVATION", {issue["code"] for issue in checked["issues"]})

    def test_projection_rejects_missing_referenced_source_file(self):
        result = projection.build_readiness_projection(self.session)
        Path(result.mapping["inputs"][0]["stored_path"]).unlink()

        checked = projection.validate_projection_mapping(result.ir, result.mapping, self.session["validation"])
        self.assertEqual("BLOCKED", checked["status"])
        self.assertIn("SOURCE_FILE_UNREADABLE", {issue["code"] for issue in checked["issues"]})

    def test_projection_rejects_missing_referenced_answers_file(self):
        result = projection.build_readiness_projection(self.session)
        for item in result.mapping["inputs"]:
            if item["role"] == "ARTPKG_ANSWERS":
                Path(item["path"]).unlink()

        checked = projection.validate_projection_mapping(result.ir, result.mapping, self.session["validation"])
        self.assertEqual("BLOCKED", checked["status"])
        self.assertIn("ANSWERS_FILE_UNREADABLE", {issue["code"] for issue in checked["issues"]})
