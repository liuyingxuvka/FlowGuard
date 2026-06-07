# flowguard-self-maintenance-mesh Specification

## Purpose
TBD - created by archiving change optimize-flowguard-self-maintenance. Update Purpose after archive.
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

