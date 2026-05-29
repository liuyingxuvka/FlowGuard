# layered-boundary-proof Specification

## Purpose
TBD - created by archiving change add-layered-boundary-proof. Update Purpose after archive.
## Requirements
### Requirement: Parent Coverage
FlowGuard SHALL require a layered proof to identify every parent responsibility
that must be covered by a child model, parent-owned boundary, read-only item, or
explicit out-of-scope disposition.

#### Scenario: Parent responsibility has no owner
- **WHEN** a parent responsibility has no child owner, parent owner, read-only owner, or out-of-scope disposition
- **THEN** the layered proof report MUST block with a coverage-gap finding

#### Scenario: Parent responsibilities are fully covered
- **WHEN** every parent responsibility has an allowed owner or disposition
- **THEN** the parent coverage table MUST contribute no blocking findings

### Requirement: Child Disjointness
FlowGuard SHALL require child model responsibilities to be disjoint unless the
overlap is explicitly declared as an allowed shared kernel or bridge.

#### Scenario: Child models illegally overlap
- **WHEN** two child models own the same function, state field, side effect, invariant, risk class, or parent responsibility without an allowed overlap
- **THEN** the layered proof report MUST block with an illegal-overlap finding

#### Scenario: Shared kernel is declared
- **WHEN** two child models share a responsibility that is declared as an allowed shared kernel or bridge
- **THEN** the layered proof report MUST keep the overlap visible but MUST NOT block for that shared item

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

### Requirement: Evidence Status
FlowGuard SHALL treat skipped, stale, not-run, running, progress-only,
release-only, or hidden evidence as non-passing for layered proof unless the
claim is explicitly scoped to exclude that evidence.

#### Scenario: Background progress is present without exit artifacts
- **WHEN** a leaf or child proof references background progress without final exit/result artifacts
- **THEN** the layered proof report MUST block the proof as progress-only

#### Scenario: Release-only evidence is deferred
- **WHEN** routine confidence defers release-only evidence
- **THEN** the layered proof report MUST report scoped confidence and MUST NOT claim full routine-plus-release proof

### Requirement: Leaf boundary matrix can require runtime path evidence
Layered boundary proof SHALL allow leaf boundary matrix cells to bind expected
`Input x State -> Set(Output x State)` behavior to runtime node evidence ids.

#### Scenario: Leaf cell has runtime path evidence
- **WHEN** a leaf matrix cell declares required runtime node ids
- **AND** current passing runtime observations cover the cell's input case,
  state case, outputs, state writes, side effects, and error paths
- **THEN** layered boundary proof SHALL accept that runtime path evidence for
  the leaf cell

#### Scenario: Leaf cell lacks runtime path evidence
- **WHEN** a leaf matrix cell requires runtime node evidence
- **AND** a required node id has no current passing observation
- **THEN** layered boundary proof SHALL block parent confidence for that leaf
  cell

#### Scenario: Coarse leaf must split or scope
- **WHEN** a leaf model cannot produce finite runtime path evidence for every
  required input/state cell
- **THEN** layered boundary proof SHALL require a lower-level split or an
  explicit scoped exemption before parent confidence can be claimed
