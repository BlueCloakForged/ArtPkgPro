# ArtPkg Intake UI and Archify Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an ArtPkg-owned local intake UI that accepts a pre-artifacts Markdown file, seeds a questionnaire draft, shows review queues for missing/uncertain/sensitive questions, and optionally calls local Archify to render a read-only Package Readiness projection.

**Architecture:** Keep ArtPkg as the parser, questionnaire state owner, validator, and authority boundary. Add focused Python modules for intake sessions/review queues, Archify projection, Archify CLI execution, and a small standard-library local web server. Archify remains an external local renderer invoked by command line; it never owns questionnaire state or approval.

**Tech Stack:** Python 3.10+, standard library `http.server`, `json`, `hashlib`, `tempfile`, `subprocess`, `email.parser`, existing `tools/artifacts_package_questionnaire.py`, optional local Node/Archify executable for integration checks.

**Spec:** `docs/superpowers/specs/2026-08-30-artpkg-archify-projection-design.md`

## Global Constraints

- ArtPkg owns uploaded pre-artifacts, questionnaire state, requirements, authority, provenance, evidence states, validation gates, next permitted action, and human approval boundaries.
- The first interface lives in ArtPkg and calls local Archify only for visual review/projection.
- The first flow is `pre-artifacts Markdown -> ArtPkg intake UI -> parser/seeder -> questionnaire draft + review queue -> human answers/confirmations -> canonical ArtPkg answers JSON -> validation -> Archify readiness projection`.
- Do not modify Archify schemas.
- Do not treat Archify validation as ArtPkg gate evidence.
- Do not infer human approval, requirement priority, authority, or risk acceptance.
- Do not use an LLM to invent graph relationships.
- Do not advance Pipeline-A, activate a BEC, authorize implementation, or authorize execution.
- Preserve `UNKNOWN`, `NONE`, `NOT_APPLICABLE`, `TO_BE_INSPECTED`, and `DEFERRED` as distinct values/states.
- Store local intake sessions under `.artpkg/intake_sessions/`; this directory must be gitignored because it can contain project-specific or restricted content.

---

## File Structure

- Modify: `.gitignore`
  - Add `.artpkg/` to exclude local intake sessions and uploaded pre-artifacts.
- Create: `tools/artpkg_intake.py`
  - Owns intake session creation, uploaded-file digesting, seeded answer merge, review queue classification, answer confirmation/rejection, and session persistence.
- Create: `tools/artpkg_archify_projection.py`
  - Converts canonical ArtPkg answers/validation into an Archify Architecture IR plus ArtPkg mapping sidecar and projection validation report.
- Create: `tools/artpkg_archify_runner.py`
  - Runs local Archify `validate`, `deliver`, and optional `visual-check`, capturing JSON receipts without changing ArtPkg status.
- Create: `tools/artpkg_intake_server.py`
  - Serves the local intake UI and JSON API using Python standard library.
- Create: `tools/artpkg_intake_ui.html`
  - Browser UI for upload, session review queues, questionnaire fields, and readiness map links.
- Modify: `tools/artifacts_package_questionnaire.py`
  - Add a small `intake-ui` CLI entry point that delegates to `artpkg_intake_server.main`.
- Create: `tests/test_artpkg_intake.py`
  - Unit tests for session creation, review queues, persistence, confirmation/rejection, and restricted-content warnings.
- Create: `tests/test_artpkg_archify_projection.py`
  - Unit tests for Archify IR/sidecar generation and fail-closed semantic checks.
- Create: `tests/test_artpkg_archify_runner.py`
  - Unit tests for subprocess command construction and receipt handling.
- Create: `tests/test_artpkg_intake_server.py`
  - Unit tests for multipart upload parsing and API response shapes.
- Modify: `README.md`
  - Document the local intake UI command and safety boundary.
- Modify: `docs/artifacts_package_questionnaire.md`
  - Add operator notes for intake sessions, review queues, and Archify projection.

---

### Task 1: Intake Session and Review Queue Core

**Files:**
- Create: `tools/artpkg_intake.py`
- Create: `tests/test_artpkg_intake.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes:
  - `artifacts_package_questionnaire.new_answers(template_path: str, output_path: str, respondent: str = "") -> dict`
  - `artifacts_package_questionnaire.seed_from_pre_artifacts(path: str) -> dict`
  - `artifacts_package_questionnaire.merge_seed_records(document: dict, seed: dict) -> dict[str, list[str]]`
  - `artifacts_package_questionnaire.validate_answers(document: dict) -> dict`
  - `artifacts_package_questionnaire.save_answers(document: dict, path: str) -> None`
  - `artifacts_package_questionnaire.load_answers(path: str) -> dict`
- Produces:
  - `sha256_file(path: str | Path) -> str`
  - `create_intake_session(pre_artifacts_path: str | Path, workspace: str | Path, template_path: str | Path | None = None, respondent: str = "") -> dict[str, Any]`
  - `load_intake_session(session_dir: str | Path) -> dict[str, Any]`
  - `save_intake_session(session: dict[str, Any]) -> None`
  - `build_review_queues(document: dict[str, Any], seed: dict[str, Any], validation: dict[str, Any]) -> dict[str, list[dict[str, Any]]]`
  - `confirm_answer(session: dict[str, Any], question_id: str, reviewer: str) -> dict[str, Any]`
  - `reject_seeded_answer(session: dict[str, Any], question_id: str, reason: str, reviewer: str) -> dict[str, Any]`

- [ ] **Step 1: Write failing tests for session creation and `.artpkg/` gitignore**

Add to `tests/test_artpkg_intake.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))

import artpkg_intake as intake


class IntakeSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.template = self.root / "reusable_artifacts_package_template.md"
        self.template.write_text("# Package\n", encoding="utf-8")
        self.pre = self.root / "pre.md"
        self.pre.write_text(
            "# Pre-Artifacts Package\n\n"
            "## 1. Project Summary\n"
            "- Project name: Example Intake\n"
            "- Primary goal: Produce a reviewable package.\n\n"
            "## 16. Authority and Decision Boundaries\n"
            "- This file is discovery context; it is not an approved implementation contract.\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_create_intake_session_persists_seed_and_answers(self):
        session = intake.create_intake_session(
            self.pre,
            self.root,
            template_path=self.template,
            respondent="Reviewer",
        )

        session_dir = Path(session["session_dir"])
        self.assertTrue((session_dir / "source_pre_artifacts.md").exists())
        self.assertTrue((session_dir / "seed.json").exists())
        self.assertTrue((session_dir / "answers.json").exists())
        self.assertEqual(intake.sha256_file(self.pre), session["source"]["sha256"])
        self.assertEqual("Example Intake", session["document"]["answers"]["PKG-001"]["value"])
        self.assertEqual("SOURCE_ARTIFACT", session["document"]["answers"]["PKG-001"]["source_type"])

    def test_gitignore_excludes_local_artpkg_sessions(self):
        gitignore = (Path(__file__).parents[1] / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".artpkg/", gitignore)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m unittest tests.test_artpkg_intake.IntakeSessionTests.test_create_intake_session_persists_seed_and_answers tests.test_artpkg_intake.IntakeSessionTests.test_gitignore_excludes_local_artpkg_sessions
```

Expected: fail because `artpkg_intake.py` does not exist and `.artpkg/` is not ignored.

- [ ] **Step 3: Implement minimal session creation**

Add `.artpkg/` to `.gitignore`.

Create `tools/artpkg_intake.py`:

```python
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
```

- [ ] **Step 4: Add review queue classification**

Append to `tools/artpkg_intake.py`:

```python
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
```

- [ ] **Step 5: Add persistence and review disposition functions**

Append to `tools/artpkg_intake.py`:

```python
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
```

- [ ] **Step 6: Run Task 1 tests**

Run:

```powershell
python -m unittest tests.test_artpkg_intake -v
```

Expected: all Task 1 tests pass.

- [ ] **Step 7: Commit Task 1**

```powershell
git add .gitignore tools/artpkg_intake.py tests/test_artpkg_intake.py
git commit -m "feat: add ArtPkg intake sessions"
```

---

### Task 2: Review Queue Semantics and Safety Tests

**Files:**
- Modify: `tests/test_artpkg_intake.py`
- Modify: `tools/artpkg_intake.py`

**Interfaces:**
- Consumes:
  - `build_review_queues(document, seed, validation)`
  - `confirm_answer(session, question_id, reviewer)`
  - `reject_seeded_answer(session, question_id, reason, reviewer)`
- Produces:
  - Stable review queue behavior for the UI and projection tasks.

- [ ] **Step 1: Add failing tests for queue classification and review dispositions**

Append to `tests/test_artpkg_intake.py`:

```python
    def test_review_queues_separate_unknown_authority_and_evidence_items(self):
        session = intake.create_intake_session(
            self.pre,
            self.root,
            template_path=self.template,
            respondent="Reviewer",
        )
        queues = session["review_queues"]

        need_ids = {item["id"] for item in queues["needs_answer"]}
        authority_ids = {item["id"] for item in queues["authority_sensitive"]}
        evidence_ids = {item["id"] for item in queues["evidence_sensitive"]}

        self.assertIn("PKG-003", need_ids)
        self.assertIn("AUT-001", authority_ids)
        self.assertIn("SEC-001", authority_ids)
        self.assertIn("OVR-007", evidence_ids)

    def test_confirm_and_reject_seeded_answers_are_durable(self):
        session = intake.create_intake_session(
            self.pre,
            self.root,
            template_path=self.template,
            respondent="Reviewer",
        )

        intake.confirm_answer(session, "PKG-001", reviewer="Reviewer")
        intake.reject_seeded_answer(session, "PKG-003", reason="Owner must be named by human", reviewer="Reviewer")

        reloaded = intake.load_intake_session(session["session_dir"])
        self.assertEqual("HUMAN_CONFIRMED", reloaded["document"]["answers"]["PKG-001"]["review_disposition"])
        self.assertEqual("HUMAN_REJECTED", reloaded["document"]["answers"]["PKG-003"]["review_disposition"])
        self.assertEqual("Owner must be named by human", reloaded["document"]["answers"]["PKG-003"]["rejection_reason"])
```

- [ ] **Step 2: Run tests to verify they fail or expose missing behavior**

Run:

```powershell
python -m unittest tests.test_artpkg_intake.IntakeSessionTests.test_review_queues_separate_unknown_authority_and_evidence_items tests.test_artpkg_intake.IntakeSessionTests.test_confirm_and_reject_seeded_answers_are_durable -v
```

Expected: fail if `SEC-001` or `OVR-007` are not generated in the fixture or if disposition persistence is incomplete.

- [ ] **Step 3: Make the fixture include evidence-sensitive and restricted-content fields**

Update the `self.pre.write_text` fixture in `tests/test_artpkg_intake.py` to include:

```python
            "## 14. Evidence and Validation\n"
            "- What is still unverified? Runtime behavior has not been validated.\n\n"
            "## 19. Sensitive or Restricted Content\n"
            "- Does this project involve sensitive data, credentials, regulated information, or restricted content? Yes\n"
            "- If yes, what safeguards are required? Local-only handling and redaction.\n"
            "- Are any redaction or access controls needed? Yes, redact customer payloads.\n\n"
```

- [ ] **Step 4: Adjust `build_review_queues` so rejected answers stay visible**

In `tools/artpkg_intake.py`, update `build_review_queues` inside the answer loop:

```python
        if disposition == "HUMAN_REJECTED":
            queues["needs_answer"].append(_queue_item(qid, item, "seeded answer was rejected and needs replacement"))
            continue
```

Place this before the unresolved-state branch.

- [ ] **Step 5: Run Task 2 tests**

Run:

```powershell
python -m unittest tests.test_artpkg_intake -v
```

Expected: all intake tests pass.

- [ ] **Step 6: Commit Task 2**

```powershell
git add tools/artpkg_intake.py tests/test_artpkg_intake.py
git commit -m "test: classify ArtPkg intake review queues"
```

---

### Task 3: Archify Readiness Projection Adapter

**Files:**
- Create: `tools/artpkg_archify_projection.py`
- Create: `tests/test_artpkg_archify_projection.py`

**Interfaces:**
- Consumes:
  - ArtPkg answer document dictionaries.
  - `artifacts_package_questionnaire.validate_answers(document) -> dict`
  - Intake session shape from `artpkg_intake.create_intake_session(pre_artifacts_path, workspace, template_path, respondent)`
- Produces:
  - `ProjectionResult` dataclass with `ir_path`, `mapping_path`, `validation_path`, `ir`, `mapping`, `projection_validation`.
  - `build_readiness_projection(session: dict[str, Any], output_dir: str | Path | None = None) -> ProjectionResult`
  - `validate_projection_mapping(ir: dict[str, Any], mapping: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]`

- [ ] **Step 1: Write failing tests for IR, sidecar, and fail-closed semantics**

Create `tests/test_artpkg_archify_projection.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m unittest tests.test_artpkg_archify_projection -v
```

Expected: fail because `artpkg_archify_projection.py` does not exist.

- [ ] **Step 3: Implement projection dataclass and helper functions**

Create `tools/artpkg_archify_projection.py`:

```python
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
```

- [ ] **Step 4: Implement `build_readiness_projection`**

Append:

```python
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
```

- [ ] **Step 5: Implement mapping and validation**

Append:

```python
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
```

- [ ] **Step 6: Run projection tests**

Run:

```powershell
python -m unittest tests.test_artpkg_archify_projection -v
```

Expected: all projection tests pass.

- [ ] **Step 7: Commit Task 3**

```powershell
git add tools/artpkg_archify_projection.py tests/test_artpkg_archify_projection.py
git commit -m "feat: project ArtPkg readiness to Archify"
```

---

### Task 4: Archify CLI Runner

**Files:**
- Create: `tools/artpkg_archify_runner.py`
- Create: `tests/test_artpkg_archify_runner.py`

**Interfaces:**
- Consumes:
  - `ProjectionResult.ir_path`
- Produces:
  - `ArchifyConfig` dataclass
  - `run_archify_validate(config: ArchifyConfig, diagram_type: str, ir_path: str | Path) -> dict[str, Any]`
  - `run_archify_deliver(config: ArchifyConfig, diagram_type: str, ir_path: str | Path, html_path: str | Path) -> dict[str, Any]`
  - `run_archify_visual_check(config: ArchifyConfig, html_path: str | Path) -> dict[str, Any]`

- [ ] **Step 1: Write failing tests for command construction and non-zero handling**

Create `tests/test_artpkg_archify_runner.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))

import artpkg_archify_runner as runner


class ArchifyRunnerTests(unittest.TestCase):
    def test_validate_uses_explicit_node_and_archify_root(self):
        config = runner.ArchifyConfig(node_executable="C:/node/node.exe", archify_root="D:/archify/archify")
        completed = runner.subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"ok": True, "checks": []}),
            stderr="",
        )
        with patch("artpkg_archify_runner.subprocess.run", return_value=completed) as run:
            result = runner.run_archify_validate(config, "architecture", "input.json")

        self.assertTrue(result["ok"])
        args = run.call_args.args[0]
        self.assertEqual("C:/node/node.exe", args[0])
        self.assertEqual("bin/archify.mjs", args[1])
        self.assertIn("--json", args)
        self.assertEqual("D:/archify/archify", str(run.call_args.kwargs["cwd"]))

    def test_nonzero_archify_result_is_not_success(self):
        config = runner.ArchifyConfig(node_executable="node", archify_root="D:/archify/archify")
        completed = runner.subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout=json.dumps({"ok": False, "error": "bad diagram"}),
            stderr="",
        )
        with patch("artpkg_archify_runner.subprocess.run", return_value=completed):
            result = runner.run_archify_validate(config, "architecture", "input.json")

        self.assertFalse(result["ok"])
        self.assertEqual(1, result["exit_code"])
        self.assertEqual("bad diagram", result["receipt"]["error"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m unittest tests.test_artpkg_archify_runner -v
```

Expected: fail because `artpkg_archify_runner.py` does not exist.

- [ ] **Step 3: Implement the runner**

Create `tools/artpkg_archify_runner.py`:

```python
"""Local Archify command runner for ArtPkg review projections."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ArchifyConfig:
    node_executable: str = "node"
    archify_root: str = "D:/archify/archify"
    quality: str = "showcase"


def _run(config: ArchifyConfig, args: list[str]) -> dict[str, Any]:
    command = [config.node_executable, "bin/archify.mjs", *args, "--json"]
    completed = subprocess.run(command, cwd=Path(config.archify_root), text=True, capture_output=True)
    try:
        receipt = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        receipt = {"ok": False, "error": "Archify did not return JSON", "stdout": completed.stdout}
    return {
        "ok": completed.returncode == 0 and receipt.get("ok") is True,
        "exit_code": completed.returncode,
        "command": command,
        "cwd": config.archify_root,
        "receipt": receipt,
        "stderr": completed.stderr,
    }


def run_archify_validate(config: ArchifyConfig, diagram_type: str, ir_path: str | Path) -> dict[str, Any]:
    return _run(config, ["validate", diagram_type, str(ir_path), "--quality", config.quality])


def run_archify_deliver(config: ArchifyConfig, diagram_type: str, ir_path: str | Path, html_path: str | Path) -> dict[str, Any]:
    return _run(config, ["deliver", diagram_type, str(ir_path), str(html_path), "--quality", config.quality])


def run_archify_visual_check(config: ArchifyConfig, html_path: str | Path) -> dict[str, Any]:
    return _run(config, ["visual-check", str(html_path)])
```

- [ ] **Step 4: Run runner tests**

Run:

```powershell
python -m unittest tests.test_artpkg_archify_runner -v
```

Expected: all runner tests pass.

- [ ] **Step 5: Run a local integration smoke if Archify exists**

Run:

```powershell
python - <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, "tools")
from artpkg_archify_runner import ArchifyConfig, run_archify_validate
root = Path("D:/archify/archify")
node = Path("C:/Users/vin/AppData/Local/nvm/v20.18.2/node.exe")
if root.exists() and node.exists():
    result = run_archify_validate(ArchifyConfig(str(node), str(root)), "architecture", root / "examples" / "web-app.architecture.json")
    print(result["ok"], result["exit_code"])
else:
    print("SKIPPED")
PY
```

Expected on this machine: `True 0`. If Archify or Node is unavailable, record `SKIPPED` in the task notes and do not fail the implementation.

- [ ] **Step 6: Commit Task 4**

```powershell
git add tools/artpkg_archify_runner.py tests/test_artpkg_archify_runner.py
git commit -m "feat: add local Archify runner"
```

---

### Task 5: Local Intake Server API

**Files:**
- Create: `tools/artpkg_intake_server.py`
- Create: `tests/test_artpkg_intake_server.py`

**Interfaces:**
- Consumes:
  - `artpkg_intake.create_intake_session(pre_artifacts_path, workspace, template_path, respondent)`
  - `artpkg_intake.load_intake_session(session_dir)`
  - `artpkg_intake.confirm_answer(session, question_id, reviewer)`
  - `artpkg_intake.reject_seeded_answer(session, question_id, reason, reviewer)`
  - `artpkg_archify_projection.build_readiness_projection(session)`
  - `artpkg_archify_runner.run_archify_validate(config, diagram_type, ir_path)`
  - `artpkg_archify_runner.run_archify_deliver(config, diagram_type, ir_path, html_path)`
- Produces HTTP endpoints:
  - `GET /` -> HTML UI
  - `POST /api/intake` -> creates session from multipart `file`
  - `GET /api/session?dir=<session_dir>` -> returns session summary
  - `POST /api/session/confirm` -> confirms `question_id`
  - `POST /api/session/reject` -> rejects `question_id` with reason
  - `POST /api/session/project` -> builds Archify readiness projection, optionally validates/delivers

- [ ] **Step 1: Write failing tests for multipart parsing and API summary shape**

Create `tests/test_artpkg_intake_server.py`:

```python
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))

import artpkg_intake_server as server


class IntakeServerTests(unittest.TestCase):
    def test_parse_multipart_markdown_upload(self):
        boundary = "----artpkg"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="pre.md"\r\n'
            "Content-Type: text/markdown\r\n\r\n"
            "# Pre-Artifacts Package\r\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")

        upload = server.parse_multipart_upload(f"multipart/form-data; boundary={boundary}", body)
        self.assertEqual("pre.md", upload.filename)
        self.assertIn(b"Pre-Artifacts", upload.content)

    def test_session_summary_excludes_full_document_payload(self):
        session = {
            "session_id": "S",
            "session_dir": "D:/tmp/S",
            "source": {"sha256": "abc"},
            "validation": {"status": "DRAFT"},
            "review_queues": {"needs_answer": [{"id": "PKG-003"}]},
            "document": {"answers": {"PKG-001": {"value": "Example"}}},
        }
        summary = server.session_summary(session)
        self.assertNotIn("document", summary)
        self.assertEqual("S", summary["session_id"])
        self.assertEqual(1, summary["queue_counts"]["needs_answer"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m unittest tests.test_artpkg_intake_server -v
```

Expected: fail because `artpkg_intake_server.py` does not exist.

- [ ] **Step 3: Implement upload parser and summaries**

Create `tools/artpkg_intake_server.py`:

```python
"""Local ArtPkg intake web UI server."""
from __future__ import annotations

import argparse
import json
import tempfile
import webbrowser
from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import artpkg_intake
import artpkg_archify_projection


@dataclass
class UploadedFile:
    filename: str
    content: bytes
    content_type: str


def parse_multipart_upload(content_type: str, body: bytes) -> UploadedFile:
    headers = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
    message = BytesParser(policy=default).parsebytes(headers + body)
    for part in message.iter_parts():
        disposition = part.get_content_disposition()
        if disposition == "form-data" and part.get_param("name", header="content-disposition") == "file":
            filename = part.get_filename() or "pre-artifacts.md"
            return UploadedFile(filename=filename, content=part.get_payload(decode=True) or b"", content_type=part.get_content_type())
    raise ValueError("multipart upload did not include file")


def session_summary(session: dict[str, Any]) -> dict[str, Any]:
    queues = session.get("review_queues", {})
    return {
        "session_id": session.get("session_id"),
        "session_dir": session.get("session_dir"),
        "source": session.get("source"),
        "validation": session.get("validation"),
        "review_queues": queues,
        "queue_counts": {name: len(items) for name, items in queues.items()},
        "answers_path": session.get("answers_path"),
    }
```

- [ ] **Step 4: Implement request handler**

Append:

```python
class IntakeHandler(BaseHTTPRequestHandler):
    workspace = Path.cwd()
    template_path: Path | None = None

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            html = (Path(__file__).with_name("artpkg_intake_ui.html")).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
            return
        if parsed.path == "/api/session":
            params = parse_qs(parsed.query)
            session_dir = params.get("dir", [""])[0]
            session = artpkg_intake.load_intake_session(session_dir)
            self._json(200, session_summary(session))
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            if parsed.path == "/api/intake":
                upload = parse_multipart_upload(self.headers.get("Content-Type", ""), body)
                if Path(upload.filename).suffix.lower() not in {".md", ".markdown", ".txt"}:
                    raise ValueError("unsupported upload type")
                upload_dir = Path(tempfile.mkdtemp(prefix="artpkg-upload-"))
                source = upload_dir / Path(upload.filename).name
                source.write_bytes(upload.content)
                session = artpkg_intake.create_intake_session(source, self.workspace, template_path=self.template_path)
                self._json(200, session_summary(session))
                return

            payload = json.loads(body.decode("utf-8") or "{}")
            session = artpkg_intake.load_intake_session(payload["session_dir"])
            if parsed.path == "/api/session/confirm":
                artpkg_intake.confirm_answer(session, payload["question_id"], payload.get("reviewer", "UI reviewer"))
                self._json(200, session_summary(session))
                return
            if parsed.path == "/api/session/reject":
                artpkg_intake.reject_seeded_answer(session, payload["question_id"], payload.get("reason", "Rejected in UI"), payload.get("reviewer", "UI reviewer"))
                self._json(200, session_summary(session))
                return
            if parsed.path == "/api/session/project":
                result = artpkg_archify_projection.build_readiness_projection(session)
                summary = session_summary(session)
                summary["projection"] = {"ir_path": result.ir_path, "mapping_path": result.mapping_path, "validation_path": result.validation_path}
                self._json(200, summary)
                return
            self._json(404, {"error": "not found"})
        except Exception as exc:
            self._json(400, {"error": str(exc)})
```

- [ ] **Step 5: Implement server main**

Append:

```python
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local ArtPkg intake UI.")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--template", default=None)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args(argv)

    IntakeHandler.workspace = Path(args.workspace).expanduser().resolve()
    IntakeHandler.template_path = Path(args.template).expanduser().resolve() if args.template else None
    server = ThreadingHTTPServer((args.host, args.port), IntakeHandler)
    url = f"http://{args.host}:{args.port}/"
    print(f"ArtPkg intake UI running at {url}")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run server tests**

Run:

```powershell
python -m unittest tests.test_artpkg_intake_server -v
```

Expected: all server tests pass.

- [ ] **Step 7: Commit Task 5**

```powershell
git add tools/artpkg_intake_server.py tests/test_artpkg_intake_server.py
git commit -m "feat: add local ArtPkg intake server"
```

---

### Task 6: Browser Intake UI

**Files:**
- Create: `tools/artpkg_intake_ui.html`
- Modify: `tests/test_artpkg_intake_server.py`

**Interfaces:**
- Consumes:
  - `POST /api/intake`
  - `POST /api/session/confirm`
  - `POST /api/session/reject`
  - `POST /api/session/project`
- Produces:
  - A local browser UI with upload/select, queue counts, review cards, confirm/reject controls, and projection links.

- [ ] **Step 1: Add failing HTML contract test**

Append to `tests/test_artpkg_intake_server.py`:

```python
    def test_ui_contains_upload_review_and_projection_controls(self):
        html_path = Path(__file__).parents[1] / "tools" / "artpkg_intake_ui.html"
        html = html_path.read_text(encoding="utf-8")
        self.assertIn('id="preArtifactsFile"', html)
        self.assertIn('id="reviewQueues"', html)
        self.assertIn('data-action="confirm"', html)
        self.assertIn('data-action="reject"', html)
        self.assertIn('id="buildProjection"', html)
```

- [ ] **Step 2: Run HTML contract test to verify it fails**

Run:

```powershell
python -m unittest tests.test_artpkg_intake_server.IntakeServerTests.test_ui_contains_upload_review_and_projection_controls -v
```

Expected: fail because `tools/artpkg_intake_ui.html` does not exist.

- [ ] **Step 3: Create the UI shell**

Create `tools/artpkg_intake_ui.html`:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ArtPkg Intake</title>
  <style>
    :root { color-scheme: light; font-family: Inter, Segoe UI, Arial, sans-serif; background:#f6f7f9; color:#17202a; }
    body { margin:0; }
    header { padding:18px 24px; border-bottom:1px solid #d8dee6; background:#fff; display:flex; align-items:center; justify-content:space-between; gap:16px; }
    h1 { font-size:20px; margin:0; letter-spacing:0; }
    main { display:grid; grid-template-columns:320px 1fr; min-height:calc(100vh - 65px); }
    aside { border-right:1px solid #d8dee6; background:#fff; padding:18px; }
    section { padding:18px 22px; }
    label { display:block; font-weight:650; margin-bottom:8px; }
    input[type=file] { width:100%; border:1px solid #b8c2cc; border-radius:6px; padding:10px; background:#fff; }
    button { border:1px solid #8795a5; background:#fff; border-radius:6px; padding:8px 11px; cursor:pointer; }
    button.primary { background:#174ea6; border-color:#174ea6; color:#fff; }
    button.danger { border-color:#b42318; color:#b42318; }
    .stack { display:grid; gap:12px; }
    .queue-tabs { display:flex; flex-wrap:wrap; gap:8px; margin:0 0 16px; }
    .queue-tabs button[aria-pressed=true] { background:#17202a; color:#fff; }
    .card { border:1px solid #d8dee6; border-radius:8px; background:#fff; padding:14px; display:grid; gap:8px; }
    .meta { color:#52606d; font-size:12px; }
    .value { white-space:pre-wrap; background:#f6f7f9; border-radius:6px; padding:10px; font-family:Consolas, monospace; font-size:12px; }
    .actions { display:flex; gap:8px; flex-wrap:wrap; }
    .status { font-size:13px; color:#52606d; }
    iframe { width:100%; min-height:560px; border:1px solid #d8dee6; border-radius:8px; background:#fff; }
    @media (max-width: 860px) { main { grid-template-columns:1fr; } aside { border-right:0; border-bottom:1px solid #d8dee6; } }
  </style>
</head>
<body>
  <header>
    <h1>ArtPkg Intake</h1>
    <div class="status" id="status">No session loaded</div>
  </header>
  <main>
    <aside class="stack">
      <div>
        <label for="preArtifactsFile">Pre-artifacts file</label>
        <input id="preArtifactsFile" type="file" accept=".md,.markdown,.txt">
      </div>
      <button class="primary" id="upload">Start questionnaire</button>
      <button id="buildProjection">Build readiness projection</button>
      <div id="sessionMeta" class="status"></div>
    </aside>
    <section>
      <div class="queue-tabs" id="queueTabs"></div>
      <div class="stack" id="reviewQueues"></div>
      <div class="stack" id="projectionArea"></div>
    </section>
  </main>
  <script>
    let session = null;
    let activeQueue = "needs_answer";
    const labels = {
      needs_answer: "Needs answer",
      needs_confirmation: "Needs confirmation",
      authority_sensitive: "Authority-sensitive",
      evidence_sensitive: "Evidence-sensitive",
      ready_for_quick_review: "Ready"
    };

    function setStatus(text) { document.getElementById("status").textContent = text; }

    async function postJson(url, payload) {
      const response = await fetch(url, { method:"POST", headers:{ "Content-Type":"application/json" }, body:JSON.stringify(payload) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Request failed");
      return data;
    }

    function render() {
      if (!session) return;
      document.getElementById("sessionMeta").textContent = `Session: ${session.session_id}`;
      const tabs = document.getElementById("queueTabs");
      tabs.innerHTML = "";
      Object.keys(labels).forEach((name) => {
        const button = document.createElement("button");
        button.textContent = `${labels[name]} (${session.queue_counts[name] || 0})`;
        button.setAttribute("aria-pressed", String(activeQueue === name));
        button.onclick = () => { activeQueue = name; render(); };
        tabs.appendChild(button);
      });

      const list = document.getElementById("reviewQueues");
      list.innerHTML = "";
      (session.review_queues[activeQueue] || []).forEach((item) => {
        const card = document.createElement("article");
        card.className = "card";
        card.innerHTML = `
          <strong>${item.id} ${item.label || ""}</strong>
          <div class="meta">${item.reason || ""} | ${item.state || ""} | ${item.source_type || ""} | confidence ${item.confidence_score ?? "n/a"}</div>
          <div class="value"></div>
          <div class="actions">
            <button data-action="confirm">Confirm</button>
            <button data-action="reject" class="danger">Reject</button>
          </div>
        `;
        card.querySelector(".value").textContent = typeof item.value === "string" ? item.value : JSON.stringify(item.value, null, 2);
        card.querySelector('[data-action="confirm"]').onclick = async () => {
          session = await postJson("/api/session/confirm", { session_dir:session.session_dir, question_id:item.id, reviewer:"UI reviewer" });
          render();
        };
        card.querySelector('[data-action="reject"]').onclick = async () => {
          const reason = prompt("Why is this seeded value rejected?") || "Rejected in UI";
          session = await postJson("/api/session/reject", { session_dir:session.session_dir, question_id:item.id, reason, reviewer:"UI reviewer" });
          render();
        };
        list.appendChild(card);
      });
    }

    document.getElementById("upload").onclick = async () => {
      const file = document.getElementById("preArtifactsFile").files[0];
      if (!file) { setStatus("Choose a pre-artifacts file first"); return; }
      const body = new FormData();
      body.append("file", file);
      setStatus("Creating intake session");
      const response = await fetch("/api/intake", { method:"POST", body });
      session = await response.json();
      if (!response.ok) { setStatus(session.error || "Upload failed"); return; }
      setStatus("Session ready");
      render();
    };

    document.getElementById("buildProjection").onclick = async () => {
      if (!session) { setStatus("Start a session first"); return; }
      setStatus("Building readiness projection");
      session = await postJson("/api/session/project", { session_dir:session.session_dir });
      const area = document.getElementById("projectionArea");
      area.innerHTML = `<article class="card"><strong>Projection built</strong><div class="value">${JSON.stringify(session.projection, null, 2)}</div></article>`;
      setStatus("Projection ready");
      render();
    };
  </script>
</body>
</html>
```

- [ ] **Step 4: Run UI/server tests**

Run:

```powershell
python -m unittest tests.test_artpkg_intake_server -v
```

Expected: all server/UI tests pass.

- [ ] **Step 5: Commit Task 6**

```powershell
git add tools/artpkg_intake_ui.html tests/test_artpkg_intake_server.py
git commit -m "feat: add ArtPkg intake browser UI"
```

---

### Task 7: CLI Entry Point and Documentation

**Files:**
- Modify: `tools/artifacts_package_questionnaire.py`
- Modify: `README.md`
- Modify: `docs/artifacts_package_questionnaire.md`
- Modify: `tests/test_artifacts_package_questionnaire.py`

**Interfaces:**
- Consumes:
  - `artpkg_intake_server.main(argv: list[str] | None = None) -> int`
- Produces:
  - CLI command:
    - `python tools/artifacts_package_questionnaire.py intake-ui --workspace . --port 8765 --open`

- [ ] **Step 1: Add failing CLI parser test**

Append to `tests/test_artifacts_package_questionnaire.py`:

```python
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
```

- [ ] **Step 2: Run CLI parser test to verify it fails**

Run:

```powershell
python -m unittest tests.test_artifacts_package_questionnaire.QuestionnaireTests.test_intake_ui_command_delegates_to_server -v
```

Expected: fail because `intake-ui` and `start_intake_ui` do not exist.

- [ ] **Step 3: Add server delegation to CLI**

In `tools/artifacts_package_questionnaire.py`, add near other top-level helpers:

```python
def start_intake_ui(argv: list[str]) -> int:
    import artpkg_intake_server
    return artpkg_intake_server.main(argv)
```

At the start of `main`, before constructing the existing `argparse.ArgumentParser`, add this dispatch so `intake-ui` can preserve remaining arguments:

```python
def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    if argv and argv[0] == "intake-ui":
        return start_intake_ui(argv[1:])
```

Then keep the existing parser setup immediately after that block. The first unchanged parser lines should remain:

```python
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
```

Keep the existing `start`, `resume`, `validate`, and `generate` behavior unchanged.

- [ ] **Step 4: Update docs**

Add to `README.md` after "Start a questionnaire":

```markdown
## Start the local intake UI

The local intake UI lets a reviewer upload or select a pre-artifacts Markdown
file, seed a draft questionnaire, and review fields grouped by urgency.

```text
python tools/artifacts_package_questionnaire.py intake-ui --workspace . --port 8765 --open
```

The UI is ArtPkg-owned. It does not grant approval, implementation authority,
execution authority, publication authority, deployment authority, or permission
to process sensitive content. Local sessions are written under `.artpkg/` and
are gitignored because they can contain project-specific or restricted
information.
```

Add the same operational command to `docs/artifacts_package_questionnaire.md`, including:

```markdown
## Local intake UI

Use `intake-ui` for browser-assisted review of pre-artifacts input. The UI
creates a local intake session, shows review queues, and can generate an
Archify readiness projection for review. ArtPkg validation remains the only
package readiness calculation.
```

- [ ] **Step 5: Run CLI and documentation tests**

Run:

```powershell
python -m unittest tests.test_artifacts_package_questionnaire.QuestionnaireTests.test_intake_ui_command_delegates_to_server -v
python -m unittest tests.test_artifacts_package_questionnaire -v
```

Expected: all questionnaire tests pass.

- [ ] **Step 6: Commit Task 7**

```powershell
git add tools/artifacts_package_questionnaire.py tests/test_artifacts_package_questionnaire.py README.md docs/artifacts_package_questionnaire.md
git commit -m "feat: expose ArtPkg intake UI command"
```

---

### Task 8: End-to-End Local Smoke Test

**Files:**
- No new source files expected.
- May create ignored runtime files under `.artpkg/`.

**Interfaces:**
- Consumes:
  - `python tools/artifacts_package_questionnaire.py intake-ui`
  - Local browser at `http://127.0.0.1:8765/`
  - Optional local Archify at `D:\archify\archify`
- Produces:
  - Evidence that a user can upload pre-artifacts, see review queues, and build a readiness projection.

- [ ] **Step 1: Run full unit suite**

Run:

```powershell
python -m unittest discover -s tests -v
```

Expected: all tests pass.

- [ ] **Step 2: Start the local server**

Run:

```powershell
python tools/artifacts_package_questionnaire.py intake-ui --workspace . --port 8765
```

Expected output:

```text
ArtPkg intake UI running at http://127.0.0.1:8765/
```

- [ ] **Step 3: Open the UI manually**

Open:

```text
http://127.0.0.1:8765/
```

Use `pre-art-pkg-template.md` or another safe pre-artifacts Markdown fixture. Do not upload credentials, tokens, private payloads, or regulated personal data.

Expected:

- Upload creates a session under `.artpkg/intake_sessions/`.
- Review tabs show counts for `Needs answer`, `Needs confirmation`, `Authority-sensitive`, `Evidence-sensitive`, and `Ready`.
- Confirming an answer removes or changes its review disposition after refresh.
- Rejecting an answer keeps it visible as needing replacement.
- Building projection writes:
  - `artpkg-readiness.architecture.json`
  - `artpkg-readiness.mapping.json`
  - `artpkg-readiness.projection-validation.json`

- [ ] **Step 4: Optional Archify render smoke**

If `D:\archify\archify` and a working Node executable exist, run:

```powershell
& "C:\Users\vin\AppData\Local\nvm\v20.18.2\node.exe" D:\archify\archify\bin\archify.mjs validate architecture .artpkg\intake_sessions\<session-id>\artpkg-readiness.architecture.json --quality showcase --json
```

Expected:

```json
{"ok": true}
```

If Archify reports layout diagnostics, repair only the generated projection layout in `tools/artpkg_archify_projection.py` and add a fixture-based regression test.

- [ ] **Step 5: Stop the server**

Press `Ctrl+C`.

Expected: process exits without stack trace.

- [ ] **Step 6: Final status check**

Run:

```powershell
git status --short
```

Expected:

- Source/test/doc changes are committed.
- `.artpkg/` runtime files are ignored.
- Any pre-existing unrelated dirty files remain untouched.

---

## Implementation Notes

- Keep the UI intentionally plain and workflow-focused. This is an operational review tool, not a landing page.
- Do not add React/Vite yet. The repository is currently Python-first and the first slice does not need a frontend build pipeline.
- Do not put sensitive uploaded content in committed fixtures. Tests should use synthetic text only.
- Do not claim Archify projection success unless the local Archify command exits `0` and returns `ok: true`.
- A generated readiness map is a review artifact. It never changes ArtPkg validation status or authority.

## Execution Recommendation

Use subagent-driven development. Task boundaries are independent enough for fresh workers: intake session core, projection adapter, runner, server, UI, CLI/docs, and smoke test can each be reviewed separately.
