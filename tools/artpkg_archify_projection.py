"""Project ArtPkg readiness into Archify IR plus a semantic mapping sidecar."""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import artifacts_package_questionnaire as questionnaire

DETERMINISTIC_EDGE_RULES = {
    "sourceSeedsDraft": "EDGE_RULE_SOURCE_ARTIFACT_SEEDS_DRAFT",
    "draftBuildsQueues": "EDGE_RULE_DRAFT_ANSWERS_CLASSIFIED_INTO_REVIEW_QUEUES",
    "queuesExposeAuthority": "EDGE_RULE_AUTHORITY_SENSITIVE_QUEUE_ITEMS_INFORM_AUTHORITY_NODE",
    "queuesExposeAcceptance": "EDGE_RULE_EVIDENCE_QUEUE_ITEMS_INFORM_ACCEPTANCE_NODE",
    "draftBuildsEvidence": "EDGE_RULE_DRAFT_RECORDS_EXPOSE_EVIDENCE_CANDIDATES",
    "authorityBlocksGates": "EDGE_RULE_AUT_001_CONSTRAINS_GATE_READINESS",
    "acceptanceBlocksGates": "EDGE_RULE_ACCEPTANCE_CRITERIA_CONSTRAIN_GATE_READINESS",
    "evidenceBlocksGates": "EDGE_RULE_EVIDENCE_STATE_CONSTRAINS_GATE_READINESS",
    "gatesConstrainAction": "EDGE_RULE_VALIDATE_ANSWERS_NEXT_ACTION_CONSTRAINS_ACTION_NODE",
}


@dataclass
class ProjectionResult:
    ir_path: str
    mapping_path: str
    validation_path: str
    ir: dict[str, Any]
    mapping: dict[str, Any]
    projection_validation: dict[str, Any]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def _answer(document: dict[str, Any], qid: str, default: str = "UNKNOWN") -> dict[str, Any]:
    return document.get("answers", {}).get(qid, {"value": default, "state": default, "source_type": "DERIVED_BY_SCRIPT"})


def _count_queue(session: dict[str, Any], queue: str) -> int:
    return len(session.get("review_queues", {}).get(queue, []))


def _component(component_id: str, kind: str, label: str, sublabel: str, x: int, y: int, tag: str) -> dict[str, Any]:
    return {"id": component_id, "type": kind, "label": label, "sublabel": sublabel, "pos": [x, y], "size": [168, 70], "tag": tag}


def build_readiness_projection(session: dict[str, Any], output_dir: str | Path | None = None) -> ProjectionResult:
    document = session["document"]
    validation = questionnaire.validate_answers(document)
    session["validation"] = validation
    root = Path(output_dir or session["session_dir"]).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    needs_answer = _count_queue(session, "needs_answer")
    needs_confirmation = _count_queue(session, "needs_confirmation")
    authority_items = _count_queue(session, "authority_sensitive")
    evidence_items = _count_queue(session, "evidence_sensitive")
    gate_summary = ", ".join(f"{key}:{gate.get('result', 'UNKNOWN')}" for key, gate in validation.get("gates", {}).items()) or "not evaluated"
    authority = _answer(document, "AUT-001").get("value", "UNKNOWN")
    next_action = _answer(document, "HND-007").get("value", "HUMAN_REVIEW_ONLY")

    ir = {
        "schema_version": 1,
        "diagram_type": "architecture",
        "meta": {
            "title": "ArtPkg Intake Readiness",
            "quality_profile": "showcase",
            "visual_preset": "blueprint",
            "views": [
                {"id": "reviewQueuesView", "label": "Review queues", "focus": ["preArtifacts", "seededDraft", "reviewQueues"], "note": "See what the upload seeded and what still needs human review."},
                {"id": "whyBlockedView", "label": "Why blocked", "focus": ["reviewQueues", "acceptanceCriteria", "authorityState", "gateReadiness"], "note": "Missing answers, acceptance criteria, evidence, or authority keep gates from advancing."},
                {"id": "nextActionView", "label": "Next action", "focus": ["gateReadiness", "nextPermittedAction"], "note": "The map guides review only; it does not authorize implementation."},
            ],
        },
        "components": [
            _component("preArtifacts", "external", "Pre-Artifacts", "uploaded Markdown source", 40, 330, "SOURCE"),
            _component("seededDraft", "backend", "Seeded Draft", "ArtPkg parser/seeder", 260, 330, "DRAFT"),
            _component("reviewQueues", "frontend", "Review Queues", f"{needs_answer} answer / {needs_confirmation} confirm", 500, 190, "HUMAN REVIEW"),
            _component("authorityState", "security", "Authority State", f"AUT-001 {authority}", 760, 120, "NO AUTO APPROVAL"),
            _component("acceptanceCriteria", "security", "Acceptance Criteria", "must link requirements to evidence", 760, 300, "CHECK"),
            _component("evidenceState", "messagebus", "Evidence State", f"{evidence_items} evidence-sensitive fields", 500, 470, "NOT PROOF"),
            _component("gateReadiness", "security", "Gate Readiness", gate_summary, 1000, 260, validation.get("status", "DRAFT")),
            _component("nextPermittedAction", "frontend", "Next Action", str(next_action)[:42], 1000, 470, "REVIEW ONLY"),
        ],
        "boundaries": [
            {"kind": "region", "label": "ArtPkg-owned local intake; Archify renders review only", "wraps": ["preArtifacts", "seededDraft", "reviewQueues", "authorityState", "acceptanceCriteria", "evidenceState", "gateReadiness", "nextPermittedAction"], "pad": 26}
        ],
        "connections": [
            {"id": "sourceSeedsDraft", "from": "preArtifacts", "to": "seededDraft", "label": "seed", "variant": "emphasis", "labelDy": 48},
            {"id": "draftBuildsQueues", "from": "seededDraft", "to": "reviewQueues", "label": "classify questions", "variant": "emphasis"},
            {"id": "queuesExposeAuthority", "from": "reviewQueues", "to": "authorityState", "label": f"{authority_items} sensitive", "variant": "security"},
            {"id": "queuesExposeAcceptance", "from": "reviewQueues", "to": "acceptanceCriteria", "label": "criteria gaps", "variant": "security"},
            {"id": "draftBuildsEvidence", "from": "seededDraft", "to": "evidenceState", "label": "evidence candidates", "variant": "dashed"},
            {"id": "authorityBlocksGates", "from": "authorityState", "to": "gateReadiness", "label": "no implicit authority", "variant": "security"},
            {"id": "acceptanceBlocksGates", "from": "acceptanceCriteria", "to": "gateReadiness", "label": "must be accepted", "variant": "security"},
            {"id": "evidenceBlocksGates", "from": "evidenceState", "to": "gateReadiness", "label": "must be verified", "variant": "security"},
            {"id": "gatesConstrainAction", "from": "gateReadiness", "to": "nextPermittedAction", "label": "limits action", "variant": "emphasis"},
        ],
    }

    mapping = _mapping_for(session, ir)
    projection_validation = validate_projection_mapping(ir, mapping, validation)
    if projection_validation["status"] != "PASS":
        raise ValueError(json.dumps(projection_validation, sort_keys=True))

    ir_path = root / "artpkg-readiness.architecture.json"
    mapping_path = root / "artpkg-readiness.mapping.json"
    validation_path = root / "artpkg-readiness.projection-validation.json"
    _write_json(ir_path, ir)
    _write_json(mapping_path, mapping)
    _write_json(validation_path, projection_validation)
    return ProjectionResult(str(ir_path), str(mapping_path), str(validation_path), ir, mapping, projection_validation)


def _mapping_for(session: dict[str, Any], ir: dict[str, Any]) -> dict[str, Any]:
    document = session["document"]
    source = session.get("source", {})
    validation = session.get("validation", {})
    record_node_answers = {
        "preArtifacts": ["PKG-007"],
        "seededDraft": ["PKG-002"],
        "authorityState": ["AUT-001", "AUT-008", "AUT-009"],
        "evidenceState": ["VAL-001", "VAL-002", "VAL-003", "VAL-004"],
        "nextPermittedAction": ["HND-007"],
    }
    aggregations = {
        "reviewQueues": {
            "record_set": "INTAKE-REVIEW-QUEUES",
            "sections": list(session.get("review_queues", {}).keys()),
            "member_ids": sorted(item.get("id", "UNKNOWN") for queue in session.get("review_queues", {}).values() for item in queue),
            "rule": "AGGREGATE_REVIEW_QUEUE_MEMBERS_BY_ARTPKG_INTAKE_CLASSIFICATION",
        },
        "acceptanceCriteria": {
            "record_set": "AC-SET",
            "sections": ["acceptance_criteria"],
            "member_ids": [record["id"] for record in document.get("records", {}).get("acceptance_criteria", [])],
            "rule": "AGGREGATE_SECTION_RECORDS_FROM_ARTPKG_AC_SET",
        },
        "evidenceState": {
            "record_set": "EVD-SET",
            "sections": ["evidence"],
            "member_ids": [record["id"] for record in document.get("records", {}).get("evidence", [])],
            "rule": "AGGREGATE_SECTION_RECORDS_FROM_ARTPKG_EVD_SET",
        },
        "gateReadiness": {
            "record_set": "ARTPKG_VALIDATION_GATES",
            "sections": ["validation.gates"],
            "member_ids": [f"Gate {key}" for key in sorted(validation.get("gates", {}))],
            "rule": "AGGREGATE_VALIDATE_ANSWERS_GATE_RESULTS_A_THROUGH_D",
        },
    }
    source_catalog = _source_catalog(document, aggregations)
    authority_value = _answer(document, "AUT-001", "NOT_EVALUATED").get("value", "UNKNOWN")
    nodes = []
    for component in ir["components"]:
        component_id = component["id"]
        answer_ids = record_node_answers.get(component_id, [])
        aggregation = aggregations.get(component_id)
        authority_state = authority_value if component_id == "authorityState" else "NOT_AUTHORITY"
        nodes.append({
            "archify_id": component_id,
            "kind": "readiness_component",
            "mapping_type": "aggregation" if aggregation else "records",
            "artpkg_records": answer_ids,
            "aggregation": copy.deepcopy(aggregation),
            "source_answers": {qid: _source_answer(document, qid) for qid in answer_ids},
            "source_records": _source_records(document, aggregation.get("sections", []) if aggregation else []),
            "provenance": "DERIVED_BY_SCRIPT" if component_id in {"reviewQueues", "gateReadiness", "nextPermittedAction"} else "SOURCE_ARTIFACT",
            "answer_state": "SEE_SOURCE_SEMANTICS",
            "source_semantics": {"ir_label": component.get("label"), "ir_sublabel": component.get("sublabel"), "ir_tag": component.get("tag")},
            "authority_state": authority_state,
            "relationship_status": "deterministic_projection_rule",
            "source_artifact_sha256": source.get("sha256"),
        })
    return {
        "schema_version": 1,
        "artifact_type": "ARTPKG_ARCHIFY_MAPPING_SIDECAR",
        "status": "DRAFT_REVIEW_ARTIFACT",
        "inputs": [{"path": source.get("path"), "stored_path": source.get("stored_path"), "sha256": source.get("sha256"), "role": "SOURCE_ARTIFACT"}],
        "source_catalog": source_catalog,
        "validation_status": validation.get("status"),
        "projection_rules": [
            {"id": "RULE-001", "description": "Every Archify node maps to an ArtPkg record group or explicit deterministic aggregation."},
            {"id": "RULE-002", "description": "Every Archify edge maps to a deterministic intake/readiness relationship."},
            {"id": "RULE-003", "description": "Archify rendering cannot change ArtPkg authority, gate status, or next permitted action."},
        ],
        "deterministic_edge_rules": copy.deepcopy(DETERMINISTIC_EDGE_RULES),
        "nodes": nodes,
        "edges": [{"archify_id": edge["id"], "relation_type": "deterministic_readiness_relation", "rule": DETERMINISTIC_EDGE_RULES[edge["id"]]} for edge in ir.get("connections", [])],
        "negative_assertions": [
            "No node grants implementation authority.",
            "No evidence node claims runtime verification.",
            "No Archify receipt is treated as ArtPkg gate evidence.",
        ],
    }


def _source_answer(document: dict[str, Any], qid: str) -> dict[str, Any]:
    item = document.get("answers", {}).get(qid, {})
    return {
        "value": item.get("value", "UNKNOWN"),
        "state": item.get("state", "UNKNOWN"),
        "source_type": item.get("source_type", "UNKNOWN"),
        "source_reference": item.get("source_reference"),
    }


def _source_records(document: dict[str, Any], sections: list[str]) -> dict[str, list[dict[str, Any]]]:
    records: dict[str, list[dict[str, Any]]] = {}
    for section in sections:
        if section.startswith("validation."):
            continue
        records[section] = [
            {
                "id": record.get("id"),
                "fields": record.get("fields", {}),
                "source_type": record.get("source_type"),
                "source_reference": record.get("source_reference"),
            }
            for record in document.get("records", {}).get(section, [])
        ]
    return records


def _source_catalog(document: dict[str, Any], aggregations: dict[str, dict[str, Any]]) -> dict[str, Any]:
    answer_ids = sorted(set(questionnaire.QUESTION_CATALOG) | set(document.get("answers", {})))
    record_ids = sorted(record["id"] for records in document.get("records", {}).values() for record in records)
    return {
        "answer_ids": answer_ids,
        "record_ids": record_ids,
        "aggregation_sets": {item["record_set"]: copy.deepcopy(item) for item in aggregations.values()},
    }


def validate_projection_mapping(ir: dict[str, Any], mapping: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    component_ids = {component["id"] for component in ir.get("components", [])}
    components_by_id = {component["id"]: component for component in ir.get("components", [])}
    mapped_node_ids = {node.get("archify_id") for node in mapping.get("nodes", [])}
    edge_ids = {edge["id"] for edge in ir.get("connections", []) if "id" in edge}
    mapped_edge_ids = {edge.get("archify_id") for edge in mapping.get("edges", [])}
    source_catalog = mapping.get("source_catalog", {})
    known_records = set(source_catalog.get("answer_ids", [])) | set(source_catalog.get("record_ids", []))
    aggregation_sets = source_catalog.get("aggregation_sets", {})
    source_inputs = [item for item in mapping.get("inputs", []) if item.get("role") == "SOURCE_ARTIFACT"]
    input_digests = {item.get("sha256") for item in source_inputs}

    for missing in sorted(component_ids - mapped_node_ids):
        issues.append({"code": "UNMAPPED_NODE", "subject": missing})
    for missing in sorted(edge_ids - mapped_edge_ids):
        issues.append({"code": "UNMAPPED_EDGE", "subject": missing})
    if len(source_inputs) != 1 or len(input_digests) != 1 or not next(iter(input_digests), None):
        issues.append({"code": "SOURCE_DIGEST_MISSING", "subject": "inputs"})
    for node in mapping.get("nodes", []):
        archify_id = node.get("archify_id", "UNKNOWN")
        if node.get("source_artifact_sha256") not in input_digests:
            issues.append({"code": "SOURCE_DIGEST_MISSING", "subject": archify_id})
        records = node.get("artpkg_records", [])
        aggregation = node.get("aggregation")
        if records == [] and not aggregation:
            issues.append({"code": "EMPTY_RECORD_MAPPING", "subject": archify_id})
        for record_id in records:
            if record_id not in known_records:
                issues.append({"code": "UNKNOWN_RECORD_MAPPING", "subject": record_id})
        if node.get("mapping_type") == "aggregation":
            if not _valid_aggregation(aggregation, aggregation_sets):
                issues.append({"code": "AGGREGATION_METADATA_MISSING", "subject": archify_id})
        elif aggregation:
            issues.append({"code": "AGGREGATION_METADATA_MISSING", "subject": archify_id})

        if archify_id == "authorityState":
            source_authority = _source_authority_state(node)
            if source_authority is None or node.get("authority_state") != source_authority:
                issues.append({"code": "AUTHORITY_ELEVATION", "subject": "authorityState"})
        if archify_id == "evidenceState" and _claims_verified_evidence(node, components_by_id.get("evidenceState", {})):
            issues.append({"code": "EVIDENCE_ELEVATION", "subject": "evidenceState"})
    for edge in mapping.get("edges", []):
        if edge.get("archify_id") not in edge_ids:
            issues.append({"code": "UNMAPPED_EDGE", "subject": edge.get("archify_id", "UNKNOWN")})
        if edge.get("relation_type") != "deterministic_readiness_relation" or edge.get("rule") != DETERMINISTIC_EDGE_RULES.get(edge.get("archify_id")):
            issues.append({"code": "INVALID_EDGE_RULE", "subject": edge.get("archify_id", "UNKNOWN")})

    return {
        "schema_version": 1,
        "status": "PASS" if not issues else "BLOCKED",
        "issues": issues,
        "artpkg_validation_status": validation.get("status"),
    }


def _valid_aggregation(aggregation: Any, aggregation_sets: dict[str, Any]) -> bool:
    if not isinstance(aggregation, dict):
        return False
    record_set = aggregation.get("record_set")
    rule = aggregation.get("rule")
    sections = aggregation.get("sections")
    member_ids = aggregation.get("member_ids")
    if not record_set or not rule or not isinstance(sections, list) or not isinstance(member_ids, list):
        return False
    return aggregation_sets.get(record_set) == aggregation


def _source_authority_state(node: dict[str, Any]) -> Any:
    source_authority = node.get("source_answers", {}).get("AUT-001")
    if not source_authority:
        return None
    return source_authority.get("value", "UNKNOWN")


def _claims_verified_evidence(node: dict[str, Any], component: dict[str, Any]) -> bool:
    elevated = {"VERIFIED", "PASS", "PASSED", "RUNTIME_VERIFIED", "PROOF_EXISTS"}
    for item in node.get("source_answers", {}).values():
        if str(item.get("state", "")).upper() in elevated or str(item.get("value", "")).upper() in elevated:
            return True
    for field in ("label", "sublabel", "tag"):
        text = str(component.get(field, "")).upper()
        if any(token in text for token in elevated):
            return True
        if "PROOF EXISTS" in text or "RUNTIME PROOF" in text:
            return True
    return False
