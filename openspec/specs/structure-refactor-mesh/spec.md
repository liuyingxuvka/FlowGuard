# structure-refactor-mesh Specification

## Purpose
TBD - created during OpenSpec archive normalization so historical
StructureMesh deltas can be archived into a main spec.
## Requirements
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

### Requirement: StructureMesh requires model-derived target split structure
FlowGuard SHALL require StructureMesh reviews for existing large-script or
large-module decomposition to include target child structure evidence derived
from a FlowGuard functional model before parent refactor confidence is claimed.

#### Scenario: Existing large script split has target structure evidence
- **WHEN** a StructureMesh plan reviews an existing large script split
- **THEN** the plan includes source model evidence, target child modules,
  FunctionBlock mapping, state-owner mapping, side-effect-owner mapping, facade
  plan, validation plan, and rationale

#### Scenario: Existing split lacks model-derived target structure
- **WHEN** a StructureMesh plan reviews an existing large script split without
  model-derived target structure evidence
- **THEN** StructureMesh reports a blocker and does not return a green continue
  decision

### Requirement: StructureMesh keeps its existing-code scope
StructureMesh SHALL remain scoped to existing large scripts, modules, packages,
commands, or API surfaces being decomposed, and SHALL NOT become the direct
entry point for no-code architecture planning.

#### Scenario: No-code architecture request
- **WHEN** a user asks for a structure recommendation before any code exists
- **THEN** the code structure recommendation route handles the request instead
  of StructureMesh

#### Scenario: Existing module decomposition
- **WHEN** an existing large module is being split
- **THEN** StructureMesh reviews the model-derived target split together with
  ownership, facade, dependency, config, and parity evidence

### Requirement: Target split derivation supports StructureMesh ownership review
Model-derived target split evidence SHALL be compatible with StructureMesh
partition ownership, module evidence, and public entrypoint evidence so the
target recommendation is reviewed rather than left as prose.

#### Scenario: Target recommendation enters the mesh
- **WHEN** a target structure recommendation exists for an existing split
- **THEN** StructureMesh consumes it as structured evidence and checks that its
  mappings align with partition owners and child modules

#### Scenario: Recommendation conflicts with ownership evidence
- **WHEN** the target recommendation assigns a state field or side effect to a
  different owner than the StructureMesh plan
- **THEN** StructureMesh reports a target ownership mismatch

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

### Requirement: Self-maintenance facade parity
Structure Refactor Mesh SHALL govern internal self-maintenance module splits through public entrypoint parity, facade preservation, ownership, and validation evidence.

#### Scenario: Oversized route module is split
- **WHEN** an oversized route module moves review internals into child helpers
- **THEN** the original public entrypoint SHALL remain available until parity evidence supports any contraction

