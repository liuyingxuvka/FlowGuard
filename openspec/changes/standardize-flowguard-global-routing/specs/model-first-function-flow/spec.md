## MODIFIED Requirements

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
