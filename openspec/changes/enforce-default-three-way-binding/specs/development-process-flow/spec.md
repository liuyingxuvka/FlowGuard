## ADDED Requirements

### Requirement: Model-code-test changes stale linked evidence

DevelopmentProcessFlow SHALL treat model, code, and test edits as linked
invalidations for full confidence.

#### Scenario: One side of the binding changes
- **WHEN** a model obligation, code contract, code source, or test evidence row
  changes
- **THEN** previously claimed three-way binding evidence for the affected row
  becomes stale until the minimum revalidation plan refreshes it.
