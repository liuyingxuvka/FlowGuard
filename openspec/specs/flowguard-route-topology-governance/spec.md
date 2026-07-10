# flowguard-route-topology-governance Specification

## Purpose

Define the typed ownership and liveness rules for FlowGuard route handoffs so every target resolves to one authority, every allowed cycle has bounded progress, and routing hazards produce deterministic blocking diagnostics.

## Requirements
### Requirement: Typed Route Handoffs
Every route handoff SHALL declare a `target_kind`, `target_id`, activation condition, and claim scope. Allowed target kinds MUST be `skill`, `internal_route`, `helper_api`, or `external_action`, and the target MUST resolve under the rules for its declared kind.

#### Scenario: Skill handoff resolves
- **WHEN** a handoff declares `target_kind=skill`
- **THEN** its target id resolves to exactly one member of the canonical FlowGuard suite inventory

#### Scenario: Internal route is mislabeled as a skill
- **WHEN** a kernel-owned internal route is declared with `target_kind=skill`
- **THEN** topology validation fails with a target-kind-mismatch diagnostic

#### Scenario: Target is dangling
- **WHEN** a handoff names an id that is absent from the appropriate target registry
- **THEN** topology validation fails and identifies the source route, target kind, and unresolved id

### Requirement: Unique Route Ownership
Every public-owner/direct route SHALL have exactly one canonical public skill owner. Every internal route SHALL have exactly one owner skill and one internal route id. Duplicate, missing, or contradictory ownership MUST block route closure.

#### Scenario: Public route has no owner
- **WHEN** a public-owner/direct profile omits `skill_name`
- **THEN** topology validation fails with a missing-public-owner diagnostic

#### Scenario: Route has two owners
- **WHEN** two skills claim primary ownership of the same public route id
- **THEN** topology validation fails with both claimants and no fallback owner is selected

### Requirement: Bounded Cycle Liveness
Every strongly connected route component SHALL declare a progress measure, an allowed evidence or state delta, terminal success and blocked conditions, and a finite re-entry bound. Re-entry without the declared delta MUST terminate as blocked at or before the bound.

#### Scenario: Rework loop makes progress
- **WHEN** a cycle re-enters with a new accepted evidence receipt that changes its progress measure
- **THEN** the cycle may continue within its declared bound

#### Scenario: Rework loop repeats unchanged
- **WHEN** a cycle re-enters with unchanged inputs and no allowed delta
- **THEN** liveness validation reaches the typed blocked terminal before exceeding the re-entry bound

#### Scenario: Cycle lacks a bound
- **WHEN** a strongly connected component has no finite re-entry or review bound
- **THEN** topology validation fails with an unbounded-cycle diagnostic

### Requirement: Deterministic Topology Diagnostics
Topology validation SHALL produce deterministic machine-readable findings for dangling targets, target-kind mismatch, missing/duplicate owners, unbounded cycles, absent terminals, and unchanged-loop progress. Findings SHALL include affected route ids and SHALL prevent broad routing confidence.

#### Scenario: Multiple hazards exist
- **WHEN** a graph contains both a dangling target and an unbounded cycle
- **THEN** the result reports both hazards in stable order and returns a failing status
