## ADDED Requirements

### Requirement: Self-maintenance preflight handoff
Existing model preflight SHALL feed the self-maintenance mesh before new FlowGuard route boundaries are added.

#### Scenario: Similar existing route exists
- **WHEN** the preflight finds a similar existing model, route, or maintenance group
- **THEN** it SHALL recommend reuse, extension, child model, or duplicate-boundary review before creating a new self-maintenance boundary
