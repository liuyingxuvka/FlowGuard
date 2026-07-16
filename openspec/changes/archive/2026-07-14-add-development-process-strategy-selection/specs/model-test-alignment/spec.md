## ADDED Requirements

### Requirement: Strategy bindings resolve to model and code owners
Model-Test Alignment SHALL validate that every process strategy binding names existing failure-cluster or repair-batch ids, model obligation ids, and owner code-contract ids, and SHALL preserve missing bindings as blockers.

#### Scenario: Repair batch has no owner contract
- **WHEN** a strategy binding references an obligation but no owner code contract
- **THEN** Model-Test Alignment reports an incomplete strategy binding
