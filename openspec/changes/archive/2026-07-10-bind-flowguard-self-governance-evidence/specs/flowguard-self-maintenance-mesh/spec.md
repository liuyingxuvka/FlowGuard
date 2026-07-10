## ADDED Requirements

### Requirement: Parent Closure Consumes Real Child Receipts
Full self-maintenance closure SHALL require current receipts for suite inventory, SkillGuard deep contracts, behavior commitments, route topology, model-test alignment, TestMesh, model regression, installation/version state, and documentation/distribution gates. The parent model and runner MUST load and verify those receipts and MUST NOT manufacture passing child reports.

#### Scenario: SkillGuard child receipt is missing
- **WHEN** every child except SkillGuard deep certification has a current passing receipt
- **THEN** full self-maintenance remains blocked and identifies the missing child

#### Scenario: Runner constructs pass in memory
- **WHEN** a runner attempts to provide a child status without a verifiable receipt id and fingerprint
- **THEN** the parent rejects the child report as unbound evidence

### Requirement: Synthetic Evidence Transitions Are Forbidden
Self-maintenance state transitions MUST NOT set multiple evidence domains to current/pass without independently consumed receipts for each domain. Evidence booleans, if retained as view fields, SHALL be derived from verified receipt state.

#### Scenario: One action sets all evidence flags
- **WHEN** a transition attempts to set suite, ledger, DCAR, TestMesh, model-miss, and route evidence to true together without child receipts
- **THEN** model conformance or contract validation fails the transition

### Requirement: Full Governance Uses Exact Status Semantics
For full self-governance, every required child MUST be current and exact `pass`. `pass_with_gaps`, `scoped`, `stale`, `skipped`, `not_run`, `progress_only`, and `blocked` MUST remain visible and MUST NOT satisfy the parent full claim.

#### Scenario: Child passes with gaps
- **WHEN** the topology child reports `pass_with_gaps`
- **THEN** the parent reports an open topology gap and cannot emit full pass

#### Scenario: Scoped formal case meets expected boolean
- **WHEN** a scoped model case reports non-failing status but the parent claim is full
- **THEN** the formal summary does not promote it to full observed success

### Requirement: Three Layer Governance Status
Self-governance output SHALL separately report `engine_and_core_tests`, `skill_contract_governance`, and `full_self_governance`, with evidence, blockers, skipped checks, residual risk, and claim boundary for each layer.

#### Scenario: Engine passes and contracts fail
- **WHEN** core tests pass but any required skill deep contract fails
- **THEN** engine status is pass, skill contract governance is fail, and full self-governance is blocked
