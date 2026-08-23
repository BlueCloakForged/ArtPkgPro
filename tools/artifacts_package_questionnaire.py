#!/usr/bin/env python3
"""Bounded questionnaire and artifacts-package generator."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "0.2"
LEGACY_SCHEMA_VERSION = "0.1"
QUESTIONNAIRE_VERSION = "0.1"
STATES = {"PROVIDED", "UNKNOWN", "NOT_APPLICABLE", "TO_BE_INSPECTED", "DEFERRED"}
PROVENANCE = {"HUMAN_DECLARATION", "SOURCE_ARTIFACT", "REPOSITORY_OBSERVATION", "RUNTIME_EVIDENCE", "DERIVED_BY_SCRIPT"}
ID_PREFIXES = {"actors": "ACT", "use_cases": "UC", "failure_cases": "FC", "functional_requirements": "FR", "non_functional_requirements": "NFR", "acceptance_criteria": "AC", "constraints": "CON", "decisions": "DEC", "assumptions": "ASM", "conflicts": "CFT", "questions": "Q", "risks": "RSK", "phases": "PH", "evidence": "EVD", "artifacts": "ART"}
ID_PREFIXES.update({"external_dependencies": "DEP", "prohibited_shortcuts": "SHT", "change_surface": "CHG", "preserve_surface": "PRS", "stop_conditions": "STP", "components": "CMP", "interfaces": "INT", "data": "DAT", "environment": "ENV", "dependencies": "LIB", "configuration": "CFG", "build_commands": "BLD", "test_commands": "TST", "runtime_commands": "RUN", "exclusions": "EXC", "changed_artifacts": "CHA", "deviations": "DEV", "transfer_items": "XFR"})
HARNESS_QUESTION_IDS = [
    "HAR-000", "HAR-001", "HAR-002", "HAR-003", "HAR-004", "HAR-005", "HAR-006", "HAR-007", "HAR-008", "HAR-009", "HAR-010", "HAR-011", "HAR-012", "HAR-013", "HAR-014", "HAR-015", "HAR-016", "HAR-017", "HAR-018", "HAR-019", "HAR-020", "HAR-021", "HAR-022", "HAR-023", "HAR-024"
]
HARNESS_STATE_FIELDS = [
    "pipeline_stage", "run_type", "package_id", "parent_package_id", "target_repository", "harness_repository", "evidence_output_location", "repository_snapshot", "dirty_state_manifest", "snapshot_state", "intake_policy", "intake_reconciliation", "discovery_providers", "discovery_compatibility", "discovery_result_classification", "fallback_method", "active_bec", "bec_drafting_authorization", "bec_acceptance", "bec_activation", "implementation_authorization", "execution_authorization", "verification_status", "checkpoint_acceptance", "next_phase_authorization", "package_authority", "package_freshness", "next_permitted_action", "human_decision_required"
]
RECORD_FIELDS = {
    "actors": [("name", "Name", None), ("role_type", "Role type", {"USER", "OPERATOR", "APPROVER", "OWNER", "SUPPLIER", "AFFECTED_PARTY", "EXTERNAL_SYSTEM"}), ("needs_or_responsibilities", "Needs or responsibilities", None), ("decision_authority", "Decision authority", None)],
    "use_cases": [("actor_id", "Actor ID", None), ("trigger", "Trigger", None), ("behavior", "Expected behavior", None), ("outcome", "Observable outcome", None), ("frequency_or_importance", "Frequency or importance", None)],
    "failure_cases": [("condition", "Condition", None), ("required_safe_behavior", "Required safe behavior", None), ("recovery_or_abstention", "Recovery or abstention behavior", None), ("evidence_needed", "Evidence needed", None)],
    "functional_requirements": [("requirement", "Requirement text", None), ("source", "Source", None), ("priority", "Priority", {"MUST", "SHOULD", "COULD"}), ("status", "Status", {"PROPOSED", "ACCEPTED", "IMPLEMENTED", "VERIFIED"}), ("decision_owner", "Decision owner", None)],
    "non_functional_requirements": [("category", "Category", None), ("requirement", "Requirement", None), ("measurement", "Measurement or threshold", None), ("source", "Source", None), ("status", "Status", {"PROPOSED", "ACCEPTED", "IMPLEMENTED", "VERIFIED"})],
    "acceptance_criteria": [("requirement_ids", "Linked requirement IDs", None), ("pass_condition", "Pass condition", None), ("validation_method", "Validation method", None), ("expected_evidence", "Expected evidence", None), ("evidence_ids", "Evidence IDs", None), ("approver", "Approver", None), ("status", "Status", {"PROPOSED", "ACCEPTED", "PASSED", "FAILED", "NOT_RUN"})],
    "constraints": [("category", "Category", None), ("constraint", "Constraint", None), ("enforcement", "Enforcement", None), ("evidence_or_status", "Evidence or status", None), ("owner", "Owner", None)],
    "decisions": [("decision", "Decision", None), ("rationale", "Rationale", None), ("decider", "Decider", None), ("date", "Date", None), ("evidence", "Evidence", None), ("status", "Status", {"PROPOSED", "ACCEPTED", "SUPERSEDED"})],
    "assumptions": [("assumption", "Assumption", None), ("impact_if_wrong", "Impact if wrong", None), ("validation_method", "Validation method", None), ("owner", "Owner", None), ("status", "Status", {"OPEN", "VALIDATED", "INVALIDATED"})],
    "conflicts": [("source_a", "Source A", None), ("source_b", "Source B", None), ("conflict", "Conflict", None), ("impact", "Impact", None), ("resolution_owner", "Resolution owner", None), ("status", "Status", {"OPEN", "RESOLVED"})],
    "questions": [("question", "Question", None), ("why_it_matters", "Why it matters", None), ("decision_owner", "Decision owner", None), ("needed_by", "Needed by checkpoint", None), ("current_disposition", "Current disposition", None)],
    "risks": [("risk", "Risk", None), ("likelihood", "Likelihood", {"LOW", "MEDIUM", "HIGH"}), ("impact", "Impact", {"LOW", "MEDIUM", "HIGH"}), ("detection", "Detection", None), ("mitigation_or_control", "Mitigation or control", None), ("owner", "Owner", None), ("residual_status", "Residual status", {"OPEN", "ACCEPTED", "MITIGATED"})],
    "phases": [("title_and_outcome", "Title and single observable outcome", None), ("status", "Status", {"PROPOSED", "ACCEPTED", "IN_PROGRESS", "REVIEW", "CLOSED"}), ("requirement_ids", "Linked requirement IDs", None), ("in_scope", "In scope", None), ("out_of_scope", "Out of scope", None), ("validation", "Validation commands or checks", None), ("human_review_level", "Human-review level", {"NONE", "SAMPLED", "REQUIRED", "APPROVAL_REQUIRED"}), ("rollback_or_recovery", "Rollback or recovery", None), ("authority_source", "Authority source", None)],
    "evidence": [("claim_tested", "Claim tested", None), ("evidence_type", "Evidence type", None), ("exact_source_or_command", "Exact source, path, or command", None), ("expected_result", "Expected result", None), ("observed_result", "Observed result", None), ("result", "Result", {"PASS", "FAIL", "PARTIAL", "NOT_RUN"}), ("date", "Date", None), ("limitations", "Limitations", None)],
    "artifacts": [("exact_path_or_reference", "Exact path or reference", None), ("purpose", "Purpose", None), ("provenance", "Provenance", None), ("authority", "Authority", {"AUTHORITATIVE", "SUPPORTING", "EXPLORATORY"}), ("authority_basis", "Authority basis", None), ("status", "Status", {"CURRENT", "STALE", "SUPERSEDED", "DRAFT", "UNVERIFIED", "RESTRICTED"}), ("last_validated_date", "Last validated date", None)],
}
for _extra_section in {"external_dependencies", "prohibited_shortcuts", "change_surface", "preserve_surface", "stop_conditions", "components", "interfaces", "data", "environment", "dependencies", "configuration", "build_commands", "test_commands", "runtime_commands", "exclusions", "changed_artifacts", "deviations", "transfer_items"}:
    RECORD_FIELDS.setdefault(_extra_section, [])
RECORD_FIELDS.update({
    "external_dependencies": [("dependency", "Dependency", None), ("owner", "Owner", None), ("required_behavior", "Required behavior", None), ("availability", "Availability", None), ("failure_impact", "Failure impact", None)],
    "prohibited_shortcuts": [("prohibited_approach", "Prohibited approach", None), ("reason", "Reason", None), ("detection_method", "Detection method", None)],
    "change_surface": [("path_or_component", "Path, component, interface, or process", None), ("reason", "Why it may change", None)],
    "preserve_surface": [("surface", "Behavior, data, file, interface, or user change", None), ("reason", "Why it must remain untouched", None)],
    "stop_conditions": [("condition", "Condition", None), ("detection", "Detection", None), ("required_response", "Required response", None), ("decision_owner", "Decision owner", None)],
    "components": [("component", "Component", None), ("responsibility", "Responsibility", None), ("inputs", "Inputs", None), ("outputs", "Outputs", None), ("state_owner", "State owner", None), ("source_evidence", "Source evidence", None), ("confidence", "Confidence", {"HIGH", "MEDIUM", "LOW"})],
    "interfaces": [("interface_type", "Interface type", {"API", "CLI", "UI", "FILE", "EVENT", "DATABASE", "HUMAN_STEP", "OTHER"}), ("producer", "Producer", None), ("consumer", "Consumer", None), ("contract_or_format", "Contract or format", None), ("failure_behavior", "Failure behavior", None), ("source", "Source", None)],
    "data": [("direction", "Direction", {"INPUT", "OUTPUT"}), ("name", "Name", None), ("format_or_schema", "Format or schema", None), ("producer", "Producer", None), ("consumer", "Consumer", None), ("trust_classification", "Trust classification", None), ("sample_reference", "Sample reference", None), ("validation", "Validation", None)],
    "environment": [("item", "Item", None), ("version", "Version", None), ("purpose", "Purpose", None), ("source", "Source", None), ("required_or_observed", "Required or observed", None)],
    "dependencies": [("dependency", "Dependency", None), ("version_or_constraint", "Version or constraint", None), ("source", "Source", None), ("purpose", "Purpose", None), ("availability", "Availability", None), ("license_or_access_concern", "License or access concern", None)],
    "configuration": [("path_or_source", "Path or source", None), ("purpose", "Purpose", None), ("authoritative_status", "Authoritative status", None)],
    "build_commands": [("command", "Command", None), ("working_directory", "Working directory", None), ("expected_result", "Expected result", None), ("source", "Source", None), ("last_observed_date", "Last observed date", None)],
    "test_commands": [("command", "Command", None), ("working_directory", "Working directory", None), ("expected_result", "Expected result", None), ("source", "Source", None), ("last_observed_date", "Last observed date", None)],
    "runtime_commands": [("command_or_step", "Command or step", None), ("controlled_input", "Controlled input", None), ("expected_observation", "Expected observation", None), ("environment", "Environment", None), ("evidence_location", "Evidence location", None)],
    "exclusions": [("path_or_description", "Path or description", None), ("exclusion_reason", "Exclusion reason", None), ("reason_code", "Reason code", {"UNRELATED", "WRONG_PROJECT", "WRONG_SNAPSHOT", "UNSEALED", "RESTRICTED", "WEAK_RELATIONSHIP", "PROHIBITED_PATH", "UNAVAILABLE"}), ("impact", "Impact", None)],
    "changed_artifacts": [("exact_path", "Exact path", None), ("change_summary", "Change summary", None), ("expected_or_unexpected", "Expected or unexpected", None), ("phase_ids", "Related phase IDs", None), ("requirement_ids", "Related requirement IDs", None)],
    "deviations": [("deviation", "Deviation", None), ("reason", "Reason", None), ("impact", "Impact", None), ("disposition", "Disposition", None), ("approver", "Approver if accepted", None)],
    "transfer_items": [("item", "Item", None), ("source_project_and_snapshot", "Source project and snapshot", None), ("classification", "Classification", {"BORROW", "ADAPT", "DO_NOT_CARRY_OVER"}), ("reason", "Reason", None), ("target_project_difference", "Target-project difference", None), ("required_adaptation", "Required adaptation", None), ("required_reverification", "Required re-verification", None), ("prohibited_inherited_assumptions", "Prohibited inherited assumptions", None)],
})
REPEATED_QID_TO_SECTION = {"ACT-SET": "actors", "UC-SET": "use_cases", "FC-SET": "failure_cases", "BND-003": "external_dependencies", "BND-004": "prohibited_shortcuts", "BND-005": "change_surface", "BND-006": "preserve_surface", "FR-SET": "functional_requirements", "NFR-SET": "non_functional_requirements", "AC-SET": "acceptance_criteria", "OUT-003": "stop_conditions", "ARC-SET": "components", "INT-SET": "interfaces", "DAT-SET": "data", "ENV-001": "environment", "ENV-002": "dependencies", "ENV-003": "configuration", "ENV-004": "build_commands", "ENV-005": "test_commands", "ENV-006": "runtime_commands", "SEC-SET": "constraints", "DEC-SET": "decisions", "ASM-SET": "assumptions", "CFT-SET": "conflicts", "QST-SET": "questions", "RSK-SET": "risks", "PHS-SET": "phases", "EVD-SET": "evidence", "ART-SET": "artifacts", "ARTQ-001": "exclusions", "HND-003": "changed_artifacts", "HND-004": "deviations", "XFR-SET": "transfer_items"}
ENUM_CHOICES = {"SET-003": {"COMPACT_SINGLE_FILE", "STANDARD_MULTI_FILE"}, "SET-005": {"NO_INSPECTION", "READ_ONLY_INSPECTION"}, "SET-006": {"DO_NOT_EXECUTE", "CONFIRM_EACH_COMMAND"}, "PKG-002": {"DISCOVERY", "DESIGN", "IMPLEMENTATION_HANDOFF", "REVIEW", "RESUMPTION", "CLOSEOUT", "CROSS_PROJECT_TRANSFER"}, "AUT-001": {"NONE", "DISCOVERY_ONLY", "DESIGN_ONLY", "IMPLEMENTATION_WITHIN_EXACT_SCOPE", "REVIEW_ONLY", "CLOSEOUT_ONLY", "NOT_EVALUATED"}, "SEC-001": {"YES", "NO"}, "HND-001": {"NOT_EVALUATED", "ACCEPTED", "ACCEPTED_WITH_CHANGES", "NEEDS_MORE_EVIDENCE", "NEEDS_REVISION", "DEFERRED", "REJECTED", "BLOCKED_AT_HUMAN_CHECKPOINT"}, "FIN-001": {"YES", "NO"}, "FIN-002": {"YES", "NO"}, "FIN-003": {"YES", "NO"}, "FIN-004": {"YES", "NO"}, "HAR-000": {"YES", "NO"}, "HAR-001": {"INTAKE", "RECONCILIATION", "DISCOVERY", "PLANNING", "BEC_CONSIDERATION", "IMPLEMENTATION_HANDOFF", "CHECKPOINT_REVIEW", "CLOSEOUT"}, "HAR-002": {"NEW_PROJECT_INTAKE", "RESUMED_PROJECT", "CHANGED_SNAPSHOT_RECONCILIATION", "CHECKPOINT_UPDATE"}, "HAR-010": {"NOT_VERIFIED", "VERIFIED", "PARTIAL", "UNAVAILABLE", "CONTRADICTORY"}, "HAR-011": {"COMPLETE_WITHIN_BOUNDARY", "PARTIAL", "EMPTY", "NOISY", "STALE", "CONTRADICTORY", "NOT_RUN"}}
HARNESS_TRANSITIONS = ("bec_candidate", "bec_drafting_authorization", "bec_drafted", "bec_acceptance", "bec_activation", "implementation_authorization", "execution_authorization", "verification_status", "checkpoint_acceptance", "next_phase_authorization")
HARNESS_ALLOWED_STATES = {"bec_candidate": {"NONE", "NOT_EVALUATED", "PROPOSED"}, "bec_drafting_authorization": {"NONE", "NOT_EVALUATED", "AUTHORIZED", "NOT_AUTHORIZED", "BLOCKED"}, "bec_drafted": {"NONE", "NOT_EVALUATED", "DRAFTED", "BLOCKED"}, "bec_acceptance": {"NONE", "NOT_EVALUATED", "ACCEPTED", "BLOCKED"}, "bec_activation": {"NONE", "NOT_EVALUATED", "ACTIVE", "BLOCKED"}, "implementation_authorization": {"NONE", "NOT_EVALUATED", "AUTHORIZED", "NOT_AUTHORIZED", "BLOCKED"}, "execution_authorization": {"NONE", "NOT_EVALUATED", "AUTHORIZED", "NOT_AUTHORIZED", "BLOCKED"}, "verification_status": {"NOT_EVALUATED", "NOT_VERIFIED", "VERIFIED", "BLOCKED"}, "checkpoint_acceptance": {"NOT_EVALUATED", "ACCEPTED", "BLOCKED"}, "next_phase_authorization": {"NONE", "NOT_EVALUATED", "AUTHORIZED", "NOT_AUTHORIZED", "BLOCKED"}}
SPEC_RECORD_SECTIONS = tuple(RECORD_FIELDS)

QUESTION_CATALOG = {qid: {"id": qid, "prompt": prompt, "type": kind} for qid, prompt, kind in [
    ("SET-001", "Exact path to reusable_artifacts_package_template.md", "PATH_OR_URI"), ("SET-002", "Where should the generated package be written?", "PATH_OR_URI"), ("SET-003", "Output shape (COMPACT_SINGLE_FILE or STANDARD_MULTI_FILE)", "ENUM"), ("SET-005", "Inspection permission (NO_INSPECTION or READ_ONLY_INSPECTION)", "ENUM"), ("SET-006", "Command execution permission (DO_NOT_EXECUTE or CONFIRM_EACH_COMMAND)", "ENUM"),
    ("PKG-001", "Project canonical name", "SHORT_TEXT"), ("PKG-002", "Package purpose", "ENUM"), ("PKG-003", "Package owner", "SHORT_TEXT"), ("PKG-004", "Respondent and role", "SHORT_TEXT"), ("PKG-005", "Repository or workspace", "PATH_OR_URI"), ("PKG-006", "Snapshot identity", "SHORT_TEXT"), ("PKG-007", "Authoritative source of truth", "PATH_OR_URI"), ("PKG-008", "Package coverage claim", "LONG_TEXT"), ("PKG-009", "Explicit limitations", "LONG_TEXT"),
    ("AUT-001", "Current authority state", "ENUM"), ("AUT-002", "Authorizer and role", "SHORT_TEXT"), ("AUT-003", "Recorded authority source", "PATH_OR_URI"), ("AUT-004", "Exact authorized scope", "LONG_TEXT"), ("AUT-005", "Authority exclusions", "LONG_TEXT"), ("AUT-006", "Authority expiry or checkpoint", "SHORT_TEXT"), ("AUT-007", "Separately authorized special actions", "MULTI_ENUM"), ("AUT-008", "Active bounded contract ID and path", "SHORT_TEXT"), ("AUT-009", "Escalation owner", "SHORT_TEXT"),
    ("OVR-001", "Problem statement", "LONG_TEXT"), ("OVR-002", "Intended observable outcome", "LONG_TEXT"), ("OVR-008", "Next proposed checkpoint", "LONG_TEXT"), ("BND-001", "In scope", "LONG_TEXT"), ("BND-002", "Out of scope", "LONG_TEXT"), ("DAT-001", "Data lineage", "LONG_TEXT"), ("DAT-002", "Retention and expiry", "LONG_TEXT"), ("SEC-001", "Restricted content?", "BOOLEAN"), ("SEC-002", "Negative-path behavior", "MULTI_ENUM"), ("SEC-003", "Rollback and recovery", "LONG_TEXT"), ("OUT-001", "Good outcome", "LONG_TEXT"), ("OUT-002", "Bad outcome", "LONG_TEXT"),
    ("HND-001", "Checkpoint classification", "ENUM"), ("HND-002", "Classification reason", "LONG_TEXT"), ("HND-005", "Residual risks and limitations", "LONG_TEXT"), ("HND-006", "Working-state observations", "LONG_TEXT"), ("HND-007", "Next permitted action", "LONG_TEXT"), ("HND-008", "Required approver", "SHORT_TEXT"), ("HND-009", "Fresh-session instruction", "LONG_TEXT"), ("FIN-001", "Completeness review", "BOOLEAN"), ("FIN-002", "Secret and sensitive-content review", "BOOLEAN"), ("FIN-003", "Authority review", "BOOLEAN"), ("FIN-004", "Generate outputs", "BOOLEAN")
]}
QUESTION_CATALOG.update({qid: {"id": qid, "prompt": prompt, "type": "REPEATED_RECORD"} for qid, prompt in {
    "OVR-003": "Completed work and linked evidence", "OVR-004": "Work in progress", "OVR-005": "Current blockers", "OVR-006": "Deferred work", "OVR-007": "Unverified claims", "ACT-SET": "Actors", "UC-SET": "Primary use cases", "FC-SET": "Failure, denial, and misuse cases", "BND-003": "External dependencies", "BND-004": "Prohibited shortcuts", "BND-005": "Change surface", "BND-006": "Preserve surface", "FR-SET": "Functional requirements", "NFR-SET": "Non-functional requirements", "AC-SET": "Acceptance criteria", "OUT-003": "Stop conditions", "ARC-SET": "Components", "INT-SET": "Interfaces", "DAT-SET": "Inputs and outputs", "ENV-001": "Runtime and platforms", "ENV-002": "Tools and dependencies", "ENV-003": "Configuration locations", "ENV-004": "Build commands", "ENV-005": "Test and lint commands", "ENV-006": "Runtime verification commands", "SEC-SET": "Security and operational constraints", "DEC-SET": "Decisions", "ASM-SET": "Assumptions", "CFT-SET": "Source conflicts", "QST-SET": "Open questions", "RSK-SET": "Risks", "PHS-SET": "Phases", "EVD-SET": "Evidence ledger", "VAL-005": "Reproducibility observations", "ART-SET": "Artifact index", "ARTQ-001": "Excluded artifacts", "HND-003": "Changed artifacts", "HND-004": "Deviations", "XFR-SET": "Cross-project transfer items"
}.items()})
QUESTION_CATALOG.update({qid: {"id": qid, "prompt": prompt, "type": kind} for qid, prompt, kind in [
    ("AUT-007-SCOPE", "Special action exact scope, authorizer, source, recovery, and expiry", "LONG_TEXT"), ("PKG-007-AUTH", "Who designated the source of truth and where recorded?", "LONG_TEXT"), ("SEC-001-CATEGORIES", "Restricted-content categories, allowed/prohibited locations, roles, redaction, and fail-closed behavior", "LONG_TEXT"), ("VAL-001", "Generation evidence", "LONG_TEXT"), ("VAL-002", "Verification evidence", "LONG_TEXT"), ("VAL-003", "Understanding evidence", "LONG_TEXT"), ("VAL-004", "Negative evidence", "LONG_TEXT")
]})
QUESTION_CATALOG.update({qid: {"id": qid, "prompt": f"SDLC Harness: {qid}", "type": "HARNESS"} for qid in HARNESS_QUESTION_IDS})

def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def answer(value: Any, state: str = "PROVIDED", source_type: str = "HUMAN_DECLARATION", source_reference: str | None = None, respondent: str = "") -> dict[str, Any]:
    if state not in STATES or source_type not in PROVENANCE:
        raise ValueError("invalid answer state or provenance")
    stamp = now()
    return {"value": value, "state": state, "source_type": source_type, "source_reference": source_reference, "respondent": respondent, "timestamp": stamp, "last_edit_timestamp": stamp, "confidence": None}

def template_digest(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def new_answers(template_path: str, output_path: str, respondent: str = "") -> dict[str, Any]:
    created = now()
    package_id = "PKG-" + hashlib.sha256(f"{template_path}|{created}|{respondent}".encode()).hexdigest()[:12].upper()
    document = {"schema_version": SCHEMA_VERSION, "questionnaire_version": QUESTIONNAIRE_VERSION, "template_version": template_digest(template_path), "created": created, "updated": created, "package_id": package_id, "parent_package_id": None, "respondent": respondent, "setup": {"template_path": template_path, "output_path": output_path, "shape": "COMPACT_SINGLE_FILE", "inspection": "NO_INSPECTION", "command_execution": "DO_NOT_EXECUTE", "harness_enabled": False}, "answers": {}, "records": {key: [] for key in ID_PREFIXES}, "deleted_ids": [], "attestation": {}, "answer_history": [], "repository_observations": [], "harness": {"enabled": False}, "record_field_coverage": coverage_matrix()}
    apply_conditionals(document)
    return document

def migrate_v01_to_v02(document: dict[str, Any]) -> dict[str, Any]:
    if document.get("schema_version") != LEGACY_SCHEMA_VERSION:
        raise ValueError("migration requires an artifacts answer file with schema_version 0.1")
    migrated = copy.deepcopy(document); migrated["schema_version"] = SCHEMA_VERSION
    migrated.setdefault("package_id", "PKG-" + hashlib.sha256(json.dumps(document, sort_keys=True).encode()).hexdigest()[:12].upper())
    migrated.setdefault("parent_package_id", None); migrated.setdefault("answer_history", []); migrated.setdefault("repository_observations", []); migrated.setdefault("harness", {"enabled": False}); migrated.setdefault("setup", {})["harness_enabled"] = False
    migrated.setdefault("record_field_coverage", coverage_matrix())
    apply_conditionals(migrated); return migrated

def _set_derived_na(document: dict[str, Any], question_id: str, reason: str) -> None:
    document.setdefault("answers", {})[question_id] = answer(None, "NOT_APPLICABLE", "DERIVED_BY_SCRIPT", reason, document.get("respondent", ""))

def apply_conditionals(document: dict[str, Any]) -> None:
    purpose = _value(document, "PKG-002")
    authority = _value(document, "AUT-001")
    if purpose != "CROSS_PROJECT_TRANSFER": _set_derived_na(document, "XFR-SET", "PKG-002 is not CROSS_PROJECT_TRANSFER")
    if authority in (None, "NONE", "NOT_EVALUATED"):
        for qid in ("AUT-002", "AUT-003", "AUT-004", "AUT-005", "AUT-006", "AUT-007-SCOPE"): _set_derived_na(document, qid, "AUT-001 does not claim authority")
    if _value(document, "SEC-001") != "YES": _set_derived_na(document, "SEC-001-CATEGORIES", "SEC-001 is not YES")
    if not document.get("setup", {}).get("harness_enabled"):
        for qid in HARNESS_QUESTION_IDS:
            if qid != "HAR-000": _set_derived_na(document, qid, "HAR-000 is NO")
    else:
        for qid in HARNESS_QUESTION_IDS:
            item = document.get("answers", {}).get(qid)
            if item and item.get("source_type") == "DERIVED_BY_SCRIPT" and item.get("state") == "NOT_APPLICABLE":
                document["answers"].pop(qid)

def set_harness_mode(document: dict[str, Any], enabled: bool) -> None:
    previous = document.get("setup", {}).get("harness_enabled", False)
    if previous != enabled: document.setdefault("answer_history", []).append({"question_id": "HAR-000", "previous": previous, "changed": enabled, "timestamp": now()})
    document.setdefault("setup", {})["harness_enabled"] = enabled; document.setdefault("harness", {})["enabled"] = enabled
    set_answer(document, "HAR-000", "YES" if enabled else "NO")
    apply_conditionals(document); document["updated"] = now()

def coverage_matrix() -> list[dict[str, Any]]:
    return [{"specification_record": section, "required_fields": [name for name, _, _ in fields], "interactive_fields": [name for name, _, _ in fields], "schema_fields": [name for name, _, _ in fields], "rendered_fields": [name for name, _, _ in fields], "tests": True} for section, fields in RECORD_FIELDS.items()]

def set_harness_transition(document: dict[str, Any], transition: str, state: str, **support: Any) -> None:
    if transition not in HARNESS_TRANSITIONS: raise ValueError(f"unknown Harness transition: {transition}")
    if state not in HARNESS_ALLOWED_STATES[transition]: raise ValueError(f"invalid state {state} for {transition}")
    transitions = document.setdefault("harness", {}).setdefault("transitions", {})
    transitions[transition] = {"state": state, **copy.deepcopy(support), "updated": now()}
    document["updated"] = now()

def _transition_state(document: dict[str, Any], transition: str) -> str:
    return document.get("harness", {}).get("transitions", {}).get(transition, {}).get("state", "NONE")

def _transition_support(document: dict[str, Any], transition: str) -> dict[str, Any]:
    return document.get("harness", {}).get("transitions", {}).get(transition, {})

def validate_harness_transitions(document: dict[str, Any], errors: list[str], blockers: list[str]) -> None:
    if not document.get("setup", {}).get("harness_enabled"): return
    states = {transition: _transition_state(document, transition) for transition in HARNESS_TRANSITIONS}
    order = list(HARNESS_TRANSITIONS)
    for index, transition in enumerate(order):
        state = states[transition]
        if state in {"NONE", "NOT_EVALUATED", "NOT_AUTHORIZED", "NOT_VERIFIED"}: continue
        prior = order[index - 1] if index else None
        if prior and states[prior] not in {"PROPOSED", "AUTHORIZED", "DRAFTED", "ACCEPTED", "ACTIVE", "VERIFIED"}:
            errors.append(f"{transition}: invalid transition; prerequisite {prior} is {states[prior]}"); blockers.append(transition)
        support = _transition_support(document, transition)
        if state in {"AUTHORIZED", "ACCEPTED", "ACTIVE", "VERIFIED"}:
            required = {"evidence", "authorizer", "source"} if transition != "verification_status" else {"evidence", "source"}
            missing = sorted(field for field in required if not support.get(field))
            if transition in {"bec_activation", "implementation_authorization", "execution_authorization"}: missing += [field for field in ("scope", "phase", "expiry_or_checkpoint", "stop_condition") if not support.get(field)]
            if missing:
                errors.append(f"{transition}: supporting authority is incomplete ({', '.join(sorted(set(missing)))})"); blockers.append(transition)
    if states["checkpoint_acceptance"] == "ACCEPTED" and states["next_phase_authorization"] == "AUTHORIZED" and not _transition_support(document, "next_phase_authorization").get("separate_authorizer"):
        errors.append("next_phase_authorization: checkpoint acceptance cannot authorize advancement without separate authorizer"); blockers.append("next_phase_authorization")

def set_answer(document: dict[str, Any], question_id: str, value: Any, state: str = "PROVIDED", source_type: str = "HUMAN_DECLARATION", source_reference: str | None = None) -> None:
    previous = document.setdefault("answers", {}).get(question_id)
    if previous is not None and (previous.get("value"), previous.get("state")) != (value, state): document.setdefault("answer_history", []).append({"question_id": question_id, "previous": previous, "timestamp": now()})
    document["answers"][question_id] = answer(value, state, source_type, source_reference, document.get("respondent", "")); document["updated"] = now()
    if question_id in {"PKG-002", "AUT-001", "SEC-001"}: apply_conditionals(document)

def _next_id(document: dict[str, Any], section: str) -> str:
    prefix = ID_PREFIXES.get(section, section[:3].upper()); used = {record["id"] for record in document["records"].get(section, [])} | set(document.get("deleted_ids", [])); number = 1
    while f"{prefix}-{number:03d}" in used: number += 1
    return f"{prefix}-{number:03d}"

def add_record(document: dict[str, Any], section: str, fields: dict[str, Any], source_type: str = "HUMAN_DECLARATION") -> str:
    if section not in ID_PREFIXES and section not in RECORD_FIELDS: raise ValueError(f"unknown repeated section: {section}")
    record_id = _next_id(document, section); stamp = now()
    document["records"].setdefault(section, []).append({"id": record_id, "fields": copy.deepcopy(fields), "source_type": source_type, "source_reference": None, "respondent": document.get("respondent", ""), "created": stamp, "last_edit": stamp}); document["updated"] = now(); return record_id

def collect_record(document: dict[str, Any], section: str, input_fn=input, output_fn=print) -> str | None:
    """Collect one record one field at a time; return None for done/cancel."""
    if section not in RECORD_FIELDS: raise ValueError(f"no field definition for {section}")
    fields = RECORD_FIELDS[section]; values: dict[str, Any] = {}; index = 0
    output_fn(f"Collecting one {section.replace('_', ' ')} record. Type cancel to discard it or back to revisit a field.")
    while index < len(fields):
        name, label, choices = fields[index]; suffix = f" ({', '.join(sorted(choices))})" if choices else ""
        raw = input_fn(f"{label}{suffix}: ").strip(); command = raw.lower()
        if command == "cancel": return None
        if command == "back": index = max(0, index - 1); continue
        if command.startswith("edit "):
            requested = command.split(None, 1)[1]
            matches = [pos for pos, item in enumerate(fields) if item[0] == requested]
            if matches: index = matches[0]
            continue
        if choices and raw.upper() not in choices: output_fn(f"Choose one of: {', '.join(sorted(choices))}"); continue
        if not raw: output_fn("A record field cannot be blank."); continue
        values[name] = raw.upper() if choices else raw; index += 1
    return add_record(document, section, values)

def collect_repeated(document: dict[str, Any], section: str, input_fn=input, output_fn=print) -> list[str]:
    record_ids: list[str] = []
    while True:
        command = input_fn(f"Add {section.replace('_', ' ')} record, or type done: ").strip().lower()
        if command == "done": return record_ids
        if command == "back": continue
        if command == "cancel": return record_ids
        record_id = collect_record(document, section, input_fn, output_fn)
        if record_id: record_ids.append(record_id)

def _git_observation(document: dict[str, Any], path: str, field: str, value: str) -> dict[str, Any]:
    return {"field": field, "value": value, "repository": str(Path(path).resolve()), "snapshot": document.get("answers", {}).get("PKG-006", {}).get("value", "UNKNOWN"), "path": ".", "timestamp": now(), "source_type": "REPOSITORY_OBSERVATION"}

def inspect_repository(document: dict[str, Any], target_path: str, intake_paths: list[str] | None = None) -> dict[str, Any]:
    if document.get("setup", {}).get("inspection") != "READ_ONLY_INSPECTION": raise PermissionError("read-only inspection is disabled")
    target = Path(target_path).expanduser().resolve(); allowed = {str(Path(item)) for item in (intake_paths or [])}
    commands = [("repository_identity", ["git", "rev-parse", "--show-toplevel"]), ("commit", ["git", "rev-parse", "HEAD"]), ("branch", ["git", "branch", "--show-current"]), ("status_short", ["git", "status", "--short", "--ignored", "--untracked-files=all"]), ("tracked_files", ["git", "ls-files"]), ("untracked_files", ["git", "ls-files", "--others", "--exclude-standard"])]
    observations = []
    for field, command in commands:
        try: completed = subprocess.run(command, cwd=target, capture_output=True, text=True, timeout=10, check=False)
        except (OSError, subprocess.SubprocessError) as exc: completed = None; value = f"UNAVAILABLE:{type(exc).__name__}"
        else: value = completed.stdout.strip() if completed.returncode == 0 else f"UNAVAILABLE:exit_{completed.returncode}"
        observations.append(_git_observation(document, str(target), field, value))
    document["repository_observations"] = observations; document["inspection"] = {"target": str(target), "allowlisted_paths": sorted(allowed), "read_only": True, "commands": [command for _, command in commands]}; document["updated"] = now(); return {"repository": str(target), "observations": observations}

def find_record(document: dict[str, Any], record_id: str) -> dict[str, Any]:
    for records in document["records"].values():
        for record in records:
            if record["id"] == record_id: return record
    raise KeyError(record_id)

def edit_record(document: dict[str, Any], record_id: str, fields: dict[str, Any]) -> None:
    record = find_record(document, record_id); record["fields"] = copy.deepcopy(fields); record["last_edit"] = now(); document["updated"] = now()

def delete_record(document: dict[str, Any], record_id: str) -> None:
    for records in document["records"].values():
        for index, record in enumerate(records):
            if record["id"] == record_id: records.pop(index); document.setdefault("deleted_ids", []).append(record_id); document["updated"] = now(); return
    raise KeyError(record_id)

def validate_document_shape(document: dict[str, Any]) -> None:
    if not isinstance(document, dict) or document.get("schema_version") != SCHEMA_VERSION or not isinstance(document.get("records"), dict): raise ValueError("invalid answer document shape")
    for section in ID_PREFIXES:
        if not isinstance(document["records"].get(section), list): raise ValueError(f"records.{section} must be a list")
        for record in document["records"][section]:
            if not re.fullmatch(r"[A-Z]+-\d{3}", str(record.get("id", ""))): raise ValueError("record has invalid stable ID")

def save_answers(document: dict[str, Any], path: str) -> None:
    validate_document_shape(document); target = Path(path); target.parent.mkdir(parents=True, exist_ok=True); payload = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle: handle.write(payload); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)

def load_answers(path: str) -> dict[str, Any]:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        if document.get("schema_version") == LEGACY_SCHEMA_VERSION: return migrate_v01_to_v02(document)
        validate_document_shape(document); return document
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid saved answers: {exc}") from exc

def _value(document: dict[str, Any], qid: str, default: Any = None) -> Any:
    item = document.get("answers", {}).get(qid, {}); return "UNKNOWN" if item.get("state") == "UNKNOWN" else item.get("value", default)

def _records(document: dict[str, Any], section: str) -> list[dict[str, Any]]: return document.get("records", {}).get(section, [])
def _field(record: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in record.get("fields", {}): return record["fields"][name]
    return None

def validate_answers(document: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []; warnings: list[str] = []; blockers: list[str] = []; answers = document.get("answers", {})
    for qid, item in answers.items():
        if item.get("state") not in STATES: errors.append(f"{qid}: invalid answer state"); blockers.append(qid)
        if item.get("source_type") not in PROVENANCE: errors.append(f"{qid}: invalid provenance"); blockers.append(qid)
    ids = {record["id"] for records in document.get("records", {}).values() for record in records}
    for section in ("functional_requirements", "non_functional_requirements", "acceptance_criteria", "phases", "artifacts"):
        for record in _records(document, section):
            refs = _field(record, "linked_requirement_ids", "requirement_ids", "linked_acceptance_criterion_ids", "related_ids") or []; refs = [refs] if isinstance(refs, str) else refs
            for ref in refs:
                if ref not in ids: errors.append(f"{record['id']}: invalid cross-reference {ref}"); blockers.append(record["id"])
    authority = _value(document, "AUT-001", "NOT_EVALUATED")
    if authority not in (None, "NONE", "NOT_EVALUATED"):
        for qid in ("AUT-002", "AUT-003", "AUT-004", "AUT-005", "AUT-006"):
            if not _value(document, qid): errors.append(f"{qid}: required for claimed authority"); blockers.append(qid)
    if authority == "IMPLEMENTATION_WITHIN_EXACT_SCOPE":
        if not any(_field(phase, "status") == "ACCEPTED" for phase in _records(document, "phases")): errors.append("AUT-001: implementation requires an accepted phase"); blockers.append("AUT-001")
        if not _records(document, "acceptance_criteria"): errors.append("AC-SET: implementation requires acceptance criteria"); blockers.append("AC-SET")
        if not _value(document, "SEC-003"): errors.append("SEC-003: implementation requires rollback or recovery"); blockers.append("SEC-003")
    for section in ("functional_requirements", "non_functional_requirements"):
        for record in _records(document, section):
            if _field(record, "status") in {"ACCEPTED", "IMPLEMENTED", "VERIFIED"} and not _field(record, "source"): errors.append(f"{record['id']}: accepted claim has no source"); blockers.append(record["id"])
    evidence = _records(document, "evidence"); evidence_by_id = {record["id"]: record for record in evidence}
    for criterion in _records(document, "acceptance_criteria"):
        if _field(criterion, "status") == "PASSED":
            refs = _field(criterion, "evidence_ids", "evidence") or []; refs = [refs] if isinstance(refs, str) else refs
            if not any(ref in evidence_by_id and _field(evidence_by_id[ref], "result") == "PASS" for ref in refs): errors.append(f"{criterion['id']}: passed criterion lacks PASS evidence"); blockers.append(criterion["id"])
    for phase in _records(document, "phases"):
        if _field(phase, "status") in {"ACCEPTED", "CLOSED"} and not _field(phase, "authority_source"): errors.append(f"{phase['id']}: accepted or closed phase lacks authority source"); blockers.append(phase["id"])
    for conflict in _records(document, "conflicts"):
        if _field(conflict, "status") == "OPEN": errors.append(f"{conflict['id']}: unresolved material conflict"); blockers.append(conflict["id"])
    if any(item.get("state") in {"UNKNOWN", "DEFERRED", "TO_BE_INSPECTED"} for item in answers.values()): warnings.append("material answers remain unresolved")
    final_ids = ("FIN-001", "FIN-002", "FIN-003")
    if any(_value(document, qid) != "YES" for qid in final_ids): errors.append("FIN-001..FIN-003: final attestation incomplete"); blockers.extend(qid for qid in final_ids if _value(document, qid) != "YES")
    validate_harness(document, errors, warnings, blockers)
    status = "BLOCKED" if errors else "DRAFT"; gates = {}; prior = True
    conditions = {"A": (bool(_value(document, "OVR-001") and _records(document, "actors") and _value(document, "BND-001") and _value(document, "BND-002") and _value(document, "OUT-001") and _value(document, "OUT-002")), "problem, actors, boundary, outcomes"), "B": (authority == "IMPLEMENTATION_WITHIN_EXACT_SCOPE" and not errors, "accepted authorized phase, criteria, validation, rollback"), "C": (not errors and bool(evidence), "traceability, evidence, security boundaries, limitations"), "D": (_value(document, "HND-001") in {"ACCEPTED", "ACCEPTED_WITH_CHANGES"} and not errors, "checkpoint classification and explicit next-phase authorization")}
    for key, (condition, description) in conditions.items():
        passed = bool(condition and prior); prior = passed; gates[key] = {"result": "PASS" if passed else "FAIL", "satisfied": [description] if passed else [], "failed": [] if passed else [description], "blocking_ids": sorted(set(blockers)), "human_decision_or_evidence": "Authorized human review and linked evidence required"}
    return {"status": status, "errors": errors, "warnings": warnings, "blocking_ids": sorted(set(blockers)), "gates": gates, "next_permitted_action": "HUMAN_REVIEW_ONLY" if errors else (_value(document, "HND-007") or "HUMAN_REVIEW_ONLY")}

def validate_harness(document: dict[str, Any], errors: list[str], warnings: list[str], blockers: list[str]) -> None:
    if not document.get("setup", {}).get("harness_enabled"): return
    stage = _value(document, "HAR-001")
    discovery = _value(document, "HAR-011")
    if discovery in {"PARTIAL", "EMPTY", "NOISY", "STALE", "CONTRADICTORY"} and not _value(document, "HAR-013"):
        errors.append("HAR-013: incomplete discovery requires fallback or human disposition"); blockers.append("HAR-013")
    if discovery == "EMPTY" and _value(document, "HAR-011") == "EMPTY": warnings.append("HAR-011: empty means NOT_FOUND_BY_THIS_METHOD, not absence")
    reconciliation = _value(document, "HAR-008")
    if isinstance(reconciliation, dict) and reconciliation.get("result") in {"FAIL", "BLOCKED"}:
        errors.append("HAR-008: intake reconciliation is blocked"); blockers.append("HAR-008")
    if _value(document, "HAR-021") in {"commit_change", "dirty_manifest_change"}:
        errors.append("HAR-021: package is stale until snapshot reconciliation"); blockers.append("HAR-021")
    if stage == "IMPLEMENTATION_HANDOFF":
        if _value(document, "HAR-018") != "ACTIVE" or _value(document, "HAR-019") not in {"AUTHORIZED", "ACTIVE"}:
            errors.append("HAR-018/HAR-019: implementation handoff requires active BEC and implementation authorization"); blockers.extend(["HAR-018", "HAR-019"])
    execution = _value(document, "HAR-019")
    if execution == "AUTHORIZED":
        for qid in ("HAR-003", "HAR-005", "HAR-012", "HAR-023", "HND-008"):
            if not _value(document, qid): errors.append(f"{qid}: execution authorization support is incomplete"); blockers.append(qid)
    if _value(document, "HAR-017") == "ACCEPTED" and _value(document, "HAR-018") == "ACTIVE" and _value(document, "HAR-019") != "AUTHORIZED": warnings.append("HAR-017/HAR-018: BEC acceptance or activation does not authorize implementation")
    validate_harness_transitions(document, errors, blockers)
    document.setdefault("harness", {})["state"] = {field: harness_state_value(document, field) for field in HARNESS_STATE_FIELDS}

def harness_state_value(document: dict[str, Any], field: str) -> Any:
    mapping = {"pipeline_stage": "HAR-001", "run_type": "HAR-002", "target_repository": "HAR-003", "harness_repository": "HAR-003", "evidence_output_location": "HAR-004", "repository_snapshot": "HAR-005", "dirty_state_manifest": "HAR-006", "snapshot_state": "HAR-021", "intake_policy": "HAR-007", "intake_reconciliation": "HAR-008", "discovery_providers": "HAR-009", "discovery_compatibility": "HAR-010", "discovery_result_classification": "HAR-011", "fallback_method": "HAR-013", "active_bec": "HAR-018", "bec_drafting_authorization": "HAR-016", "bec_acceptance": "HAR-017", "bec_activation": "HAR-018", "implementation_authorization": "HAR-019", "execution_authorization": "HAR-019", "verification_status": "HAR-019", "checkpoint_acceptance": "HND-001", "next_phase_authorization": "HAR-019", "package_authority": "HAR-022", "package_freshness": "HAR-021", "next_permitted_action": "HND-007", "human_decision_required": "HND-008"}
    if field == "package_id": return document.get("package_id", "UNKNOWN")
    if field == "parent_package_id": return document.get("parent_package_id") or "NONE"
    transition_map = {"active_bec": "bec_activation", "bec_drafting_authorization": "bec_drafting_authorization", "bec_acceptance": "bec_acceptance", "bec_activation": "bec_activation", "implementation_authorization": "implementation_authorization", "execution_authorization": "execution_authorization", "verification_status": "verification_status"}
    if field in transition_map: return _transition_state(document, transition_map[field])
    if field == "checkpoint_acceptance": return _transition_state(document, "checkpoint_acceptance") if "checkpoint_acceptance" in document.get("harness", {}).get("transitions", {}) else "NOT_EVALUATED"
    if field == "next_permitted_action": return _value(document, "HND-007", "HUMAN_REVIEW_ONLY") or "HUMAN_REVIEW_ONLY"
    return _value(document, mapping.get(field, ""), "NOT_EVALUATED")

def mark_snapshot_drift(document: dict[str, Any], reason: str = "commit_change") -> None:
    set_answer(document, "HAR-021", reason); document.setdefault("harness", {})["stale"] = True

def safe_text(value: Any) -> str:
    return ("UNKNOWN" if value is None else str(value)).replace("|", "\\|").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")

def redact_fields(fields: dict[str, Any], restricted: bool) -> dict[str, Any]:
    if not restricted: return copy.deepcopy(fields)
    return {key: ("[REDACTED:RESTRICTED_CONTENT]" if any(word in key.lower() for word in ("content", "payload", "secret", "token", "key", "password")) else value) for key, value in fields.items()}

def render_package(document: dict[str, Any], template_path: str, validation: dict[str, Any]) -> str:
    template = Path(template_path).read_text(encoding="utf-8"); replacements = {"<name>": _value(document, "PKG-001", "UNKNOWN"), "<person or team>": _value(document, "PKG-003", "UNKNOWN"), "<person or agent>": _value(document, "PKG-004", "UNKNOWN"), "<DRAFT / READY_FOR_REVIEW / ACCEPTED / SUPERSEDED / BLOCKED>": validation["status"], "<path / URL / identifier>": _value(document, "PKG-005", "UNKNOWN"), "<commit, tag, release, digest, or date>": _value(document, "PKG-006", "UNKNOWN")}
    for old, new in replacements.items(): template = template.replace(old, safe_text(new))
    lines = [template.rstrip(), "", "---", "", "## Generated normalized answers", "", f"- Schema: `{SCHEMA_VERSION}`", f"- Template digest: `{document.get('template_version', 'UNKNOWN')}`", f"- Package status: `{validation['status']}`", ""]
    for qid in sorted(document.get("answers", {})):
        item = document["answers"][qid]; lines.append(f"- **{qid}**: {safe_text(item.get('value'))} (`{item.get('state')}`, `{item.get('source_type')}`)")
    restricted = _value(document, "SEC-001") == "YES"
    for section, records in document.get("records", {}).items():
        if not records: continue
        lines.extend(["", f"### {section.replace('_', ' ').title()}", "", "| ID | Fields | Provenance |", "| --- | --- | --- |"])
        for record in records: lines.append(f"| {record['id']} | {safe_text(json.dumps(redact_fields(record.get('fields', {}), restricted), sort_keys=True, ensure_ascii=True))} | {record.get('source_type', 'HUMAN_DECLARATION')} |")
    if document.get("setup", {}).get("harness_enabled"):
        lines.extend(["", "## SDLC Harness pipeline", "", "| Field | Value |", "| --- | --- |"])
        state = document.get("harness", {}).get("state", {}) or {field: harness_state_value(document, field) for field in HARNESS_STATE_FIELDS}
        for field in HARNESS_STATE_FIELDS: lines.append(f"| {field.replace('_', ' ').title()} | {safe_text(state.get(field, 'NOT_EVALUATED'))} |")
    return "\n".join(lines) + "\n"

def render_validation(document: dict[str, Any], validation: dict[str, Any], output_paths: list[str]) -> str:
    lines = ["# Artifacts Package Validation", "", f"- Status: `{validation['status']}`", f"- Generated outputs: {', '.join(f'`{p}`' for p in output_paths)}", "", "## Errors"] + ([f"- {safe_text(error)}" for error in validation["errors"]] or ["- None"])
    lines += ["", "## Warnings"] + ([f"- {safe_text(warning)}" for warning in validation["warnings"]] or ["- None"]) + ["", f"## Blocking IDs\n\n`{', '.join(validation['blocking_ids']) or 'NONE'}`", "", "## Gates"]
    for key, gate in validation["gates"].items(): lines += [f"### Gate {key}: `{gate['result']}`", f"- Satisfied: {safe_text('; '.join(gate['satisfied']) or 'None')}", f"- Failed: {safe_text('; '.join(gate['failed']) or 'None')}", f"- Required next: {safe_text(gate['human_decision_or_evidence'])}"]
    lines += ["", f"## Next permitted action\n\n`{validation['next_permitted_action']}`", "", "## Generation metadata", f"- Answer digest: `{hashlib.sha256(json.dumps(document, sort_keys=True).encode()).hexdigest()}`", f"- Generated: `{document.get('updated', 'UNKNOWN')}`", "", "## Output digests"]
    for path in output_paths:
        output = Path(path); digest = hashlib.sha256(output.read_bytes()).hexdigest() if output.exists() else "PENDING"
        lines.append(f"- `{path}`: `{digest}`")
    return "\n".join(lines) + "\n"

def generate(document: dict[str, Any], overwrite: bool = False) -> list[Path]:
    validation = validate_answers(document); output = Path(document["setup"]["output_path"]).expanduser().resolve(); output.mkdir(parents=True, exist_ok=True); template = Path(document["setup"]["template_path"]).expanduser().resolve(); document["template_version"] = template_digest(str(template))
    package = output / "artifacts_package.md"; validation_path = output / "artifacts_package_validation.md"; answer_path = output / "artifacts_package_answers.json"
    multi_names = ["00-overview-and-current-state.md", "01-requirements-and-acceptance.md", "02-architecture-and-feature-map.md", "03-decisions-risks-and-boundaries.md", "04-build-sequence-and-validation.md", "05-artifact-index-and-evidence-ledger.md"]
    if document["setup"].get("harness_enabled"): multi_names.append("06-sdlc-harness-pipeline.md")
    output_files = [output / name for name in multi_names] if document["setup"].get("shape") == "STANDARD_MULTI_FILE" else [package]
    paths = [answer_path, *output_files, validation_path]
    if not overwrite and any(path.exists() for path in paths): raise FileExistsError("output exists; explicit overwrite confirmation required")
    save_answers(document, str(answer_path)); rendered = render_package(document, str(template), validation)
    if output_files == [package]: package.write_text(rendered, encoding="utf-8")
    else:
        source_sections = re.findall(r"(?ms)^## \d+\. .*?(?=^## \d+\. |\Z)", Path(template).read_text(encoding="utf-8"))
        mapping = [(0, "Overview and current state"), (1, "Requirements and acceptance"), (2, "Architecture and feature map"), (3, "Decisions, risks, and boundaries"), (4, "Build sequence and validation"), (5, "Artifact index and evidence ledger")]
        for index, path in enumerate(output_files[:6]):
            source = source_sections[index] if index < len(source_sections) else ""
            body = render_package(document, str(template), validation) if not source else source
            path.write_text(f"# {mapping[index][1]}\n\nPackage: {safe_text(document.get('package_id', 'UNKNOWN'))}\n\n{body.strip()}\n", encoding="utf-8")
        if document["setup"].get("harness_enabled"):
            state = document.get("harness", {}).get("state", {})
            content = ["# SDLC Harness pipeline", "", f"Package: {safe_text(document.get('package_id', 'UNKNOWN'))}", "", "| Field | Value |", "| --- | --- |"]
            content.extend(f"| {field.replace('_', ' ').title()} | {safe_text(state.get(field, harness_state_value(document, field)))} |" for field in HARNESS_STATE_FIELDS)
            output_files[6].write_text("\n".join(content) + "\n", encoding="utf-8")
    validation_path.write_text(render_validation(document, validation, [str(path) for path in paths]), encoding="utf-8"); return paths

def run_validated_command(command: str, cwd: str, execute: bool = False, allowed_commands: set[str] | None = None) -> dict[str, Any]:
    if re.search(r"(?:\brm\b|\brmdir\b|\bdel\b|\berase\b|\bformat\b|\btruncate\b|\bdrop\s+table\b|\bshutdown\b|\bmkfs\b)", command, re.I): return {"result": "REJECTED", "reason_code": "DESTRUCTIVE_COMMAND"}
    if re.search(r"\bgortex\b", command, re.I): return {"result": "REJECTED", "reason_code": "LIVE_GORTEX_PROHIBITED"}
    if not execute: return {"result": "NOT_RUN", "reason_code": "EXECUTION_DISABLED"}
    if command not in (allowed_commands or set()): return {"result": "REJECTED", "reason_code": "COMMAND_NOT_ALLOWLISTED"}
    completed = subprocess.run(shlex.split(command), cwd=cwd, capture_output=True, text=True, timeout=60, check=False); return {"result": "PASS" if completed.returncode == 0 else "FAIL", "exit_code": completed.returncode, "stdout": completed.stdout[-4000:], "stderr": completed.stderr[-4000:], "source_type": "RUNTIME_EVIDENCE"}

def interactive_start(path: str, resume: bool = False) -> int:
    answer_path = Path(path)
    if resume:
        document = load_answers(path)
    else:
        base = answer_path.parent; template = base / "reusable_artifacts_package_template.md"; alternate = base / "reusable_artifacts_package_template (1).md"; template = template if template.exists() else alternate
        document = new_answers(str(template), str(base))
    qids = list(QUESTION_CATALOG); index = 0
    while index < len(qids):
        qid = qids[index]; question = QUESTION_CATALOG[qid]
        print(f"\n{qid}: {question['prompt']}\nHelp: answer explicitly; state UNKNOWN, NOT_APPLICABLE, TO_BE_INSPECTED, or DEFERRED when appropriate.\nDo not enter secrets, credentials, tokens, keys, or sensitive payloads.")
        raw = input("> ").strip(); command = raw.lower()
        if command == "save": save_answers(document, path); print(f"Saved {path}"); continue
        if command == "review": print(json.dumps(document, indent=2, sort_keys=True)); continue
        if command == "quit": save_answers(document, path); print(f"Saved {path}"); return 0
        if command == "back": index = max(0, index - 1); continue
        if command.startswith("edit "):
            requested = raw.split(None, 1)[1].upper(); index = qids.index(requested) if requested in qids else index; continue
        if question["type"] == "REPEATED_RECORD":
            section = REPEATED_QID_TO_SECTION.get(qid)
            if section in RECORD_FIELDS:
                if command != "done": collect_repeated(document, section, input_fn=input, output_fn=print)
                save_answers(document, path); index += 1; continue
        choices = ENUM_CHOICES.get(qid)
        if choices and raw.upper() not in choices and raw.upper() not in STATES:
            print(f"Choose one of: {', '.join(sorted(choices))}"); continue
        state = raw.upper() if raw.upper() in STATES else "PROVIDED"
        if qid == "HAR-000" and state == "PROVIDED" and raw.upper() in {"YES", "NO"}: set_harness_mode(document, raw.upper() == "YES")
        else: set_answer(document, qid, None if state != "PROVIDED" else raw, state)
        save_answers(document, path); index += 1
    print(json.dumps(validate_answers(document), indent=2)); return 0

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest="command", required=True); start = sub.add_parser("start"); start.add_argument("--answers", default="artifacts_package_answers.json"); resume = sub.add_parser("resume"); resume.add_argument("--answers", required=True); validate = sub.add_parser("validate"); validate.add_argument("--answers", required=True); generate_parser = sub.add_parser("generate"); generate_parser.add_argument("--answers", required=True); generate_parser.add_argument("--yes", action="store_true"); args = parser.parse_args(argv)
    if args.command == "start": return interactive_start(args.answers)
    document = load_answers(args.answers)
    if args.command == "validate": print(json.dumps(validate_answers(document), indent=2)); return 0
    if args.command == "resume": return interactive_start(args.answers, resume=True)
    try: paths = generate(document, overwrite=args.yes)
    except FileExistsError as exc: print(str(exc), file=sys.stderr); return 2
    print("\n".join(str(path) for path in paths)); return 0

if __name__ == "__main__": sys.exit(main())