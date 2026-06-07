# transition-coverage-matrix Specification

## Purpose
TBD - created by archiving change enforce-default-three-way-binding. Update Purpose after archive.
## Requirements
### Requirement: Transition cells can bind code contracts

Transition coverage cells SHALL support direct code-contract and runtime-node
targets so state transitions can be locked to implementation and tests.

#### Scenario: Transition cell names code owner
- **WHEN** a transition coverage cell declares a code contract id
- **THEN** generated alignment evidence can verify that tests prove the code
  contract implementing the projected transition obligation.

#### Scenario: Transition cell lacks code owner in full confidence claim
- **WHEN** a required transition-derived obligation is reviewed for full
  confidence
- **AND** no code contract owner is bound to that transition obligation
- **THEN** Model-Test Alignment SHALL block or scope the claim.

### Requirement: Transition coverage matrix
FlowGuard SHALL provide a transition coverage matrix helper that represents modeled transition coverage as finite cells.

#### Scenario: Transition cell records model behavior
- **WHEN** a transition coverage cell is declared
- **THEN** it records source state, trigger, target state, optional expected output, optional function block, risk class, required test kinds, and a stable cell id

#### Scenario: Matrix groups transition cells
- **WHEN** a matrix is declared for a model boundary
- **THEN** it preserves matrix id, model id, source route, cells, and optional scoped-out cell ids with reasons

### Requirement: Transition coverage projects to model obligations
FlowGuard SHALL project transition coverage cells into Model-Test Alignment obligations.

#### Scenario: Cell becomes model obligation
- **WHEN** a transition coverage cell is projected
- **THEN** FlowGuard creates a required model obligation with type `transition_coverage`
- **AND** the generated obligation includes the cell trigger, source state, target state, expected output, and required test kinds

#### Scenario: Scoped-out cell is not silently required
- **WHEN** a matrix declares a cell as scoped out with a reason
- **THEN** the projection excludes that cell from required obligations
- **AND** the scoped-out reason remains available for reporting

### Requirement: Transition coverage projects to TestMesh leaf-cell requirements
FlowGuard SHALL project transition coverage matrices into required leaf-cell ids for TestMesh when validation is large, slow, layered, or child-owned.

#### Scenario: Required cell ids are generated
- **WHEN** a matrix has required cells
- **THEN** FlowGuard can return their cell ids as required TestMesh leaf-cell ids

#### Scenario: Scoped-out cell ids are excluded
- **WHEN** a matrix has scoped-out cells
- **THEN** the TestMesh projection does not require those cell ids

