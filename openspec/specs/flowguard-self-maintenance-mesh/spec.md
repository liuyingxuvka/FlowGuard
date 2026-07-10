# flowguard-self-maintenance-mesh Specification

## Purpose
This capability defines how FlowGuard uses its own route, API, field, test, install, shadow, and git evidence to maintain FlowGuard itself without overclaiming completion.
## Requirements
### Requirement: Self-maintenance parent mesh
FlowGuard SHALL provide a parent self-maintenance model that coordinates route graph completeness, field layering, structure governance, validation evidence, install/shadow sync, and final closure evidence without replacing the specialist route checks.

#### Scenario: Child route evidence is current
- **WHEN** the self-maintenance mesh receives current child closure reports for route graph, fields, structure, validation, and closure
- **THEN** it SHALL allow a scoped self-maintenance confidence claim that names the covered routes and evidence artifacts

#### Scenario: Child route evidence is stale
- **WHEN** any child route report is stale, skipped, blocked, partial, or missing
- **THEN** the self-maintenance mesh SHALL downgrade the broad claim and emit the owning next action

### Requirement: Route graph completeness child
The self-maintenance mesh SHALL include a child check that compares installed route capabilities with AI-facing route discovery groups.

#### Scenario: Installed route is not discoverable
- **WHEN** an installed FlowGuard route has templates, helpers, skills, or docs but no compact route discovery group
- **THEN** the child check SHALL report a route graph gap with the expected group id and route owner

### Requirement: Field layering child
The self-maintenance mesh SHALL include a child check that classifies fields as core, route-owned, shared evidence, metadata/display, compatibility, removed, blocked, delegated, preserved, or out-of-scope.

#### Scenario: Compatibility field lacks disposition
- **WHEN** a field is old, replaced, aliased, fallback-like, or compatibility-like
- **THEN** the field layering child SHALL require an explicit disposition before broad confidence

### Requirement: AI journey simulation
The self-maintenance mesh SHALL simulate at least one AI maintenance journey from user intent to route selection, route-owned evidence, validation, and closure boundary.

#### Scenario: AI entry sees route-first path
- **WHEN** an AI needs to maintain fields, structure, tests, or route handoffs
- **THEN** the simulated journey SHALL reach a compact route profile before exposing the flat public helper surface

### Requirement: Self-maintenance default plan folds common fields
FlowGuard SHALL provide a public helper that builds the common
`SelfMaintenancePlan` from route profiles, public route API groups, AI entry
profiles, and field layer defaults while preserving explicit advanced plan
construction.

#### Scenario: Default plan is reviewable
- **WHEN** a caller provides only a plan id and current child closure reports
- **THEN** the helper returns a `SelfMaintenancePlan` that
  `review_flowguard_self_maintenance(...)` can validate without requiring the
  caller to manually fill the route graph fields

#### Scenario: Full fields remain available
- **WHEN** a specialist route needs to override route profiles, AI profiles,
  field layers, or API group ids
- **THEN** direct `SelfMaintenancePlan` construction remains supported

### Requirement: Self-maintenance scans runner entry evidence
The self-maintenance mesh SHALL include current self-model runner entry evidence
when it reviews fallback, direct-entry, compatibility, and prompt cleanup risk.

#### Scenario: Runner still uses direct Explorer
- **WHEN** a current `.flowguard` runner script calls `Explorer(...)` directly
- **THEN** self-maintenance evidence MUST classify the runner as a cleanup gap
  instead of treating the model as fully current

#### Scenario: Runner uses formal helper
- **WHEN** a current `.flowguard` runner script delegates through the formal
  workflow-suite helper and adoption audit reports no current direct Explorer
  runner warnings
- **THEN** self-maintenance evidence MAY treat the runner entry path as current
  for this maintenance claim

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

