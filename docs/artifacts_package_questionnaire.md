# Artifacts package questionnaire

This is a Python CLI for creating a bounded, evidence-grounded package from
the supplied template. It records answers with state and
provenance, validates traceability and authority boundaries, and never treats
generation as approval. Schema `0.2` adds optional Evidence-First SDLC Harness
pipeline state; schema `0.1` files migrate on load without losing IDs or
provenance.

The questionnaire CLI uses only the standard library. The v0.3 requirements
gateway in `tools/artpkg_v03.py` requires `jsonschema`; install it with
`python -m pip install -r requirements.txt`.

## Commands

```text
python tools/artifacts_package_questionnaire.py start --answers answers.json
python tools/artifacts_package_questionnaire.py resume --answers answers.json
python tools/artifacts_package_questionnaire.py validate --answers answers.json
python tools/artifacts_package_questionnaire.py generate --answers answers.json --yes
```

`--yes` is required when generation would overwrite any output. Commands in
answers are recorded only; they are not executed by the package generator.
The optional command runner rejects destructive commands and requires explicit
execution by its caller. Inspection is not performed by this implementation.

## Local intake UI

Use `intake-ui` for browser-assisted review of pre-artifacts input. The UI
creates a local intake session, shows review queues, and can generate an
Archify readiness projection for review. ArtPkg validation remains the only
package readiness calculation.

```text
python tools/artifacts_package_questionnaire.py intake-ui --workspace . --port 8765 --open
```

The UI is ArtPkg-owned. It does not grant approval, implementation authority,
execution authority, publication authority, deployment authority, or permission
to process sensitive content. Local sessions are written under `.artpkg/` and
are gitignored because they can contain project-specific or restricted
information.

The answer file is atomically replaced after each accepted answer. Repeated
records use stable IDs such as `ACT-001`, `FR-001`, and `EVD-001`; deleted IDs
are retained so later records are never renumbered. `UNKNOWN`, `NONE`, and
`NOT_APPLICABLE` remain distinct values/states.

## Terminal guidance and routing

Every terminal question includes a **What this question means** explanation
and a safe example. Repeated-record fields receive the same contextual help.
When a controlling answer makes a dependent question inapplicable, the CLI
skips it and retains a `DERIVED_BY_SCRIPT` / `NOT_APPLICABLE` record with the
reason. This reduces irrelevant prompts without inferring human authority,
approval, requirements, priorities, or risk acceptance.

Generation produces `artifacts_package_answers.json`,
`artifacts_package.md`, and `artifacts_package_validation.md`. The latter
contains errors, warnings, blocking IDs, and Gate A through Gate D results.
Restricted field names are redacted with a content-free reason code.

## Coverage and lifecycle contract

`coverage_matrix()` is the source-of-truth coverage matrix. Every repeated
record has explicit required, interactive, schema, rendered, and tested field
lists; no generic record fallback is used. The normalized answer file stores
the matrix under `record_field_coverage`.

Harness authority transitions are stored separately under
`harness.transitions` and are validated in order: BEC candidate, drafting
authorization, drafted, human acceptance, activation, implementation
authorization, execution authorization, verification, checkpoint acceptance,
and separately authorized advancement. Use `set_harness_transition()` for
machine-readable transition records; missing prerequisites or supporting
authority are blocking errors.

The validation report includes digests for the answer file and generated
package files, but intentionally excludes its own digest to avoid recursive
content. Unsupported schema versions are rejected; v0.1 files migrate
deterministically to v0.2.

## Harness mode

Set `HAR-000` to `YES` through the API or questionnaire to expose pipeline
state and generate `06-sdlc-harness-pipeline.md`. `NO` derives every Harness
answer as `NOT_APPLICABLE`. The implementation records repository metadata
through a fixed read-only Git allowlist only; it never invokes Gortex, performs
network access, or grants BEC, implementation, execution, acceptance, or
advancement authority.

## v0.3 requirements gateway contract

`tools/artpkg_v03.py` provides the ArtPkg-side contract for
`REQUIREMENT_INTAKE` and `EVIDENCE_ENRICHED_SCOPE`. The former is human
requirement authority with its own semantic revision/digest; the latter embeds
the exact approved authority snapshot and requires a separately supplied
current ArtPkg 1 intake for authority validation. `export_dwo()`
fails closed unless an intake is approved for discovery.

The validators return machine-readable dispositions including
`REQUIREMENT_INSUFFICIENT`, `STALE_REQUIREMENT_BINDING`, `SCOPE_NOT_APPROVED`,
and `IMPLEMENTATION_AUTHORITY_ABSENT`. These are ArtPkg contract results only;
Pipeline-A enforcement remains outside this repository.
