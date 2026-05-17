## ADDED Requirements

### Requirement: Structure partitions have explicit owners
FlowGuard SHALL allow projects to declare structure partition items for
functions, modules, state fields, config reads, side effects, entrypoints, and
behavior contracts, and SHALL assign each owning item to a parent, child,
read-only, or shared-kernel owner.

#### Scenario: Complete structure ownership
- **WHEN** every owning structure partition has a valid registered owner
- **THEN** StructureMesh reports no coverage-gap finding for that parent module

#### Scenario: Missing structure owner
- **WHEN** a structure partition item has no owner
- **THEN** StructureMesh reports a coverage-gap finding and does not return a
  green continue decision

### Requirement: Public entrypoints remain compatible
FlowGuard SHALL keep public entrypoint compatibility visible during
facade-first structure refactors.

#### Scenario: Removed public entrypoint
- **WHEN** a public CLI, API, or function entrypoint is removed without
  compatibility evidence
- **THEN** StructureMesh reports an entrypoint compatibility finding and blocks
  green confidence

#### Scenario: Facade retained
- **WHEN** the old parent facade remains available and behavior parity evidence
  is current
- **THEN** StructureMesh allows the facade to support routine confidence

### Requirement: Duplicate ownership is blocked
FlowGuard SHALL reject structure splits where sibling modules both own the same
state write, side effect, config default, or structure partition unless the
ownership is read-only or explicitly shared-kernel.

#### Scenario: Duplicate state owner
- **WHEN** two child modules both own the same state write
- **THEN** StructureMesh reports an ownership conflict and blocks green
  continuation

### Requirement: Dependency cycles and config drift remain visible
FlowGuard SHALL expose dependency cycles and configuration/default drift during
large-script decomposition.

#### Scenario: Dependency cycle introduced
- **WHEN** the refactor introduces a non-allowed dependency cycle
- **THEN** StructureMesh reports a dependency-cycle finding

#### Scenario: Config default drift
- **WHEN** a child module changes a config read, environment variable, path
  default, or default value without explicit parity evidence
- **THEN** StructureMesh reports a config-drift finding

### Requirement: Behavior parity evidence gates confidence
FlowGuard SHALL distinguish structure split intent from behavior preservation
evidence.

#### Scenario: Missing behavior parity evidence
- **WHEN** a child module is marked split complete but has no current parity
  evidence
- **THEN** StructureMesh reports missing parity evidence

### Requirement: Routine and release structure scopes are distinct
FlowGuard SHALL distinguish routine refactor confidence from release confidence
so release-required parity evidence remains visible before publishing.

#### Scenario: Routine scope with pending release-only parity
- **WHEN** routine validation is requested and release-only parity evidence is
  pending
- **THEN** StructureMesh may return routine green while reporting the release
  obligation as deferred

#### Scenario: Release scope with missing release parity
- **WHEN** release validation is requested and release-required parity evidence
  is not current
- **THEN** StructureMesh blocks release green confidence

## MODIFIED Requirements

### Requirement: model-first-function-flow routes structure decomposition
The `model-first-function-flow` Skill SHALL include a
`structure_mesh_maintenance` route for large-script, large-module,
facade-first, entrypoint-sensitive, ownership-sensitive, side-effect-sensitive,
or behavior-parity-sensitive refactors.

#### Scenario: Large script split
- **WHEN** an agent plans to split a large script into smaller modules while
  preserving behavior
- **THEN** the Skill routes through StructureMesh before broad completion or
  release confidence
