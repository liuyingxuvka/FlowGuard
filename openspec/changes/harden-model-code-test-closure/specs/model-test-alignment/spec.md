## ADDED Requirements

### Requirement: Source audit can gate real-code alignment
Model-Test Alignment SHALL let a plan require conservative Python source audit
evidence before a real-code model-code-test claim can become green.

#### Scenario: Missing required source audit blocks alignment
- **WHEN** a `ModelTestAlignmentPlan` sets `require_source_audit` to true
- **AND** no source audit report is attached
- **THEN** `review_model_test_alignment(...)` SHALL return a blocked report
- **AND** the findings SHALL include `missing_source_audit_report`

#### Scenario: Failed source audit blocks alignment
- **WHEN** a required source audit report is attached
- **AND** that report is not OK
- **THEN** `review_model_test_alignment(...)` SHALL include `source_audit_blocked`
- **AND** the final decision SHALL NOT be `model_test_alignment_green`

#### Scenario: Required source audit must cover plan contracts and tests
- **WHEN** source audit is required
- **AND** the attached green source audit does not cover a required code
  contract or test evidence row used by the plan
- **THEN** Model-Test Alignment SHALL report a source-audit coverage finding
  instead of treating the unrelated green report as closure

### Requirement: Binding rows summarize behavior closure
Model-Test Alignment SHALL produce binding rows that summarize each required
model obligation's closure chain across owner code, tests, boundary evidence,
runtime evidence, payload evidence, field projections, source audit, and open
gaps.

#### Scenario: Binding row includes owner path symbol and tests
- **WHEN** a model obligation has an owner code contract and current external
  test evidence
- **THEN** the binding row SHALL include the owner code contract id, code path,
  code symbol, and test evidence ids

#### Scenario: Binding row carries source audit and open gaps
- **WHEN** source audit is required or alignment findings remain open for an
  obligation
- **THEN** the binding row SHALL expose a source audit decision and open gap
  codes so an agent final claim can cite the row without hiding gaps

### Requirement: Counterexample and known-bad obligations close through target-aware code tests
Model-Test Alignment SHALL require model obligations that cite counterexample
or known-bad closure targets to close through current external test evidence
bound to the owner code contract and the same target id.

#### Scenario: Counterexample obligation lacks regression test
- **WHEN** a model obligation requires a `counterexample_regression` target id
- **AND** no current passing external test evidence is bound to the owner code
  contract and the same target id
- **THEN** the report SHALL include
  `missing_counterexample_regression_test`

#### Scenario: Known-bad obligation lacks replay test
- **WHEN** a model obligation requires a `known_bad_replay` target id
- **AND** no current passing external test evidence is bound to the owner code
  contract and the same target id
- **THEN** the report SHALL include `missing_known_bad_replay_test`

#### Scenario: Internal-path closure cannot close bad-trace target
- **WHEN** counterexample or known-bad closure evidence exists only as an
  internal-path assertion
- **THEN** Model-Test Alignment SHALL keep the obligation blocked until an
  external-contract or mixed assertion closes the target
