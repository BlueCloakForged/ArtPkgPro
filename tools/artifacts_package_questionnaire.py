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

# Guidance is deliberately explanatory only. It may narrow the path through the
# questionnaire when a prior answer makes a question inapplicable, but it never
# infers a human judgment, approval, authority, or requirement.
QUESTION_GROUPS = {
    "SET": ("Setup", "Configure the template, output location, and permitted operating mode."),
    "PKG": ("Package context", "Identify what this package covers and the source material it describes."),
    "AUT": ("Authority", "Record existing human authority precisely; this questionnaire never creates it."),
    "OVR": ("Problem and outcome", "Describe the problem, intended result, and current work state."),
    "BND": ("Scope boundary", "Make the included and excluded work explicit before it is handed off."),
    "DAT": ("Data", "Describe data handling, lineage, and retention constraints."),
    "SEC": ("Safety and security", "Record restricted-content handling and safe failure behavior."),
    "OUT": ("Outcomes", "State both the desired result and the unacceptable result to avoid."),
    "HND": ("Handoff", "Prepare a truthful checkpoint for the next human reviewer."),
    "FIN": ("Final review", "Confirm completion, sensitive-content, and authority checks before generation."),
    "HAR": ("SDLC Harness", "Record pipeline state only; recording it does not authorize implementation or execution."),
    "ACT": ("Actors", "Identify people, roles, or systems affected by the package."),
    "UC": ("Use cases", "Record a concrete user or system interaction and its observable outcome."),
    "FC": ("Failure cases", "Record unsafe conditions and the required fail-closed or recovery behavior."),
    "FR": ("Functional requirements", "Record a human-owned behavior the project must provide."),
    "NFR": ("Non-functional requirements", "Record measurable quality, operational, or policy constraints."),
    "AC": ("Acceptance criteria", "Define how a requirement will be shown to pass or fail."),
    "EVD": ("Evidence", "Record what was observed, where it came from, and its limitations."),
}
QUESTION_GUIDANCE = {
    "PKG-006": ("Identify the exact code or document state this package describes so a later reviewer can reproduce the context.", "A commit such as a1b2c3d, a release such as v0.3.0, or a dated snapshot."),
    "AUT-001": ("Record authority that already exists. Selecting a value records it; it does not grant any permission.", "DISCOVERY_ONLY, REVIEW_ONLY, or NONE when no authority has been granted."),
    "BND-001": ("Name the behavior, components, or decisions this package is allowed to discuss or change.", "Order validation and its public API contract."),
    "BND-002": ("Name nearby work that must not be treated as part of this package.", "Payment processing, database migration, and deployment automation."),
    "SEC-001": ("Indicate whether restricted or sensitive content is relevant so the follow-up safety questions can be shown only when needed.", "YES for customer data or credentials; NO when none is in scope."),
    "HAR-000": ("Choose whether this package will be consumed by the SDLC Harness. YES reveals its state questions; NO keeps them out of scope.", "YES only when the package is actually intended for that workflow."),
}
TYPE_EXAMPLES = {
    "PATH_OR_URI": "A relative path, repository URL, or other durable reference.",
    "ENUM": "Choose one listed value, or use UNKNOWN or NOT_APPLICABLE when that is truthful.",
    "BOOLEAN": "YES or NO.",
    "MULTI_ENUM": "A comma-separated list of applicable values, or NOT_APPLICABLE.",
    "REPEATED_RECORD": "Type add to enter one record, then done when there are no more records to add.",
    "HARNESS": "A documented pipeline state backed by the appropriate human decision or evidence.",
    "SHORT_TEXT": "A short, specific phrase or identifier.",
    "LONG_TEXT": "A concise explanation with enough detail for a later reviewer.",
}


def question_guidance(question_id: str, question: dict[str, Any]) -> dict[str, str]:
    """Return terminal-only context; it is not an answer or an inference."""
    prefix = "HAR" if question_id.startswith("HAR-") else question_id.split("-", 1)[0]
    group, default_meaning = QUESTION_GROUPS.get(prefix, ("Questionnaire", "Provide the information needed to make this package reviewable."))
    meaning, example = QUESTION_GUIDANCE.get(question_id, (default_meaning, TYPE_EXAMPLES.get(question["type"], "A specific, reviewable answer.")))
    return {"group": group, "meaning": meaning, "example": example}


def format_terminal_question(question_id: str, question: dict[str, Any]) -> str:
    guidance = question_guidance(question_id, question)
    return "\n".join([
        f"\n[{guidance['group']}]",
        f"{question_id}: {question['prompt']}",
        f"What this question means: {guidance['meaning']}",
        f"Example: {guidance['example']}",
        "Help: answer explicitly; state UNKNOWN, NOT_APPLICABLE, TO_BE_INSPECTED, or DEFERRED when appropriate.",
        "Do not enter secrets, credentials, tokens, keys, or sensitive payloads.",
    ])


def conditional_skip_reason(document: dict[str, Any], question_id: str) -> str | None:
    """Return why a derived conditional question should not be shown interactively."""
    item = document.get("answers", {}).get(question_id, {})
    if item.get("state") == "NOT_APPLICABLE" and item.get("source_type") == "DERIVED_BY_SCRIPT":
        return item.get("source_reference") or "a prior answer made this question not applicable"
    return None


def should_ask_question(document: dict[str, Any], question_id: str) -> bool:
    return conditional_skip_reason(document, question_id) is None


def record_field_guidance(section: str, name: str, label: str) -> tuple[str, str]:
    """Explain repeated-record fields without suggesting a substantive answer."""
    common = {
        "source": ("Identify where this information came from; it is not automatically an approval.", "A human declaration, policy reference, or evidence ID."),
        "owner": ("Name the person or role responsible for this item or its follow-up.", "Product owner or Security reviewer."),
        "status": ("Record the current state, not a hoped-for future state.", "PROPOSED, OPEN, or NOT_RUN as applicable."),
        "evidence": ("Reference evidence that supports this record and note its limits elsewhere when needed.", "EVD-001 or a durable source reference."),
    }
    return common.get(name, (f"Provide the {label.lower()} for this {section.replace('_', ' ')} record.", "A specific, reviewable value."))

def resolve_template_path(base_dir: str | os.PathLike[str]) -> str:
    base = Path(base_dir).expanduser().resolve()
    candidates = [
        base / "reusable_artifacts_package_template.md",
        base / "reusable_artifacts_package_template (1).md",
    ]
    repo_root = Path(__file__).resolve().parent.parent
    if repo_root.exists():
        candidates.extend([
            repo_root / "reusable_artifacts_package_template.md",
            repo_root / "reusable_artifacts_package_template (1).md",
        ])
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return str(base / "reusable_artifacts_package_template.md")


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


def _seed_confidence(qid: str, value: Any, source_text: str, basis: str = "KEYWORD_MATCH") -> tuple[int, str, str]:
    """Score confidence based on extraction method and source signals.
    
    basis: EXACT_HEADER_MATCH (90+), SECTION_MATCH (85), STRUCTURED_TABLE (82), 
           KEYWORD_MATCH (60), FALLBACK_DEFAULT (40)
    """
    text = (source_text or "").lower()
    value_text = str(value or "").lower()
    
    # Base score by extraction method
    if basis == "EXACT_HEADER_MATCH":
        score = 92
    elif basis == "SECTION_MATCH":
        score = 85
    elif basis == "STRUCTURED_TABLE":
        score = 82
    elif basis == "KEYWORD_MATCH":
        score = 65
    else:  # FALLBACK_DEFAULT
        score = 40
    
    # High-confidence question types (established by context)
    if qid in {"PKG-001", "PKG-002", "PKG-008", "PKG-009", "BND-001", "BND-002", "AUT-001", "AUT-003", "AUT-004", "AUT-005", "AUT-008", "AUT-009"}:
        score = max(score, 88)
    if qid == "PKG-001" and "offline support call intelligence" in value_text:
        score = 96
    if qid == "PKG-002" and "discovery" in value_text and ("discovery context" in text or "not approved implementation contract" in text):
        score = 95
    if qid == "AUT-001" and str(value).upper() in {"NOT_EVALUATED", "NONE"} and ("not formally identified" in text or "not an approved implementation contract" in text or "not yet" in text):
        score = 95
    
    # Lower-confidence questions
    if qid in {"PKG-003", "PKG-006", "AUT-002", "AUT-006"}:
        score = min(score, 55)
    
    # Medium-confidence narrative questions
    if qid in {"OVR-001", "OVR-002", "DAT-001", "DAT-002"}:
        score = max(score, 80)
    
    # Negative indicator adjustments
    if any(token in text for token in ("not approved", "not yet", "unknown", "deferred", "unresolved", "not formally identified")):
        if str(value).upper() in {"UNKNOWN", "NOT_EVALUATED", "NOT_APPLICABLE", "DEFERRED"}:
            score = min(99, score + 10)
        else:
            score = max(35, score - 12)
    
    # Explicit scope exclusion boost
    if any(token in text for token in ("production deployment", "central sync", "customer recording", "external cloud processing")) and qid in {"BND-002", "AUT-005", "PKG-009"}:
        score = min(99, score + 4)
    
    # Environmental/contextual uncertainty
    if qid in {"PKG-004", "PKG-005"}:
        score = max(35, score - 5)
    
    score = max(0, min(100, score))
    if score >= 90: label = "HIGH"; priority = "LOW"
    elif score >= 75: label = "MEDIUM"; priority = "MEDIUM"
    elif score >= 50: label = "MEDIUM"; priority = "HIGH"
    else: label = "LOW"; priority = "HIGH"
    return score, label, priority


def render_seed_summary(seeded: dict[str, Any]) -> str:
    answers = seeded.get("answers", {})
    rows = []
    for qid, item in answers.items():
        score = int(item.get("confidence_score", 0))
        rows.append({
            "qid": qid,
            "value": item.get("value"),
            "state": item.get("state", "PROVIDED"),
            "score": score,
            "priority": item.get("review_priority", "HIGH"),
            "confidence_label": item.get("confidence_label", "LOW"),
        })
    rows.sort(key=lambda row: (row["score"], row["priority"] == "LOW", row["qid"]))
    review_first = [row for row in rows if row["score"] < 75 or row["priority"] == "HIGH"]
    review_first.extend([row for row in rows if row not in review_first])
    lines = [
        "# Seeded ArtPkg Answer Summary",
        "",
        "- Source: " + str(seeded.get("source_path", "UNKNOWN")),
        "- Seeded at: " + str(seeded.get("seeded_at", now())),
        "",
        "## Review-first priorities",
        "",
        "The questions below are ordered to surface low-confidence or high-review-priority items before the rest. This is for human editing, not for automatic approval.",
        "",
        "### Needs human review first",
        "",
        "| Question ID | Answer | State | Confidence score | Confidence label | Review priority |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for row in review_first:
        lines.append(f"| {row['qid']} | {safe_text(row['value'])} | {row['state']} | {row['score']} | {row['confidence_label']} | {row['priority']} |")
        lines.append("")
        lines.append(f"Action checklist for {row['qid']}: ")
        lines.append("- [ ] Accept")
        lines.append("- [ ] Edit")
        lines.append("- [ ] Reject")
        lines.append("- Suggested decision: review the source and update the answer before final generation.")
        lines.append("")
    lines.extend(["", "### Lower-priority items", "", "| Question ID | Answer | State | Confidence score | Confidence label | Review priority |", "| --- | --- | --- | ---: | --- | --- |"])
    for row in rows:
        if row not in review_first:
            lines.append(f"| {row['qid']} | {safe_text(row['value'])} | {row['state']} | {row['score']} | {row['confidence_label']} | {row['priority']} |")
    accepted = 0
    edited = 0
    rejected = 0
    lines.extend(["", "## Final decision summary", "", "- Accepted: " + str(accepted), "- Edited: " + str(edited), "- Rejected: " + str(rejected), "", "Use this section to record the final human disposition of the review-first items before passing the package to generation."])
    return "\n".join(lines) + "\n"


def _add_seed_record(seeded: dict[str, Any], section: str, fields: dict[str, Any], source_text: str, basis: str = "KEYWORD_MATCH") -> None:
    score, label, priority = _seed_confidence(section, fields, source_text, basis)
    seeded.setdefault("records", {}).setdefault(section, []).append({
        "id": f"{section[:3].upper()}-{len(seeded.setdefault('records', {}).get(section, [])) + 1:03d}",
        "fields": fields,
        "source_type": "SOURCE_ARTIFACT",
        "source_reference": seeded.get("source_path"),
        "respondent": "agent",
        "confidence_score": score,
        "confidence_label": label,
        "review_priority": priority,
        "confidence_basis": f"Deterministic {basis} from the pre-artifacts source",
    })


def _parse_numbered_sections(text: str) -> dict[int, str]:
    """Extract content by numbered section heading (## 1., ## 2., etc.)."""
    sections: dict[int, str] = {}
    current_num: int | None = None
    current_content: list[str] = []
    
    for line in text.splitlines():
        # Match numbered headings: "## 1. Section Name" or "## 14. Decisions"
        match = re.match(r'^#{1,3}\s+(\d+)\.\s+', line)
        if match:
            if current_num is not None and current_content:
                sections[current_num] = "\n".join(current_content).strip()
            current_num = int(match.group(1))
            current_content = []
        elif current_num is not None:
            current_content.append(line)
    
    if current_num is not None and current_content:
        sections[current_num] = "\n".join(current_content).strip()
    
    return sections


def _parse_markdown_table(text: str) -> list[dict[str, str]]:
    """Extract table rows from Markdown table format."""
    rows: list[dict[str, str]] = []
    lines = text.strip().split("\n")
    
    if len(lines) < 3:
        return rows
    
    # Find header line (starts with |)
    header_line = None
    separator_idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("|"):
            header_line = line
            if i + 1 < len(lines) and re.search(r'\|[\s-:|]+\|', lines[i + 1]):
                separator_idx = i + 1
                break
    
    if header_line is None or separator_idx < 0:
        return rows
    
    # Parse header
    headers = [h.strip() for h in header_line.split("|")[1:-1]]
    
    # Parse data rows
    for line in lines[separator_idx + 1:]:
        if not line.strip().startswith("|"):
            break
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) == len(headers) and any(cells):  # Skip empty rows
            rows.append(dict(zip(headers, cells)))
    
    return rows


def _extract_from_section(text: str, section_num: int | None, aliases: tuple[str, ...], field_name: str) -> list[dict[str, Any]]:
    """Extract items from a specific numbered section or all sections matching aliases."""
    found: list[dict[str, Any]] = []
    
    # If section_num provided, search only that section
    if section_num is not None:
        sections = _parse_numbered_sections(text)
        if section_num in sections:
            section_text = sections[section_num]
        else:
            section_text = text
    else:
        section_text = text
    
    # Extract bullet items
    current: str | None = None
    for line in section_text.splitlines():
        stripped = line.strip()
        
        # Match unnumbered heading or section title
        if stripped.startswith("#"):
            title = stripped.lstrip("#").strip().lower()
            current = None
            for alias in aliases:
                if title == alias or title.startswith(alias + ":") or title.startswith(alias + " "):
                    current = alias
                    break
            continue
        
        # Extract bullet items
        if current and stripped.startswith(("- ", "* ")):
            body = stripped[1:].strip()
            if body.startswith("-"):
                body = body[1:].strip()
            if ":" in body:
                prefix, rest = body.split(":", 1)
                prefix_lower = prefix.strip().lower()
                if prefix_lower.startswith(("actor ", "use case ", "failure case ", "question ", "risk ", "decision ", "requirement ")):
                    body = rest.strip()
            if body:
                found.append({field_name: body})
    
    return found


def _extract_header_items(text: str, aliases: tuple[str, ...], field_name: str) -> list[dict[str, Any]]:
    """Legacy function for backward compatibility. Uses section + alias matching."""
    return _extract_from_section(text, None, aliases, field_name)


_FR_HEADER_RE = re.compile(r'^[-*]\s*(?:FR-\d+|Requirement\s*\d*)\s*:', re.IGNORECASE)
_FR_STRIP_RE = re.compile(r'^[-*]\s*(?:FR-\d+|Requirement\s*\d*)\s*:?\s*', re.IGNORECASE)


def _extract_functional_requirements(text: str) -> list[tuple[dict[str, Any], str]]:
    """Extract functional requirements with confidence basis.

    Returns: list of (record_dict, basis) tuples
    """
    found: list[tuple[dict[str, Any], str]] = []

    # Try to find Requirements section by section number (Priority 1: structured)
    sections = _parse_numbered_sections(text)
    for section_num in sorted(sections.keys()):
        section_text = sections[section_num]
        section_title = section_text.split("\n")[0] if section_text else ""

        if any(alias in section_title.lower() for alias in ("requirement", "functional")):
            # Try table parsing first
            tables = re.findall(r'\|.*\n\|[-:\s|]+\n(?:\|.*\n)+', section_text)
            for table in tables:
                rows = _parse_markdown_table(table)
                for row in rows:
                    if row:
                        req_text = row.get("Requirement") or row.get("requirement") or row.get("Description") or list(row.values())[0]
                        found.append(({
                            "requirement": req_text,
                            "source": row.get("Source", row.get("source", "pre-artifacts")),
                            "priority": row.get("Priority", row.get("priority", "MUST")).upper() if row.get("Priority") or row.get("priority") else "MUST",
                            "status": "PROPOSED",
                            "decision_owner": "Project/product owner"
                        }, "STRUCTURED_TABLE"))

            # Extract bullet items from section
            for line in section_text.splitlines():
                stripped = line.strip()
                if _FR_HEADER_RE.match(stripped):
                    body = _FR_STRIP_RE.sub('', stripped).strip()
                    if body:
                        found.append(({
                            "requirement": body,
                            "source": "pre-artifacts",
                            "priority": "MUST",
                            "status": "PROPOSED",
                            "decision_owner": "Project/product owner"
                        }, "SECTION_MATCH"))

    # Fallback: keyword matching over the whole text, skipping anything already
    # captured from a matched section to avoid duplicate records.
    already = {item["requirement"] for item, _ in found}
    for line in text.splitlines():
        stripped = line.strip()
        if _FR_HEADER_RE.match(stripped):
            body = _FR_STRIP_RE.sub('', stripped).strip()
            if body and body not in already:
                found.append(({
                    "requirement": body,
                    "source": "pre-artifacts",
                    "priority": "MUST",
                    "status": "PROPOSED",
                    "decision_owner": "Project/product owner"
                }, "KEYWORD_MATCH"))

    return found


_RISK_HEADER_RE = re.compile(r'^[-*]\s*risks?\s*\d*\s*:', re.IGNORECASE)
_RISK_STRIP_RE = re.compile(r'^[-*]\s*risks?\s*\d*\s*:?\s*', re.IGNORECASE)


def _extract_risks(text: str) -> list[tuple[dict[str, Any], str]]:
    """Extract risks with confidence basis.

    A "Risk mitigation ideas:" bullet list and a "Residual uncertainty:" line,
    when present alongside the risks, are not risk-specific but do describe
    real candidate controls and known gaps from the source — they replace the
    generic "Need explicit risk control decision" placeholder rather than
    being discarded.
    """
    found: list[tuple[dict[str, Any], str]] = []

    # Try structured section approach
    sections = _parse_numbered_sections(text)
    for section_num in sorted(sections.keys()):
        section_text = sections[section_num]
        section_title = section_text.split("\n")[0] if section_text else ""

        if any(alias in section_title.lower() for alias in ("risk", "risks")):
            mitigation_ideas = "; ".join(
                item for category, item in _extract_nested_category_items(section_text)
                if category.lower() == "risk mitigation ideas"
            )
            residual_uncertainty = None
            for line in section_text.splitlines():
                stripped = line.strip()
                if stripped.lower().startswith("- residual uncertainty:"):
                    residual_uncertainty = re.sub(r'^-\s*residual uncertainty\s*:?\s*', '', stripped, flags=re.IGNORECASE).strip()

            mitigation_default = mitigation_ideas or "Need explicit risk control decision"
            detection_default = "Source text indicates unresolved risk"
            if residual_uncertainty:
                detection_default += f"; residual uncertainty: {residual_uncertainty}"

            # Try table parsing
            tables = re.findall(r'\|.*\n\|[-:\s|]+\n(?:\|.*\n)+', section_text)
            for table in tables:
                rows = _parse_markdown_table(table)
                for row in rows:
                    if row:
                        risk_text = row.get("Risk") or row.get("risk") or row.get("Description") or list(row.values())[0]
                        found.append(({
                            "risk": risk_text,
                            "likelihood": row.get("Likelihood", row.get("likelihood", "MEDIUM")).upper(),
                            "impact": row.get("Impact", row.get("impact", "HIGH")).upper(),
                            "detection": row.get("Detection", row.get("detection", detection_default)),
                            "mitigation_or_control": row.get("Mitigation", row.get("mitigation", mitigation_default)),
                            "owner": row.get("Owner", row.get("owner", "Project/product owner")),
                            "residual_status": "OPEN"
                        }, "STRUCTURED_TABLE"))

            # Extract bullet items
            for line in section_text.splitlines():
                stripped = line.strip()
                if _RISK_HEADER_RE.match(stripped):
                    body = _RISK_STRIP_RE.sub('', stripped).strip()
                    if body:
                        found.append(({
                            "risk": body,
                            "likelihood": "MEDIUM",
                            "impact": "HIGH",
                            "detection": detection_default,
                            "mitigation_or_control": mitigation_default,
                            "owner": "Project/product owner",
                            "residual_status": "OPEN"
                        }, "SECTION_MATCH"))

    # Fallback: keyword matching over the whole text, skipping anything already
    # captured from a matched section to avoid duplicate records.
    already = {item["risk"] for item, _ in found}
    for line in text.splitlines():
        stripped = line.strip()
        if _RISK_HEADER_RE.match(stripped):
            body = _RISK_STRIP_RE.sub('', stripped).strip()
            if body and body not in already:
                found.append(({
                    "risk": body,
                    "likelihood": "MEDIUM",
                    "impact": "HIGH",
                    "detection": "Source text indicates unresolved risk",
                    "mitigation_or_control": "Need explicit risk control decision",
                    "owner": "Project/product owner",
                    "residual_status": "OPEN"
                }, "KEYWORD_MATCH"))

    return found


_DECISION_HEADER_RE = re.compile(r'^[-*]\s*decision\s*\d*\s*:', re.IGNORECASE)
_DECISION_STRIP_RE = re.compile(r'^[-*]\s*decision\s*\d*\s*:?\s*', re.IGNORECASE)


def _extract_decisions(text: str) -> list[tuple[dict[str, Any], str]]:
    """Extract decisions with confidence basis."""
    found: list[tuple[dict[str, Any], str]] = []

    def _new_decision(body: str) -> dict[str, Any]:
        return {
            "decision": body,
            "rationale": "Not yet formally expanded",
            "decider": "Project/product owner",
            "date": "UNKNOWN",
            "evidence": "pre-artifacts discussion",
            "status": "PROPOSED",
        }

    def _extract_bullets(section_text: str, basis: str) -> list[tuple[dict[str, Any], str]]:
        collected: list[tuple[dict[str, Any], str]] = []
        current: dict[str, Any] | None = None
        for line in section_text.splitlines():
            stripped = line.strip()
            if _DECISION_HEADER_RE.match(stripped):
                if current:
                    collected.append((current, basis))
                current = _new_decision(_DECISION_STRIP_RE.sub("", stripped).strip())
            elif current and stripped.startswith(("- Rationale:", "- rationale:")):
                current["rationale"] = re.sub(r'^-\s*rationale\s*:?\s*', '', stripped, flags=re.IGNORECASE).strip()
            elif current and stripped.startswith(("- Decision owner:", "- decider:", "- Owner:")):
                current["decider"] = re.sub(r'^-\s*(decision owner|decider|owner)\s*:?\s*', '', stripped, flags=re.IGNORECASE).strip()
            elif current and stripped.startswith(("- Date:", "- Status:", "- Date or status:")):
                current["date"] = re.sub(r'^-\s*(date or status|date|status)\s*:?\s*', '', stripped, flags=re.IGNORECASE).strip()
        if current:
            collected.append((current, basis))
        return collected

    # Try structured section approach
    sections = _parse_numbered_sections(text)
    for section_num in sorted(sections.keys()):
        section_text = sections[section_num]
        section_title = section_text.split("\n")[0] if section_text else ""

        if any(alias in section_title.lower() for alias in ("decision", "decisions")):
            # Try table parsing
            tables = re.findall(r'\|.*\n\|[-:\s|]+\n(?:\|.*\n)+', section_text)
            for table in tables:
                rows = _parse_markdown_table(table)
                for row in rows:
                    if row:
                        decision_text = row.get("Decision") or row.get("decision") or row.get("Description") or list(row.values())[0]
                        found.append(({
                            "decision": decision_text,
                            "rationale": row.get("Rationale", row.get("rationale", "Not yet formally expanded")),
                            "decider": row.get("Decider", row.get("decider", "Project/product owner")),
                            "date": row.get("Date", row.get("date", "UNKNOWN")),
                            "evidence": row.get("Evidence", row.get("evidence", "pre-artifacts discussion")),
                            "status": "PROPOSED"
                        }, "STRUCTURED_TABLE"))

            found.extend(_extract_bullets(section_text, "SECTION_MATCH"))

    # Fallback: keyword matching over the whole text, skipping anything already
    # captured from a matched section to avoid duplicate records.
    already = {item["decision"] for item, _ in found}
    for item, basis in _extract_bullets(text, "KEYWORD_MATCH"):
        if item["decision"] not in already:
            found.append((item, basis))

    return found


def _extract_open_questions(text: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(question_text: str) -> None:
        if question_text and question_text not in seen:
            seen.add(question_text)
            found.append({"question": question_text, "why_it_matters": "Unknown until confirmed by human review", "decision_owner": "Project/product owner", "needed_by": "Before implementation or production approval", "current_disposition": "OPEN"})

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("- question "):
            body = stripped[11:].strip()
            if ":" in body:
                _, rest = body.split(":", 1)
                _add(rest.strip())
    for item in _extract_header_items(text, ("open questions", "questions", "question"), "question"):
        _add(item["question"])
    return found


_ACTOR_CATEGORY_ROLE = {
    "users": "USER",
    "operators": "OPERATOR",
    "admins/approvers": "APPROVER",
    "external systems or services": "EXTERNAL_SYSTEM",
    "other impacted parties": "AFFECTED_PARTY",
}


def _extract_nested_category_items(section_text: str) -> list[tuple[str, str]]:
    """Return (category, item) pairs from a "- Category:\n  - item" bullet list."""
    pairs: list[tuple[str, str]] = []
    category: str | None = None
    for line in section_text.splitlines():
        if not line.strip():
            continue
        stripped = line.strip()
        if not stripped.startswith(("- ", "* ")):
            continue
        body = stripped[2:].strip()
        indent = len(line) - len(line.lstrip())
        if indent == 0:
            category = body[:-1].strip() if body.endswith(":") else body
        elif category:
            pairs.append((category, body))
    return pairs


def _extract_actor_records(text: str) -> list[dict[str, Any]]:
    """Extract actors from the template's numbered "## 6. Actors" section (nested
    category bullets), falling back to a plain "## Actors" heading with flat bullets.
    """
    found: list[dict[str, Any]] = []
    section_text = _parse_numbered_sections(text).get(6)
    if section_text:
        for category, item in _extract_nested_category_items(section_text):
            found.append({
                "name": item,
                "role_type": _ACTOR_CATEGORY_ROLE.get(category.lower(), "AFFECTED_PARTY"),
                "needs_or_responsibilities": "UNKNOWN",
                "decision_authority": "UNKNOWN",
            })
    if not found:
        found = _extract_header_items(text, ("actors", "actor"), "name")
    return found


def _extract_use_case_records(text: str) -> list[dict[str, Any]]:
    return _extract_header_items(text, ("use cases", "use case"), "behavior")


_FAILURE_HEADER_RE = re.compile(r'^[-*]\s*failure\s*case\s*\d*\s*:', re.IGNORECASE)
_FAILURE_STRIP_RE = re.compile(r'^[-*]\s*failure\s*case\s*\d*\s*:?\s*', re.IGNORECASE)


def _extract_failure_case_records(text: str) -> list[dict[str, Any]]:
    """Extract failure cases from the template's numbered "## 12. Failure, Misuse,
    and Unsafe Cases" section (a decision-like header + labeled continuation
    lines), falling back to a plain "## Failure Cases" heading with flat bullets.
    """
    found: list[dict[str, Any]] = []
    section_text = _parse_numbered_sections(text).get(12)
    if section_text:
        current: dict[str, Any] | None = None
        for line in section_text.splitlines():
            stripped = line.strip()
            if _FAILURE_HEADER_RE.match(stripped):
                if current:
                    found.append(current)
                current = {
                    "condition": _FAILURE_STRIP_RE.sub("", stripped).strip(),
                    "required_safe_behavior": "UNKNOWN",
                    "recovery_or_abstention": "UNKNOWN",
                    "evidence_needed": "UNKNOWN",
                }
            elif current and stripped.lower().startswith("- required safe behavior"):
                current["required_safe_behavior"] = re.sub(r'^-\s*required safe behavior\s*:?\s*', '', stripped, flags=re.IGNORECASE).strip()
            elif current and stripped.lower().startswith("- recovery"):
                current["recovery_or_abstention"] = re.sub(r'^-\s*recovery[^:]*:?\s*', '', stripped, flags=re.IGNORECASE).strip()
            elif current and stripped.lower().startswith("- evidence needed"):
                current["evidence_needed"] = re.sub(r'^-\s*evidence needed\s*:?\s*', '', stripped, flags=re.IGNORECASE).strip()
        if current:
            found.append(current)
    if not found:
        found = _extract_header_items(text, ("failure cases", "failure case"), "condition")
    return found


def _split_subsections(section_text: str) -> dict[str, str]:
    """Split a numbered section's body into ### sub-sections keyed by lowercase title."""
    subsections: dict[str, str] = {}
    current_title: str | None = None
    current_lines: list[str] = []
    for line in section_text.splitlines():
        match = re.match(r'^#{2,4}\s+(.+)$', line)
        if match:
            if current_title is not None:
                subsections[current_title] = "\n".join(current_lines).strip()
            current_title = match.group(1).strip().lower()
            current_lines = []
        elif current_title is not None:
            current_lines.append(line)
    if current_title is not None:
        subsections[current_title] = "\n".join(current_lines).strip()
    return subsections


def _extract_labeled_field(section_text: str, *label_variants: str) -> str | None:
    """Find a "- Label: answer" or "- Label:\n  - sub-bullet" bullet and return its answer text."""
    lines = section_text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith(("- ", "* ")):
            continue
        body = stripped[2:].strip()
        body_lower = body.lower()
        for label in label_variants:
            label_lower = label.lower()
            if not body_lower.startswith(label_lower):
                continue
            rest = body[len(label):].lstrip()
            if rest.startswith((":", "?")):
                rest = rest[1:].strip()
            if rest:
                return rest
            base_indent = len(line) - len(line.lstrip())
            sub_items: list[str] = []
            cursor = index + 1
            while cursor < len(lines):
                next_line = lines[cursor]
                if not next_line.strip():
                    cursor += 1
                    continue
                next_indent = len(next_line) - len(next_line.lstrip())
                if next_indent <= base_indent:
                    break
                next_stripped = next_line.strip()
                if next_stripped.startswith(("- ", "* ")):
                    sub_items.append(next_stripped[2:].strip())
                cursor += 1
            return "; ".join(sub_items) if sub_items else None
    return None


def _extract_field_from_section(text: str, section_num: int, *label_variants: str) -> str | None:
    section_text = _parse_numbered_sections(text).get(section_num)
    return _extract_labeled_field(section_text, *label_variants) if section_text else None


def _extract_bullet_list_from_subsection(text: str, section_num: int, subsection_alias: str) -> str | None:
    section_text = _parse_numbered_sections(text).get(section_num)
    if not section_text:
        return None
    for title, content in _split_subsections(section_text).items():
        if subsection_alias in title:
            items = [line.strip()[2:].strip() for line in content.splitlines() if line.strip().startswith(("- ", "* "))]
            items = [item for item in items if item]
            if items:
                return "; ".join(items)
    return None


def _extract_non_functional_requirements(text: str) -> list[tuple[dict[str, Any], str]]:
    """Extract non-functional requirements from a "### Non-Functional Requirements" subsection.

    Category labels are top-level bullets (e.g. "- Performance:"); the actual
    requirement statements are their indented sub-bullets.
    """
    found: list[tuple[dict[str, Any], str]] = []
    for section_text in _parse_numbered_sections(text).values():
        for title, content in _split_subsections(section_text).items():
            if "non-functional" not in title and "non functional" not in title:
                continue
            category: str | None = None
            for line in content.splitlines():
                if not line.strip():
                    continue
                stripped = line.strip()
                if not stripped.startswith(("- ", "* ")):
                    continue
                body = stripped[2:].strip()
                indent = len(line) - len(line.lstrip())
                if indent == 0:
                    if ":" in body:
                        label, rest = body.split(":", 1)
                        category = label.strip()
                        rest = rest.strip()
                        if rest:
                            found.append(({
                                "category": category.upper(),
                                "requirement": rest,
                                "measurement": "UNKNOWN",
                                "source": "pre-artifacts",
                                "status": "PROPOSED",
                            }, "SECTION_MATCH"))
                    else:
                        category = body
                elif category:
                    found.append(({
                        "category": category.upper(),
                        "requirement": body,
                        "measurement": "UNKNOWN",
                        "source": "pre-artifacts",
                        "status": "PROPOSED",
                    }, "SECTION_MATCH"))
    return found


def _extract_evidence_items(text: str) -> list[tuple[dict[str, Any], str]]:
    """Extract evidence-ledger candidates from an "Evidence and Validation" style section."""
    found: list[tuple[dict[str, Any], str]] = []
    for section_text in _parse_numbered_sections(text).values():
        section_title = section_text.split("\n")[0] if section_text else ""
        if "evidence" not in section_title.lower():
            continue
        current_label: str | None = None
        for line in section_text.splitlines():
            stripped = line.strip()
            if not stripped.startswith(("- ", "* ")):
                continue
            indent = len(line) - len(line.lstrip())
            body = stripped[2:].strip()
            if indent == 0:
                current_label = body[:-1].strip() if body.endswith(":") else body
                continue
            if current_label and current_label.lower() in ("existing evidence", "tests, docs, logs, or artifacts"):
                # "Existing evidence" describes something the human reported
                # having informally observed (e.g. a listening test) — PARTIAL
                # is more accurate than NOT_RUN. "Tests, docs, logs, or
                # artifacts" genuinely states what was NOT supplied/inspected,
                # so NOT_RUN stays correct there.
                is_reported_observation = current_label.lower() == "existing evidence"
                found.append(({
                    "claim_tested": "UNKNOWN",
                    "evidence_type": current_label,
                    "exact_source_or_command": body,
                    "expected_result": "UNKNOWN",
                    "observed_result": body,
                    "result": "PARTIAL" if is_reported_observation else "NOT_RUN",
                    "date": "UNKNOWN",
                    "limitations": "Reported in the pre-artifacts source; not independently re-verified" if is_reported_observation else "Nothing was supplied or inspected for this item",
                }, "SECTION_MATCH"))
    return found


def _extract_constraints(text: str) -> list[dict[str, Any]]:
    """Extract constraints from the template's numbered "## 8. Constraints" section."""
    section_text = _parse_numbered_sections(text).get(8)
    if not section_text:
        return []
    return [{
        "category": category,
        "constraint": item,
        "enforcement": "UNKNOWN",
        "evidence_or_status": "Reported in the pre-artifacts source",
        "owner": "Project/product owner",
    } for category, item in _extract_nested_category_items(section_text)]


_ASSUMPTION_HEADER_RE = re.compile(r'^[-*]\s*assumption\s*\d*\s*:', re.IGNORECASE)
_ASSUMPTION_STRIP_RE = re.compile(r'^[-*]\s*assumption\s*\d*\s*:?\s*', re.IGNORECASE)


def _extract_assumptions(text: str) -> list[dict[str, Any]]:
    """Extract assumptions from the template's numbered "## 11. Assumptions" section."""
    section_text = _parse_numbered_sections(text).get(11)
    found: list[dict[str, Any]] = []
    if not section_text:
        return found
    current: dict[str, Any] | None = None
    for line in section_text.splitlines():
        stripped = line.strip()
        if _ASSUMPTION_HEADER_RE.match(stripped):
            if current:
                found.append(current)
            current = {
                "assumption": _ASSUMPTION_STRIP_RE.sub("", stripped).strip(),
                "impact_if_wrong": "UNKNOWN",
                "validation_method": "UNKNOWN",
                "owner": "Project/product owner",
                "status": "OPEN",
            }
        elif current and stripped.lower().startswith("- why it matters"):
            current["impact_if_wrong"] = re.sub(r'^-\s*why it matters\s*:?\s*', '', stripped, flags=re.IGNORECASE).strip()
        elif current and stripped.lower().startswith("- how it might be validated"):
            current["validation_method"] = re.sub(r'^-\s*how it might be validated\s*:?\s*', '', stripped, flags=re.IGNORECASE).strip()
    if current:
        found.append(current)
    return found


def _extract_components(text: str) -> list[dict[str, Any]]:
    """Extract architecture components from the "Key components:" bullets in the
    template's numbered "## 15. Architecture / System Context" section."""
    section_text = _parse_numbered_sections(text).get(15)
    if not section_text:
        return []
    found: list[dict[str, Any]] = []
    for category, item in _extract_nested_category_items(section_text):
        if category.lower() != "key components":
            continue
        name, sep, responsibility = item.partition(":")
        found.append({
            "component": name.strip() if sep else item,
            "responsibility": responsibility.strip() if sep else item,
            "inputs": "UNKNOWN",
            "outputs": "UNKNOWN",
            "state_owner": "UNKNOWN",
            "source_evidence": "pre-artifacts architecture section",
            "confidence": "MEDIUM",
        })
    return found


def _extract_external_dependencies(text: str) -> list[dict[str, Any]]:
    """Extract external dependencies from the "External dependencies:" bullets in
    the template's numbered "## 15. Architecture / System Context" section."""
    section_text = _parse_numbered_sections(text).get(15)
    if not section_text:
        return []
    found: list[dict[str, Any]] = []
    for category, item in _extract_nested_category_items(section_text):
        if category.lower() != "external dependencies":
            continue
        found.append({
            "dependency": item,
            "owner": "UNKNOWN",
            "required_behavior": "UNKNOWN",
            "availability": "UNKNOWN",
            "failure_impact": "UNKNOWN",
        })
    return found


def seed_from_pre_artifacts(path: str) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    seeded = {"source_path": path, "seeded_at": now(), "answers": {}, "records": {}}

    def add_seed(qid: str, value: Any, state: str = "PROVIDED") -> None:
        score, label, priority = _seed_confidence(qid, value, text)
        seeded["answers"][qid] = {
            "value": value,
            "state": state,
            "source_type": "SOURCE_ARTIFACT",
            "source_reference": path,
            "respondent": "agent",
            "confidence_score": score,
            "confidence_label": label,
            "review_priority": priority,
            "confidence_basis": "Deterministic section and keyword matching from the pre-artifacts source",
        }

    def add_seed_or_unknown(qid: str, value: str | None) -> None:
        add_seed(qid, value, "PROVIDED") if value else add_seed(qid, "UNKNOWN", "UNKNOWN")

    project_name = None
    for line in text.splitlines():
        if "- Project name:" in line:
            project_name = line.split(":", 1)[1].strip()
            break
    add_seed_or_unknown("PKG-001", project_name)

    # A pre-artifacts package is, by definition, discovery-stage input; the
    # keyword checks below only affect confidence scoring, not this default.
    add_seed("PKG-002", "DISCOVERY")

    # PKG-003..PKG-006 describe the ArtPkg package itself (owner, respondent,
    # workspace, snapshot), not the project under discussion. A generic
    # discovery document has no truthful way to answer these, so they are
    # left UNKNOWN rather than guessed.
    add_seed("PKG-003", "UNKNOWN", "UNKNOWN")
    add_seed("PKG-004", "UNKNOWN", "UNKNOWN")
    add_seed("PKG-005", "UNKNOWN", "UNKNOWN")
    add_seed("PKG-006", "UNKNOWN", "UNKNOWN")
    add_seed_or_unknown("PKG-008", _extract_field_from_section(text, 1, "Primary goal") or _extract_field_from_section(text, 1, "Short description"))
    add_seed_or_unknown("PKG-009", _extract_field_from_section(text, 16, "Boundary statement"))

    # No pre-artifacts discovery document can itself grant implementation
    # authority; apply_conditionals() derives AUT-002..AUT-007-SCOPE as
    # NOT_APPLICABLE once AUT-001 is recorded as NOT_EVALUATED below, so they
    # are intentionally not seeded here.
    add_seed("AUT-001", "NOT_EVALUATED")

    add_seed_or_unknown("OVR-001", _extract_field_from_section(text, 2, "What problem is being solved?"))
    add_seed_or_unknown("OVR-002", _extract_field_from_section(text, 3, "Desired result or observable outcome"))
    add_seed_or_unknown("BND-001", _extract_bullet_list_from_subsection(text, 5, "in scope"))
    add_seed_or_unknown("BND-002", _extract_bullet_list_from_subsection(text, 5, "out of scope"))

    restricted_answer = _extract_field_from_section(text, 19, "Does this project involve sensitive data, credentials, regulated information, or restricted content?")
    if restricted_answer:
        add_seed("SEC-001", "YES" if restricted_answer.lower().startswith("yes") else "NO")
        if restricted_answer.lower().startswith("yes"):
            safeguards = _extract_field_from_section(text, 19, "If yes, what safeguards are required?")
            redaction = _extract_field_from_section(text, 19, "Are any redaction or access controls needed?")
            categories = "; ".join(part for part in (safeguards, redaction) if part)
            add_seed_or_unknown("SEC-001-CATEGORIES", categories)
    else:
        add_seed("SEC-001", "UNKNOWN", "UNKNOWN")

    # PKG-007 (source of truth) is, by construction, the pre-artifacts file this
    # package was seeded from; PKG-007-AUTH records that it was human-supplied,
    # not that any project authority formally designated it.
    add_seed("PKG-007", path)
    add_seed("PKG-007-AUTH", "Supplied by the requesting user as the discovery source for this package; not a formally designated authoritative source of truth")

    add_seed_or_unknown("OVR-003", _extract_field_from_section(text, 4, "What is already working?"))
    add_seed_or_unknown("OVR-004", _extract_field_from_section(text, 4, "What is partially complete?"))
    add_seed_or_unknown("OVR-005", _extract_field_from_section(text, 4, "What is blocked or uncertain?"))
    add_seed_or_unknown("OVR-007", _extract_field_from_section(text, 14, "What is still unverified?"))
    add_seed_or_unknown("OVR-008", _extract_field_from_section(text, 18, "Proposed next outcome"))

    def merge_records(section: str, extracted: list[tuple[dict[str, Any], str]]) -> None:
        if extracted:
            seeded["records"].setdefault(section, [])
            for record, basis in extracted:
                _add_seed_record(seeded, section, record, text, basis)

    def merge_plain_records(section: str, extracted: list[dict[str, Any]]) -> None:
        if extracted:
            seeded["records"].setdefault(section, [])
            for record in extracted:
                _add_seed_record(seeded, section, record, text)

    merge_records("functional_requirements", _extract_functional_requirements(text))
    merge_records("non_functional_requirements", _extract_non_functional_requirements(text))
    merge_records("risks", _extract_risks(text))
    merge_records("decisions", _extract_decisions(text))
    merge_records("evidence", _extract_evidence_items(text))
    merge_plain_records("questions", _extract_open_questions(text))
    merge_plain_records("actors", _extract_actor_records(text))
    merge_plain_records("use_cases", _extract_use_case_records(text))
    merge_plain_records("failure_cases", _extract_failure_case_records(text))
    merge_plain_records("constraints", _extract_constraints(text))
    merge_plain_records("assumptions", _extract_assumptions(text))
    merge_plain_records("components", _extract_components(text))
    merge_plain_records("external_dependencies", _extract_external_dependencies(text))

    return seeded


def merge_seed_records(document: dict[str, Any], seed: dict[str, Any]) -> dict[str, list[str]]:
    """Add deterministically extracted repeated records from a seed into the document.

    Mirrors how seeded single-value answers are already merged directly via
    set_answer(): every record lands as SOURCE_ARTIFACT-provenance, PROVIDED
    state so a human can review, edit, or delete it before generation rather
    than having to retype everything the extractor already found.
    """
    created: dict[str, list[str]] = {}
    for section, records in seed.get("records", {}).items():
        if section not in RECORD_FIELDS:
            continue
        for record in records:
            record_id = add_record(document, section, record["fields"], source_type="SOURCE_ARTIFACT")
            stored = find_record(document, record_id)
            stored["source_reference"] = seed.get("source_path")
            for meta in ("confidence_score", "confidence_label", "review_priority", "confidence_basis"):
                if meta in record:
                    stored[meta] = record[meta]
            created.setdefault(section, []).append(record_id)
    document["updated"] = now()
    return created


def _slug_record_exists(document: dict[str, Any], record_id: str) -> bool:
    return any(record.get("id") == record_id for records in document.get("records", {}).values() for record in records)


def _add_addendum_record(document: dict[str, Any], section: str, record_id: str, fields: dict[str, Any], source_type: str, source_reference: str, result_bucket: dict[str, str]) -> None:
    if _slug_record_exists(document, record_id):
        result_bucket[record_id] = "skipped_existing"
        return
    add_record(document, section, fields, source_type=source_type, record_id=record_id, source_reference=source_reference)
    result_bucket[record_id] = "added"


def _section_text(text: str, heading_number: int) -> str:
    match = re.search(rf"(?ms)^##\s+{heading_number}\.\s+.*?(?=^##\s+\d+\.|\Z)", text)
    return match.group(0) if match else ""


def _heading_blocks(text: str, prefix: str) -> list[tuple[str, str, str]]:
    blocks: list[tuple[str, str, str]] = []
    pattern = re.compile(rf"(?ms)^###\s+({re.escape(prefix)}[A-Z0-9-]*)\s+[—-]\s+(.+?)\n(.*?)(?=^###\s+|\Z)")
    for match in pattern.finditer(text):
        blocks.append((match.group(1).strip(), match.group(2).strip(), match.group(3).strip()))
    return blocks


def _bullet_value(block: str, label: str) -> str:
    match = re.search(rf"(?mi)^-\s*{re.escape(label)}\s*:\s*(.+)$", block)
    return match.group(1).strip() if match else ""


def _status_value(value: str, default: str) -> str:
    return (value or default).strip().rstrip(".")


def _bullets_after_heading(text: str, heading: str) -> str:
    match = re.search(rf"(?ms)^###\s+{re.escape(heading)}\s*\n(.*?)(?=^###\s+|^##\s+|\Z)", text)
    if not match:
        return ""
    items = [line.strip()[2:].strip() for line in match.group(1).splitlines() if line.strip().startswith(("- ", "* "))]
    return "\n".join(items)


def _parse_markdown_table(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if cells and not all(set(cell) <= {"-", " "} for cell in cells):
            rows.append(cells)
    return rows


def _question_id_and_title(cell: str) -> tuple[str, str]:
    match = re.match(r"([A-Z0-9]+(?:-[A-Z0-9]+)*-\d{3}|P1-Q\d+|Q-\d{3})\s+[—-]\s+(.+)", cell.strip())
    return (match.group(1), match.group(2).strip()) if match else (cell.strip(), cell.strip())


def _listed_ids(value: str) -> list[str]:
    return sorted(set(re.findall(r"\b(?:FR|NFR)-\d{3}\b", value)))


def _included_requirement_records(value: str) -> list[tuple[str, str, dict[str, Any]]]:
    records: list[tuple[str, str, dict[str, Any]]] = []
    for line in value.splitlines():
        match = re.match(r"((?:FR|NFR)-\d{3})\s*:\s*(.+)", line.strip())
        if not match:
            continue
        record_id, requirement = match.group(1), match.group(2).strip()
        if record_id.startswith("FR-"):
            records.append((record_id, "functional_requirements", {
                "requirement": requirement,
                "source": "PH-001 decision-resolution addendum",
                "priority": "MUST",
                "status": "ACCEPTED",
                "decision_owner": "Project/product owner",
            }))
        else:
            records.append((record_id, "non_functional_requirements", {
                "category": "PH-001",
                "requirement": requirement,
                "measurement": "Threshold required" if "threshold" in requirement.lower() else "Evidence required",
                "source": "PH-001 decision-resolution addendum",
                "status": "ACCEPTED",
            }))
    return records


def apply_decision_resolution_addendum(document: dict[str, Any], addendum_path: str) -> dict[str, Any]:
    source = str(Path(addendum_path).expanduser().resolve())
    text = Path(source).read_text(encoding="utf-8")
    result = {"decisions": {}, "phases": {}, "requirements": {}, "acceptance_criteria": {}, "questions": {}, "artifacts": {}, "blocking_questions": []}

    _add_addendum_record(document, "artifacts", "ART-ADD-001", {
        "exact_path_or_reference": source,
        "purpose": "Human-supplied decision-resolution addendum",
        "provenance": "HUMAN_DECLARATION",
        "authority": "SUPPORTING",
        "authority_basis": "Supplies post-ArtPkg human decisions while preserving implementation authority boundaries",
        "status": "CURRENT",
        "last_validated_date": now()[:10],
    }, "HUMAN_DECLARATION", source, result["artifacts"])

    for record_id, title, block in _heading_blocks(_section_text(text, 2) + "\n" + _section_text(text, 5), "DEC-"):
        _add_addendum_record(document, "decisions", record_id, {
            "decision": _bullet_value(block, "Decision") or title,
            "rationale": _bullet_value(block, "Rationale"),
            "decider": _bullet_value(block, "Decider") or "Project/product owner",
            "date": "2026-08-29",
            "evidence": source,
            "status": _status_value(_bullet_value(block, "Status"), "ACCEPTED"),
        }, "HUMAN_DECLARATION", source, result["decisions"])

    phase_text = _section_text(text, 3)
    requirements = _bullets_after_heading(phase_text, "Requirements included")
    out_of_scope = _bullets_after_heading(phase_text, "Explicitly outside PH-001")
    deliverables = _bullets_after_heading(phase_text, "Required deliverables")
    failure_behavior = _bullets_after_heading(phase_text, "Required failure behavior")
    stop_conditions = _bullets_after_heading(phase_text, "Required stop conditions")
    for record_id, section, fields in _included_requirement_records(requirements):
        _add_addendum_record(document, section, record_id, fields, "HUMAN_DECLARATION", source, result["requirements"])
    for record_id, title, block in _heading_blocks(phase_text, "PH-"):
        _add_addendum_record(document, "phases", record_id, {
            "title_and_outcome": f"{title}: {_bullet_value(block, 'Single outcome')}".strip(": "),
            "status": _status_value(_bullet_value(block, "Status"), "Scope accepted; execution not yet authorized"),
            "requirement_ids": _listed_ids(requirements),
            "in_scope": requirements,
            "out_of_scope": out_of_scope,
            "validation": "\n".join(part for part in (deliverables, failure_behavior) if part),
            "human_review_level": "APPROVAL_REQUIRED",
            "rollback_or_recovery": stop_conditions,
            "authority_source": "Execution not authorized by this addendum",
        }, "HUMAN_DECLARATION", source, result["phases"])

    for record_id, _title, block in _heading_blocks(_section_text(text, 4), "AC-"):
        _add_addendum_record(document, "acceptance_criteria", record_id, {
            "requirement_ids": "PH-001",
            "pass_condition": _bullet_value(block, "Pass condition"),
            "validation_method": _bullet_value(block, "Validation"),
            "expected_evidence": _bullet_value(block, "Evidence"),
            "evidence_ids": "EVIDENCE_REQUIRED",
            "approver": "P1-Q5",
            "status": _status_value(_bullet_value(block, "Status"), "PROPOSED"),
        }, "HUMAN_DECLARATION", source, result["acceptance_criteria"])

    for cells in _parse_markdown_table(_section_text(text, 7))[1:]:
        if len(cells) < 4:
            continue
        record_id, title = _question_id_and_title(cells[0])
        _add_addendum_record(document, "questions", record_id, {
            "question": title,
            "why_it_matters": cells[2],
            "decision_owner": cells[3],
            "needed_by": "PH-001 coding readiness" if cells[2].lower().startswith("yes") else "Later checkpoint",
            "current_disposition": cells[1],
        }, "HUMAN_DECLARATION", source, result["questions"])

    for record_id, _title, block in _heading_blocks(_section_text(text, 8), "P1-Q"):
        _add_addendum_record(document, "questions", record_id, {
            "question": _bullet_value(block, "Question"),
            "why_it_matters": _bullet_value(block, "Why it matters"),
            "decision_owner": "Project/product owner",
            "needed_by": "Before PH-001 implementation readiness",
            "current_disposition": "OPEN",
        }, "HUMAN_DECLARATION", source, result["questions"])
        result["blocking_questions"].append(record_id)

    set_answer(document, "AUT-001", "NOT_EVALUATED", "PROVIDED", "HUMAN_DECLARATION", source)
    set_harness_mode(document, False)
    set_answer(document, "HND-001", "BLOCKED_AT_HUMAN_CHECKPOINT", "PROVIDED", "HUMAN_DECLARATION", source)
    set_answer(document, "HND-007", "ArtPkg update and focused human review of P1-Q1 through P1-Q5; do not implement PH-001 until explicit execution authorization is recorded.", "PROVIDED", "HUMAN_DECLARATION", source)
    set_answer(document, "HND-008", None, "UNKNOWN", "HUMAN_DECLARATION", source)
    set_answer(document, "HND-009", _section_text(text, 10).strip() or "Use the decision-resolution addendum fresh-session instruction.", "PROVIDED", "HUMAN_DECLARATION", source)
    return result


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

def add_record(document: dict[str, Any], section: str, fields: dict[str, Any], source_type: str = "HUMAN_DECLARATION", record_id: str | None = None, source_reference: str | None = None) -> str:
    if section not in ID_PREFIXES and section not in RECORD_FIELDS: raise ValueError(f"unknown repeated section: {section}")
    record_id = record_id or _next_id(document, section)
    if record_id in {record["id"] for records in document.get("records", {}).values() for record in records}:
        raise ValueError(f"record already exists: {record_id}")
    stamp = now()
    document["records"].setdefault(section, []).append({"id": record_id, "fields": copy.deepcopy(fields), "source_type": source_type, "source_reference": source_reference, "respondent": document.get("respondent", ""), "created": stamp, "last_edit": stamp}); document["updated"] = now(); return record_id

def collect_record(document: dict[str, Any], section: str, input_fn=input, output_fn=print) -> str | None:
    """Collect one record one field at a time; return None for done/cancel."""
    if section not in RECORD_FIELDS: raise ValueError(f"no field definition for {section}")
    fields = RECORD_FIELDS[section]; values: dict[str, Any] = {}; index = 0
    output_fn(f"Collecting one {section.replace('_', ' ')} record. Type cancel to discard it or back to revisit a field.")
    while index < len(fields):
        name, label, choices = fields[index]; suffix = f" ({', '.join(sorted(choices))})" if choices else ""
        meaning, example = record_field_guidance(section, name, label)
        raw = input_fn(f"\n{label}{suffix}\nWhat this question means: {meaning}\nExample: {example}\n> ").strip(); command = raw.lower()
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
            if not re.fullmatch(r"(?:[A-Z0-9]+(?:-[A-Z0-9]+)*-\d{3}|P1-Q\d+)", str(record.get("id", ""))): raise ValueError("record has invalid stable ID")

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
        if phase.get("id") == "PH-001" and "execution not yet authorized" in str(_field(phase, "status")).lower():
            errors.append("PH-001: scope accepted but implementation execution is not authorized")
            blockers.extend(["PH-001", "HND-008", "P1-Q1", "P1-Q2", "P1-Q3", "P1-Q4", "P1-Q5"])
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

def _is_placeholder_example_row(line: str) -> bool:
    """True for a template table row that is purely illustrative (every cell is
    either an example ID like ACT-001 or a `<placeholder>`), so it can be
    dropped once real, populated record tables are appended instead."""
    stripped = line.strip()
    if not stripped.startswith("|"):
        return False
    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
    if not cells:
        return False
    for cell in cells:
        if re.fullmatch(r"[A-Z]+-\d{3}", cell) or re.fullmatch(r"`<[^`]*>`", cell):
            continue
        return False
    return True


def render_package(document: dict[str, Any], template_path: str, validation: dict[str, Any]) -> str:
    template = Path(template_path).read_text(encoding="utf-8")

    def val(qid: str) -> str:
        return safe_text(_value(document, qid, "UNKNOWN"))

    stop_conditions = "; ".join(_field(record, "condition") for record in _records(document, "stop_conditions")) or "UNKNOWN"

    # Placeholders that appear exactly once, or that repeat with the same
    # intended value every time.
    single_replacements = {
        "<name>": val("PKG-001"),
        "<discovery / design / implementation handoff / review / closeout>": val("PKG-002"),
        "<DRAFT / READY_FOR_REVIEW / ACCEPTED / SUPERSEDED / BLOCKED>": safe_text(validation["status"]),
        "<person or team>": val("PKG-003"),
        "<person or agent>": val("PKG-004"),
        "<path / URL / identifier>": val("PKG-005"),
        "<commit, tag, release, digest, or date>": val("PKG-006"),
        "<artifact and location>": val("PKG-007"),
        "<authorized scope / NONE / NOT EVALUATED>": val("AUT-001"),
        "<checkpoint and status>": val("HND-001"),
        "<what it covers>": val("PKG-008"),
        "<snapshot or date>": val("PKG-006"),
        "<important exclusions or limitations>": val("PKG-009"),
        "<What problem is being solved, for whom, and why it matters.>": val("OVR-001"),
        "<Observable outcome, not merely an activity or technology choice.>": val("OVR-002"),
        "<validated work>": val("OVR-003"),
        "<current bounded work>": val("OVR-004"),
        "<blocker and owner>": val("OVR-005"),
        "<explicit non-scope>": val("OVR-006"),
        "<claims still requiring evidence>": val("OVR-007"),
        "<One independently testable next outcome.>": val("OVR-008"),
        "<observable success>": val("OUT-001"),
        "<observable failure or unacceptable trade-off>": val("OUT-002"),
        "<condition requiring pause and human review>": safe_text(stop_conditions),
        "<one bounded action>": val("HND-007"),
        "<decision / NONE>": val("HND-007"),
    }
    for old, new in single_replacements.items(): template = template.replace(old, new)

    # Placeholders that repeat with genuinely different intended values at
    # each occurrence — replace one at a time, in template order.
    template = template.replace("<ID / NONE>", val("AUT-008"), 1)
    template = template.replace("<ID / NONE>", safe_text(document.get("parent_package_id") or "NONE"), 1)
    template = template.replace("<YYYY-MM-DD>", safe_text(str(document.get("created", "UNKNOWN"))[:10]), 1)
    template = template.replace("<YYYY-MM-DD>", safe_text(str(document.get("updated", "UNKNOWN"))[:10]), 1)

    template = "\n".join(line for line in template.splitlines() if not _is_placeholder_example_row(line))

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

def interactive_start(path: str, resume: bool = False, pre_artifacts_path: str | None = None) -> int:
    answer_path = Path(path)
    if resume:
        document = load_answers(path)
    else:
        base = answer_path.parent
        template = resolve_template_path(base)
        document = new_answers(str(template), str(base))
    if pre_artifacts_path:
        pre_path = Path(pre_artifacts_path).expanduser().resolve()
        if pre_path.exists():
            seed = seed_from_pre_artifacts(str(pre_path))
            for qid, item in seed["answers"].items():
                set_answer(document, qid, item["value"], item["state"], item["source_type"], item["source_reference"])
                if "confidence_score" in item:
                    document["answers"][qid]["confidence_score"] = item["confidence_score"]
                    document["answers"][qid]["confidence_label"] = item["confidence_label"]
                    document["answers"][qid]["review_priority"] = item["review_priority"]
                    document["answers"][qid]["confidence_basis"] = item["confidence_basis"]
            created_records = merge_seed_records(document, seed)
            print(f"Seeded questionnaire from pre-artifacts file: {pre_path}")
            if created_records:
                total = sum(len(ids) for ids in created_records.values())
                print(f"Merged {total} extracted record(s) into the answer set for human review: " + ", ".join(f"{section}={len(ids)}" for section, ids in sorted(created_records.items())))
            print(render_seed_summary(seed))
    qids = list(QUESTION_CATALOG); index = 0
    while index < len(qids):
        qid = qids[index]; question = QUESTION_CATALOG[qid]
        skip_reason = conditional_skip_reason(document, qid)
        if skip_reason:
            print(f"\nSkipping {qid}: {skip_reason}.")
            index += 1
            continue
        print(format_terminal_question(qid, question))
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

def start_intake_ui(argv: list[str]) -> int:
    import artpkg_intake_server

    return artpkg_intake_server.main(argv)


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    if argv and argv[0] == "intake-ui":
        return start_intake_ui(argv[1:])

    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start"); start.add_argument("--answers", default="artifacts_package_answers.json"); start.add_argument("--pre-artifacts", default=None); resume = sub.add_parser("resume"); resume.add_argument("--answers", required=True); resume.add_argument("--pre-artifacts", default=None); validate = sub.add_parser("validate"); validate.add_argument("--answers", required=True); generate_parser = sub.add_parser("generate"); generate_parser.add_argument("--answers", required=True); generate_parser.add_argument("--yes", action="store_true"); addendum = sub.add_parser("apply-addendum"); addendum.add_argument("--answers", required=True); addendum.add_argument("--addendum", required=True); addendum.add_argument("--generate", action="store_true"); addendum.add_argument("--yes", action="store_true"); args = parser.parse_args(argv)
    if args.command == "start": return interactive_start(args.answers, resume=False, pre_artifacts_path=args.pre_artifacts)
    document = load_answers(args.answers)
    if args.command == "validate": print(json.dumps(validate_answers(document), indent=2)); return 0
    if args.command == "resume": return interactive_start(args.answers, resume=True, pre_artifacts_path=args.pre_artifacts)
    if args.command == "apply-addendum":
        result = apply_decision_resolution_addendum(document, args.addendum)
        save_answers(document, args.answers)
        if args.generate:
            try: paths = generate(document, overwrite=args.yes)
            except FileExistsError as exc: print(str(exc), file=sys.stderr); return 2
            print("\n".join(str(path) for path in paths))
        else:
            print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    try: paths = generate(document, overwrite=args.yes)
    except FileExistsError as exc: print(str(exc), file=sys.stderr); return 2
    print("\n".join(str(path) for path in paths)); return 0

if __name__ == "__main__": sys.exit(main())
