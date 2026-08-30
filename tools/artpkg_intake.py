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


def _queue_item(qid: str, item: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "kind": "answer",
        "id": qid,
        "label": _question_text(qid),
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
            queues["needs_answer"].append(_queue_item(qid, item, "seeded answer rejected; replacement required"))
        elif state in {"UNKNOWN", "DEFERRED", "TO_BE_INSPECTED"} or qid in blocking_ids:
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
            review_item = {
                "kind": "record",
                "id": record["id"],
                "section": section,
                "label": section.replace("_", " ").title(),
                "state": record.get("review_disposition", "SEEDED_PENDING_REVIEW"),
                "value": record.get("fields", {}),
                "confidence_score": record.get("confidence_score"),
                "review_priority": record.get("review_priority"),
                "source_type": record.get("source_type"),
                "source_reference": record.get("source_reference"),
                "reason": "seeded record needs human review",
            }
            if record.get("confidence_score", 0) < 90:
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


def reject_seeded_answer(session: dict[str, Any], question_id: str, reason: str, reviewer: str) -> dict[str, Any]:
    item = session["document"]["answers"][question_id]
    item["review_disposition"] = "HUMAN_REJECTED"
    item["rejection_reason"] = reason
    item["reviewer"] = reviewer
    item["last_edit_timestamp"] = now()
    _refresh_session(session)
    return item


def _refresh_session(session: dict[str, Any]) -> None:
    session_dir = Path(session["session_dir"])
    questionnaire.save_answers(session["document"], str(session_dir / "answers.json"))
    seed = json.loads((session_dir / "seed.json").read_text(encoding="utf-8"))
    session["validation"] = questionnaire.validate_answers(session["document"])
    session["review_queues"] = build_review_queues(session["document"], seed, session["validation"])
    save_intake_session(session)
