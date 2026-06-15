## ADDED Requirements

### Requirement: ModelMesh closure projects to transition coverage
FlowGuard SHALL provide a helper that projects ModelMesh closure transitions
into finite transition coverage cells so parent/child handoffs become explicit
Model-Test Alignment and TestMesh obligations.

#### Scenario: Closure transition becomes transition cell
- **WHEN** a mesh closure model declares a transition
- **THEN** FlowGuard SHALL generate a transition coverage cell with stable cell
  id, source state from consumed tokens, trigger from the transition id, target
  state from emitted tokens, and any owner code or runtime node target supplied
  by the transition

#### Scenario: Rejection retry transition requires negative evidence
- **WHEN** a closure transition is loop-like or declares repeated input tokens
- **THEN** the generated transition coverage cell SHALL require happy-path,
  failure-path, negative-path, and replay test kinds

#### Scenario: Generated cells feed existing projections
- **WHEN** ModelMesh-derived transition coverage is generated
- **THEN** the existing projection helpers SHALL produce model obligations,
  code contracts, and TestMesh required leaf-cell ids from those cells
