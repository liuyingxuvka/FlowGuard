## ADDED Requirements

### Requirement: Strategy selection is exported through the existing process API group
The public API SHALL expose canonical strategy inputs, reports, cost comparison, and review functions through the existing DevelopmentProcessFlow group while keeping executable model helpers and internal routing private.

#### Scenario: API discovery
- **WHEN** a caller inspects the DevelopmentProcessFlow route API group
- **THEN** the canonical strategy-selection types and review function are discoverable without a new public route id
