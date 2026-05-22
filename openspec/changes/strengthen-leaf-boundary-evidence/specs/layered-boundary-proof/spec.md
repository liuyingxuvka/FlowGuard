## MODIFIED Requirements

### Requirement: Leaf Boundary Matrix

FlowGuard SHALL require each leaf model with finite real-code inputs and states
to provide a complete boundary matrix over `Input x State -> Set(Output x
State)`, including output, next state, state write, side-effect, and error-path
evidence.

#### Scenario: Leaf matrix is not the declared Cartesian product
- **WHEN** a leaf matrix declares finite input cases and state cases
- **THEN** the expected cell ids MUST match the full input/state Cartesian
  product
- **AND** missing or unexpected cells MUST block parent confidence

#### Scenario: Leaf omits required behavior
- **WHEN** a leaf cell observes fewer outputs, next states, state writes, side
  effects, or error paths than the cell declares
- **THEN** the layered proof report MUST block with a missing-behavior finding

#### Scenario: Leaf matrix cell uses internal-only evidence
- **WHEN** a leaf cell has current passing evidence but its assertion scope does
  not prove the external contract boundary
- **THEN** the layered proof report MUST block leaf confidence
