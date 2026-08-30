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

    def test_pre_artifacts_seed_generates_confidence_and_summary(self):
        sample_path = self.root / "pre_artifacts.md"
        sample_path.write_text(
            "# Pre-Artifacts Package\n\n"
            "## 1. Project Summary\n"
            "- Project name: Offline Support Call Intelligence\n"
            "- Primary goal: Produce accurate, reviewable support-call records without sending customer audio externally.\n\n"
            "## 2. Problem Statement\n"
            "- What problem is being solved? Support technicians need a dependable record of customer calls.\n\n"
            "## 5. Scope\n"
            "### In Scope\n"
            "- Single-seat pilot on one Windows 11 workstation\n\n"
            "### Out of Scope\n"
            "- Production deployment and external cloud processing\n\n"
            "## 16. Authority and Decision Boundaries\n"
            "- This file is discovery context for ArtPkg; it is not an approved implementation contract.\n",
            encoding="utf-8",
        )
        seeded = q.seed_from_pre_artifacts(str(sample_path))
        self.assertEqual("Offline Support Call Intelligence", seeded["answers"]["PKG-001"]["value"])
        self.assertEqual("DISCOVERY", seeded["answers"]["PKG-002"]["value"])
        self.assertGreaterEqual(seeded["answers"]["PKG-002"]["confidence_score"], 80)
        self.assertIn("review_priority", seeded["answers"]["PKG-002"])
        summary = q.render_seed_summary(seeded)
        self.assertIn("Confidence score", summary)
        self.assertIn("PKG-002", summary)

    def test_apply_decision_resolution_addendum_preserves_authority_boundaries(self):
        addendum = self.root / "addendum.md"
        addendum.write_text(
            "# ArtPkg Decision-Resolution Addendum\n\n"
            "## 2. Confirmed First-Phase Decision\n\n"
            "### DEC-015 - First coding phase is capture foundation\n\n"
            "- Decision: Option A, Capture Foundation, is approved as the first bounded coding phase.\n"
            "- Decider: Project/product owner.\n"
            "- Status: Accepted for phase scoping.\n"
            "- Rationale: Dual-stream source capture must be proven independently.\n\n"
            "### DEC-016 - Synthetic test data only\n\n"
            "- Decision: PH-001 shall use synthetic calls only.\n"
            "- Status: Accepted.\n\n"
            "## 3. Proposed Bounded Phase Record\n\n"
            "### PH-001 - Windows Dual-Stream Capture Validation\n\n"
            "- Single outcome: Capture utility records technician and customer sources separately.\n"
            "- Status: Scope accepted; execution not yet authorized.\n\n"
            "### Required stop conditions\n\n"
            "- Stop if real customer content is proposed for testing.\n\n"
            "## 4. Proposed PH-001 Acceptance-Criteria Skeleton\n\n"
            "### AC-P1-001 - Endpoint enumeration\n\n"
            "- Pass condition: Intended endpoints are enumerated.\n"
            "- Validation: Runtime device inventory.\n"
            "- Evidence: device_inventory.json.\n\n"
            "### AC-P1-004 - Shared timing and drift\n\n"
            "- Pass condition: Sources remain aligned within approved tolerance.\n"
            "- Validation: Compare offsets and durations.\n"
            "- Evidence: capture metadata.\n"
            "- Status: THRESHOLD REQUIRED.\n\n"
            "## 7. Disposition of Existing Open Questions\n\n"
            "| Question | Disposition after this addendum | Blocks PH-001 coding? | Required owner/action |\n"
            "| --- | --- | --- | --- |\n"
            "| Q-001 - Exact 3CX client and version | OPEN; inspect and record from reference workstation | Does not block initial scaffolding | Pilot operator |\n"
            "| Q-012 - Duration, volume, processing time | PARTIALLY OPEN; PH-001 test duration and capture tolerances still required | Yes, in narrowed PH-001 form | Product owner |\n\n"
            "## 8. Remaining Questions the ArtPkg Agent Should Ask Now\n\n"
            "### P1-Q1 - Target repository\n\n"
            "- Question: Should PH-001 be implemented in a new repository?\n"
            "- Why it matters: The harness requires an explicit target.\n\n"
            "### P1-Q5 - Approver and authorization\n\n"
            "- Question: Which named person or organizational role approves PH-001 scope?\n"
            "- Why it matters: The package records authority as NOT_EVALUATED.\n\n",
            encoding="utf-8",
        )
        q.add_record(self.document, "decisions", {"decision": "Existing", "status": "ACCEPTED"}, record_id="DEC-015")

        result = q.apply_decision_resolution_addendum(self.document, str(addendum))

        self.assertEqual("NOT_EVALUATED", self.document["answers"]["AUT-001"]["value"])
        self.assertEqual("BLOCKED_AT_HUMAN_CHECKPOINT", self.document["answers"]["HND-001"]["value"])
        self.assertEqual("NO", self.document["answers"]["HAR-000"]["value"])
        self.assertEqual("skipped_existing", result["decisions"]["DEC-015"])
        self.assertEqual("added", result["decisions"]["DEC-016"])
        self.assertEqual("added", result["phases"]["PH-001"])
        self.assertEqual("added", result["acceptance_criteria"]["AC-P1-004"])
        self.assertIn("P1-Q1", result["blocking_questions"])
        self.assertIn("P1-Q5", result["blocking_questions"])

        decisions = {record["id"]: record for record in self.document["records"]["decisions"]}
        phases = {record["id"]: record for record in self.document["records"]["phases"]}
        criteria = {record["id"]: record for record in self.document["records"]["acceptance_criteria"]}
        questions = {record["id"]: record for record in self.document["records"]["questions"]}
        artifacts = {record["fields"]["exact_path_or_reference"]: record for record in self.document["records"]["artifacts"]}

        self.assertEqual("Existing", decisions["DEC-015"]["fields"]["decision"])
        self.assertEqual("PH-001 shall use synthetic calls only.", decisions["DEC-016"]["fields"]["decision"])
        self.assertEqual("HUMAN_DECLARATION", decisions["DEC-016"]["source_type"])
        self.assertEqual("Scope accepted; execution not yet authorized", phases["PH-001"]["fields"]["status"])
        self.assertEqual("THRESHOLD REQUIRED", criteria["AC-P1-004"]["fields"]["status"])
        self.assertEqual("OPEN; inspect and record from reference workstation", questions["Q-001"]["fields"]["current_disposition"])
        self.assertEqual("OPEN", questions["P1-Q1"]["fields"]["current_disposition"])
        self.assertEqual("SUPPORTING", artifacts[str(addendum.resolve())]["fields"]["authority"])

        validation = q.validate_answers(self.document)
        self.assertEqual("BLOCKED", validation["status"])
        self.assertIn("HND-008", validation["blocking_ids"])

    def test_apply_decision_resolution_addendum_creates_phase_requirement_records(self):
        addendum = self.root / "addendum.md"
        addendum.write_text(
            "# ArtPkg Decision-Resolution Addendum\n\n"
            "## 3. Proposed Bounded Phase Record\n\n"
            "### PH-001 - Windows Dual-Stream Capture Validation\n\n"
            "- Single outcome: Capture utility records selected endpoints.\n"
            "- Status: Scope accepted; execution not yet authorized.\n\n"
            "### Requirements included\n\n"
            "- FR-001: Physical Windows 11, one technician, one active session.\n"
            "- NFR-001: Capture has priority over downstream processing.\n",
            encoding="utf-8",
        )

        q.apply_decision_resolution_addendum(self.document, str(addendum))
        functional = {record["id"]: record for record in self.document["records"]["functional_requirements"]}
        non_functional = {record["id"]: record for record in self.document["records"]["non_functional_requirements"]}
        validation = q.validate_answers(self.document)

        self.assertEqual("Physical Windows 11, one technician, one active session.", functional["FR-001"]["fields"]["requirement"])
        self.assertEqual("Capture has priority over downstream processing.", non_functional["NFR-001"]["fields"]["requirement"])
        self.assertNotIn("PH-001: invalid cross-reference FR-001", validation["errors"])
        self.assertNotIn("PH-001: invalid cross-reference NFR-001", validation["errors"])

    def test_apply_addendum_command_writes_answers_and_regenerates_outputs(self):
        answers = self.root / "answers.json"
        addendum = self.root / "addendum.md"
        addendum.write_text(
            "# ArtPkg Decision-Resolution Addendum\n\n"
            "## 2. Confirmed First-Phase Decision\n\n"
            "### DEC-015 - First coding phase is capture foundation\n\n"
            "- Decision: Option A, Capture Foundation, is approved as the first bounded coding phase.\n"
            "- Status: Accepted.\n\n"
            "## 3. Proposed Bounded Phase Record\n\n"
            "### PH-001 - Windows Dual-Stream Capture Validation\n\n"
            "- Single outcome: Capture utility records selected endpoints.\n"
            "- Status: Scope accepted; execution not yet authorized.\n\n"
            "## 4. Proposed PH-001 Acceptance-Criteria Skeleton\n\n"
            "### AC-P1-001 - Endpoint enumeration\n\n"
            "- Pass condition: Endpoints are enumerated.\n"
            "- Validation: Runtime inventory.\n"
            "- Evidence: device_inventory.json.\n\n"
            "## 8. Remaining Questions the ArtPkg Agent Should Ask Now\n\n"
            "### P1-Q1 - Target repository\n\n"
            "- Question: What exact path/name is authorized?\n"
            "- Why it matters: The harness requires an explicit target.\n",
            encoding="utf-8",
        )
        q.save_answers(self.document, str(answers))

        code = q.main(["apply-addendum", "--answers", str(answers), "--addendum", str(addendum), "--generate", "--yes"])
        loaded = q.load_answers(str(answers))
        package = self.root / "artifacts_package.md"
        validation_path = self.root / "artifacts_package_validation.md"

        self.assertEqual(0, code)
        self.assertTrue(package.exists())
        self.assertTrue(validation_path.exists())
        self.assertEqual("BLOCKED_AT_HUMAN_CHECKPOINT", loaded["answers"]["HND-001"]["value"])
        self.assertIn("PH-001", package.read_text(encoding="utf-8"))
        self.assertIn("BLOCKED", validation_path.read_text(encoding="utf-8"))

    def test_pre_artifacts_seed_extracts_repeated_records(self):
        sample_path = self.root / "pre_artifacts_records.md"
        sample_path.write_text(
            "# Pre-Artifacts Package\n\n"
            "## 7. Requirements\n"
            "### Functional Requirements\n"
            "- FR-01: The pilot shall capture technician and customer audio separately.\n"
            "- FR-02: The technician shall review and approve the transcript.\n\n"
            "## 9. Risks\n"
            "- Risk 1: Playback contamination may create false customer content.\n"
            "- Risk 2: Automatic call detection may start or end incorrectly.\n\n"
            "## 10. Decisions\n"
            "- Decision 1: Customer conversation processing shall remain local.\n"
            "  - Rationale: Privacy and offline operation are primary product goals.\n"
            "  - Decision owner: Product owner.\n",
            encoding="utf-8",
        )
        seeded = q.seed_from_pre_artifacts(str(sample_path))
        self.assertGreater(len(seeded["records"]["functional_requirements"]), 0)
        self.assertGreater(len(seeded["records"]["risks"]), 0)
        self.assertGreater(len(seeded["records"]["decisions"]), 0)
        self.assertIn("requirement", seeded["records"]["functional_requirements"][0]["fields"])
        self.assertIn("risk", seeded["records"]["risks"][0]["fields"])

    def test_seed_summary_prioritizes_low_confidence_items_first(self):
        seeded = {
            "source_path": "example.md",
            "seeded_at": q.now(),
            "answers": {
                "PKG-003": {"value": "UNKNOWN", "state": "UNKNOWN", "confidence_score": 40, "confidence_label": "LOW", "review_priority": "HIGH"},
                "PKG-002": {"value": "DISCOVERY", "state": "PROVIDED", "confidence_score": 95, "confidence_label": "HIGH", "review_priority": "LOW"},
            },
            "records": {},
        }
        summary = q.render_seed_summary(seeded)
        self.assertLess(summary.index("PKG-003"), summary.index("PKG-002"))
        self.assertIn("Needs human review first", summary)

    def test_seed_summary_includes_explicit_accept_edit_reject_checklist(self):
        sample_path = self.root / "pre_artifacts_checklist.md"
        sample_path.write_text(
            "# Pre-Artifacts Package\n\n"
            "- Project name: Example Pilot\n"
            "- Package owner: Unknown\n",
            encoding="utf-8",
        )
        seeded = q.seed_from_pre_artifacts(str(sample_path))
        summary = q.render_seed_summary(seeded)
        self.assertIn("[ ] Accept", summary)
        self.assertIn("[ ] Edit", summary)
        self.assertIn("[ ] Reject", summary)
        self.assertIn("Action checklist", summary)

    def test_seed_summary_includes_final_decision_totals(self):
        sample_path = self.root / "pre_artifacts_decision_totals.md"
        sample_path.write_text(
            "# Pre-Artifacts Package\n\n"
            "- Project name: Example Pilot\n"
            "- Package owner: Unknown\n",
            encoding="utf-8",
        )
        seeded = q.seed_from_pre_artifacts(str(sample_path))
        summary = q.render_seed_summary(seeded)
        self.assertIn("## Final decision summary", summary)
        self.assertIn("Accepted:", summary)
        self.assertIn("Edited:", summary)
        self.assertIn("Rejected:", summary)

    def test_pre_artifacts_seed_extracts_heading_based_sections(self):
        sample_path = self.root / "pre_artifacts_headings.md"
        sample_path.write_text(
            "# Pre-Artifacts Package\n\n"
            "## Actors\n"
            "- Actor 1: Support technician\n"
            "- Actor 2: Customer\n\n"
            "## Use Cases\n"
            "- Use case 1: Review a call after it completes\n"
            "- Use case 2: Export a summary for follow-up\n\n"
            "## Failure Cases\n"
            "- Failure case 1: Loopback capture includes unrelated desktop audio\n"
            "- Failure case 2: Automatic call start fails and the operator must recover manually\n\n"
            "## Open Questions\n"
            "- Question 1: Which call-state signal is acceptable for automation?\n",
            encoding="utf-8",
        )
        seeded = q.seed_from_pre_artifacts(str(sample_path))
        self.assertGreater(len(seeded["records"].get("actors", [])), 0)
        self.assertGreater(len(seeded["records"].get("use_cases", [])), 0)
        self.assertGreater(len(seeded["records"].get("failure_cases", [])), 0)
        self.assertGreater(len(seeded["records"].get("questions", [])), 0)

    def test_template_resolution_falls_back_to_repo_root(self):
        base_dir = self.root / "outside"; base_dir.mkdir()
        resolved = q.resolve_template_path(str(base_dir))
        self.assertTrue(Path(resolved).exists())
        self.assertIn("reusable_artifacts_package_template", Path(resolved).name)

    def test_merge_seed_records_writes_records_into_document(self):
        seed = {
            "source_path": "example.md",
            "records": {
                "risks": [{
                    "fields": {"risk": "Playback contamination", "likelihood": "MEDIUM", "impact": "HIGH", "detection": "d", "mitigation_or_control": "m", "owner": "o", "residual_status": "OPEN"},
                    "confidence_score": 82, "confidence_label": "MEDIUM", "review_priority": "MEDIUM", "confidence_basis": "SECTION_MATCH",
                }],
            },
        }
        created = q.merge_seed_records(self.document, seed)
        self.assertEqual(1, len(created["risks"]))
        stored = q.find_record(self.document, created["risks"][0])
        self.assertEqual("Playback contamination", stored["fields"]["risk"])
        self.assertEqual("SOURCE_ARTIFACT", stored["source_type"])
        self.assertEqual("example.md", stored["source_reference"])
        self.assertEqual(82, stored["confidence_score"])

    def test_pre_artifacts_seed_extracts_problem_statement_and_scope(self):
        sample_path = self.root / "pre_artifacts_fields.md"
        sample_path.write_text(
            "# Pre-Artifacts Package\n\n"
            "## 1. Project Summary\n"
            "- Project name: Example Pilot\n"
            "- Primary goal: Produce a reviewable local record without cloud processing.\n\n"
            "## 2. Problem Statement\n"
            "- What problem is being solved? Technicians need a dependable call record.\n\n"
            "## 3. Intended Outcome\n"
            "- Desired result or observable outcome: A technician reviews an approved transcript.\n\n"
            "## 5. Scope\n"
            "### In Scope\n"
            "- Single-seat pilot capture.\n"
            "### Out of Scope\n"
            "- Production deployment.\n",
            encoding="utf-8",
        )
        seeded = q.seed_from_pre_artifacts(str(sample_path))
        self.assertEqual("Technicians need a dependable call record.", seeded["answers"]["OVR-001"]["value"])
        self.assertEqual("A technician reviews an approved transcript.", seeded["answers"]["OVR-002"]["value"])
        self.assertIn("Single-seat pilot capture.", seeded["answers"]["BND-001"]["value"])
        self.assertIn("Production deployment.", seeded["answers"]["BND-002"]["value"])
        self.assertIn("Produce a reviewable local record", seeded["answers"]["PKG-008"]["value"])

    def test_pre_artifacts_seed_leaves_unresolvable_package_metadata_unknown(self):
        sample_path = self.root / "pre_artifacts_no_metadata.md"
        sample_path.write_text(
            "# Pre-Artifacts Package\n\n"
            "## 1. Project Summary\n"
            "- Project name: Example Pilot\n",
            encoding="utf-8",
        )
        seeded = q.seed_from_pre_artifacts(str(sample_path))
        for qid in ("PKG-003", "PKG-004", "PKG-005", "PKG-006"):
            self.assertEqual("UNKNOWN", seeded["answers"][qid]["state"])
        self.assertNotIn("AUT-002", seeded["answers"])
        self.assertNotIn("AUT-004", seeded["answers"])

    def test_pre_artifacts_seed_does_not_fabricate_authority_when_none_claimed(self):
        sample_path = self.root / "pre_artifacts_authority.md"
        sample_path.write_text("# Pre-Artifacts Package\n\n- Project name: Example Pilot\n", encoding="utf-8")
        seed = q.seed_from_pre_artifacts(str(sample_path))
        document = q.new_answers(str(self.template), str(self.root), "Tester")
        for qid, item in seed["answers"].items():
            q.set_answer(document, qid, item["value"], item["state"], item["source_type"], item["source_reference"])
        self.assertEqual("NOT_APPLICABLE", document["answers"]["AUT-004"]["state"])
        self.assertEqual("DERIVED_BY_SCRIPT", document["answers"]["AUT-004"]["source_type"])

    def test_pre_artifacts_seed_extracts_non_functional_requirements_and_evidence(self):
        sample_path = self.root / "pre_artifacts_nfr_evidence.md"
        sample_path.write_text(
            "# Pre-Artifacts Package\n\n"
            "## 7. Requirements\n"
            "### Non-Functional Requirements\n"
            "- Performance:\n"
            "  - Audio capture shall have priority over transcription.\n"
            "- Security:\n"
            "  - The pilot Web UI shall bind to localhost only.\n\n"
            "## 14. Evidence and Validation\n"
            "- Existing evidence:\n"
            "  - A user-observed OBS test confirmed dual capture was audible.\n",
            encoding="utf-8",
        )
        seeded = q.seed_from_pre_artifacts(str(sample_path))
        nfrs = seeded["records"]["non_functional_requirements"]
        self.assertEqual(2, len(nfrs))
        self.assertEqual("PERFORMANCE", nfrs[0]["fields"]["category"])
        evidence = seeded["records"]["evidence"]
        self.assertEqual(1, len(evidence))
        self.assertIn("OBS test", evidence[0]["fields"]["exact_source_or_command"])

    def test_decision_date_or_status_field_is_captured(self):
        text = (
            "## 10. Decisions\n"
            "- Decision 1: Keep processing local.\n"
            "  - Rationale: Privacy.\n"
            "  - Decision owner: Product owner.\n"
            "  - Date or status: Confirmed 2026-08-29.\n"
        )
        found = q._extract_decisions(text)
        self.assertEqual(1, len(found))
        self.assertEqual("Confirmed 2026-08-29.", found[0][0]["date"])

    def test_pre_artifacts_seed_extracts_numbered_actors_and_failure_cases(self):
        sample_path = self.root / "pre_artifacts_numbered.md"
        sample_path.write_text(
            "# Pre-Artifacts Package\n\n"
            "## 6. Actors\n"
            "- Users:\n"
            "  - Pilot support technician.\n"
            "- External systems or services:\n"
            "  - 3CX call platform.\n\n"
            "## 12. Failure, Misuse, and Unsafe Cases\n"
            "- Failure case 1: A device disconnects mid-call.\n"
            "  - Required safe behavior: Do not silently drop the session.\n"
            "  - Recovery or abstention behavior: Pause and prompt for reselection.\n"
            "  - Evidence needed: Device-removal test.\n",
            encoding="utf-8",
        )
        actors = q._extract_actor_records(open(sample_path, encoding="utf-8").read())
        self.assertEqual(2, len(actors))
        self.assertEqual("USER", actors[0]["role_type"])
        self.assertEqual("EXTERNAL_SYSTEM", actors[1]["role_type"])
        failures = q._extract_failure_case_records(open(sample_path, encoding="utf-8").read())
        self.assertEqual(1, len(failures))
        self.assertEqual("A device disconnects mid-call.", failures[0]["condition"])
        self.assertEqual("Do not silently drop the session.", failures[0]["required_safe_behavior"])
        self.assertEqual("Pause and prompt for reselection.", failures[0]["recovery_or_abstention"])
        self.assertEqual("Device-removal test.", failures[0]["evidence_needed"])

    def test_pre_artifacts_seed_extracts_constraints_assumptions_components_dependencies(self):
        text = (
            "## 8. Constraints\n"
            "- Technical constraints:\n"
            "  - Target OS is Windows 11.\n\n"
            "## 11. Assumptions\n"
            "- Assumption 1: Devices are correctly enumerated.\n"
            "  - Why it matters: Wrong device selection breaks capture.\n"
            "  - How it might be validated: Manual device inventory check.\n\n"
            "## 15. Architecture / System Context\n"
            "- Key components:\n"
            "  - Capture Service: Captures audio from selected devices.\n"
            "- External dependencies:\n"
            "  - 3CX for call routing.\n"
        )
        constraints = q._extract_constraints(text)
        self.assertEqual(1, len(constraints))
        self.assertEqual("Technical constraints", constraints[0]["category"])
        self.assertEqual("Target OS is Windows 11.", constraints[0]["constraint"])

        assumptions = q._extract_assumptions(text)
        self.assertEqual(1, len(assumptions))
        self.assertEqual("Devices are correctly enumerated.", assumptions[0]["assumption"])
        self.assertEqual("Wrong device selection breaks capture.", assumptions[0]["impact_if_wrong"])
        self.assertEqual("Manual device inventory check.", assumptions[0]["validation_method"])

        components = q._extract_components(text)
        self.assertEqual(1, len(components))
        self.assertEqual("Capture Service", components[0]["component"])
        self.assertEqual("Captures audio from selected devices.", components[0]["responsibility"])

        deps = q._extract_external_dependencies(text)
        self.assertEqual(1, len(deps))
        self.assertEqual("3CX for call routing.", deps[0]["dependency"])

    def test_pre_artifacts_seed_extracts_restricted_content_flag(self):
        sample_path = self.root / "pre_artifacts_sec.md"
        sample_path.write_text(
            "# Pre-Artifacts Package\n\n"
            "## 19. Sensitive or Restricted Content\n"
            "- Does this project involve sensitive data, credentials, regulated information, or restricted content? Yes. Customer voices and names.\n"
            "- If yes, what safeguards are required?\n"
            "  - Local-only processing.\n"
            "- Are any redaction or access controls needed?\n"
            "  - Yes, exact categories unresolved.\n",
            encoding="utf-8",
        )
        seeded = q.seed_from_pre_artifacts(str(sample_path))
        self.assertEqual("YES", seeded["answers"]["SEC-001"]["value"])
        self.assertIn("Local-only processing", seeded["answers"]["SEC-001-CATEGORIES"]["value"])

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

    def test_terminal_guidance_explains_questions_without_inferring_answers(self):
        rendered = q.format_terminal_question("PKG-006", q.QUESTION_CATALOG["PKG-006"])
        self.assertIn("What this question means:", rendered)
        self.assertIn("Example:", rendered)
        self.assertIn("Snapshot", rendered)
        self.assertIn("a1b2c3d", rendered)

    def test_derived_conditionals_are_skipped_but_human_answers_are_not(self):
        self.assertFalse(q.should_ask_question(self.document, "HAR-001"))
        self.assertIn("HAR-000 is NO", q.conditional_skip_reason(self.document, "HAR-001"))
        q.set_answer(self.document, "HAR-001", "INTAKE")
        self.assertTrue(q.should_ask_question(self.document, "HAR-001"))

    def test_repeated_record_field_prompt_contains_context(self):
        values = iter(["cancel"])
        prompts = []
        q.collect_record(self.document, "actors", input_fn=lambda prompt: prompts.append(prompt) or next(values), output_fn=lambda _text: None)
        self.assertIn("What this question means:", prompts[0])
        self.assertIn("Example:", prompts[0])

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

    def test_intake_ui_command_delegates_to_server(self):
        called = {}

        def fake_main(argv):
            called["argv"] = argv
            return 0

        original = q.start_intake_ui
        try:
            q.start_intake_ui = fake_main
            result = q.main(["intake-ui", "--workspace", str(self.root), "--port", "9999"])
        finally:
            q.start_intake_ui = original

        self.assertEqual(0, result)
        self.assertEqual(["--workspace", str(self.root), "--port", "9999"], called["argv"])


if __name__ == "__main__":
    unittest.main()
