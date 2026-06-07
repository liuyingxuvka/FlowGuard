## ADDED Requirements

### Requirement: Maintenance scan routes model-angle gaps
Maintenance scan SHALL route unresolved model-angle gaps to existing owner
routes without validating those routes itself.

#### Scenario: Model-angle signal is unresolved
- **WHEN** a maintenance scan receives a model-angle gap signal
- **THEN** it MUST create a maintenance action for the supplied owner route or a conservative default owner route

#### Scenario: Owner route evidence is attached
- **WHEN** current owner-route evidence is attached to a model-angle action
- **THEN** the action MAY resolve while preserving the model-angle signal id and owner-route evidence id
