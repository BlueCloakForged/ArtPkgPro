"""Project ArtPkg readiness into Archify IR plus a semantic mapping sidecar."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
    validation = session["validation"]
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
    source = session.get("source", {})
    validation = session.get("validation", {})
    node_records = {
        "preArtifacts": ["PKG-007"],
        "seededDraft": ["PKG-002"],
        "reviewQueues": ["INTAKE-REVIEW-QUEUES"],
        "authorityState": ["AUT-001", "AUT-008", "AUT-009"],
        "acceptanceCriteria": ["AC-SET"],
        "evidenceState": ["EVD-SET", "VAL-001", "VAL-002", "VAL-003", "VAL-004"],
        "gateReadiness": ["Gate A", "Gate B", "Gate C", "Gate D"],
        "nextPermittedAction": ["HND-007"],
    }
    nodes = []
    for component in ir["components"]:
        component_id = component["id"]
        authority_state = "NO_IMPLEMENTATION_AUTHORITY" if component_id == "authorityState" else "NOT_AUTHORITY"
        nodes.append({
            "archify_id": component_id,
            "kind": "readiness_component",
            "artpkg_records": node_records[component_id],
            "provenance": "DERIVED_BY_SCRIPT" if component_id in {"reviewQueues", "gateReadiness", "nextPermittedAction"} else "SOURCE_ARTIFACT",
            "answer_state": component.get("tag", "UNKNOWN"),
            "authority_state": authority_state,
            "relationship_status": "deterministic_projection_rule",
            "source_artifact_sha256": source.get("sha256"),
        })
    return {
        "schema_version": 1,
        "artifact_type": "ARTPKG_ARCHIFY_MAPPING_SIDECAR",
        "status": "DRAFT_REVIEW_ARTIFACT",
        "inputs": [{"path": source.get("path"), "stored_path": source.get("stored_path"), "sha256": source.get("sha256"), "role": "SOURCE_ARTIFACT"}],
        "validation_status": validation.get("status"),
        "projection_rules": [
            {"id": "RULE-001", "description": "Every Archify node maps to an ArtPkg record group or explicit deterministic aggregation."},
            {"id": "RULE-002", "description": "Every Archify edge maps to a deterministic intake/readiness relationship."},
            {"id": "RULE-003", "description": "Archify rendering cannot change ArtPkg authority, gate status, or next permitted action."},
        ],
        "nodes": nodes,
        "edges": [{"archify_id": edge["id"], "relation_type": "deterministic_readiness_relation", "rule": "RULE-002"} for edge in ir.get("connections", [])],
        "negative_assertions": [
            "No node grants implementation authority.",
            "No evidence node claims runtime verification.",
            "No Archify receipt is treated as ArtPkg gate evidence.",
        ],
    }


def validate_projection_mapping(ir: dict[str, Any], mapping: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    component_ids = {component["id"] for component in ir.get("components", [])}
    mapped_node_ids = {node.get("archify_id") for node in mapping.get("nodes", [])}
    edge_ids = {edge["id"] for edge in ir.get("connections", []) if "id" in edge}
    mapped_edge_ids = {edge.get("archify_id") for edge in mapping.get("edges", [])}

    for missing in sorted(component_ids - mapped_node_ids):
        issues.append({"code": "UNMAPPED_NODE", "subject": missing})
    for missing in sorted(edge_ids - mapped_edge_ids):
        issues.append({"code": "UNMAPPED_EDGE", "subject": missing})
    for node in mapping.get("nodes", []):
        if node.get("archify_id") == "authorityState" and node.get("authority_state") not in {"NO_IMPLEMENTATION_AUTHORITY", "NOT_EVALUATED", "NOT_AUTHORITY"}:
            issues.append({"code": "AUTHORITY_ELEVATION", "subject": "authorityState"})
        if node.get("archify_id") == "evidenceState" and node.get("authority_state") in {"VERIFIED", "PASS"}:
            issues.append({"code": "EVIDENCE_ELEVATION", "subject": "evidenceState"})

    return {
        "schema_version": 1,
        "status": "PASS" if not issues else "BLOCKED",
        "issues": issues,
        "artpkg_validation_status": validation.get("status"),
    }
