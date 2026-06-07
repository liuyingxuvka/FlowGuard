## ADDED Requirements

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
