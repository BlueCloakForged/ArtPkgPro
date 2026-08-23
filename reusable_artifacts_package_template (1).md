# Reusable Artifacts Package Template

> Purpose: Create the smallest evidence-grounded package that allows a new person or AI-assisted development session to understand the project, verify its current state, and perform only the next authorized work without replaying the full project history.

## How to use this template

- Include only sections that materially apply, but never omit a material uncertainty, conflict, risk, or limitation.
- Prefer links to authoritative source files over copied content.
- Keep facts, inferences, proposals, decisions, approvals, and validation results visibly distinct.
- Give requirements, decisions, risks, and phases stable identifiers.
- Record exact paths, versions, dates, commands, and results where available.
- Redact sensitive data while preserving content-free reason codes and traceability.
- Do not present an artifact package as complete repository understanding, correctness proof, implementation authorization, or permission to deploy.

---

## 0. Package control

| Field | Value |
| --- | --- |
| Project | `<name>` |
| Package purpose | `<discovery / design / implementation handoff / review / closeout>` |
| Package status | `<DRAFT / READY_FOR_REVIEW / ACCEPTED / SUPERSEDED / BLOCKED>` |
| Owner | `<person or team>` |
| Prepared by | `<person or agent>` |
| Created | `<YYYY-MM-DD>` |
| Last updated | `<YYYY-MM-DD>` |
| Repository or workspace | `<path / URL / identifier>` |
| Version or snapshot | `<commit, tag, release, digest, or date>` |
| Authoritative source of truth | `<artifact and location>` |
| Active bounded contract | `<ID / NONE>` |
| Current implementation authority | `<authorized scope / NONE / NOT EVALUATED>` |
| Current checkpoint | `<checkpoint and status>` |
| Next permitted action | `<one bounded action>` |
| Human decision required | `<decision / NONE>` |

### Package claim

This package represents `<what it covers>` at `<snapshot or date>`. It does not claim `<important exclusions or limitations>`.

### Authority statement

Describe who can approve scope, implementation, release, deployment, data access, or destructive changes. If this is unknown, record `UNKNOWN` rather than inferring authority.

---

## 1. Executive overview

### Problem

`<What problem is being solved, for whom, and why it matters.>`

### Intended outcome

`<Observable outcome, not merely an activity or technology choice.>`

### Current state

- Completed: `<validated work>`
- In progress: `<current bounded work>`
- Blocked: `<blocker and owner>`
- Deferred: `<explicit non-scope>`
- Unverified: `<claims still requiring evidence>`

### Recommended next checkpoint

`<One independently testable next outcome.>`

---

## 2. Actors, use cases, and boundaries

### Actors

| Actor ID | Actor | Role | Needs or responsibilities | Authority |
| --- | --- | --- | --- | --- |
| ACT-001 | `<actor>` | `<user/operator/system/approver>` | `<needs>` | `<authority>` |

### Primary use cases

| Use-case ID | Actor | Trigger | Expected outcome |
| --- | --- | --- | --- |
| UC-001 | `<actor>` | `<trigger>` | `<outcome>` |

### Failure and misuse cases

| Case ID | Condition | Required behavior | Evidence needed |
| --- | --- | --- | --- |
| FC-001 | `<failure, misuse, or denied action>` | `<fail safely / abstain / recover>` | `<test or observation>` |

### System boundary

- In scope: `<capabilities, components, data, users>`
- Out of scope: `<explicit exclusions>`
- External dependencies: `<systems or teams outside the boundary>`
- Prohibited shortcuts: `<approaches that would invalidate safety or evidence>`

---

## 3. Requirements and acceptance

### Functional requirements

| Requirement ID | Requirement | Source | Priority | Status |
| --- | --- | --- | --- | --- |
| FR-001 | `<testable behavior>` | `<source or decision>` | `<must/should/could>` | `<proposed/accepted/implemented/verified>` |

### Non-functional requirements

| Requirement ID | Category | Requirement | Measurement | Status |
| --- | --- | --- | --- | --- |
| NFR-001 | `<security/performance/privacy/reliability/etc.>` | `<requirement>` | `<threshold or method>` | `<status>` |

### Acceptance criteria

| Criterion ID | Requirement IDs | Pass condition | Validation method | Evidence artifact |
| --- | --- | --- | --- | --- |
| AC-001 | `<FR/NFR IDs>` | `<observable pass condition>` | `<test/review/runtime check>` | `<path or pending>` |

### Definition of good and bad

- Good outcome: `<observable success>`
- Bad outcome: `<observable failure or unacceptable trade-off>`
- Stop condition: `<condition requiring pause and human review>`

---

## 4. Architecture and information flow

### Architecture or feature map

Describe the relevant components, ownership boundaries, and relationships. Link each claim to inspected sources. Use a diagram only when it improves understanding.

| Component | Responsibility | Inputs | Outputs | State owner | Source evidence |
| --- | --- | --- | --- | --- | --- |
| `<component>` | `<responsibility>` | `<inputs>` | `<outputs>` | `<owner>` | `<path/reference>` |

### Interfaces and data

- Inputs: `<formats, schemas, examples, trust level>`
- Outputs: `<formats, schemas, consumers>`
- Interfaces: `<API, CLI, UI, file, event, human step>`
- Data lineage: `<source → transformations → destination>`
- Retention and expiry: `<rules>`
- Representative samples: `<safe sample paths>`

### Operating environment

- Runtime and platform: `<versions>`
- Tools and dependencies: `<versions and sources>`
- Configuration: `<authoritative locations; never include secrets>`
- Build command: `<exact command or NOT ESTABLISHED>`
- Test command: `<exact command or NOT ESTABLISHED>`
- Runtime verification: `<exact command or NOT ESTABLISHED>`

---

## 5. Security, privacy, and operational constraints

| Constraint ID | Area | Constraint | Enforcement | Evidence or status |
| --- | --- | --- | --- | --- |
| CON-001 | `<security/privacy/data/operations>` | `<constraint>` | `<technical/process control>` | `<evidence/status>` |

Record, as applicable:

- authentication and authorization;
- sensitive or restricted data handling;
- redaction and logging rules;
- read/write and execution boundaries;
- network and external-service constraints;
- fail-closed and abstention behavior;
- secrets management;
- rollback and recovery expectations;
- prohibited persistence, mutation, or deployment behavior.

---

## 6. Decisions, assumptions, conflicts, and questions

### Decision register

| Decision ID | Decision | Rationale | Decider | Date | Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| DEC-001 | `<decision>` | `<why>` | `<authorized person>` | `<date>` | `<reference>` | `<accepted/superseded/proposed>` |

### Assumption register

| Assumption ID | Assumption | Impact if wrong | Validation method | Status |
| --- | --- | --- | --- | --- |
| ASM-001 | `<assumption>` | `<impact>` | `<how to test>` | `<open/validated/invalidated>` |

### Source conflicts

| Conflict ID | Conflicting sources or claims | Impact | Resolution owner | Status |
| --- | --- | --- | --- | --- |
| CFT-001 | `<source A vs source B>` | `<impact>` | `<owner>` | `<open/resolved>` |

### Open questions

| Question ID | Question | Why it matters | Decision owner | Needed by |
| --- | --- | --- | --- | --- |
| Q-001 | `<question>` | `<scope/architecture/safety/validation impact>` | `<owner>` | `<checkpoint>` |

---

## 7. Risks and controls

| Risk ID | Risk | Likelihood | Impact | Control or mitigation | Residual status |
| --- | --- | --- | --- | --- | --- |
| RSK-001 | `<risk>` | `<L/M/H>` | `<L/M/H>` | `<control>` | `<open/accepted/mitigated>` |

Include risks arising from missing evidence, stale snapshots, incorrect authority, data leakage, inferred relationships, dependency changes, rollback difficulty, and validation gaps when relevant.

---

## 8. Phased build or investigation sequence

| Phase ID | Single outcome | In scope | Out of scope | Requirement IDs | Validation | Human gate | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PH-001 | `<independently testable outcome>` | `<scope>` | `<non-scope>` | `<IDs>` | `<commands/checks>` | `<review level>` | `<status>` |

For each active phase, record:

- prerequisites;
- expected files or components;
- deliverables;
- exact validation commands;
- evidence to retain;
- negative-path checks;
- rollback boundary;
- stop conditions;
- whether the next phase requires separate approval.

---

## 9. Validation and evidence record

### Evidence ledger

| Evidence ID | Claim tested | Evidence type | Exact source, path, or command | Result | Date | Limitations |
| --- | --- | --- | --- | --- | --- | --- |
| EVD-001 | `<claim>` | `<test/log/diff/runtime observation/review>` | `<exact reference>` | `<pass/fail/partial/not run>` | `<date>` | `<what this does not prove>` |

### Validation summary

- Generation: `<Were the expected artifacts or changes produced?>`
- Verification: `<Do tests and observations support the required behavior?>`
- Understanding: `<Can the result explain what changed, why, and what remains uncertain?>`
- Negative evidence: `<Denied actions, abstentions, non-events, isolation, or leakage checks>`
- Unverified claims: `<claims that remain proposals or inferences>`

### Reproducibility

```text
Environment:
Snapshot/version:
Command:
Expected result:
Observed result:
Evidence location:
```

---

## 10. Artifact index

| Artifact ID | Path or reference | Purpose | Provenance | Authority | Related IDs | Status | Last validated |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ART-001 | `<path>` | `<purpose>` | `<created from / supplied by / generated by>` | `<authoritative/supporting/exploratory>` | `<requirements, decisions, phases>` | `<current/stale/superseded/draft>` | `<date>` |

### Artifact admission rules

- Admit artifacts through exact paths, identifiers, or corroborated relationships.
- Label stale, historical, unverified, generated, or exploratory material.
- Do not infer causal relationships, semantic equivalence, hidden reasoning, or authority from proximity or similarity.
- Exclude unrelated, wrong-project, wrong-snapshot, unsealed, restricted, or weak semantic-only material.
- Record why any expected artifact was excluded or could not be inspected.

---

## 11. Handoff and checkpoint closeout

### Checkpoint classification

Choose one:

- `ACCEPTED`
- `ACCEPTED_WITH_CHANGES`
- `NEEDS_MORE_EVIDENCE`
- `NEEDS_REVISION`
- `DEFERRED`
- `REJECTED`
- `BLOCKED_AT_HUMAN_CHECKPOINT`

### Closeout summary

- Outcome: `<classification and concise reason>`
- Changed or created artifacts: `<exact paths>`
- Validation performed: `<commands and results>`
- Deviations: `<difference from accepted scope>`
- Residual risks: `<open risks>`
- Deferred work: `<explicit non-scope>`
- Working-tree or environment observations: `<relevant state>`
- Next permitted action: `<one bounded action>`
- Required approver: `<person/role or NONE>`

---

## 13. SDLC Harness pipeline

Include this section only when Harness mode is enabled. Every field remains
visible when its value is `NONE`, `UNKNOWN`, `NOT_EVALUATED`, or
`NOT_APPLICABLE`.

| Field | Value |
| --- | --- |
| Pipeline stage | `<stage>` |
| Run type | `<run type>` |
| Package ID | `<stable package ID>` |
| Parent package ID | `<ID / NONE>` |
| Target repository | `<path / identifier>` |
| Harness repository | `<path / identifier>` |
| Evidence output location | `<path>` |
| Repository snapshot | `<snapshot>` |
| Dirty-state manifest | `<manifest>` |
| Snapshot state | `<current / stale>` |
| Intake policy | `<policy>` |
| Intake reconciliation | `<result>` |
| Discovery providers | `<providers>` |
| Discovery compatibility | `<state>` |
| Discovery result classification | `<classification>` |
| Fallback method | `<method / NONE>` |
| Active BEC | `<state>` |
| BEC drafting authorization | `<state>` |
| BEC acceptance | `<state>` |
| BEC activation | `<state>` |
| Implementation authorization | `<state>` |
| Execution authorization | `<state>` |
| Verification status | `<state>` |
| Checkpoint acceptance | `<state>` |
| Next-phase authorization | `<state>` |
| Package authority | `<state>` |
| Package freshness | `<state>` |
| Next permitted action | `<action>` |
| Human decision required | `<decision>` |

### Fresh-session instruction

`<Concise instruction telling the next person or agent what to read, what it may do, what it must not do, and where it must stop.>`

---

## 12. Package limitations

Unless separately established by evidence and approval, this package:

- is not complete repository or business-domain understanding;
- is not proof that the design or implementation is correct;
- does not replace source inspection, tests, security review, or human judgment;
- does not authorize implementation, publication, deployment, data mutation, or the next phase;
- does not promote generated material into an authoritative source of truth;
- must be reconciled when the repository, environment, dependencies, requirements, or authority state changes.

---

## Recommended package shapes

### Compact single-file package

Use this template as one file for small discovery, design, or handoff efforts.

### Standard multi-file package

For larger projects, split it into:

1. `00-overview-and-current-state.md`
2. `01-requirements-and-acceptance.md`
3. `02-architecture-and-feature-map.md`
4. `03-decisions-risks-and-boundaries.md`
5. `04-build-sequence-and-validation.md`
6. `05-artifact-index-and-evidence-ledger.md`

### Cross-project transfer

For each item being transferred, classify it as:

| Item | Classification | Reason | Required adaptation or verification |
| --- | --- | --- | --- |
| `<artifact, pattern, or decision>` | `<BORROW / ADAPT / DO_NOT_CARRY_OVER>` | `<reason>` | `<work needed>` |

