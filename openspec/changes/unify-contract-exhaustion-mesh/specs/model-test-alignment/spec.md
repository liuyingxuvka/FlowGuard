## ADDED Requirements

### Requirement: Alignment consumes contract-exhaustion case ids
FlowGuard Model-Test Alignment MUST be able to bind model obligations, owner
code contracts, and test evidence to canonical contract-exhaustion case ids.

#### Scenario: Same-class test binds canonical case
- **WHEN** a same-class generalized test is required for a model-miss repair
- **THEN** the test evidence records the canonical ContractMutationCase id it
  covers

#### Scenario: Payload evidence binds canonical case
- **WHEN** payload validation evidence covers a generated contract-exhaustion
  payload mutation
- **THEN** Model-Test Alignment can compare the evidence against the payload
  contract and canonical case id

#### Scenario: Missing canonical case blocks coverage
- **WHEN** a required contract-exhaustion case exists but no current aligned
  test evidence covers it
- **THEN** Model-Test Alignment reports the coverage gap
