## ADDED Requirements

### Requirement: Combination cases bind model, code, and tests
Model-Test Alignment SHALL treat every required ContractExhaustionMesh
combination case as a model obligation that must bind to an owner code contract
and current external-contract test evidence before full semantic alignment.

#### Scenario: Combination case lacks code contract
- **WHEN** a required generated combination case is projected into
  Model-Test Alignment
- **AND** no owner code contract implements that case's model obligation
- **THEN** alignment reports a code-contract gap

#### Scenario: Combination case lacks external test evidence
- **WHEN** a required generated combination case has a model obligation and code
  contract
- **AND** no current external-contract test evidence covers the case id
- **THEN** alignment reports a missing combination-case test evidence gap

### Requirement: Test evidence must cite generated case ids
Model-Test Alignment SHALL not count a test as covering Cartesian coverage
unless the test evidence cites the generated combination case id or a current
TestMesh shard that owns that case id.

#### Scenario: Helper-only test is insufficient
- **WHEN** test evidence passes but covers only an internal helper path and not
  the generated combination case id or owner code contract
- **THEN** Model-Test Alignment blocks full combination-case alignment
