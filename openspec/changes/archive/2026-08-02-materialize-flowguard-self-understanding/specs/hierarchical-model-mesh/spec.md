## ADDED Requirements

### Requirement: Self topology records semantic model relationships
The FlowGuard self topology SHALL record affected parent/child, refinement, sibling-impact, and consumer relationships between models rather than representing the model set only as a flat inventory.

#### Scenario: Child behavior changes
- **WHEN** an affected child model changes an obligation consumed by a parent or sibling
- **THEN** the topology identifies the dependent relationship and its freshness impact
