## ADDED Requirements

### Requirement: Maintenance scan routes change signals to existing FlowGuard maintenance routes
FlowGuard SHALL provide a maintenance scan helper that consumes project-change signals and returns concrete maintenance actions that name existing FlowGuard route ids.

#### Scenario: Model code test mismatch requires alignment
- **WHEN** a scan includes changed model and code or test artifacts for a broad completion claim
- **THEN** the scan MUST return a required `model_test_alignment` action
- **AND** the action MUST explain that model/code/test evidence must be joined by the owning route before broad confidence

#### Scenario: Skipped candidate skill stays visible
- **WHEN** a scan includes a skipped candidate FlowGuard route with no accepted scope reason
- **THEN** the scan MUST return a required `agent_workflow_rehearsal` action
- **AND** the claim MUST remain blocked or scoped until the skipped-route consequence is resolved

### Requirement: Maintenance scan covers structure and reduction debt without replacing owning routes
The maintenance scan helper SHALL detect explicit signals for architecture reduction, code structure split, model mesh, and test mesh needs, then route them to the owning FlowGuard routes without performing the refactor or split itself.

#### Scenario: Reducible branch routes to architecture reduction
- **WHEN** a scan includes a reducible duplicate branch, pass-through adapter, removable state field, or duplicate validation signal
- **THEN** the scan MUST return an `architecture_reduction` action
- **AND** the action MUST not claim behavior-preserving deletion until the architecture reduction route supplies proof

#### Scenario: Split pressure routes to mesh routes
- **WHEN** a scan includes oversized model, stale child model evidence, large module, public API split, slow tests, progress-only tests, or broad validation signals
- **THEN** the scan MUST return the matching `model_mesh_maintenance`, `structure_mesh_maintenance`, or `test_mesh_maintenance` action
- **AND** the action MUST preserve the owner route as the place where split or parity evidence is proven

### Requirement: Maintenance scan preserves scoped claims and non-goals
The maintenance scan helper SHALL distinguish required, suggested, optional, scoped, and blocked outcomes without treating the scan itself as executable validation.

#### Scenario: No maintenance signal passes scan only
- **WHEN** a scan has no changed model/code/test/structure/evidence signals and no broad confidence claim
- **THEN** the scan MAY return `maintenance_scan_clear`
- **AND** the report MUST state that this is a scan result, not model/test/replay validation

#### Scenario: Missing required action scopes broad claim
- **WHEN** a broad done, release, publish, or production-confidence claim has at least one required maintenance action without current owner-route evidence
- **THEN** the scan MUST return a blocked or scoped decision instead of full maintenance confidence

### Requirement: Maintenance scan is available through API and template surfaces
FlowGuard SHALL expose the maintenance scan helper through the public helper API and provide a small template/CLI entry so projects can adapt it without copying large prompts.

#### Scenario: API exposes scan helper
- **WHEN** a user imports FlowGuard public helper APIs
- **THEN** maintenance scan row types and `review_maintenance_scan` MUST be available outside the core API

#### Scenario: Template demonstrates routing
- **WHEN** the maintenance scan template is printed or written
- **THEN** it MUST include a runnable example that shows clear, required alignment, and structure/reduction routing cases
