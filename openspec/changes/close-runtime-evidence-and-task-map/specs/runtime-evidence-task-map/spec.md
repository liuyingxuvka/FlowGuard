## Purpose

Provide an evidence-aware task map that lets an AI navigate from a changed path to the current model, contract, impact closure, validation owner, and explicit evidence gaps without creating a second authority.

## ADDED Requirements

### Requirement: Task map resolves a bounded current work context
The task-map route SHALL resolve a project root and changed path to selected code coordinates, accepted intent, typed impact paths, must-preserve contracts, validation owners, and explicit gaps using current authoritative objects.

#### Scenario: Changed leaf has current authority
- **WHEN** a caller supplies a valid root and changed path whose owner and accepted snapshot are current
- **THEN** the route returns the exact surface, symbol, source fingerprint, owner, intent source, contract members, impact reasons, and native validation selector

#### Scenario: Current authority is unavailable
- **WHEN** the changed path can be observed but no independently verified accepted snapshot or unique owner exists
- **THEN** the route returns observed structure and a typed `accepted_snapshot_unavailable` or `owner_ambiguous` gap without claiming currentness or launching a producer

### Requirement: Compact task maps preserve blockers and provenance
The compact task-map envelope SHALL be deterministic, bounded, paginable, and SHALL retain complete gap/blocker counts, denominator fingerprints, provenance, and continuation references when the body exceeds its size bound.

#### Scenario: Map exceeds the compact bound
- **WHEN** the task context has more entries than fit in the configured compact envelope
- **THEN** the route omits only stably ordered body entries, reports omitted counts and continuation references, and keeps every blocker and evidence status visible

#### Scenario: Read-only map request
- **WHEN** a caller requests a task map without an execution flag
- **THEN** no model/test producer, source write, installation write, or accepted-pointer activation occurs

### Requirement: Route cost and profile boundaries remain explicit
The task-map and route-selection surfaces SHALL distinguish `light`, `affected`, and `full` execution before any producer is started. A read-only map SHALL reuse one invocation-local currentness observation and SHALL NOT launch a producer, acquire a lease, create a run directory, or write authority/install state. An affected map SHALL use one typed impact closure and SHALL NOT add unrelated siblings through a second independent traversal. A full claim SHALL remain blocked until its declared source, owner, reverse-input, and external projection gates are frozen.

#### Scenario: Read-only route is requested with changed paths
- **WHEN** a caller asks to inspect a changed path without a typed write or qualification operation
- **THEN** the route remains `light`, reports the path as context or a bounded map input, and performs zero producer invocations

#### Scenario: Explicit profile conflicts with operation facts
- **WHEN** a caller requests `light` for a typed change or `full` for a typed read-only audit
- **THEN** the decision is blocked with a typed conflict and no producer is started; the route does not auto-upgrade or silently downgrade

#### Scenario: Partitioned composition lacks an independent coupling denominator
- **WHEN** a candidate claims full-equivalent coverage but its current boundary source, required interaction group, relation materialization, or interface/refinement evidence is missing or stale
- **THEN** the result remains scoped or blocked and cannot be promoted by a caller-supplied `verified`, `complete`, or `independent` flag
