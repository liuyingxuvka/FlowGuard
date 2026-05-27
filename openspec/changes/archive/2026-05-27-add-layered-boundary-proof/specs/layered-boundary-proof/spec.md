## ADDED Requirements

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
input, output, state, side-effect, and evidence-id contract before the parent
can be green.

#### Scenario: Parent consumes stale child evidence
- **WHEN** a parent reattachment record consumes an evidence id that does not match the current child evidence id
- **THEN** the layered proof report MUST block parent confidence as stale or not reattached

#### Scenario: Child output is outside parent handoff
- **WHEN** a child emits an output, state owner, side effect, or outgoing contract outside the parent reattachment allowance
- **THEN** the layered proof report MUST block with a reattachment finding

### Requirement: Leaf Boundary Matrix
FlowGuard SHALL require each leaf model with finite real-code inputs and states
to provide a complete boundary matrix over `Input x State -> Set(Output x
State)`, including output, next state, state write, side-effect, and error-path
evidence.

#### Scenario: Leaf matrix cell is missing
- **WHEN** a leaf model declares an input/state cell but does not provide current passing evidence for it
- **THEN** the layered proof report MUST block leaf confidence with a missing-cell finding

#### Scenario: Leaf matrix is too large
- **WHEN** a leaf model cannot provide finite complete boundary matrix evidence
- **THEN** the layered proof report MUST require further model split or an explicit scoped exemption before the leaf can support parent confidence

#### Scenario: Leaf emits forbidden behavior
- **WHEN** observed leaf behavior includes an output, next state, state write, side effect, or error path outside the declared cell allowance
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
