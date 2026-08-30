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
