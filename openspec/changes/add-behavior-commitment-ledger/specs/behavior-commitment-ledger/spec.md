## ADDED Requirements

### Requirement: Ledger records all in-scope behavior commitments
FlowGuard SHALL provide a Behavior Commitment Ledger that records every
in-scope external behavior promise for the selected project, work package, or
release boundary.

#### Scenario: Complete commitment is accepted
- **WHEN** a commitment names a stable id, label, actor, trigger, expected result, failure boundary, source refs, primary owner model id, validation boundary, and rationale
- **THEN** the ledger review SHALL treat the commitment as registered

#### Scenario: Missing commitment blocks full coverage
- **WHEN** an expected in-scope commitment id is absent from the ledger
- **THEN** the ledger review SHALL report `expected_commitment_missing`
- **AND** the report SHALL NOT support broad confidence

### Requirement: Source surfaces and commitments map both ways
FlowGuard SHALL require in-scope source surfaces to map to commitments and
in-scope commitments to trace back to source surfaces.

#### Scenario: Source surface has no commitment
- **WHEN** a public source surface is in scope and has no commitment ids
- **THEN** the ledger review SHALL report `source_surface_missing_commitment`

#### Scenario: Commitment has no source evidence
- **WHEN** a commitment is in scope and has no source refs
- **THEN** the ledger review SHALL report `commitment_missing_source_ref`

### Requirement: Each commitment has one primary owner model
FlowGuard SHALL require exactly one primary owner model for each in-scope
commitment and SHALL treat supporting or child models as subordinate coverage.

#### Scenario: Missing primary owner blocks
- **WHEN** an in-scope commitment has no primary owner model id
- **THEN** the ledger review SHALL report `commitment_missing_primary_owner`

#### Scenario: Primary owner overlaps supporting owner
- **WHEN** a commitment lists the same model as both primary and supporting or child
- **THEN** the ledger review SHALL report `primary_owner_also_supporting`

### Requirement: Dependencies remain explicit and closed
FlowGuard SHALL require commitment dependencies to refer to registered
commitments within the same ledger boundary unless they are explicitly
externalized.

#### Scenario: Unknown dependency blocks
- **WHEN** a commitment depends on an unknown commitment id
- **THEN** the ledger review SHALL report `commitment_dependency_unknown`

### Requirement: Scoped-out behavior remains accountable
FlowGuard SHALL require scoped-out, deferred, removed, or compatibility
behavior rows to record owner, reason, validation boundary, and rationale.

#### Scenario: Scoped-out row lacks reason
- **WHEN** a commitment or source surface is scoped out without reason, owner, validation boundary, or rationale
- **THEN** the ledger review SHALL report `scoped_out_behavior_missing_disposition`

### Requirement: Path-sensitive commitments consume Primary Path Authority
FlowGuard SHALL require each path-sensitive behavior commitment to carry
Primary Path Authority evidence and SHALL treat blocked PPA decisions as
blocked commitment coverage.

#### Scenario: Path-sensitive commitment lacks PPA evidence
- **WHEN** a commitment is marked `path_sensitive=true` and has no PPA report, decision, receipt, or risk gate id
- **THEN** the ledger review SHALL report `commitment_missing_primary_path_authority`

#### Scenario: PPA blocked result blocks commitment
- **WHEN** a path-sensitive commitment carries a blocked PPA decision
- **THEN** the ledger review SHALL report `commitment_primary_path_blocked`
- **AND** the report SHALL NOT support broad confidence

### Requirement: Ledger exposes downstream evidence ids
FlowGuard SHALL expose commitment coverage case ids, test shard ids, risk gate
ids, and PPA evidence ids so downstream routes consume the same boundary.

#### Scenario: Report includes downstream ids
- **WHEN** a ledger review includes registered commitments with evidence bindings
- **THEN** the report SHALL expose covered commitment ids, path-sensitive commitment ids, PPA-blocked commitment ids, and required risk gate ids

### Requirement: Ledger supports finite Cartesian coverage planning
FlowGuard SHALL provide canonical ContractExhaustionMesh axes and interaction
groups for behavior commitment coverage.

#### Scenario: Coverage universe includes PPA axis
- **WHEN** a ledger coverage plan is generated
- **THEN** the plan SHALL include source mapping, owner state, evidence state, dependency state, path sensitivity, PPA result, and release gate axes
