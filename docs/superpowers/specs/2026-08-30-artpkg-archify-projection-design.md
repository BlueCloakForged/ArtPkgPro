# ArtPkg Archify Projection Design

Date: 2026-08-30

Status: Draft for human review; revised to include ArtPkg-owned intake UI

## Purpose

ArtPkg should use Archify as a local visual projection and review layer for package intake, package readiness, scope, system context, and evidence reconciliation. ArtPkg remains the semantic source of truth: it owns uploaded pre-artifacts, questionnaire state, requirements, authority, provenance, evidence states, validation gates, next permitted action, and human approval boundaries.

Archify renders bounded, interactive maps from typed JSON IR. A valid Archify diagram proves the diagram is structurally valid and visually deliverable; it does not prove that an ArtPkg package is complete, approved, implementation-ready, or safe to advance.

The practical review model is:

```text
pre-artifacts + intent + package records + observations + evidence -> traceable views -> targeted human review
```

This replaces an unsafe model:

```text
source code -> diagram -> human approval
```

## Evidence From Spike

A throwaway read-only spike was completed against the local ArtPkg and Archify copies:

- ArtPkg workspace: `D:\ArtPkg`
- Archify workspace: `D:\archify`
- Spike artifacts: `C:\Users\vin\AppData\Local\Temp\artpkg-archify-spike`
- Return handoff: `C:\Users\vin\AppData\Local\Temp\return_handoff_artpkg_archify_readiness_spike.md`

The spike produced:

- `artpkg-readiness.architecture.json`
- `artpkg-readiness.mapping.json`
- `artpkg-readiness.html`
- `projection-validation.md`
- Archify visual-check screenshots and receipts

Archify validation passed `9 / 9` showcase checks with zero errors and zero warnings. Delivery passed and produced a standalone HTML artifact. Visual-check initially failed when summary cards caused vertical overflow; a graph-first version passed containment, readability, and viewer chrome checks at `1440x900`, `1600x1000`, `1920x1080`, and `2048x1320`.

The spike used `example-artpkg-seeded-output.md`, not a canonical `artifacts_package_answers.json`. That limitation is important: the spike proves projection feasibility and review value, not correctness of a final package.

## Scope

### In Scope

The first official capability should be an ArtPkg-owned local intake interface plus a read-only projection adapter that:

- Lets a user upload or select a pre-artifacts Markdown file.
- Runs ArtPkg-owned parsing/seeding logic.
- Starts or resumes the ArtPkg questionnaire from the seeded draft.
- Shows which questionnaire answers still require human input.
- Groups unanswered, uncertain, authority-sensitive, and evidence-sensitive fields for review.
- Accepts canonical ArtPkg answers JSON and validation output.
- Optionally accepts generated package Markdown for display references.
- Emits a valid Archify JSON IR file.
- Emits a semantic mapping sidecar.
- Emits a projection validation report.
- Invokes local Archify validation and delivery for visual review.
- Fails closed when records, relationships, digests, or authority semantics are ambiguous.

The first interface flow should begin with Intake Review, then use Package Readiness as the first Archify-backed view. It answers:

1. Why is the package blocked?
2. What has already been accepted?
3. What remains proposed, unknown, or deferred?
4. What evidence is missing?
5. What is the next permitted action?

The intake UI should also answer:

1. Which questionnaire fields were seeded from the pre-artifacts file?
2. Which required fields still need user answers?
3. Which seeded fields require confirmation before canonical generation?
4. Which fields are authority-sensitive, privacy-sensitive, or evidence-sensitive?
5. What is the smallest next review action the user should take?

### Out of Scope

The first official capability must not:

- Modify Archify schemas.
- Move the first user interface into Archify.
- Treat Archify validation as ArtPkg gate evidence.
- Infer human approval, requirement priority, authority, or risk acceptance.
- Use an LLM to invent graph relationships.
- Visualize every ArtPkg record by default.
- Advance Pipeline-A, activate a BEC, authorize implementation, or authorize execution.
- Replace ArtPkg validation.
- Require the local Archify docs server to be running.
- Merge ArtPkg and Archify into one project before the ArtPkg-owned workflow proves useful across a full package lifecycle.

## Architecture

The first system has seven units:

1. ArtPkg intake UI
2. Pre-artifacts upload/select handler
3. ArtPkg parser/seeder
4. ArtPkg semantic normalizer
5. View projector
6. Mapping sidecar writer
7. Archify runner

The flow is:

```text
pre-artifacts Markdown
  -> ArtPkg intake UI
  -> upload/select handler
  -> ArtPkg parser/seeder
  -> questionnaire draft + review queue
  -> human answers/confirmations
  -> canonical ArtPkg answers JSON
  + ArtPkg validation report
  + optional package Markdown
  -> semantic normalizer
  -> view projector
  -> Archify IR + mapping sidecar + projection report
  -> Archify validate/deliver
  -> human review artifact
```

The intake UI and adapter should live on the ArtPkg side. Archify should remain an external local renderer/validator invoked through its documented CLI:

```text
node bin/archify.mjs validate <type> <candidate.json> --quality showcase --json
node bin/archify.mjs deliver <type> <candidate.json> <output.html> --quality showcase --json
node bin/archify.mjs visual-check <output.html> --json
```

If the global `node` shim is unavailable, the adapter may accept an explicit Node executable path. The spike succeeded with:

```text
C:\Users\vin\AppData\Local\nvm\v20.18.2\node.exe
```

## Components

### ArtPkg Intake UI

Provides the first user interface for processing projects through ArtPkg. It should be local-first and ArtPkg-owned. The UI should let the user upload or select a pre-artifacts file, review seeded questionnaire answers, answer missing fields, confirm or reject seeded values, and see why specific fields matter.

The UI should organize review into queues:

- `Needs answer`: required fields that are missing, `UNKNOWN`, or `DEFERRED` without an owner/checkpoint.
- `Needs confirmation`: seeded values that are plausible but not yet human-confirmed.
- `Authority-sensitive`: approval, scope, implementation, deployment, publication, recording, privacy, and special-action questions.
- `Evidence-sensitive`: claims, acceptance criteria, validation commands, runtime evidence, and negative evidence.
- `Ready for quick review`: high-confidence fields that are still visible but not blocking the user first.

The UI must not silently convert seeded values into accepted ArtPkg authority. Human confirmation must be explicit and recorded with provenance.

### Pre-Artifacts Upload/Select Handler

Accepts a local Markdown pre-artifacts file selected by the user. It computes a digest, records the source path, rejects unsupported file types, and warns the user not to upload secrets, credentials, private payloads, or regulated personal data unless ArtPkg has an explicit safe handling rule for that content.

The handler should support local file selection first. Drag-and-drop and archive upload can wait until the base lifecycle works.

### ArtPkg Parser/Seeder

Uses ArtPkg-owned deterministic parsing and seeding logic to populate a draft questionnaire. It may propose answers with confidence and source references, but it cannot create authority, approve requirements, accept criteria, or mark evidence as passed.

The parser/seeder should preserve the current CLI behavior where `UNKNOWN`, `NONE`, `NOT_APPLICABLE`, `TO_BE_INSPECTED`, and `DEFERRED` remain distinct.

### Source Loader

Reads only explicit input files supplied by the operator or ArtPkg workflow. It computes SHA-256 digests before projection and records them in the mapping sidecar and projection report.

Inputs:

- `artifacts_package_answers.json`
- `artifacts_package_validation.md` or equivalent validation JSON if added later
- optional generated package Markdown
- optional repository observation manifest
- optional runtime evidence manifest

It must reject missing required files unless the selected view is explicitly allowed to visualize missing artifacts as blockers.

### Semantic Normalizer

Builds an internal projection model from ArtPkg records without changing them. It preserves:

- stable ArtPkg IDs
- answer state
- source type
- source reference
- confidence, when present
- authority state
- requirement status
- acceptance criterion status
- evidence result
- gate result
- next permitted action

It does not create requirements, approve criteria, accept risks, or upgrade evidence.

### View Projector

Converts the normalized model into a bounded Archify diagram. The first supported view is:

- `package-readiness`: an Architecture diagram focused on readiness blockers and permitted next action.

Later supported views may include:

- `phase-scope`: accepted phase, allowed change surface, preserved surface, deferred capabilities.
- `system-context`: actors, local systems, external dependencies, data movement, trust boundaries.
- `verification`: acceptance criteria, test evidence, runtime evidence, negative evidence.
- `reconciliation`: declared system vs observed system vs verified system.
- `revision-delta`: previous package vs regenerated package.

Each view must prefer aggregation over visual overload. The default target is 8 to 12 primary nodes, with additional record detail available through the sidecar and source files.

### Mapping Sidecar Writer

Archify schemas intentionally reject unknown fields. Therefore ArtPkg semantics should not be forced into Archify `tag`, `sublabel`, or presentation fields beyond brief visible labels.

The sidecar is the semantic contract. It maps each Archify node and edge to ArtPkg records or documented aggregations.

Minimum sidecar shape:

```json
{
  "schema_version": 1,
  "artifact_type": "ARTPKG_ARCHIFY_MAPPING_SIDECAR",
  "inputs": [],
  "projection_rules": [],
  "nodes": [],
  "edges": [],
  "negative_assertions": []
}
```

Every sidecar node should include:

- Archify ID
- kind
- ArtPkg record IDs or aggregation ID
- provenance
- answer state
- authority state
- relationship status
- source artifact digest

Every sidecar edge should include:

- Archify relationship ID
- relation type
- source record IDs or projection rule ID
- whether the relationship is declared, observed, derived, proposed, or future

### Archify Runner

Runs Archify as a local external tool and captures validation receipts. It should not require the Archify documentation server at `http://127.0.0.1:5173`; that server is useful for human inspection but not required for deterministic projection.

The runner records:

- command
- working directory
- exit code
- stdout JSON
- stderr, if any
- specification SHA-256
- artifact SHA-256
- visual-check result, when available

## View Semantics

### Declared System

Shows what ArtPkg says should exist:

- human-declared requirements
- accepted boundaries
- accepted or proposed phases
- prohibited behavior
- authority state
- stop conditions

Declared views must clearly distinguish `PROPOSED`, `ACCEPTED`, `UNKNOWN`, `DEFERRED`, and `NOT_APPLICABLE`.

### Observed System

Shows what read-only discovery finds:

- components
- files
- interfaces
- dependencies
- data movement
- repository metadata

Observed views must label observations as `REPOSITORY_OBSERVATION`. They cannot infer business intent, approval, requirement priority, or correctness.

### Verified System

Shows what tests and runtime evidence demonstrate:

- tests
- logs
- runtime evidence
- negative evidence
- validation commands
- observed result
- evidence limitations

Only evidence records with passing results may be visualized as verified. `SOURCE_ARTIFACT`, `PARTIAL`, and `NOT_RUN` evidence must remain visually distinct.

### Reconciliation View

Shows gaps between declared, observed, and verified systems:

- requirement with no observed component
- component with no approved requirement
- acceptance criterion with no test
- test result with no acceptance criterion
- observed data flow absent from approved design
- implementation beyond the authorized phase
- declared security boundary not enforced by observed system
- proposed behavior incorrectly represented as verified

This view is the long-term value center, but it should come after Package Readiness and Phase Scope are implemented.

## Fail-Closed Rules

The adapter must fail projection or mark the artifact blocked when:

- An Archify node does not resolve to an ArtPkg record or explicit aggregation.
- An Archify edge does not resolve to a declared relationship, observed relationship, or deterministic projection rule.
- A `PROPOSED` item is displayed as `ACCEPTED`.
- `SOURCE_ARTIFACT`, `PARTIAL`, or `NOT_RUN` evidence is displayed as verified.
- Authority is missing, unknown, or not evaluated and the map omits that fact.
- Input package digests differ from the digests recorded in the sidecar.
- A stale map is requested without an explicit stale marker.
- Unmapped records are silently omitted from a view where they are material.
- A diagram attempts to change ArtPkg gate status or next permitted action.
- The count of represented blockers differs from the source validation output.
- A generated Archify file contains unapproved semantic fields that Archify ignores or rejects.

Failure should still be useful. When possible, emit a projection validation report explaining exactly which record, edge, digest, or rule blocked delivery.

## Data and Artifacts

The official output set should be:

```text
artpkg-readiness.architecture.json
artpkg-readiness.mapping.json
artpkg-readiness.html
artpkg-readiness.projection-validation.md
artpkg-readiness.archify-delivery.json
artpkg-readiness.visual-check.json
```

For generated ArtPkg standard packages, these can later be placed beside the package output or under a dedicated `visualizations/` directory. That placement should be explicit in the questionnaire answers or generation options.

The projection output is a review artifact. It is not an authority artifact unless a future ArtPkg schema explicitly admits it as supporting evidence with correct limitations.

## Questionnaire and Pre-Artifacts Upload Direction

The questionnaire and pre-artifacts upload should first live in ArtPkg. ArtPkg owns the UI, upload/select flow, parser/seeder, questionnaire state, validation, generated package, and approval boundaries. Archify is called locally to render review views that help the user see which questions need answering and why.

The first official flow is:

```text
ArtPkg intake UI
  -> pre-artifacts upload/select
  -> ArtPkg parser/seeder
  -> human review queue
  -> canonical answers JSON
  -> ArtPkg validation
  -> Archify readiness projection
  -> human review
  -> generation/approval decision remains outside Archify
```

Archify can make the upload/review experience more legible, but it should not become the parser of record or the approval mechanism in the first system. The official parser and validator remain ArtPkg-owned.

If this ArtPkg-owned system proves it can help a user create a full artifacts package through its lifecycle, a later phase may merge the projects and create an Archify-hosted interface that calls into ArtPkg logic. That later phase should require separate approval and a new design because it changes ownership boundaries, packaging, runtime assumptions, and likely the public product surface.

## Error Handling

The adapter should classify failures as:

- input missing
- input digest mismatch
- unsupported upload type
- unsafe upload content warning unresolved
- unsupported ArtPkg schema version
- invalid ArtPkg validation state
- questionnaire draft persistence failure
- seeded answer conflict
- unmapped node
- unmapped edge
- stale projection
- authority elevation attempt
- evidence elevation attempt
- Archify schema validation failure
- Archify layout validation failure
- Archify delivery failure
- visual-check failure
- local tool unavailable

Each failure should report:

- stable code
- affected record or element ID
- source artifact
- observed value
- expected value
- supported fix
- whether generation was skipped or produced a blocked projection

## Testing Strategy

Unit tests should cover:

- canonical answers and validation inputs are loaded with digests.
- missing canonical answers are represented as blockers only in views that allow missing-artifact visualization.
- every emitted Archify node has a sidecar mapping.
- every emitted Archify edge has a sidecar mapping.
- proposed records are never displayed as accepted.
- `NOT_RUN` evidence is never displayed as verified.
- missing authority is never omitted from Package Readiness.
- stale input digest fails projection.
- unmapped records are counted and reported.
- Archify validation failure prevents delivered success.
- visual-check failure is recorded without modifying ArtPkg status.
- any future Archify-hosted merged-interface markers are labeled success-contingent and out of current scope.
- pre-artifacts upload computes and records source digest.
- seeded questionnaire answers retain source references and confidence.
- seeded values require explicit human confirmation before becoming canonical accepted answers.
- authority-sensitive and evidence-sensitive fields appear in the correct review queues.
- rejecting a seeded value leaves a durable review disposition rather than deleting uncertainty.

Integration tests should use a small fixture ArtPkg package and run local Archify validation. They should not require network access, publication, deployment, Gortex, or external AI services.

Negative tests are required before production use:

- false relationship injection
- authority elevation
- evidence elevation
- omitted blocker
- stale digest
- unsupported schema field
- accepted phase without authority source
- requirement with missing acceptance criterion
- uploaded pre-artifacts file containing a restricted-content marker
- seeded authority answer incorrectly treated as human approval

## Acceptance Criteria

The design is ready for implementation planning when:

- The ArtPkg-owned intake UI boundary is accepted.
- The Package Readiness view contract is accepted.
- The sidecar mapping contract is accepted.
- Fail-closed rules are accepted.
- The later Archify-hosted merged interface is confirmed as success-contingent future work.
- The local Archify invocation strategy is accepted.
- Test expectations include semantic negative tests, not only render checks.

The implementation is successful when a user can upload or select a pre-artifacts file, begin the questionnaire, and identify, within a few minutes:

1. which fields still require answers,
2. which seeded answers require confirmation,
3. which fields are authority-sensitive or evidence-sensitive,
4. why the package is blocked,
5. what action is permitted next.

The Archify-backed readiness view remains successful when a reviewer can open the generated HTML and identify, within a few minutes:

1. why the package is blocked,
2. what is accepted,
3. what remains proposed, unknown, or deferred,
4. what evidence is missing,
5. what action is permitted next,

while every displayed fact and relationship traces back to ArtPkg records, source artifacts, or documented deterministic aggregation rules.

## Open Questions

1. Should projection outputs live beside generated packages or under a dedicated `visualizations/` subdirectory?
2. Should the intake UI be a small local web app, a desktop browser app served by ArtPkg, or a lightweight terminal-plus-browser hybrid?
3. Should visual-check be required for every generated map or only for release/package artifacts?
4. What is the canonical validation input shape: Markdown report only, JSON validation report, or both?
5. How should the adapter discover the local Archify path: config value, environment variable, CLI flag, or default search?
6. Where should draft questionnaire state live while the user is still reviewing seeded answers?
7. Which confidence threshold moves a seeded answer from `Needs confirmation` to `Ready for quick review`?

## Recommendation

Proceed to implementation planning for an ArtPkg-owned local intake UI with a narrow Package Readiness projection adapter. Keep the first slice practical: pre-artifacts Markdown in, seeded questionnaire draft plus review queues out, canonical ArtPkg validation preserved, Archify IR plus sidecar plus receipts generated for review. Defer any Archify-hosted merged interface until the ArtPkg-owned workflow proves it can carry a user through a full artifacts package lifecycle.
