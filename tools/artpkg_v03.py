"""ArtPkg v0.3 requirements-gateway contracts.

This module deliberately contains no Pipeline-A enforcement.  It produces and
validates the ArtPkg-side contracts that Pipeline-A may consume.
"""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_VERSION = "0.3"
ARTIFACT_TYPES = {"GENERAL", "REQUIREMENT_INTAKE", "EVIDENCE_ENRICHED_SCOPE"}
REQUIREMENT_STATUSES = {"DRAFT", "NEEDS_REFINEMENT", "APPROVED_FOR_DISCOVERY", "SUPERSEDED", "REJECTED"}
SCOPE_STATUSES = {"DRAFT", "EVIDENCE_BOUND", "SCOPE_APPROVED", "SUPERSEDED", "REJECTED", "BLOCKED"}
AUTHORITY_BASES = {"PRODUCT_OWNER_DECLARATION", "DOMAIN_OWNER_DECLARATION", "REGULATORY_SOURCE", "CONTRACTUAL_SOURCE", "POLICY_SOURCE", "OTHER_HUMAN_APPROVED_SOURCE"}
CONFIDENCE = {"HIGH", "MEDIUM", "LOW"}
HUMAN_CONFIDENCE_BASES = {"HUMAN_OWNER_JUDGMENT", "HUMAN_DOMAIN_JUDGMENT", "HUMAN_APPROVER_JUDGMENT", "OTHER_HUMAN_DECLARED_BASIS"}
EVIDENCE_RELATIONS = {"SUPPORTS_SCOPE_INTERPRETATION", "CONTRADICTS_CURRENT_BEHAVIOR", "REQUIRES_REQUIREMENT_REFINEMENT"}
FORBIDDEN_EVIDENCE_RELATIONS = {"DERIVES_REQUIREMENT"}
REQUIREMENT_FIELDS = ("intended_behavior", "trigger_or_applicability", "expected_valid_outcome", "expected_invalid_fail_closed_outcome", "business_or_domain_reason", "compatibility_constraints", "regulatory_policy_constraints", "exclusions_non_goals")
SCHEMA_PATH = Path(__file__).parents[1] / "schemas" / "artifacts_package_answers_v0.3.schema.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _schema_errors(document: dict[str, Any]) -> list[str]:
    """Return deterministic v0.3 schema errors; legacy documents bypass this path."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    return sorted(error.message for error in validator.iter_errors(document))


def validate_v03_schema(document: dict[str, Any]) -> None:
    errors = _schema_errors(document)
    if errors:
        raise ValueError("invalid ArtPkg v0.3 schema: " + "; ".join(errors))


def _id(prefix: str, payload: Any) -> str:
    return prefix + "-" + hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()[:12].upper()


def _authority_payload(intake: dict[str, Any]) -> dict[str, Any]:
    """The sole digest input: human requirement authority, not package/evidence metadata."""
    value = intake["requirement_intake"]
    return {
        "intake_id": value["intake_id"],
        "requirement_revision": value["requirement_revision"],
        "status": value["status"],
        "requirement_authority_basis": value["requirement_authority_basis"],
        "human_owner": value["human_owner"],
        "human_approver": value["human_approver"],
        "approval": value["approval"],
        "requirements": value["requirements"],
        "unresolved_questions": value["unresolved_questions"],
        "discovery_eligibility": value["discovery_eligibility"],
        "revision_lineage": value["revision_lineage"],
    }


def requirement_digest(intake: dict[str, Any]) -> str:
    return sha256(_authority_payload(intake))


def new_requirement_intake(package_id: str, owner: dict[str, str], approver: dict[str, str], authority_basis: str, requirements: list[dict[str, Any]], *, intake_id: str | None = None) -> dict[str, Any]:
    if authority_basis not in AUTHORITY_BASES:
        raise ValueError("invalid requirement_authority_basis")
    intake_id = intake_id or _id("RI", {"package_id": package_id, "requirements": requirements})
    document = {
        "schema_version": SCHEMA_VERSION, "artifact_type": "REQUIREMENT_INTAKE",
        "package": {"package_id": package_id, "package_revision": 1, "created_at": utc_now(), "updated_at": utc_now()},
        "requirement_intake": {
            "intake_id": intake_id, "requirement_revision": 1, "requirement_digest": "PENDING",
            "status": "DRAFT", "requirement_authority_basis": authority_basis,
            "human_owner": copy.deepcopy(owner), "human_approver": copy.deepcopy(approver),
            "approval": {"status": "DRAFT", "approved_at": None, "approval_reference": None},
            "requirements": copy.deepcopy(requirements), "unresolved_questions": [],
            "revision_lineage": {"supersedes_requirement_intake_id": None, "supersedes_requirement_digest": None, "change_reason": None},
            "discovery_eligibility": {"eligible": False, "boundary": None, "exclusions": [], "expiry_or_checkpoint": None, "stop_conditions": []},
        },
    }
    document["requirement_intake"]["requirement_digest"] = requirement_digest(document)
    document["package"]["package_digest"] = sha256(document["package"])
    return document


def revise_requirement_intake(document: dict[str, Any], changes: dict[str, Any], change_reason: str) -> dict[str, Any]:
    """Return a new semantic revision; package-only edits use update_package_metadata."""
    if document.get("artifact_type") != "REQUIREMENT_INTAKE":
        raise ValueError("requirement revision requires REQUIREMENT_INTAKE")
    revised = copy.deepcopy(document); current = revised["requirement_intake"]
    prior_digest = current["requirement_digest"]
    for key, value in changes.items():
        if key not in current:
            raise ValueError(f"unknown requirement authority field: {key}")
        current[key] = copy.deepcopy(value)
    current["requirement_revision"] += 1
    current["revision_lineage"] = {"supersedes_requirement_intake_id": current["intake_id"], "supersedes_requirement_digest": prior_digest, "change_reason": change_reason}
    current["requirement_digest"] = requirement_digest(revised)
    _touch_package(revised)
    return revised


def update_package_metadata(document: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
    """Metadata-only edit; requirement digest intentionally remains unchanged."""
    result = copy.deepcopy(document); result["package"].update(copy.deepcopy(changes)); _touch_package(result)
    return result


def _touch_package(document: dict[str, Any]) -> None:
    package = document["package"]; package["package_revision"] = int(package.get("package_revision", 0)) + 1; package["updated_at"] = utc_now()
    package["package_digest"] = sha256({key: value for key, value in package.items() if key != "package_digest"})


def disposition(reason_code: str, *, blocking_ids: list[str] | None = None, missing_fields: list[str] | None = None, refinement_owner: Any = None, next_permitted_action: str = "HUMAN_REVIEW_ONLY", candidate_scoping_authority: str = "NONE", implementation_authority: str = "NONE") -> dict[str, Any]:
    return {"status": "BLOCKED", "reason_code": reason_code, "blocking_ids": sorted(set(blocking_ids or [])), "missing_fields": sorted(set(missing_fields or [])), "refinement_owner": refinement_owner, "next_permitted_action": next_permitted_action, "candidate_scoping_authority": candidate_scoping_authority, "implementation_authority": implementation_authority}


def validate_requirement_intake(document: dict[str, Any]) -> dict[str, Any]:
    if document.get("schema_version") != SCHEMA_VERSION or document.get("artifact_type") != "REQUIREMENT_INTAKE":
        return disposition("REQUIREMENT_INSUFFICIENT", missing_fields=["valid_v0_3_requirement_intake"])
    intake = document.get("requirement_intake")
    if not isinstance(intake, dict):
        return disposition("REQUIREMENT_INSUFFICIENT", missing_fields=["schema_valid_v0_3_requirement_intake"])
    schema_errors = _schema_errors(document)
    if schema_errors and not {"intake_id", "requirement_revision", "requirement_digest", "requirements", "unresolved_questions", "discovery_eligibility"} <= set(intake):
        return disposition("REQUIREMENT_INSUFFICIENT", missing_fields=["schema_valid_v0_3_requirement_intake"])
    missing: list[str] = []; blocking: list[str] = []
    if intake.get("status") not in REQUIREMENT_STATUSES: missing.append("requirement_status")
    if intake.get("requirement_authority_basis") not in AUTHORITY_BASES: missing.append("requirement_authority_basis")
    for name in ("human_owner", "human_approver"):
        if not intake.get(name, {}).get("name_or_role"): missing.append(name)
    for requirement in intake.get("requirements", []):
        rid = requirement.get("requirement_id", "REQUIREMENT")
        blocking.append(rid)
        for field in REQUIREMENT_FIELDS:
            value = requirement.get(field)
            if value in (None, "", [], {}): missing.append(f"{rid}.{field}")
        confidence = requirement.get("requirement_confidence", {})
        if (confidence.get("value") not in CONFIDENCE
                or confidence.get("basis_type") not in HUMAN_CONFIDENCE_BASES
                or confidence.get("human_attestation") is not True
                or confidence.get("evidence_used_as_authority") is not False
                or not confidence.get("basis_text")):
            missing.append(f"{rid}.requirement_confidence")
        if requirement.get("source_type", "HUMAN_DECLARATION") != "HUMAN_DECLARATION": missing.append(f"{rid}.human_requirement_authority")
    if not intake.get("requirements"): missing.append("requirements")
    material_questions = [q.get("question_id", "QUESTION") for q in intake.get("unresolved_questions", []) if q.get("materiality", "MATERIAL") == "MATERIAL" and q.get("status", "OPEN") != "RESOLVED"]
    if material_questions: missing.append("material_unresolved_questions"); blocking.extend(material_questions)
    approval = intake.get("approval", {})
    eligibility = intake.get("discovery_eligibility", {})
    if intake.get("status") == "APPROVED_FOR_DISCOVERY":
        if approval.get("status") != "APPROVED_FOR_DISCOVERY" or not approval.get("approved_at") or not approval.get("approval_reference"): missing.append("approval_record")
        for field in ("boundary", "exclusions", "expiry_or_checkpoint", "stop_conditions"):
            if eligibility.get(field) in (None, "", [], {}): missing.append(f"discovery_eligibility.{field}")
        if not eligibility.get("eligible"): missing.append("discovery_eligibility.eligible")
    if intake.get("requirement_digest") != requirement_digest(document): missing.append("requirement_digest")
    if schema_errors: missing.append("schema_valid_v0_3_requirement_intake")
    if missing:
        return disposition("REQUIREMENT_INSUFFICIENT", blocking_ids=blocking, missing_fields=missing, refinement_owner=intake.get("human_owner"), next_permitted_action="ARTPKG_1_REFINEMENT_ONLY")
    return {"status": "PASS", "reason_code": None, "blocking_ids": [], "missing_fields": [], "requirement_digest": intake["requirement_digest"], "discovery_eligible": intake["status"] == "APPROVED_FOR_DISCOVERY"}


def approved_requirement_snapshot(intake: dict[str, Any]) -> dict[str, Any]:
    result = validate_requirement_intake(intake)
    if result["status"] != "PASS" or not result["discovery_eligible"]:
        raise ValueError("requirement intake is not approved for discovery")
    value = intake["requirement_intake"]
    return copy.deepcopy({"intake_id": value["intake_id"], "requirement_revision": value["requirement_revision"], "requirement_digest": value["requirement_digest"], "approved_requirement_authority": _authority_payload(intake)})


def export_dwo(intake: dict[str, Any], selected_requirement_ids: list[str]) -> dict[str, Any]:
    snapshot = approved_requirement_snapshot(intake); authority = snapshot["approved_requirement_authority"]
    available = {item["requirement_id"] for item in authority["requirements"]}
    if not selected_requirement_ids or not set(selected_requirement_ids) <= available:
        raise ValueError("DWO selected requirements are missing or invalid")
    dwo = {"dwo_id": _id("DWO", {"snapshot": snapshot, "selected": selected_requirement_ids}), "requirement_binding": {**snapshot, "selected_requirement_ids": sorted(selected_requirement_ids)}, "approval_attestation": authority["approval"], "discovery_authority": authority["discovery_eligibility"], "stale_binding_invariant": "Requirement intake ID, revision, and digest must match the current approved immutable snapshot."}
    dwo["dwo_digest"] = sha256(dwo); return dwo


def new_evidence_enriched_scope(snapshot: dict[str, Any], dwo: dict[str, Any], discovery_run: dict[str, Any], candidate: dict[str, Any], evidence: list[dict[str, Any]], *, scope_id: str | None = None) -> dict[str, Any]:
    scope_id = scope_id or _id("SCP", {"snapshot": snapshot, "candidate": candidate})
    return {"schema_version": SCHEMA_VERSION, "artifact_type": "EVIDENCE_ENRICHED_SCOPE", "package": {"package_id": _id("PKG", scope_id), "package_revision": 1, "created_at": utc_now(), "updated_at": utc_now()}, "scope": {"scope_id": scope_id, "status": "EVIDENCE_BOUND", "requirement_snapshot": copy.deepcopy(snapshot), "dwo_binding": copy.deepcopy(dwo), "discovery_run_binding": copy.deepcopy(discovery_run), "candidates": [copy.deepcopy(candidate)], "scope_approval": {"status": "DRAFT", "approver": None, "approved_at": None, "approval_reference": None}}, "evidence": copy.deepcopy(evidence)}


def validate_evidence_enriched_scope(document: dict[str, Any], current_intake: dict[str, Any] | None = None) -> dict[str, Any]:
    if document.get("schema_version") != SCHEMA_VERSION or document.get("artifact_type") != "EVIDENCE_ENRICHED_SCOPE":
        return disposition("SCOPE_NOT_APPROVED", missing_fields=["valid_v0_3_evidence_enriched_scope"])
    scope = document.get("scope")
    if not isinstance(scope, dict):
        return disposition("SCOPE_NOT_APPROVED", missing_fields=["schema_valid_v0_3_evidence_enriched_scope"])
    missing: list[str] = []; blocking: list[str] = []
    if current_intake is None:
        return disposition("STALE_REQUIREMENT_BINDING", blocking_ids=[scope.get("scope_id", "SCOPE")], missing_fields=["current_authoritative_requirement_intake"], next_permitted_action="REBIND_TO_CURRENT_ARTPKG_1")
    schema_errors = _schema_errors(document)
    if schema_errors and not {"scope_id", "requirement_snapshot", "dwo_binding", "discovery_run_binding", "candidates", "scope_approval"} <= set(scope):
        return disposition("SCOPE_NOT_APPROVED", missing_fields=["schema_valid_v0_3_evidence_enriched_scope"])
    current_result = validate_requirement_intake(current_intake)
    if current_result["status"] != "PASS" or not current_result.get("discovery_eligible"):
        return disposition("STALE_REQUIREMENT_BINDING", blocking_ids=[scope.get("scope_id", "SCOPE")], missing_fields=["current_approved_requirement_intake"], next_permitted_action="REBIND_TO_CURRENT_ARTPKG_1")
    snapshot = scope.get("requirement_snapshot", {}); authority = snapshot.get("approved_requirement_authority")
    if (not authority or sha256(authority) != snapshot.get("requirement_digest")
            or authority.get("status") != "APPROVED_FOR_DISCOVERY"
            or authority.get("approval", {}).get("status") != "APPROVED_FOR_DISCOVERY"
            or not authority.get("discovery_eligibility", {}).get("eligible")):
        return disposition("STALE_REQUIREMENT_BINDING", blocking_ids=[scope.get("scope_id", "SCOPE")], missing_fields=["current_immutable_requirement_snapshot"], next_permitted_action="REBIND_TO_CURRENT_ARTPKG_1")
    current = current_intake["requirement_intake"]
    if ((snapshot.get("intake_id"), snapshot.get("requirement_revision"), snapshot.get("requirement_digest"))
            != (current.get("intake_id"), current.get("requirement_revision"), current.get("requirement_digest"))
            or authority != _authority_payload(current_intake)):
        return disposition("STALE_REQUIREMENT_BINDING", blocking_ids=[scope.get("scope_id", "SCOPE")], missing_fields=["current_immutable_requirement_snapshot"], next_permitted_action="REBIND_TO_CURRENT_ARTPKG_1")
    dwo = scope.get("dwo_binding", {}); binding = dwo.get("requirement_binding", {})
    computed_dwo_digest = sha256({key: value for key, value in dwo.items() if key != "dwo_digest"}) if dwo else None
    required_dwo = ("dwo_id", "requirement_binding", "approval_attestation", "discovery_authority", "dwo_digest")
    required_binding = ("intake_id", "requirement_revision", "requirement_digest", "selected_requirement_ids")
    required_discovery = ("boundary", "exclusions", "expiry_or_checkpoint", "stop_conditions")
    if (any(not dwo.get(field) for field in required_dwo)
            or any(binding.get(field) in (None, "", []) for field in required_binding)
            or any(dwo.get("discovery_authority", {}).get(field) in (None, "", []) for field in required_discovery)
            or binding.get("requirement_digest") != snapshot.get("requirement_digest")
            or (binding.get("intake_id"), binding.get("requirement_revision"), binding.get("requirement_digest")) != (current["intake_id"], current["requirement_revision"], current["requirement_digest"])
            or not set(binding.get("selected_requirement_ids", [])) <= {item["requirement_id"] for item in current["requirements"]}
            or dwo.get("approval_attestation") != current["approval"]
            or dwo.get("discovery_authority") != current["discovery_eligibility"]
            or not dwo.get("dwo_digest") or dwo.get("dwo_digest") != computed_dwo_digest):
        missing.append("current_dwo_binding")
    run = scope.get("discovery_run_binding", {})
    for field in ("run_id", "snapshot", "completed_at", "evidence_manifest_digest"):
        if not run.get(field): missing.append(f"discovery_run_binding.{field}")
    candidates = scope.get("candidates", [])
    if len(candidates) != 1: missing.append("exactly_one_bounded_candidate")
    else:
        candidate = candidates[0]; blocking.append(candidate.get("candidate_id", "CANDIDATE"))
        for field in ("proposed_change", "observed_current_behavior", "execution_path", "direct_callers", "direct_tests", "contract_interface_evidence", "expected_affected_surfaces", "preserved_surfaces", "blast_radius", "positive_acceptance_criterion", "negative_fail_closed_criterion", "regression_criterion", "rollback_criterion", "implementation_exclusions"):
            if candidate.get(field) in (None, "", [], {}): missing.append(f"candidate.{field}")
        for field in ("unresolved_assumption_ids", "unresolved_conflict_ids"):
            if candidate.get(field): missing.append(f"candidate.{field}")
    for item in document.get("evidence", []):
        relation = item.get("relation_type")
        if relation in FORBIDDEN_EVIDENCE_RELATIONS or relation not in EVIDENCE_RELATIONS:
            missing.append("evidence.relation_type")
        if relation == "REQUIRES_REQUIREMENT_REFINEMENT":
            return disposition("REQUIREMENT_INSUFFICIENT", blocking_ids=[item.get("evidence_id", "EVIDENCE")], missing_fields=["requirement_refinement"], refinement_owner=authority.get("human_owner"), next_permitted_action="ARTPKG_1_REFINEMENT_ONLY")
    approval = scope.get("scope_approval", {})
    if scope.get("status") == "SCOPE_APPROVED":
        for field in ("approver", "approved_at", "approval_reference"):
            if not approval.get(field): missing.append(f"scope_approval.{field}")
        if approval.get("status") != "SCOPE_APPROVED": missing.append("scope_approval.status")
    if schema_errors: missing.append("schema_valid_v0_3_evidence_enriched_scope")
    if missing:
        return disposition("SCOPE_NOT_APPROVED", blocking_ids=blocking, missing_fields=missing, next_permitted_action="ARTPKG_2_SCOPE_REFINEMENT_ONLY")
    if scope.get("status") != "SCOPE_APPROVED":
        return disposition("SCOPE_NOT_APPROVED", blocking_ids=blocking, next_permitted_action="HUMAN_SCOPE_APPROVAL_REQUIRED", candidate_scoping_authority="DRAFT_ONLY")
    return {"status": "PASS", "reason_code": "IMPLEMENTATION_AUTHORITY_ABSENT", "blocking_ids": [], "missing_fields": [], "next_permitted_action": "SEPARATE_IMPLEMENTATION_AUTHORIZATION_REQUIRED", "candidate_scoping_authority": "SCOPE_APPROVED", "implementation_authority": "NONE"}


def load_v03_or_legacy(path: str) -> dict[str, Any]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if document.get("schema_version") == SCHEMA_VERSION:
        validate_v03_schema(document)
        return document
    if document.get("schema_version") in {"0.1", "0.2"}:
        return {"schema_version": document["schema_version"], "artifact_type": "GENERAL", "requirement_authority": "UNVERIFIED_LEGACY", "legacy_document": document}
    raise ValueError("unsupported ArtPkg schema version")


def render_v03(document: dict[str, Any]) -> str:
    if document.get("artifact_type") == "REQUIREMENT_INTAKE":
        value = document["requirement_intake"]
        return "\n".join(["# ArtPkg v0.3 Requirement Intake", "", f"- Intake ID: `{value['intake_id']}`", f"- Requirement revision: `{value['requirement_revision']}`", f"- Requirement digest: `{value['requirement_digest']}`", f"- Status: `{value['status']}`", f"- Authority basis: `{value['requirement_authority_basis']}`", "", "## Human requirements", *[f"- `{item.get('requirement_id')}`: {item.get('intended_behavior', 'UNKNOWN')}" for item in value["requirements"]], ""])
    if document.get("artifact_type") == "EVIDENCE_ENRICHED_SCOPE":
        scope = document["scope"]
        return "\n".join(["# ArtPkg v0.3 Evidence-Enriched Scope", "", f"- Scope ID: `{scope['scope_id']}`", f"- Status: `{scope['status']}`", f"- Requirement digest: `{scope['requirement_snapshot'].get('requirement_digest', 'UNKNOWN')}`", f"- Candidate count: `{len(scope.get('candidates', []))}`", ""])
    return "# ArtPkg legacy/general artifact\n\n- Requirement authority: `UNVERIFIED_LEGACY`\n"
