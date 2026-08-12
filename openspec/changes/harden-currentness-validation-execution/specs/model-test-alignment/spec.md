## ADDED Requirements

### Requirement: Alignment projects only independently verified receipt evidence
Model-Test Alignment SHALL treat a test or TestMesh receipt as coverage only
after loading the immutable receipt and concrete result and independently
verifying its exact identity, subject, primary owner, claim scope, obligation
ids, model/code/test input identities, result fingerprint, terminal status,
and receipt-store supersession state. Alignment MUST preserve the verification
result identity in its binding row and MUST NOT promote caller, reuse-ticket,
proof-reference, or task-status currentness fields.

#### Scenario: Receipt exactly covers the alignment row
- **WHEN** the loaded receipt independently verifies for the same model
  obligation, primary code contract, test target, and current input identities
- **THEN** Model-Test Alignment MAY project that verified receipt into the row
  as current test evidence

#### Scenario: Receipt id is opaque or mismatched
- **WHEN** a row names a receipt id but cannot load and verify it, or the loaded
  receipt covers another subject, owner, obligation, or fingerprint
- **THEN** Model-Test Alignment MUST keep the row unproved and expose the exact
  mismatch

#### Scenario: A newer eligible receipt exists
- **WHEN** receipt-store verification determines that the aligned receipt has
  been superseded for the same evidence boundary
- **THEN** the row MUST be stale regardless of caller-supplied currentness

### Requirement: Payload alignment requires observed executable evidence
For every payload obligation in scope, Model-Test Alignment SHALL bind the
exact payload case id, model obligation, primary code contract, external test
target, executable implementation identity, loaded result artifact, observed
payload fingerprint, oracle result, and independently verified producer
receipt. Expected payloads, planned examples, and schema-only evidence MUST NOT
close executable alignment.

#### Scenario: Planned payload has no execution
- **WHEN** a plan contains an expected payload for an obligation but no verified
  executable receipt and observed result
- **THEN** Model-Test Alignment MUST report missing external executable evidence

#### Scenario: Payload receipt binds another implementation
- **WHEN** a passing payload receipt was produced by a callable or helper
  implementation identity different from the current primary code contract
- **THEN** Model-Test Alignment MUST classify the evidence as stale or
  mismatched and keep the obligation open

