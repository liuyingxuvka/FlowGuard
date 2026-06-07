## ADDED Requirements

### Requirement: Model-Test Alignment consumes field projections
Model-Test Alignment SHALL consume field lifecycle projections so
behavior-bearing field obligations bind the same model obligation, owner code
contract, and external-contract test evidence.

#### Scenario: Field projection is fully aligned
- **WHEN** a behavior-bearing field projection names a model obligation and
  owner code contract
- **AND** current passing external-contract test evidence covers the same
  obligation and code contract
- **THEN** Model-Test Alignment MAY count the field projection as covered

#### Scenario: Field code owner is missing
- **WHEN** a required field projection has no owner code contract
- **THEN** Model-Test Alignment MUST report a missing field code contract
  finding and MUST NOT return green alignment for that field obligation

#### Scenario: Field test proves only an internal helper
- **WHEN** test evidence covers a field projection only through an internal
  helper path and not the external contract boundary
- **THEN** Model-Test Alignment MUST keep the field obligation blocked or
  scoped according to the existing assertion-scope rules
