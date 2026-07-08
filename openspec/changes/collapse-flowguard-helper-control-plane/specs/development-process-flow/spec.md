## ADDED Requirements

### Requirement: DevelopmentProcessFlow absorbs simulator and scan helpers
DevelopmentProcessFlow SHALL be the public owner for process simulation,
delegated process modes, post-change scan inputs, evidence freshness, install
sync, shadow sync, release, archive, publish, and final process claims.

#### Scenario: Process simulator helper is consumed
- **WHEN** `review_development_process_simulator()` is used
- **THEN** its evidence MUST be reported under the `development_process_flow`
  route id
- **AND** callers MUST NOT publish `development_process_simulator` as a separate
  direct route starter

#### Scenario: Maintenance scan is a process input
- **WHEN** changed artifacts, stale evidence, skipped routes, open obligations,
  or split/reduction signals are reviewed after work
- **THEN** DevelopmentProcessFlow MUST consume the scan as a post-change owner
  routing input
- **AND** the scan MUST NOT become the final confidence owner

### Requirement: Delegated process mode skills are owner-selected
DevelopmentProcessFlow SHALL select plan-detailing and agent-workflow mode
skills when those detailed reviews are required.

#### Scenario: Plan detailing is delegated
- **WHEN** DevelopmentProcessFlow selects `plan_detailing`
- **THEN** `flowguard-plan-detailing-compiler` MAY produce detailed rows
- **AND** final process confidence remains owned by DevelopmentProcessFlow

#### Scenario: Agent workflow is delegated
- **WHEN** DevelopmentProcessFlow selects `agent_workflow`
- **THEN** `flowguard-agent-workflow-rehearsal` MAY produce workflow evidence
- **AND** the delegated skill MUST NOT be a competing generic first stop
