# maintenance-scan-router Specification

## Purpose
TBD - created by archiving change upgrade-ai-agent-route-handoffs. Update Purpose after archive.
## Requirements
### Requirement: Summary reports produce maintenance scan inputs
FlowGuard SHALL provide a helper that converts a `FlowGuardSummaryReport` and
optional project-change context into a `MaintenanceScanPlan` using existing
maintenance scan row types.

#### Scenario: Summary gap becomes scan signal
- **WHEN** a summary report contains a non-pass finding ledger entry with an
  owner route and claim impact
- **THEN** the helper SHALL create a maintenance scan signal or prior
  obligation that routes to the same existing owner route

#### Scenario: Clear summary does not invent work
- **WHEN** a summary report has no non-pass ledger entries and no supplied
  changed artifacts or prior obligations
- **THEN** the helper SHALL produce a scan plan that can review as clear

### Requirement: Maintenance actions expose AI next-route metadata
Maintenance scan actions SHALL include structured next-route metadata for AI
agents, including required input kinds, suggested commands, proof gap codes,
claim effect, and source obligation ids.

#### Scenario: Required route action is unresolved
- **WHEN** a required maintenance action has no current owner-route evidence
- **THEN** the action SHALL expose the missing proof/input metadata and remain
  unresolved

#### Scenario: Current owner evidence resolves action
- **WHEN** current passing evidence exists for the action's owner route
- **THEN** the action SHALL keep the owner evidence id and report the action as
  resolved without changing the route id

### Requirement: Maintenance scan remains a thin router
Maintenance scan SHALL NOT run tests, replay adapters, model splits, code
refactors, or specialist route internals when producing actions from summary
or project-change inputs.

#### Scenario: Scan routes but does not validate
- **WHEN** a scan action routes to Model-Test Alignment or DevelopmentProcessFlow
- **THEN** the scan result SHALL identify the owner route and SHALL NOT claim
  that the owner route has passed unless current owner-route evidence is
  attached

### Requirement: Maintenance scan routes model-angle gaps
Maintenance scan SHALL route unresolved model-angle gaps to existing owner
routes without validating those routes itself.

#### Scenario: Model-angle signal is unresolved
- **WHEN** a maintenance scan receives a model-angle gap signal
- **THEN** it MUST create a maintenance action for the supplied owner route or a conservative default owner route

#### Scenario: Owner route evidence is attached
- **WHEN** current owner-route evidence is attached to a model-angle action
- **THEN** the action MAY resolve while preserving the model-angle signal id and owner-route evidence id

### Requirement: Maintenance scan reopens touched obligations
Maintenance scan SHALL consume prior open maintenance obligations and route them
through existing owner routes when current work touches their anchors.

#### Scenario: Touched code path reopens structure obligation
- **WHEN** a maintenance scan includes a prior open obligation anchored to a
  code path, symbol, module, test surface, model id, or public entrypoint
- **AND** current changed artifacts touch that anchor
- **THEN** the scan MUST return a maintenance action for the obligation's owner
  route
- **AND** broad confidence MUST remain scoped or blocked until current
  owner-route evidence resolves the action

#### Scenario: Untouched obligation remains recorded
- **WHEN** a prior obligation is active but none of the current changed
  artifacts touch its anchors
- **THEN** the scan MAY keep the obligation visible in report metadata
- **AND** it MUST NOT force an unrelated owner-route action for the current
  narrow claim

### Requirement: Maintenance scan does not validate obligations
Maintenance scan SHALL treat reopened obligations as route actions, not as proof
that the underlying structure, model, or evidence risk has been resolved.

#### Scenario: Reopened obligation has current evidence
- **WHEN** a reopened obligation's owner route has current passing evidence
- **THEN** the scan MAY mark the corresponding maintenance action resolved
- **AND** the scan report MUST still identify the owner evidence used

#### Scenario: Reopened obligation lacks evidence
- **WHEN** a reopened obligation lacks current owner-route evidence
- **THEN** the scan MUST keep the action open
- **AND** it MUST NOT report full maintenance confidence for a broad claim

### Requirement: Maintenance scan routes topology hazard gaps

FlowGuard SHALL treat unresolved model-topology hazard review gaps as model
maturation or final-risk evidence signals after non-trivial FlowGuard-managed
project work.

#### Scenario: Topology hazard gap becomes required model maturation action

- **GIVEN** a maintenance scan receives
  `MAINTENANCE_SIGNAL_TOPOLOGY_HAZARD_GAP`
- **WHEN** `review_maintenance_scan(...)` runs
- **THEN** the scan MUST return a required `model_maturation_loop` action
- **AND** unresolved broad completion confidence MUST remain scoped or blocked
  until current owner-route evidence resolves the action.

### Requirement: Maintenance scan routes state closure gaps to model maturation

FlowGuard SHALL treat state/input closure confidence gaps as model maturation
signals after non-trivial FlowGuard-managed project work.

#### Scenario: Closure gap becomes required model maturation action

- **GIVEN** a maintenance scan receives `MAINTENANCE_SIGNAL_STATE_CLOSURE_GAP`
- **WHEN** `review_maintenance_scan(...)` runs
- **THEN** the scan MUST return a required `model_maturation_loop` action
- **AND** unresolved broad completion confidence MUST remain scoped or blocked
  until current owner-route evidence resolves the action.

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

