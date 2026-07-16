## ADDED Requirements

### Requirement: Portable Verification API Cohort
The public API registry SHALL expose the portable schema, canonical identity, interpreter, model checker, refinement checker, and composition checker as one versioned ownership cohort.

#### Scenario: Public API cohort is complete
- **WHEN** a supported portable verification symbol is exported
- **THEN** it is present in the registry, import facade, documentation, and API parity tests

#### Scenario: Internal helper remains private
- **WHEN** an implementation helper is not part of the declared cohort
- **THEN** it is absent from the public registry and package facade
