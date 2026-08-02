## ADDED Requirements

### Requirement: Implementation blueprint APIs belong to the existing kernel owner
Public implementation-inventory, model-binding, blueprint-qualification, and deterministic-projection APIs SHALL be registered as one cohort under the existing model-first kernel owner. They SHALL NOT create a new route, skill, mutable authority head, or compatibility alias.

#### Scenario: Blueprint API is registered as a new public route
- **WHEN** registry metadata assigns the blueprint cohort to a new route identity
- **THEN** public API topology validation fails

#### Scenario: Public import and registry differ
- **WHEN** a blueprint symbol is publicly importable but absent from its registered cohort, or the registry lists a missing symbol
- **THEN** API parity validation fails
