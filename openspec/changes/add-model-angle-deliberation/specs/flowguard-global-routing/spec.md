## ADDED Requirements

### Requirement: Global routing includes model-angle deliberation
FlowGuard global routing SHALL expose model-angle deliberation as a lightweight
preflight companion for open-ended model sufficiency review.

#### Scenario: Route is selected
- **WHEN** a task may need another model angle beyond the current model boundary
- **THEN** routing guidance MUST point to model-angle deliberation before or during existing-model preflight

#### Scenario: Specialist route owns follow-up
- **WHEN** deliberation chooses a model update, child model, code boundary, freshness review, or human review
- **THEN** routing guidance MUST hand off to the existing owner route rather than adding a parallel session runner
