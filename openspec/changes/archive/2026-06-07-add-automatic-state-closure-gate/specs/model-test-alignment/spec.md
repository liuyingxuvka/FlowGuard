## ADDED Requirements

### Requirement: Model-test alignment treats unknown cases as boundary obligations

FlowGuard SHALL guide model-test alignment users to include representative
unknown/other cases when a model or code contract has an open external boundary.

#### Scenario: Unknown boundary cases are visible in alignment guidance

- **GIVEN** a model obligation or code boundary contract accepts finite inputs
- **WHEN** an outside-enumeration input may occur
- **THEN** model-test alignment guidance MUST ask for explicit unknown handling,
  boundary observations, tests, or a state closure report
- **AND** it MUST route unresolved unknown cases to model maturation rather than
  treating them as optional human review.
