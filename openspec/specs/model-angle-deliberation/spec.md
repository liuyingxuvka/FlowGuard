# model-angle-deliberation Specification

## Purpose
TBD - created by archiving change add-model-angle-deliberation. Update Purpose after archive.
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

