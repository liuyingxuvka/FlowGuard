# model-first-function-flow Specification

## Purpose
TBD - created during OpenSpec archive normalization so historical FlowGuard
kernel deltas can be archived into a main spec.
## Requirements
### Requirement: model-first-function-flow exposes code structure recommendation
The `model-first-function-flow` Skill SHALL expose `code_structure_recommendation`
as a parallel route for direct code architecture recommendations and
model-derived implementation structure planning.

#### Scenario: Route is available
- **WHEN** the Skill route map is read
- **THEN** `code_structure_recommendation` is listed as a route beside
  `core_modeling`, `model_mesh_maintenance`, `test_mesh_maintenance`, and
  `structure_mesh_maintenance`

#### Scenario: Core modeling remains lightweight
- **WHEN** ordinary core modeling does not need implementation structure
  planning
- **THEN** the Skill does not require the code structure recommendation route

### Requirement: model-first-function-flow is a kernel, not the universal first stop
The `model-first-function-flow` Skill SHALL identify itself as the FlowGuard
kernel for general model-first applicability, ordinary behavior/state modeling,
unclear route selection, and cross-route coordination.

#### Scenario: Clear satellite match does not stop at kernel
- **WHEN** a task clearly matches a directly installed FlowGuard satellite
  skill
- **THEN** the kernel guidance says to use that satellite skill directly

#### Scenario: Kernel handles unclear or cross-route work
- **WHEN** the route is unclear, multiple FlowGuard routes may apply, or a core
  model is needed before selecting a narrower route
- **THEN** `model-first-function-flow` remains the appropriate starting point

### Requirement: model-first-function-flow routes staged development to DevelopmentProcessFlow
The `model-first-function-flow` Skill SHALL route non-trivial staged
development or modification tasks with validation to
`development_process_flow`, in addition to final done, archive, publish, and
release-readiness evidence checks.

#### Scenario: Kernel route map includes staged development
- **WHEN** the Skill Kernel route map is read
- **THEN** the `development_process_flow` trigger includes non-trivial staged
  development or modification, step ordering, touched artifacts, validation
  evidence, evidence freshness, peer writes, minimum revalidation, and V-style
  process confidence

#### Scenario: Kernel does not wait for final readiness
- **WHEN** the task has multiple meaningful development stages and validation
  but is not yet a release/archive/publish claim
- **THEN** the Skill Kernel guidance still routes the work to
  `development_process_flow`
