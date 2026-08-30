"""Local ArtPkg intake sessions and review queues."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import artifacts_package_questionnaire as questionnaire

REVIEW_QUEUES = (
    "needs_answer",
    "needs_confirmation",
    "authority_sensitive",
    "evidence_sensitive",
    "ready_for_quick_review",
)

AUTHORITY_PREFIXES = ("AUT-", "HAR-", "HND-", "FIN-")
AUTHORITY_IDS = {"SEC-001", "SEC-001-CATEGORIES", "BND-001", "BND-002", "BND-005", "BND-006"}
EVIDENCE_PREFIXES = ("AC-", "EVD-", "VAL-")
EVIDENCE_IDS = {"OVR-003", "OVR-007", "ENV-005", "ENV-006", "OUT-003"}

DEFAULT_DOWNSTREAM_EFFECTS = [
    "Controls whether later reviewers can treat the package as complete.",
    "Changes how unresolved gaps appear in the readiness visualization.",
]

PREFIX_DOWNSTREAM_EFFECTS = {
    "AUT": [
        "Affects whether ArtPkg treats the package as discovery, review, or implementation-authorized work.",
        "Limits downstream claims that depend on human approval.",
    ],
    "BND": [
        "Prevents scope expansion when the package is handed to another reviewer or agent.",
        "Constrains authority, acceptance criteria, validation, and blast-radius visualization.",
    ],
    "AC": [
        "Determines what evidence can satisfy a requirement.",
        "Affects evidence-sensitive gaps and gate readiness.",
    ],
    "EVD": [
        "Controls whether claims are backed by inspectable source material.",
        "Affects confidence in acceptance and validation results.",
    ],
    "VAL": [
        "Affects whether the package can claim the behavior has been checked.",
        "Changes readiness and downstream handoff risk.",
    ],
    "SEC": [
        "Affects restricted-content handling and safe failure requirements.",
        "May add safety, redaction, or access-control questions downstream.",
    ],
}

PREFIX_REVIEW_GUIDANCE = {
    "AUT": {
        "decision_prompt": "Identify who granted permission, what permission exists, and where that authority is recorded.",
        "answer_scaffold": "\n".join([
            "Authority granted by:",
            "- ...",
            "",
            "Authority permits:",
            "- ...",
            "",
            "Authority does not permit:",
            "- ...",
            "",
            "Recorded in:",
            "- ...",
        ]),
    },
    "BND": {
        "decision_prompt": "What boundary should keep this artifact package from expanding beyond its intended purpose.",
        "answer_scaffold": "\n".join([
            "Boundary:",
            "- ...",
            "",
            "Included:",
            "- ...",
            "",
            "Excluded:",
            "- ...",
            "",
            "Source basis:",
            "- ...",
        ]),
    },
    "AC": {
        "decision_prompt": "What must be true before a requirement can be treated as accepted.",
        "answer_scaffold": "\n".join([
            "Pass condition:",
            "- ...",
            "",
            "Fail condition:",
            "- ...",
            "",
            "Evidence required:",
            "- ...",
        ]),
    },
    "EVD": {
        "decision_prompt": "What evidence supports a claim, where it came from, and what it does not prove.",
        "answer_scaffold": "\n".join([
            "Evidence observed:",
            "- ...",
            "",
            "Source location:",
            "- ...",
            "",
            "Supports this claim:",
            "- ...",
            "",
            "Limitations:",
            "- ...",
        ]),
    },
    "VAL": {
        "decision_prompt": "What validation has been performed and what remains unchecked.",
        "answer_scaffold": "\n".join([
            "Validated by:",
            "- ...",
            "",
            "Result:",
            "- ...",
            "",
            "Still unverified:",
            "- ...",
        ]),
    },
    "SEC": {
        "decision_prompt": "Whether sensitive, restricted, or safety-relevant material is involved and how it must be handled.",
        "answer_scaffold": "\n".join([
            "Sensitive or restricted material:",
            "- ...",
            "",
            "Required handling:",
            "- ...",
            "",
            "Controls or redactions:",
            "- ...",
        ]),
    },
}

QUESTION_REVIEW_GUIDANCE = {
    "BND-001": {
        "decision_prompt": "What work this artifact package is allowed to cover.",
        "answer_scaffold": "\n".join([
            "This package is in scope for:",
            "- ...",
            "",
            "It may discuss or change:",
            "- ...",
            "",
            "It may make decisions about:",
            "- ...",
            "",
            "It does not authorize:",
            "- ...",
            "",
            "Source basis:",
            "- ...",
        ]),
        "missing_summary": "No explicit in-scope statement was found in the uploaded artifact. Provide a human clarification before relying on scope-sensitive downstream decisions.",
    },
    "BND-002": {
        "decision_prompt": "What nearby work must stay outside this package even if it is related.",
        "answer_scaffold": "\n".join([
            "This package is out of scope for:",
            "- ...",
            "",
            "Do not infer approval to change:",
            "- ...",
            "",
            "Source basis:",
            "- ...",
        ]),
        "missing_summary": "ArtPkg did not find an explicit out-of-scope boundary in the uploaded artifact.",
    },
}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _session_id(source: Path, digest: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_stem = "".join(ch if ch.isalnum() else "-" for ch in source.stem).strip("-").lower()[:32] or "pre-artifacts"
    return f"{stamp}-{safe_stem}-{digest[:12]}"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def create_intake_session(pre_artifacts_path: str | Path, workspace: str | Path, template_path: str | Path | None = None, respondent: str = "") -> dict[str, Any]:
    source = Path(pre_artifacts_path).expanduser().resolve()
    if source.suffix.lower() not in {".md", ".markdown", ".txt"}:
        raise ValueError("unsupported upload type; expected Markdown or text pre-artifacts file")
    if not source.exists():
        raise FileNotFoundError(source)

    workspace_path = Path(workspace).expanduser().resolve()
    digest = sha256_file(source)
    session_dir = workspace_path / ".artpkg" / "intake_sessions" / _session_id(source, digest)
    session_dir.mkdir(parents=True, exist_ok=False)

    stored_source = session_dir / "source_pre_artifacts.md"
    shutil.copyfile(source, stored_source)

    resolved_template = Path(template_path).expanduser().resolve() if template_path else Path(questionnaire.resolve_template_path(workspace_path))
    document = questionnaire.new_answers(str(resolved_template), str(session_dir), respondent)
    seed = questionnaire.seed_from_pre_artifacts(str(stored_source))
    for qid, item in seed["answers"].items():
        questionnaire.set_answer(document, qid, item["value"], item["state"], "SOURCE_ARTIFACT", str(stored_source))
        document["answers"][qid]["confidence_score"] = item["confidence_score"]
        document["answers"][qid]["confidence_label"] = item["confidence_label"]
        document["answers"][qid]["review_priority"] = item["review_priority"]
        document["answers"][qid]["confidence_basis"] = item["confidence_basis"]
        document["answers"][qid]["review_disposition"] = "SEEDED_PENDING_REVIEW"
    created_records = questionnaire.merge_seed_records(document, seed)
    validation = questionnaire.validate_answers(document)
    queues = build_review_queues(document, seed, validation)

    questionnaire.save_answers(document, str(session_dir / "answers.json"))
    _write_json(session_dir / "seed.json", seed)

    session = {
        "schema_version": 1,
        "session_id": session_dir.name,
        "session_dir": str(session_dir),
        "created": now(),
        "updated": now(),
        "source": {"path": str(source), "stored_path": str(stored_source), "sha256": digest},
        "answers_path": str(session_dir / "answers.json"),
        "seed_path": str(session_dir / "seed.json"),
        "created_records": created_records,
        "validation": validation,
        "review_queues": queues,
        "document": document,
    }
    save_intake_session(session)
    return session


def _question_text(qid: str) -> str:
    return questionnaire.QUESTION_CATALOG.get(qid, {}).get("prompt", qid)


def _question_prefix(qid: str) -> str:
    return "HAR" if qid.startswith("HAR-") else qid.split("-", 1)[0]


def _default_answer_scaffold(question: dict[str, Any]) -> str:
    answer_type = question.get("type", "LONG_TEXT")
    prompt = question.get("prompt", "this question")
    if answer_type in {"ENUM", "BOOLEAN", "MULTI_ENUM"}:
        return f"Select the truthful value for {prompt}. Add a source basis when the value came from the uploaded artifact."
    if answer_type == "PATH_OR_URI":
        return "Reference:\n- ...\n\nWhy this reference is the correct package context:\n- ..."
    return "\n".join([
        "Answer:",
        "- ...",
        "",
        "Source basis:",
        "- ...",
        "",
        "Limits or uncertainty:",
        "- ...",
    ])


def _review_guidance(qid: str, question: dict[str, Any]) -> dict[str, Any]:
    specific = QUESTION_REVIEW_GUIDANCE.get(qid, {})
    prefix = _question_prefix(qid)
    family = PREFIX_REVIEW_GUIDANCE.get(prefix, {})
    return {
        "decision_prompt": specific.get(
            "decision_prompt",
            family.get("decision_prompt", f"What human-owned answer should ArtPkg use for {question.get('prompt', qid)}."),
        ),
        "answer_scaffold": specific.get("answer_scaffold", family.get("answer_scaffold", _default_answer_scaffold(question))),
        "downstream_effects": specific.get(
            "downstream_effects",
            PREFIX_DOWNSTREAM_EFFECTS.get(prefix, DEFAULT_DOWNSTREAM_EFFECTS),
        ),
        "missing_summary": specific.get(
            "missing_summary",
            "ArtPkg did not find a provided answer in the uploaded artifact. Mark it unknown, deferred, not applicable, or provide the human answer.",
        ),
    }


def _question_context(qid: str) -> dict[str, Any]:
    question = questionnaire.QUESTION_CATALOG.get(qid, {"id": qid, "prompt": qid, "type": "LONG_TEXT"})
    prefix = _question_prefix(qid)
    group, group_description = questionnaire.QUESTION_GROUPS.get(
        prefix,
        ("Questionnaire", "Provide the information needed to make this package reviewable."),
    )
    guidance = questionnaire.question_guidance(qid, question)
    review_guidance = _review_guidance(qid, question)
    return {
        "group": guidance.get("group", group),
        "group_description": group_description,
        "prompt": question.get("prompt", qid),
        "answer_type": question.get("type", "LONG_TEXT"),
        "meaning": guidance.get("meaning", group_description),
        "example": guidance.get("example", "A specific, reviewable answer."),
        "choices": sorted(questionnaire.ENUM_CHOICES.get(qid, [])),
        "decision_prompt": review_guidance["decision_prompt"],
        "answer_scaffold": review_guidance["answer_scaffold"],
        "downstream_effects": review_guidance["downstream_effects"],
        "missing_summary": review_guidance["missing_summary"],
    }


def _source_context(qid: str, item: dict[str, Any]) -> dict[str, Any]:
    question = _question_context(qid)
    state = item.get("state", "UNKNOWN")
    value = item.get("value")
    missing = state in {"UNKNOWN", "DEFERRED", "TO_BE_INSPECTED"} or value in {None, "", "UNKNOWN"}
    summary = question["missing_summary"] if missing else "ArtPkg seeded this value from the uploaded artifact. Confirm it only if it is truthful for this package."
    return {
        "answer_status": state,
        "source_status": "missing_in_source" if missing else "seeded_from_source",
        "summary": summary,
        "source_type": item.get("source_type"),
        "source_reference": item.get("source_reference"),
        "current_value": value,
    }


def _confidence_context(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": "Classification confidence",
        "score": item.get("confidence_score"),
        "confidence_label": item.get("confidence_label"),
        "basis": item.get("confidence_basis"),
        "meaning": "Confidence describes ArtPkg's deterministic classification of a missing or seeded source answer; it is not human approval.",
    }


def _state_recommendation(qid: str, item: dict[str, Any]) -> dict[str, Any]:
    state = item.get("state", "UNKNOWN")
    value = item.get("value")
    missing = state in {"UNKNOWN", "DEFERRED", "TO_BE_INSPECTED"} or value in {None, "", "UNKNOWN"}
    source_type = item.get("source_type")
    source_seeded = source_type == "SOURCE_ARTIFACT" and not missing
    sensitive = _is_authority_sensitive(qid) or _is_evidence_sensitive(qid)

    if state == "NOT_APPLICABLE":
        return {
            "suggested_state": "NOT_APPLICABLE",
            "action": "confirm_not_applicable",
            "reason": "Keep NOT_APPLICABLE only when this question cannot truthfully apply to the artifact package.",
            "fallback": "Use PROVIDED when the package needs a human answer, or TO_BE_INSPECTED when applicability is unclear.",
            "checklist": "Confirm the question is outside the package purpose and does not hide an unresolved blocker.",
            "can_auto_apply": False,
        }

    if state == "DEFERRED":
        return {
            "suggested_state": "DEFERRED",
            "action": "record_deferral_condition",
            "reason": "A deferred answer remains useful only when the package records who owns it, what will resolve it, and when it should be revisited.",
            "fallback": "Use PROVIDED when the human answer is known, or TO_BE_INSPECTED when source inspection is still needed.",
            "checklist": "Name the owner, condition, expected evidence, and review point for the deferral.",
            "can_auto_apply": False,
        }

    if missing:
        reason = "This missing answer blocks trustworthy downstream decisions."
        if qid == "BND-001":
            reason = "Scope is required before relying on scope-sensitive downstream decisions and blast-radius visualization."
        return {
            "suggested_state": "PROVIDED",
            "action": "write_human_answer",
            "reason": reason,
            "fallback": "Use TO_BE_INSPECTED if the human cannot answer yet and the source needs review.",
            "checklist": "Write a truthful human answer, cite the source basis, and avoid granting new authority by implication.",
            "can_auto_apply": False,
        }

    if source_seeded and sensitive:
        kind = "authority-sensitive" if _is_authority_sensitive(qid) else "evidence-sensitive"
        return {
            "suggested_state": "PROVIDED",
            "action": "confirm_seeded_answer",
            "reason": f"ArtPkg found a seeded value, but this {kind} field needs human confirmation before downstream checks rely on it.",
            "fallback": "Edit the answer before saving, reject it if the source value is wrong, or mark TO_BE_INSPECTED if confirmation is not possible yet.",
            "checklist": "Confirm the value is truthful, applies to this package scope, has a recorded source, and does not broaden authority.",
            "can_auto_apply": False,
        }

    if source_seeded:
        return {
            "suggested_state": "PROVIDED",
            "action": "confirm_seeded_answer",
            "reason": "ArtPkg found a seeded source value. Keep it only if the human reviewer agrees it is truthful and complete.",
            "fallback": "Edit before saving if the value is incomplete, or reject it if it is wrong.",
            "checklist": "Confirm the value matches the package source and is specific enough for later review.",
            "can_auto_apply": False,
        }

    return {
        "suggested_state": state or "PROVIDED",
        "action": "review_current_answer",
        "reason": "Review the current human-owned answer before using it for downstream package decisions.",
        "fallback": "Change the state to UNKNOWN, DEFERRED, TO_BE_INSPECTED, or NOT_APPLICABLE when that is more truthful.",
        "checklist": "Confirm the answer is specific, scoped, sourced, and still accurate.",
        "can_auto_apply": False,
    }


def _record_context(section: str) -> dict[str, Any]:
    prefix = questionnaire.ID_PREFIXES.get(section, section.split("_", 1)[0].upper())
    group, group_description = questionnaire.QUESTION_GROUPS.get(
        prefix,
        (section.replace("_", " ").title(), "Review the seeded record fields before accepting them into the package."),
    )
    return {
        "section": section,
        "label": section.replace("_", " ").title(),
        "group": group,
        "group_description": group_description,
    }


def _record_schema(section: str) -> list[dict[str, Any]]:
    fields = []
    for name, label, choices in questionnaire.RECORD_FIELDS.get(section, []):
        meaning, example = questionnaire.record_field_guidance(section, name, label)
        fields.append({
            "name": name,
            "label": label,
            "meaning": meaning,
            "example": example,
            "choices": sorted(choices or []),
        })
    return fields


def _queue_item(qid: str, item: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "kind": "answer",
        "id": qid,
        "label": _question_text(qid),
        "question": _question_context(qid),
        "source_context": _source_context(qid, item),
        "confidence_context": _confidence_context(item),
        "state_recommendation": _state_recommendation(qid, item),
        "state": item.get("state"),
        "value": item.get("value"),
        "confidence_score": item.get("confidence_score"),
        "review_priority": item.get("review_priority"),
        "source_type": item.get("source_type"),
        "source_reference": item.get("source_reference"),
        "reason": reason,
    }


def _is_authority_sensitive(qid: str) -> bool:
    return qid.startswith(AUTHORITY_PREFIXES) or qid in AUTHORITY_IDS


def _is_evidence_sensitive(qid: str) -> bool:
    return qid.startswith(EVIDENCE_PREFIXES) or qid in EVIDENCE_IDS


def build_review_queues(document: dict[str, Any], seed: dict[str, Any], validation: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    queues: dict[str, list[dict[str, Any]]] = {name: [] for name in REVIEW_QUEUES}
    blocking_ids = set(validation.get("blocking_ids", []))

    for qid in sorted(document.get("answers", {})):
        item = document["answers"][qid]
        state = item.get("state")
        score = item.get("confidence_score")
        disposition = item.get("review_disposition")

        if disposition == "HUMAN_REJECTED":
            queues["needs_answer"].append(_queue_item(qid, item, "seeded answer was rejected and needs replacement"))
        else:
            if state in {"UNKNOWN", "DEFERRED", "TO_BE_INSPECTED"} or qid in blocking_ids:
                queues["needs_answer"].append(_queue_item(qid, item, "unresolved or blocking answer"))
            elif disposition == "SEEDED_PENDING_REVIEW" and (score is None or score < 90):
                queues["needs_confirmation"].append(_queue_item(qid, item, "seeded answer needs human confirmation"))
            elif disposition == "SEEDED_PENDING_REVIEW":
                queues["ready_for_quick_review"].append(_queue_item(qid, item, "high-confidence seeded answer"))

        if _is_authority_sensitive(qid):
            queues["authority_sensitive"].append(_queue_item(qid, item, "authority, scope, safety, or approval-sensitive field"))
        if _is_evidence_sensitive(qid):
            queues["evidence_sensitive"].append(_queue_item(qid, item, "evidence, acceptance, validation, or negative-path field"))

    for section, records in sorted(document.get("records", {}).items()):
        for record in records:
            disposition = record.get("review_disposition", "SEEDED_PENDING_REVIEW")
            review_item = {
                "kind": "record",
                "id": record["id"],
                "section": section,
                "label": section.replace("_", " ").title(),
                "record_context": _record_context(section),
                "record_schema": _record_schema(section),
                "state": disposition,
                "value": record.get("fields", {}),
                "confidence_score": record.get("confidence_score"),
                "review_priority": record.get("review_priority"),
                "source_type": record.get("source_type"),
                "source_reference": record.get("source_reference"),
                "reason": "seeded record needs human review",
            }
            if disposition == "HUMAN_CONFIRMED":
                continue
            if disposition == "HUMAN_REJECTED":
                review_item["reason"] = "seeded record was rejected and needs replacement"
                queues["needs_answer"].append(review_item)
            elif record.get("confidence_score", 0) < 90:
                queues["needs_confirmation"].append(review_item)
            else:
                queues["ready_for_quick_review"].append(review_item)

    return queues


def save_intake_session(session: dict[str, Any]) -> None:
    session_dir = Path(session["session_dir"])
    session["updated"] = now()
    summary = {key: value for key, value in session.items() if key != "document"}
    _write_json(session_dir / "session.json", summary)


def load_intake_session(session_dir: str | Path) -> dict[str, Any]:
    root = Path(session_dir).expanduser().resolve()
    session = json.loads((root / "session.json").read_text(encoding="utf-8"))
    session["document"] = questionnaire.load_answers(str(root / "answers.json"))
    session["validation"] = questionnaire.validate_answers(session["document"])
    seed = json.loads((root / "seed.json").read_text(encoding="utf-8"))
    session["review_queues"] = build_review_queues(session["document"], seed, session["validation"])
    return session


def confirm_answer(session: dict[str, Any], question_id: str, reviewer: str) -> dict[str, Any]:
    item = session["document"]["answers"][question_id]
    item["review_disposition"] = "HUMAN_CONFIRMED"
    item["reviewer"] = reviewer
    item["last_edit_timestamp"] = now()
    _refresh_session(session)
    return item


def provide_answer(session: dict[str, Any], question_id: str, value: Any, reviewer: str, state: str = "PROVIDED") -> dict[str, Any]:
    if state == "PROVIDED" and value in {"", None}:
        raise ValueError("provided answers require a value")
    questionnaire.set_answer(
        session["document"],
        question_id,
        value,
        state,
        "HUMAN_DECLARATION",
        "ArtPkg intake UI",
    )
    item = session["document"]["answers"][question_id]
    item["review_disposition"] = "HUMAN_CONFIRMED"
    item["reviewer"] = reviewer
    item["last_edit_timestamp"] = now()
    _refresh_session(session)
    return item


def reject_seeded_answer(session: dict[str, Any], question_id: str, reason: str, reviewer: str) -> dict[str, Any]:
    item = session["document"]["answers"][question_id]
    item["review_disposition"] = "HUMAN_REJECTED"
    item["rejection_reason"] = reason
    item["reviewer"] = reviewer
    item["last_edit_timestamp"] = now()
    _refresh_session(session)
    return item


def confirm_record(session: dict[str, Any], record_id: str, reviewer: str) -> dict[str, Any]:
    record = questionnaire.find_record(session["document"], record_id)
    record["review_disposition"] = "HUMAN_CONFIRMED"
    record["reviewer"] = reviewer
    record["last_edit"] = now()
    _refresh_session(session)
    return record


def reject_seeded_record(session: dict[str, Any], record_id: str, reason: str, reviewer: str) -> dict[str, Any]:
    record = questionnaire.find_record(session["document"], record_id)
    record["review_disposition"] = "HUMAN_REJECTED"
    record["rejection_reason"] = reason
    record["reviewer"] = reviewer
    record["last_edit"] = now()
    _refresh_session(session)
    return record


def _refresh_session(session: dict[str, Any]) -> None:
    session_dir = Path(session["session_dir"])
    questionnaire.save_answers(session["document"], str(session_dir / "answers.json"))
    seed = json.loads((session_dir / "seed.json").read_text(encoding="utf-8"))
    session["validation"] = questionnaire.validate_answers(session["document"])
    session["review_queues"] = build_review_queues(session["document"], seed, session["validation"])
    save_intake_session(session)
