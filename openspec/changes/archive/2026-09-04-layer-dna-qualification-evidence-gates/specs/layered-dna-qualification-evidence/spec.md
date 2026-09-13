## Purpose

This capability makes provider-neutral DNA claims distinguish static model and
binding readiness from current, executed evidence, so a narrow static result
cannot be consumed as proof that the target has run successfully.

## ADDED Requirements

### Requirement: DNA qualification SHALL expose independent static and execution layers

The qualification result SHALL expose the existing static, semantic,
code-binding, and test-binding statuses together with an explicit execution
evidence status and fingerprint. The result SHALL expose a static-ready claim
separately from the broad qualified claim.

#### Scenario: Static bindings are ready but execution has not run
- **WHEN** all declared static, semantic, code, and test bindings are current but the canonical execution status is `not_run`
- **THEN** the result SHALL report static readiness, SHALL retain `execution_status=not_run`, and SHALL NOT report `qualified=true`

#### Scenario: Static and execution layers are both current
- **WHEN** every required binding is current, execution status is `passed`, and the execution evidence fingerprint is non-empty and current
- **THEN** the result SHALL report `qualified=true` and SHALL retain the exact execution evidence fingerprint

### Requirement: Broad DNA qualification SHALL fail closed on missing or non-current execution evidence

The broad qualified claim SHALL require a terminal passed execution status and
an exact current execution evidence fingerprint. Failed, blocked, stale,
skipped, running, incomplete, not-run, not-applicable, missing, or unknown
execution evidence SHALL be visible and SHALL prevent the broad claim.

#### Scenario: Execution status is passed but its evidence identity is missing
- **WHEN** all static bindings are current and the execution status is `passed` but no execution evidence fingerprint is supplied
- **THEN** the result SHALL downgrade the execution layer to a visible missing or incomplete state and SHALL NOT report `qualified=true`

#### Scenario: Execution evidence is stale or failed
- **WHEN** the execution evidence status is `stale`, `failed`, `blocked`, or another non-passed terminal state
- **THEN** the result SHALL preserve that status or its deterministic normalized equivalent and SHALL NOT report `qualified=true`

### Requirement: Readiness reviews SHALL remain non-executing and static claims SHALL remain usable

Readiness review SHALL consume already-owned execution evidence identities and
SHALL NOT launch providers, validators, target actions, or test processes.
Existing static blueprint and pre-code readiness reports SHALL remain usable
for their declared static claim boundary and SHALL not be relabeled as runtime
qualification.

#### Scenario: A caller requests a static readiness report only
- **WHEN** the caller supplies current static model, code, and test binding evidence without execution receipts
- **THEN** the static report SHALL retain its static-ready result and explicit static claim boundary
- **AND** the corresponding DNA qualification SHALL remain static-ready rather than broad-qualified

#### Scenario: A readiness result is serialized and reloaded
- **WHEN** a layered qualification result is serialized and loaded under the current schema
- **THEN** the execution status, static-ready state, broad-qualified state, fingerprints, and claim boundary SHALL round-trip exactly
