## ADDED Requirements

### Requirement: WorkContext projects intent into exact target-system behaviors
Admitted WorkContext contributions SHALL retain their canonical model-intent identities and bind only to exact current-realization or future-target behavior rows. Blanket projection to every model or behavior in a target SHALL be rejected.

#### Scenario: Active proposal targets one future behavior
- **WHEN** an admitted proposal contribution names one future model obligation and has no accepted current-realization disposition
- **THEN** it SHALL remain a future-target intent binding for that obligation
- **AND** it SHALL NOT make any current behavior or blueprint layer complete

### Requirement: WorkContext remains provider-neutral
WorkContext SHALL accept declared planning and workflow material for software and non-software targets without assuming a source language. Its provider status SHALL remain context and freshness evidence only.

#### Scenario: Workflow specification supplies intended transitions
- **WHEN** a workflow WorkContext maps exact intended transitions to the target authority
- **THEN** the canonical intent inventory MAY preserve those mappings
- **AND** native model, behavior, test, and validation owners SHALL still decide current authority and completion
