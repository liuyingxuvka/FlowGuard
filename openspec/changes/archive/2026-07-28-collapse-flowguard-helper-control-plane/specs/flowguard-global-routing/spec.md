## ADDED Requirements

### Requirement: Global routing uses public owner routes
Global FlowGuard routing SHALL present only public owner routes as direct
AI-facing route choices.

#### Scenario: Helper is consumed through owner
- **WHEN** a task needs model-angle review, similarity review, post-change
  maintenance scanning, state closure, or guard-family closure support
- **THEN** global routing MUST route the task through the public owner route
  that consumes that helper
- **AND** it MUST NOT list the helper as a competing generic first stop

#### Scenario: Route table stays compact
- **WHEN** reusable AGENTS guidance or the model-first kernel route map is read
- **THEN** it MUST show owner routes for ordinary AI selection
- **AND** it MUST describe delegated modes and feeders inside the owning route
  wording rather than as peer public entries

### Requirement: DevelopmentProcessFlow is the process hot path
Global FlowGuard routing SHALL use `development_process_flow` as the direct
route id for rough-plan, multi-skill, staged execution, install, sync, release,
archive, publish, and final process claims.

#### Scenario: Simulator id is internal
- **WHEN** a task needs the development-process simulator
- **THEN** routing MUST select `development_process_flow`
- **AND** `development_process_simulator` MUST be treated as an internal helper
  or mode selector, not as a separate public route id

### Requirement: ExistingModelPreflight owns angle and similarity consumption
Global FlowGuard routing SHALL use ExistingModelPreflight as the owner route
for current-model sufficiency, angle, and similarity evidence before selecting
or creating a boundary.

#### Scenario: Similarity is needed
- **WHEN** a task resembles another workflow or model
- **THEN** global routing MUST put similarity evidence into
  ExistingModelPreflight or a downstream owner
- **AND** it MUST NOT select model similarity as a standalone first-stop route
