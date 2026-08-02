## ADDED Requirements

### Requirement: Whole-flow claims require semantic disposition of every current model
For a whole-flow claim, the system SHALL bind every current model to a semantic disposition of connected, intentional-leaf, delegated-or-supporting, or explicitly scoped-out, with a rationale and current consumer relationship where applicable. Raw model count SHALL NOT activate or satisfy ModelMesh review.

#### Scenario: Inventory is complete but one model has no semantic disposition
- **WHEN** every current model is listed but one model lacks a semantic disposition and rationale
- **THEN** the whole-flow mesh is incomplete

#### Scenario: Model count crosses a threshold
- **WHEN** the number of models changes without any semantic topology change
- **THEN** the count alone neither activates nor satisfies ModelMesh review
