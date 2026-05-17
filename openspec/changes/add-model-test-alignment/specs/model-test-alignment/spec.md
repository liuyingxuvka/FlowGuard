## ADDED Requirements

### Requirement: Review model obligations against test evidence
FlowGuard SHALL provide a standalone model-test alignment helper that accepts explicit model obligations and plain test evidence, then reports whether every required model obligation has current acceptable test evidence.

#### Scenario: Complete alignment passes
- **WHEN** each required model obligation is referenced by at least one current passing test evidence item with an allowed test kind
- **THEN** the alignment report SHALL be OK and SHALL return `model_test_alignment_green` as the decision

#### Scenario: Missing test evidence blocks green
- **WHEN** a required model obligation has no current passing test evidence
- **THEN** the alignment report SHALL not be OK and SHALL include a `missing_test_evidence` finding for that obligation

### Requirement: Keep orphan and duplicate test claims visible
FlowGuard SHALL report tests that do not map to known model obligations and SHALL report duplicate ownership when multiple tests claim the same obligation unless sharing is explicitly allowed.

#### Scenario: Orphan test is reported
- **WHEN** a test evidence item does not reference any known model obligation
- **THEN** the alignment report SHALL include an `orphan_test_evidence` finding for that test

#### Scenario: Duplicate test ownership is reported
- **WHEN** more than one test evidence item claims the same obligation and the obligation does not allow shared evidence
- **THEN** the alignment report SHALL include a `duplicate_test_evidence_owner` finding

### Requirement: Preserve evidence freshness and result status
FlowGuard SHALL treat stale, skipped, failed, timeout, not-run, running, and error test evidence as visible gaps rather than passing coverage.

#### Scenario: Stale passing test is not current coverage
- **WHEN** a test evidence item passed but is marked not current
- **THEN** the alignment report SHALL include `stale_test_evidence` and SHALL not use it as current passing coverage

#### Scenario: Skipped test is not passing coverage
- **WHEN** a test evidence item is skipped, failed, timeout, not-run, running, or error
- **THEN** the alignment report SHALL include a non-passing evidence finding and SHALL not use it as current passing coverage

### Requirement: Flag missing risky path coverage
FlowGuard SHALL detect when a model obligation declares required test kinds and the bound test evidence only covers a subset, such as a happy path without a required failure, edge, replay, or negative path.

#### Scenario: Happy-path-only evidence is insufficient
- **WHEN** an obligation requires both `happy_path` and `failure_path` evidence but only `happy_path` evidence is current and passing
- **THEN** the alignment report SHALL include a `missing_required_test_kind` finding

### Requirement: Skill Kernel routes to model-test alignment independently
The model-first FlowGuard Skill Kernel SHALL expose `model_test_alignment` as a route that is independent of TestMesh, StructureMesh, and ModelMesh.

#### Scenario: Alignment route does not require mesh routes
- **WHEN** a project has a FlowGuard model and ordinary tests but no TestMesh, StructureMesh, or ModelMesh artifacts
- **THEN** the Skill Kernel documentation SHALL still allow `model_test_alignment` to be used
