## MODIFIED Requirements

### Requirement: Maturation compiles independent pre-code coverage intake
The maturation owner SHALL accept a current typed intake before or after
production implementation and SHALL derive the coverage universe from
independently identified task requirements, current-system ownership, typed
current-owner coverage items, and only the specialist routes triggered for the
task. The intake SHALL NOT require a separate open-ended model-angle inventory.

#### Scenario: Candidate cannot shrink the denominator
- **WHEN** a candidate model omits a task, current-system, behavior, field, UI,
  mesh, test, topology, boundary, finite-case, binding, or evidence coverage
  item supplied by a current independent owner contribution
- **THEN** maturation MUST keep that item open and MUST NOT report task-local
  full confidence

#### Scenario: Low-risk task stays narrow
- **WHEN** a task does not trigger a specialist route
- **THEN** the intake compiler MUST NOT require that route's unrelated
  inventory merely for ceremony

#### Scenario: Untyped concern has no current owner
- **WHEN** a suspected coverage concern cannot yet be assigned to a current
  owner and concrete coverage dimension
- **THEN** maturation MUST preserve an unknown-coverage item and route owner
  resolution through ExistingModelPreflight
- **AND** it MUST NOT create a free-form angle owner or count the concern as
  covered
