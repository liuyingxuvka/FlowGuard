## MODIFIED Requirements

### Requirement: Child Reattachment
FlowGuard SHALL require parent confidence to consume each child model's current
input, output, state, side-effect, evidence-id, and proof-artifact contract
before the parent can be green in strict closure mode.

#### Scenario: Parent consumes stale child evidence
- **WHEN** a parent reattachment record consumes an evidence id that does not
  match the current child evidence id
- **THEN** the layered proof report MUST block parent confidence as stale or
  not reattached

#### Scenario: Child proof artifact is missing in strict mode
- **WHEN** strict layered proof is required and a child has only a declared
  passing evidence status without a current proof artifact reference
- **THEN** the layered proof report SHALL block parent confidence as
  declaration-only child evidence

#### Scenario: Child output is outside parent handoff
- **WHEN** a child emits an output, state owner, side effect, or outgoing
  contract outside the parent reattachment allowance
- **THEN** the layered proof report MUST block with a reattachment finding

### Requirement: Leaf Boundary Matrix
FlowGuard SHALL require each leaf model with finite real-code inputs and states
to provide a complete boundary matrix over `Input x State -> Set(Output x
State)`, including output, next state, state write, side-effect, error-path,
evidence id, and proof artifact evidence.

#### Scenario: Leaf matrix cell is missing proof artifact
- **WHEN** strict layered proof is required and a leaf matrix cell has no
  current passing proof artifact
- **THEN** the layered proof report SHALL block leaf confidence with a
  declaration-only or missing-artifact finding

#### Scenario: Leaf emits forbidden behavior
- **WHEN** observed leaf behavior includes an output, next state, state write,
  side effect, or error path outside the declared cell allowance
- **THEN** the layered proof report MUST block with a boundary-overflow finding
