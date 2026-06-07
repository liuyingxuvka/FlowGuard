## ADDED Requirements

### Requirement: Self-maintenance invalidation tracking
DevelopmentProcessFlow SHALL track edits to route graph, field lifecycle rows, structure facades, tests, installed skills, OpenSpec artifacts, adoption logs, install state, shadow workspace state, and local git state as evidence-invalidating actions.

#### Scenario: Later write changes route graph
- **WHEN** a route graph or public API grouping changes after validation
- **THEN** DevelopmentProcessFlow SHALL require API surface, skill guidance, and affected route checks to be rerun before done confidence

#### Scenario: Background validation is running
- **WHEN** a long validation is still running in the background
- **THEN** DevelopmentProcessFlow SHALL treat it as liveness only, not pass evidence
