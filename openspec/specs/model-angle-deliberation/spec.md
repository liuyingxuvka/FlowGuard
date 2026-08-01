# model-angle-deliberation Specification

## Purpose
This capability defines FlowGuard's Model Angle Deliberation behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: Agents record open-ended model angle deliberation
FlowGuard SHALL provide a model-angle deliberation helper that records
free-form candidate model angles before an agent relies on one model for a
non-trivial or broad-confidence claim.

#### Scenario: Candidate angle is freely named
- **WHEN** an agent identifies a candidate model angle outside existing route names
- **THEN** the deliberation row MUST preserve the free-form angle name without requiring a fixed lens-type enum

#### Scenario: Current model limitation is explicit
- **WHEN** a deliberation row is reviewed
- **THEN** it MUST state what the current model sees, what it may miss, and what failure could be missed if the angle is ignored

### Requirement: Candidate model angles end in a disposition
Each model-angle deliberation row SHALL record a concrete disposition so the
agent cannot leave the angle as an unowned note.

#### Scenario: New or changed model is proposed
- **WHEN** a row chooses create-new-model, add-child-model, or extend-existing
- **THEN** the row MUST name a proposed model boundary or existing model target and a handoff route or open question

#### Scenario: Angle is scoped out or deferred
- **WHEN** a row chooses scope-out or defer
- **THEN** the row MUST include a reason that remains visible in the report

#### Scenario: Human review is required
- **WHEN** a row chooses needs-human-review
- **THEN** the review MUST keep the open question visible and prevent a full-confidence claim until it is resolved or scoped

### Requirement: Model angle deliberation is not validation evidence
FlowGuard SHALL treat model-angle deliberation as reasoning and routing
evidence, not proof that the owner route has passed.

#### Scenario: Owner route evidence is missing
- **WHEN** a deliberation row routes to an owner route but no current owner-route evidence is supplied
- **THEN** FlowGuard MUST keep the row unresolved or scoped instead of treating the deliberation as validation

### Requirement: Claimed angle resolution binds current owner evidence
Model Angle Deliberation SHALL treat `resolved` as a caller observation only and SHALL require current passing evidence from the declared owner route that covers the exact angle and current subject identity before the angle can stop blocking a required broad claim.

#### Scenario: Bare resolved flag is rejected
- **WHEN** a required current angle is marked resolved without current owner-route proof for that angle
- **THEN** the review MUST keep the angle unresolved or scoped and MUST NOT support full confidence

#### Scenario: Exact owner proof resolves the angle
- **WHEN** a required current angle is marked resolved and its current passing proof comes from the declared owner route, covers the angle obligation, and matches the current subject fingerprints
- **THEN** the review MAY treat the angle as resolved within the proof's declared boundary

### Requirement: Model angles contribute gaps to maturation
Model Angle Deliberation SHALL expose every unresolved, deferred, scoped, or stale required angle as a typed contribution to the task-local Model Maturation coverage universe.

#### Scenario: Unresolved angle cannot disappear from an empty caller signal list
- **WHEN** Model Angle Deliberation has an unresolved required angle and a caller supplies no matching maturation signal
- **THEN** the compiled maturation intake MUST still contain the angle coverage item and an open signal owned by the angle's declared route

