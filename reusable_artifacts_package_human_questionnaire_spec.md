# Reusable Artifacts Package Human Questionnaire Specification

> This document defines the human questions, answer types, branching rules, consistency checks, and output contract for a Python questionnaire that generates a completed package based on `reusable_artifacts_package_template.md`.

## 1. Purpose

The questionnaire should help a human provide the intent, authority, scope, decisions, and contextual knowledge that cannot safely be inferred from a repository. It should combine those declarations with separately labelled repository or runtime evidence, when available, to produce a bounded artifacts package.

The questionnaire is not itself authorization to inspect, modify, execute, publish, deploy, or delete anything. Generating an artifacts package must never silently authorize the next project phase.

## 2. Required script behavior

The IDE agent should implement the questionnaire as an adaptive command-line application.

### 2.1 Interaction requirements

- Ask one understandable question at a time.
- Show the question ID, why the answer matters, and an example when useful.
- Use numbered choices for enumerated answers.
- Support `back`, `edit <question-id>`, `save`, `resume`, `review`, and `quit` without losing answers.
- Autosave after every accepted answer.
- Permit repeated records such as actors, requirements, risks, phases, evidence, and artifacts.
- Allow the human to finish a repeated section by selecting `done`.
- Show a final review grouped by package section before generation.
- Require an explicit final confirmation before writing output files.
- Never expose secrets entered accidentally; warn the human not to enter credentials, tokens, keys, private payloads, or regulated personal data.

### 2.2 Answer-state requirements

Every answer must have one of these states:

| State | Meaning |
| --- | --- |
| `PROVIDED` | The human supplied an answer. |
| `UNKNOWN` | The answer is material but not currently known. |
| `NOT_APPLICABLE` | The question does not apply, with a recorded reason. |
| `TO_BE_INSPECTED` | The answer should come from explicitly authorized repository or runtime inspection. |
| `DEFERRED` | The answer is intentionally postponed, with owner and checkpoint. |

The script must not turn an empty response into `NONE`, `NO`, `ACCEPTED`, or `AUTHORIZED`. `UNKNOWN` and `NONE` are different states.

### 2.3 Provenance requirements

For each material answer, retain:

- question ID;
- answer value and answer state;
- source type: `HUMAN_DECLARATION`, `SOURCE_ARTIFACT`, `REPOSITORY_OBSERVATION`, `RUNTIME_EVIDENCE`, or `DERIVED_BY_SCRIPT`;
- source reference, if any;
- respondent name or role;
- timestamp;
- last edit timestamp;
- optional confidence: `HIGH`, `MEDIUM`, or `LOW`.

The generated package must visibly distinguish human declarations, inspected facts, inferences, proposals, approvals, and validation results.

### 2.4 Output requirements

The script should generate:

1. `artifacts_package_answers.json` — canonical machine-readable responses and provenance.
2. Either:
   - `artifacts_package.md`; or
   - the selected standard multi-file package.
3. `artifacts_package_validation.md` — errors, warnings, readiness gates, unresolved material questions, and generation metadata.

The questionnaire must be repeatable: the same normalized answers and template version should produce semantically equivalent output.

## 3. Questionnaire conventions

### 3.1 Common answer types

| Type | Input behavior |
| --- | --- |
| `SHORT_TEXT` | One concise line. |
| `LONG_TEXT` | Multi-line answer terminated by an explicit command. |
| `ENUM` | One value from a closed list. |
| `MULTI_ENUM` | Zero or more values from a closed list. |
| `BOOLEAN` | `YES` or `NO`; unknown must use answer state `UNKNOWN`. |
| `DATE` | ISO `YYYY-MM-DD`. |
| `PATH_OR_URI` | Exact path, URI, repository identifier, or `NONE`. |
| `ID_LIST` | Valid IDs already created in the session. |
| `COMMAND` | Exact command; store without executing by default. |
| `REPEATED_RECORD` | A typed record repeated until the user selects `done`. |

### 3.2 Stable generated IDs

The script should assign IDs deterministically in entry order:

- actors: `ACT-001`;
- use cases: `UC-001`;
- failure cases: `FC-001`;
- functional requirements: `FR-001`;
- non-functional requirements: `NFR-001`;
- acceptance criteria: `AC-001`;
- constraints: `CON-001`;
- decisions: `DEC-001`;
- assumptions: `ASM-001`;
- conflicts: `CFT-001`;
- questions: `Q-001`;
- risks: `RSK-001`;
- phases: `PH-001`;
- evidence: `EVD-001`;
- artifacts: `ART-001`.

IDs must remain stable when a saved questionnaire is resumed. Deleting an entry must not renumber later records.

---

## 4. Question catalogue

## A. Session and output setup

### SET-001 — Template location

- Prompt: “What is the exact path to `reusable_artifacts_package_template.md`?”
- Type: `PATH_OR_URI`
- Required: Yes
- Validation: The file must exist and be readable before generation.

### SET-002 — Output location

- Prompt: “Where should the generated artifacts package be written?”
- Type: `PATH_OR_URI`
- Required: Yes
- Validation: Resolve to an explicit path; do not overwrite existing files without confirmation.

### SET-003 — Package shape

- Prompt: “Which output shape should be generated?”
- Type: `ENUM`
- Values: `COMPACT_SINGLE_FILE`, `STANDARD_MULTI_FILE`
- Required: Yes

### SET-004 — Questionnaire mode

- Prompt: “Are you starting a new questionnaire or resuming a saved answer file?”
- Type: `ENUM`
- Values: `NEW`, `RESUME`
- Required: Yes
- Branch: If `RESUME`, request and validate the answer-file path.

### SET-005 — Inspection permission

- Prompt: “May the script perform read-only inspection of the named repository or workspace to suggest evidence-backed answers?”
- Type: `ENUM`
- Values: `NO_INSPECTION`, `READ_ONLY_INSPECTION`
- Required: Yes
- Rule: This permission never includes execution, mutation, network access, secret access, or prohibited paths.

### SET-006 — Command execution permission

- Prompt: “May the script run explicitly listed, non-destructive validation commands after showing each command for confirmation?”
- Type: `ENUM`
- Values: `DO_NOT_EXECUTE`, `CONFIRM_EACH_COMMAND`
- Required: Yes
- Rule: Default to `DO_NOT_EXECUTE`. This answer does not authorize implementation or destructive commands.

## B. Package control and identity

### PKG-001 — Project name

- Prompt: “What is the project’s canonical name?”
- Type: `SHORT_TEXT`
- Required: Yes

### PKG-002 — Package purpose

- Prompt: “What is this package being created to support?”
- Type: `ENUM`
- Values: `DISCOVERY`, `DESIGN`, `IMPLEMENTATION_HANDOFF`, `REVIEW`, `RESUMPTION`, `CLOSEOUT`, `CROSS_PROJECT_TRANSFER`
- Required: Yes

### PKG-003 — Package owner

- Prompt: “Who owns the accuracy and maintenance of this package?”
- Type: `SHORT_TEXT`
- Required: Yes

### PKG-004 — Respondent

- Prompt: “Who is answering this questionnaire, and in what role?”
- Type: `SHORT_TEXT`
- Required: Yes

### PKG-005 — Repository or workspace

- Prompt: “What exact repository, directory, or workspace does this package describe?”
- Type: `PATH_OR_URI`
- Required: Yes unless the project has no repository.

### PKG-006 — Snapshot identity

- Prompt: “What commit, tag, release, digest, or dated snapshot does the package describe?”
- Type: `SHORT_TEXT`
- Required: Material; `UNKNOWN` is allowed but creates a warning.
- Inspection suggestion: Git commit and working-tree state may be proposed only under read-only inspection.

### PKG-007 — Source of truth

- Prompt: “Which artifact or location is currently authoritative for project scope and decisions?”
- Type: `PATH_OR_URI`
- Required: Material.
- Follow-up: “Who designated it authoritative, and where is that designation recorded?”

### PKG-008 — Package coverage claim

- Prompt: “In one sentence, what does this package claim to cover?”
- Type: `LONG_TEXT`
- Required: Yes

### PKG-009 — Explicit limitations

- Prompt: “What does this package explicitly not claim or prove?”
- Type: `LONG_TEXT`
- Required: Yes

## C. Authority and permission boundaries

### AUT-001 — Current authority state

- Prompt: “What work, if any, is currently authorized?”
- Type: `ENUM`
- Values: `NONE`, `DISCOVERY_ONLY`, `DESIGN_ONLY`, `IMPLEMENTATION_WITHIN_EXACT_SCOPE`, `REVIEW_ONLY`, `CLOSEOUT_ONLY`, `NOT_EVALUATED`
- Required: Yes
- Rule: No option authorizes publication, deployment, destructive migration, sensitive-data access, or the next phase unless separately answered below.

### AUT-002 — Authorizer

- Prompt: “Who granted this authority, and what role gives them that authority?”
- Type: `SHORT_TEXT`
- Required when: `AUT-001` is anything other than `NONE` or `NOT_EVALUATED`.

### AUT-003 — Authority source

- Prompt: “Where is the authorization recorded?”
- Type: `PATH_OR_URI`
- Required when: Authority is claimed.

### AUT-004 — Authorized scope

- Prompt: “State the exact authorized scope, including affected components or paths.”
- Type: `LONG_TEXT`
- Required when: Authority is claimed.

### AUT-005 — Authority exclusions

- Prompt: “What actions remain explicitly unauthorized?”
- Type: `LONG_TEXT`
- Required when: Authority is claimed.

### AUT-006 — Authority duration

- Prompt: “Does the authorization expire or end at a named checkpoint?”
- Type: `SHORT_TEXT`
- Required when: Authority is claimed.

### AUT-007 — Special action authority

- Prompt: “Which special actions are separately authorized?”
- Type: `MULTI_ENUM`
- Values: `NONE`, `PUBLICATION`, `DEPLOYMENT`, `DATA_MUTATION`, `DESTRUCTIVE_MIGRATION`, `SENSITIVE_DATA_ACCESS`, `NETWORK_ACCESS`
- Required: Yes
- Follow-up for every selected action: exact scope, authorizer, source, rollback or recovery expectation, and expiry.

### AUT-008 — Active bounded contract

- Prompt: “Is there an accepted bounded execution or phase contract? If yes, provide its ID and exact path.”
- Type: `SHORT_TEXT` plus `PATH_OR_URI`
- Required: Yes; `NONE` is allowed.

### AUT-009 — Escalation owner

- Prompt: “Who must resolve uncertainty or approve a stop-condition decision?”
- Type: `SHORT_TEXT`
- Required: Yes

## D. Problem, outcome, and current state

### OVR-001 — Problem statement

- Prompt: “What problem is being solved, for whom, and why does it matter?”
- Type: `LONG_TEXT`
- Required: Yes

### OVR-002 — Intended observable outcome

- Prompt: “What observable result should exist if the project succeeds?”
- Type: `LONG_TEXT`
- Required: Yes
- Rule: Reject answers that describe only an activity, tool, or implementation method without an outcome.

### OVR-003 — Completed work

- Prompt: “What work has been completed, and which evidence validates each claim?”
- Type: `REPEATED_RECORD`
- Fields: claim; evidence reference; validation status.
- Required: At least one record or an explicit `NONE`.

### OVR-004 — Work in progress

- Prompt: “What bounded work is currently in progress?”
- Type: `REPEATED_RECORD`
- Fields: work item; owner; scope; checkpoint; status.

### OVR-005 — Blockers

- Prompt: “What currently prevents safe progress?”
- Type: `REPEATED_RECORD`
- Fields: blocker; impact; resolution owner; required decision or evidence.

### OVR-006 — Deferred work

- Prompt: “What work is deliberately deferred and must remain outside current scope?”
- Type: `REPEATED_RECORD`
- Fields: item; reason; reconsideration condition or checkpoint.

### OVR-007 — Unverified claims

- Prompt: “Which important claims remain unverified?”
- Type: `REPEATED_RECORD`
- Fields: claim; why unverified; evidence needed; owner.

### OVR-008 — Next proposed checkpoint

- Prompt: “What is the next independently testable outcome you recommend?”
- Type: `LONG_TEXT`
- Required: Yes
- Rule: A recommendation is not authorization.

## E. Actors and use cases

### ACT-SET — Actors

- Prompt: “Add each person, role, team, or external system that uses, operates, approves, supplies, or is affected by the project.”
- Type: `REPEATED_RECORD`
- Fields: name; role type (`USER`, `OPERATOR`, `APPROVER`, `OWNER`, `SUPPLIER`, `AFFECTED_PARTY`, `EXTERNAL_SYSTEM`); needs or responsibilities; decision authority.
- Required: At least one.

### UC-SET — Primary use cases

- Prompt: “Describe a primary use case as actor, trigger, expected behavior, and observable outcome.”
- Type: `REPEATED_RECORD`
- Fields: actor ID; trigger; behavior; outcome; frequency or importance.
- Required: At least one.

### FC-SET — Failure, denial, and misuse cases

- Prompt: “What can fail, be misused, or require denial, and what should the system do?”
- Type: `REPEATED_RECORD`
- Fields: condition; required safe behavior; recovery or abstention behavior; evidence needed.
- Required: At least one for implementation or review packages; otherwise material.

## F. Scope and system boundary

### BND-001 — In scope

- Prompt: “Which capabilities, components, users, data, and environments are inside this package’s boundary?”
- Type: `LONG_TEXT`
- Required: Yes

### BND-002 — Out of scope

- Prompt: “What is explicitly outside the current boundary?”
- Type: `LONG_TEXT`
- Required: Yes

### BND-003 — External dependencies

- Prompt: “Which systems, teams, services, datasets, or decisions sit outside the boundary but affect the outcome?”
- Type: `REPEATED_RECORD`
- Fields: dependency; owner; required behavior; availability; failure impact.

### BND-004 — Prohibited shortcuts

- Prompt: “Which shortcuts or approaches would invalidate safety, evidence, traceability, or maintainability?”
- Type: `REPEATED_RECORD`
- Fields: prohibited approach; reason; detection method.
- Required: Material.

### BND-005 — Change surface

- Prompt: “Which exact paths, components, interfaces, or processes may change in the currently proposed phase?”
- Type: `REPEATED_RECORD`
- Required when: `IMPLEMENTATION_HANDOFF` or implementation authority is claimed.

### BND-006 — Preserve surface

- Prompt: “Which behavior, data, files, interfaces, or user changes must remain untouched?”
- Type: `REPEATED_RECORD`
- Required when: `IMPLEMENTATION_HANDOFF`, `REVIEW`, or `CLOSEOUT`.

## G. Requirements and acceptance

### FR-SET — Functional requirements

- Prompt: “Add one observable behavior the solution must, should, or could provide.”
- Type: `REPEATED_RECORD`
- Fields: requirement text; source; priority (`MUST`, `SHOULD`, `COULD`); status (`PROPOSED`, `ACCEPTED`, `IMPLEMENTED`, `VERIFIED`); decision owner.
- Required: At least one unless the package is discovery-only.

### NFR-SET — Non-functional requirements

- Prompt: “Add a measurable quality or constraint requirement.”
- Type: `REPEATED_RECORD`
- Fields: category; requirement; measurement or threshold; source; status.
- Categories: `SECURITY`, `PRIVACY`, `PERFORMANCE`, `RELIABILITY`, `USABILITY`, `ACCESSIBILITY`, `MAINTAINABILITY`, `PORTABILITY`, `AUDITABILITY`, `COMPLIANCE`, `OTHER`.

### AC-SET — Acceptance criteria

- Prompt: “For one or more requirements, state an observable and falsifiable pass condition.”
- Type: `REPEATED_RECORD`
- Fields: linked requirement IDs; pass condition; validation method; expected evidence; approver; status (`PROPOSED`, `ACCEPTED`, `PASSED`, `FAILED`, `NOT_RUN`).
- Required when: Any requirement is `ACCEPTED`, `IMPLEMENTED`, or `VERIFIED`.

### OUT-001 — Good outcome

- Prompt: “What observable result would count as a good outcome?”
- Type: `LONG_TEXT`
- Required: Yes

### OUT-002 — Bad outcome

- Prompt: “What observable result or trade-off would be unacceptable?”
- Type: `LONG_TEXT`
- Required: Yes

### OUT-003 — Stop conditions

- Prompt: “What conditions require work to stop and return to human review?”
- Type: `REPEATED_RECORD`
- Fields: condition; detection; required response; decision owner.
- Required: Yes

## H. Architecture, interfaces, and data

### ARC-SET — Components

- Prompt: “Add each relevant component and describe its responsibility and ownership.”
- Type: `REPEATED_RECORD`
- Fields: component; responsibility; inputs; outputs; state owner; source evidence; confidence.
- Rule: If source evidence is missing, label the record `HUMAN_DECLARATION` or `PROPOSED`; do not label it observed.

### INT-SET — Interfaces

- Prompt: “Add each relevant interface between users, components, or external systems.”
- Type: `REPEATED_RECORD`
- Fields: interface type (`API`, `CLI`, `UI`, `FILE`, `EVENT`, `DATABASE`, `HUMAN_STEP`, `OTHER`); producer; consumer; contract or format; failure behavior; source.

### DAT-SET — Inputs and outputs

- Prompt: “Add an important input or output and its format, trust level, and handling requirements.”
- Type: `REPEATED_RECORD`
- Fields: direction (`INPUT`, `OUTPUT`); name; format or schema; producer; consumer; trust classification; sample reference; validation.

### DAT-001 — Data lineage

- Prompt: “Describe the known path from original data source through transformations to destination.”
- Type: `LONG_TEXT`
- Required when: The project processes or moves data.
- Rule: Explicitly label missing lineage; never infer causal links from filenames or similarity.

### DAT-002 — Retention and expiry

- Prompt: “What retention, deletion, expiry, or freshness rules apply?”
- Type: `LONG_TEXT`
- Required when: Data or generated evidence persists.

## I. Operating environment

### ENV-001 — Runtime and platforms

- Prompt: “Which operating systems, runtimes, hardware, deployment targets, and versions matter?”
- Type: `REPEATED_RECORD`
- Fields: item; version; purpose; source; required or observed.

### ENV-002 — Tools and dependencies

- Prompt: “Which tools, libraries, APIs, models, or services are required?”
- Type: `REPEATED_RECORD`
- Fields: dependency; version or constraint; source; purpose; availability; license or access concern.

### ENV-003 — Configuration locations

- Prompt: “Where is configuration defined?”
- Type: `REPEATED_RECORD`
- Fields: path or source; purpose; authoritative status.
- Warning: Never record secret values.

### ENV-004 — Build commands

- Prompt: “What exact commands build or prepare the project?”
- Type: `REPEATED_RECORD` of `COMMAND`
- Fields: command; working directory; expected result; source; last observed date.

### ENV-005 — Test and lint commands

- Prompt: “What exact commands run tests, linting, static analysis, or schema checks?”
- Type: `REPEATED_RECORD` of `COMMAND`
- Fields: command; working directory; expected result; source; last observed date.

### ENV-006 — Runtime verification commands

- Prompt: “What exact commands or manual steps verify real runtime behavior?”
- Type: `REPEATED_RECORD`
- Fields: command or step; controlled input; expected observation; environment; evidence location.

## J. Security, privacy, and operational controls

### SEC-SET — Constraints and controls

- Prompt: “Add each material security, privacy, authorization, data-handling, or operational constraint.”
- Type: `REPEATED_RECORD`
- Fields: category; constraint; enforcement; evidence or status; owner.
- Categories: `AUTHENTICATION`, `AUTHORIZATION`, `SENSITIVE_DATA`, `REDACTION`, `LOGGING`, `READ_WRITE_BOUNDARY`, `EXECUTION_BOUNDARY`, `NETWORK`, `SECRETS`, `FAIL_CLOSED`, `ABSTENTION`, `PERSISTENCE`, `DEPLOYMENT`, `RECOVERY`, `COMPLIANCE`, `OTHER`.
- Required: At least one or an explicit human declaration that no material constraint has yet been identified.

### SEC-001 — Restricted content

- Prompt: “Could the project contain restricted, confidential, regulated, personal, licensed, or otherwise non-shareable content?”
- Type: `BOOLEAN`
- Required: Yes
- If yes: Ask for categories, allowed locations, prohibited locations, access roles, redaction rule, and fail-closed behavior. Do not request the sensitive content itself.

### SEC-002 — Negative-path behavior

- Prompt: “When access, validation, provenance, or authority is missing, should the process deny, abstain, quarantine, redact, or escalate?”
- Type: `MULTI_ENUM`
- Values: `DENY`, `ABSTAIN`, `QUARANTINE`, `REDACT`, `ESCALATE`, `OTHER`
- Required: Yes

### SEC-003 — Rollback and recovery

- Prompt: “What rollback, retry, restart, recovery, or degraded-mode behavior is required?”
- Type: `LONG_TEXT`
- Required when: Implementation, deployment, mutation, or runtime operation is in scope.

## K. Decisions, assumptions, conflicts, and open questions

### DEC-SET — Decisions

- Prompt: “Add a project decision and identify who made it and where it is recorded.”
- Type: `REPEATED_RECORD`
- Fields: decision; rationale; decider; date; evidence; status (`PROPOSED`, `ACCEPTED`, `SUPERSEDED`).

### ASM-SET — Assumptions

- Prompt: “Add an assumption that could affect scope, architecture, safety, or validation.”
- Type: `REPEATED_RECORD`
- Fields: assumption; impact if wrong; validation method; owner; status (`OPEN`, `VALIDATED`, `INVALIDATED`).

### CFT-SET — Source conflicts

- Prompt: “Do any sources, instructions, claims, or authority statements conflict?”
- Type: `REPEATED_RECORD`
- Fields: source A; source B; conflict; impact; resolution owner; status (`OPEN`, `RESOLVED`).
- Required: Explicit `NONE_IDENTIFIED` or at least one entry.

### QST-SET — Open questions

- Prompt: “Add an unresolved question that could change scope, architecture, safety, authority, or validation.”
- Type: `REPEATED_RECORD`
- Fields: question; why it matters; decision owner; needed by checkpoint; current disposition.

## L. Risks and controls

### RSK-SET — Risks

- Prompt: “Add a material project risk and its control.”
- Type: `REPEATED_RECORD`
- Fields: risk; likelihood (`LOW`, `MEDIUM`, `HIGH`); impact (`LOW`, `MEDIUM`, `HIGH`); detection; mitigation or control; owner; residual status (`OPEN`, `ACCEPTED`, `MITIGATED`).
- Suggested categories: missing evidence, stale snapshot, wrong authority, data leakage, inferred relationships, dependency change, rollback difficulty, validation gap, operational failure.
- Required: At least one or explicit `NONE_IDENTIFIED_YET`, which creates a warning rather than proving no risk exists.

## M. Phased build or investigation sequence

### PHS-SET — Phases

- Prompt: “Add one phase with a single independently testable outcome.”
- Type: `REPEATED_RECORD`
- Fields:
  - title and single observable outcome;
  - status (`PROPOSED`, `ACCEPTED`, `IN_PROGRESS`, `REVIEW`, `CLOSED`);
  - linked requirement IDs;
  - in-scope items;
  - out-of-scope items;
  - prerequisites;
  - expected change surface;
  - deliverables;
  - linked acceptance-criterion IDs;
  - exact validation commands or manual checks;
  - negative or isolation test;
  - expected evidence artifacts;
  - risks and detection;
  - rollback or recovery;
  - human-review level (`NONE`, `SAMPLED`, `REQUIRED`, `APPROVAL_REQUIRED`);
  - review focus;
  - stop condition;
  - authority source.
- Required when: `IMPLEMENTATION_HANDOFF`, `RESUMPTION`, or implementation authority is claimed.
- Rule: A phase cannot be `ACCEPTED` without an authority source and accepted acceptance criteria.

## N. Validation and evidence

### EVD-SET — Evidence ledger

- Prompt: “Add an evidence item supporting or refuting a material claim.”
- Type: `REPEATED_RECORD`
- Fields: claim tested; evidence type (`TEST`, `LOG`, `DIFF`, `RUNTIME_OBSERVATION`, `MANUAL_REVIEW`, `SOURCE_ARTIFACT`, `NEGATIVE_EVENT`, `OTHER`); exact source, path, or command; controlled input; expected result; observed result; result (`PASS`, `FAIL`, `PARTIAL`, `NOT_RUN`); date; limitations.
- Required for: Any `VERIFIED`, `PASSED`, `ACCEPTED`, or `CLOSED` claim.

### VAL-001 — Generation evidence

- Prompt: “Were the expected artifacts or changes produced? Identify the evidence.”
- Type: `LONG_TEXT`
- Required for: `REVIEW` or `CLOSEOUT`.

### VAL-002 — Verification evidence

- Prompt: “Which tests, checks, or observations support the required behavior?”
- Type: `LONG_TEXT`
- Required for: `REVIEW` or `CLOSEOUT`.

### VAL-003 — Understanding evidence

- Prompt: “Can the result explain what changed, why, its requirement links, and what remains uncertain?”
- Type: `LONG_TEXT`
- Required for: `REVIEW` or `CLOSEOUT`.

### VAL-004 — Negative evidence

- Prompt: “Which denied actions, abstentions, non-events, isolation checks, or failure tests provide useful evidence?”
- Type: `LONG_TEXT`
- Required when: Security, isolation, denial, or non-contamination is material.

### VAL-005 — Reproducibility record

- Prompt: “Add a reproducible validation observation.”
- Type: `REPEATED_RECORD`
- Fields: environment; snapshot; command or steps; controlled input; expected result; observed result; evidence location.

## O. Artifact inventory and admission

### ART-SET — Artifact index

- Prompt: “Add an artifact that should be admitted to the package.”
- Type: `REPEATED_RECORD`
- Fields: exact path or reference; purpose; provenance; authority (`AUTHORITATIVE`, `SUPPORTING`, `EXPLORATORY`); authority basis; related requirement, decision, risk, or phase IDs; status (`CURRENT`, `STALE`, `SUPERSEDED`, `DRAFT`, `UNVERIFIED`, `RESTRICTED`); last validated date; digest or version if available.
- Required: At least the authoritative source and generated package artifacts.

### ARTQ-001 — Excluded artifacts

- Prompt: “Were any expected or discovered artifacts excluded?”
- Type: `REPEATED_RECORD`
- Fields: path or description; exclusion reason; reason code; impact.
- Suggested reason codes: `UNRELATED`, `WRONG_PROJECT`, `WRONG_SNAPSHOT`, `UNSEALED`, `RESTRICTED`, `WEAK_RELATIONSHIP`, `PROHIBITED_PATH`, `UNAVAILABLE`.

### ARTQ-002 — Admission confirmation

- Prompt: “Do admitted artifacts have exact paths or identifiers, explicit provenance, and an appropriate authority and freshness label?”
- Type: `BOOLEAN`
- Required: Yes
- Rule: `NO` creates a validation error for readiness claims.

## P. Handoff and closeout

### HND-001 — Checkpoint classification

- Prompt: “What is the current checkpoint classification?”
- Type: `ENUM`
- Values: `NOT_EVALUATED`, `ACCEPTED`, `ACCEPTED_WITH_CHANGES`, `NEEDS_MORE_EVIDENCE`, `NEEDS_REVISION`, `DEFERRED`, `REJECTED`, `BLOCKED_AT_HUMAN_CHECKPOINT`
- Required: Yes
- Rule: The script must not derive `ACCEPTED` solely from test counts or human optimism. Acceptance requires linked evidence and an authorized reviewer.

### HND-002 — Classification reason

- Prompt: “Why is that checkpoint classification justified, and who made the classification?”
- Type: `LONG_TEXT`
- Required unless: `NOT_EVALUATED`.

### HND-003 — Changed artifacts

- Prompt: “Which artifacts or code changed during this checkpoint?”
- Type: `REPEATED_RECORD`
- Fields: exact path; change summary; expected or unexpected; related phase and requirement IDs.
- Required for: `REVIEW` or `CLOSEOUT`.

### HND-004 — Deviations

- Prompt: “What deviated from the accepted scope, plan, or expected evidence?”
- Type: `REPEATED_RECORD`
- Fields: deviation; reason; impact; disposition; approver if accepted.

### HND-005 — Residual risks and limitations

- Prompt: “Which risks, limitations, and unproven claims remain?”
- Type: `LONG_TEXT`
- Required: Yes

### HND-006 — Working-state observations

- Prompt: “What relevant working-tree, environment, or pre-existing change state must the next session preserve?”
- Type: `LONG_TEXT`
- Required when: A repository or runtime environment is involved.

### HND-007 — Next permitted action

- Prompt: “What single bounded action may happen next?”
- Type: `LONG_TEXT`
- Required: Yes
- Rule: If no action is authorized, use `HUMAN_REVIEW_ONLY` or `NONE`.

### HND-008 — Required approver

- Prompt: “Who, if anyone, must approve the next action?”
- Type: `SHORT_TEXT`
- Required: Yes; `NONE` is allowed only if no approval is required.

### HND-009 — Fresh-session instruction

- Prompt: “Tell a fresh person or agent what to read, what it may do, what it must not do, and where it must stop.”
- Type: `LONG_TEXT`
- Required: Yes

## Q. Cross-project transfer module

Ask only when `PKG-002 = CROSS_PROJECT_TRANSFER`.

### XFR-SET — Transfer items

- Prompt: “Add an artifact, pattern, decision, or component considered for transfer.”
- Type: `REPEATED_RECORD`
- Fields: item; source project and snapshot; classification (`BORROW`, `ADAPT`, `DO_NOT_CARRY_OVER`); reason; target-project difference; required adaptation; required re-verification; prohibited inherited assumptions.
- Required: At least one.

## R. Final human attestation

### FIN-001 — Completeness review

- Prompt: “Have all material uncertainties, conflicts, risks, exclusions, and unverified claims been recorded?”
- Type: `BOOLEAN`
- Required: Yes

### FIN-002 — Secret and sensitive-content review

- Prompt: “Have you confirmed that the answers and proposed output contain no secrets or unnecessarily exposed sensitive payloads?”
- Type: `BOOLEAN`
- Required: Yes

### FIN-003 — Authority review

- Prompt: “Do you understand that generating or accepting this package does not authorize implementation, deployment, publication, destructive change, sensitive-data access, or the next phase unless that authority is separately and explicitly recorded?”
- Type: `BOOLEAN`
- Required: Must be `YES` to generate a package marked ready or accepted.

### FIN-004 — Generate outputs

- Prompt: “Generate the artifacts package and validation report from the reviewed answers?”
- Type: `BOOLEAN`
- Required: Yes

---

## 5. Deterministic consistency rules

The Python implementation must evaluate these rules before generation. Errors do not need to prevent generation of a `DRAFT` or `BLOCKED` package, but they must prevent unsupported readiness or authorization claims.

### 5.1 Authority rules

1. If authority is claimed, require an authorizer, authority source, exact scope, exclusions, and duration or checkpoint.
2. `IMPLEMENTATION_WITHIN_EXACT_SCOPE` requires at least one accepted phase, linked accepted acceptance criteria, a defined change surface, feasible validation, rollback or recovery, and named human-review level.
3. Special-action authority requires its own authorizer, source, exact scope, and recovery expectation.
4. An accepted checkpoint does not imply authority for the next phase, deployment, publication, or destructive mutation.
5. If authority evidence conflicts with scope or package purpose, set package status to `BLOCKED` and next permitted action to `HUMAN_REVIEW_ONLY`.

### 5.2 Traceability rules

1. Every accepted, implemented, or verified requirement must have a source and linked acceptance criterion.
2. Every passed acceptance criterion must link to evidence with result `PASS`.
3. Every accepted or closed phase must link to requirements, acceptance criteria, validation, evidence, and an authority source.
4. Every artifact marked `AUTHORITATIVE` must include an authority basis.
5. Every evidence-backed architectural claim must include a source reference; otherwise label it declared or proposed.
6. References to IDs that do not exist are errors.

### 5.3 Status rules

1. A package begins as `DRAFT`.
2. Material `UNKNOWN`, unresolved high-impact conflict, missing required evidence, missing owner, or failed final attestation prevents `READY_FOR_REVIEW` or `ACCEPTED`.
3. A `VERIFIED`, `PASSED`, `ACCEPTED`, or `CLOSED` status without evidence is an error.
4. `NONE_IDENTIFIED` means no item has been identified; it does not prove absence.
5. Repository inspection cannot promote a proposal into an accepted decision or grant human authority.

### 5.4 Scope and safety rules

1. In-scope and out-of-scope descriptions must not materially overlap without a recorded conflict.
2. A prohibited shortcut cannot also appear in an authorized phase.
3. Restricted artifacts must not be copied into output; retain only safe metadata and reason codes.
4. Commands are recorded but not executed unless `CONFIRM_EACH_COMMAND` was selected and the human approves the exact command at runtime.
5. The script must reject destructive commands from questionnaire-driven execution even if they appear in an answer.
6. Read-only inspection results must record repository, snapshot, path, and inspection time.

## 6. Readiness-gate calculations

The validation report should compute, but never silently approve, these gates.

### Gate A — Ready to plan

Pass when the problem, actors, boundary, critical requirements, non-goals, good and bad outcomes, and stop conditions are explicit, with no material unresolved contradiction or ownerless high-impact assumption.

### Gate B — Ready to implement

Pass when Gate A passes and the current phase is accepted, independently testable, authorized within exact scope, linked to accepted criteria, supported by prerequisites, bounded by a known change and rollback surface, and has feasible validation plus named human review.

### Gate C — Ready for checkpoint acceptance review

Pass when scope fidelity, traceability, test evidence, required runtime evidence, isolation, recovery, provenance, security boundaries, and honest limitations are sufficiently recorded for an authorized human reviewer to decide. Passing Gate C is readiness for review, not automatic acceptance.

### Gate D — Ready to advance

Pass only when the checkpoint classification permits advancement, durable context and the artifact index are current, deferred work is visible, and the next phase has separate explicit authorization.

For every gate, output:

- `PASS`, `FAIL`, or `NOT_EVALUATED`;
- satisfied conditions;
- failed conditions;
- blocking question or record IDs;
- the exact human decision or evidence required next.

## 7. Generation behavior

### 7.1 Human versus inspected answers

When read-only inspection is enabled, the script may suggest answers for repository paths, snapshot identity, project layout, configuration locations, dependencies, commands found in documentation, and artifact candidates. The human must accept, edit, reject, or mark each suggestion `TO_BE_INSPECTED`.

The script must not infer:

- business intent;
- authority or approval;
- accepted scope;
- causal or semantic relationships;
- requirement priority;
- risk acceptance;
- correctness;
- deployment readiness;
- identity or role of an approver.

### 7.2 Output rendering

- Omit empty optional tables only when the corresponding answer is genuinely `NOT_APPLICABLE`.
- Render material `UNKNOWN` and `DEFERRED` items visibly.
- Preserve stable IDs and provenance across regeneration.
- Include the template version and answer-file digest in generation metadata.
- Sort human-entered repeated records by stable ID, not alphabetically.
- Escape Markdown table delimiters and unsafe markup.
- Never reproduce secret values or restricted payload content.
- Record output paths and hashes in the validation report.

### 7.3 Default blocking outcome

If the package contains material conflicts, missing authority, missing acceptance criteria, missing validation, or unreviewed sensitive-data constraints, the script should still offer to generate a truthful package with:

- package status: `BLOCKED` or `DRAFT`;
- implementation authority: `NONE` or `NOT_EVALUATED`;
- next permitted action: `HUMAN_REVIEW_ONLY`;
- a concise list of blocking question IDs.

It must not pressure the human to select stronger answers merely to make a gate pass.

## 8. Minimum test expectations for the IDE implementation

The IDE agent should add tests covering at least:

1. new questionnaire and resume flow;
2. stable IDs after add, edit, delete, save, and resume;
3. compact and multi-file generation;
4. `UNKNOWN` versus `NONE` preservation;
5. implementation authority rejected without authorizer, scope, accepted criteria, and phase;
6. accepted or verified claims rejected without evidence;
7. unresolved source conflict produces a blocked state;
8. read-only inspection cannot grant authority or acceptance;
9. commands are not executed by default;
10. destructive command execution is rejected;
11. restricted content is redacted while reason codes remain;
12. invalid cross-references are reported;
13. deterministic output from identical normalized answers;
14. existing output requires overwrite confirmation;
15. final attestation failure prevents ready or accepted status;
16. Gate A through Gate D results include reasons and blocking IDs.

## 9. IDE-agent implementation handoff

Provide the IDE agent with this specification and `reusable_artifacts_package_template.md`, then instruct it to:

1. inspect the target repository before proposing file locations or integration points;
2. report conflicts with existing project instructions or questionnaire tooling;
3. implement only the questionnaire, persistence, validation, and Markdown-generation capability;
4. keep repository inspection optional and read-only;
5. avoid implementation, deployment, or generic command-execution capabilities;
6. use a versioned JSON schema for the canonical answer file;
7. add automated tests for the minimum expectations above;
8. run the project’s approved validation commands;
9. provide exact changed paths, commands, results, limitations, and evidence;
10. stop at a human-review checkpoint without starting another phase.

## 10. SDLC Harness revision contract

When `HAR-000` is `YES`, the questionnaire records the bounded pipeline
stage, run type, target and Harness repositories, evidence location, snapshot
and dirty-state manifest, intake reconciliation, discovery metadata, source
authority classifications, BEC lifecycle transitions, implementation and
execution authority separately, verification, checkpoint acceptance, package
freshness, and next permitted action. These fields are evidence or human
declarations and never grant authority by generation.

When `HAR-000` is `NO`, all Harness fields are derived `NOT_APPLICABLE` answers
and cannot affect general readiness. Empty discovery means
`NOT_FOUND_BY_THIS_METHOD`; partial, noisy, stale, or contradictory discovery
requires fallback or human disposition. Schema `0.1` files migrate
deterministically to schema `0.2` on load; unsupported versions are rejected.
