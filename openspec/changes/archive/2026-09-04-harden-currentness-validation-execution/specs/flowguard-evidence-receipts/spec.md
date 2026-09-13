## MODIFIED Requirements

### Requirement: Freshness Is Derived From Current Inputs
The system SHALL derive receipt freshness at read time from loaded current
functional inputs, contract/check/suite hashes, producer version, environment
policy, loaded proof-result fingerprint, and loaded required child receipts.
The verifier MUST resolve those values from their authoritative stores and
MUST NOT treat caller-supplied `current`, `matches`, `actual_fingerprint`, or
supersession values as authoritative.

#### Scenario: Input file changes
- **WHEN** a required input snapshot no longer matches the current raw or
  required semantic hash loaded by the verifier
- **THEN** the receipt is classified stale with the changed artifact id

#### Scenario: Caller sets current true
- **WHEN** legacy input includes `current=true` but a required hash mismatches
- **THEN** the derived status remains stale and the caller flag is ignored or
  rejected

#### Scenario: Caller supplies the expected value as actual
- **WHEN** a caller repeats an expected fingerprint in an
  `actual_fingerprint` or match field but the authoritative store differs
- **THEN** receipt verification MUST use the store value and fail freshness

### Requirement: Exact Parent Child Consumption
A parent receipt SHALL satisfy a child obligation only when the required child
mapping key, required receipt id, loaded child `receipt_id`, and independent
verification-result `receipt_id` are identical. The required subject and
loaded child subject MUST be identical; the child MUST cover the exact required
obligations and eligible claim scope; and the required, consumed, loaded, and
independently computed fingerprints MUST agree. The receipt store SHALL derive
whether a newer eligible child supersedes the consumed child. Caller-provided
aliases, match flags, or supersession hints MUST NOT authorize parent closure.

#### Scenario: Parent consumes old child
- **WHEN** the receipt store contains a newer eligible child for the same
  subject, producer, scope, and obligation boundary but the parent names the
  prior receipt
- **THEN** parent freshness fails with a superseded-child finding

#### Scenario: Child was not consumed
- **WHEN** a current child exists but its id is absent from the parent consumed
  list
- **THEN** the parent obligation remains unsatisfied

#### Scenario: Mapping key aliases another receipt
- **WHEN** the child mapping key names the required receipt but the loaded
  receipt or verification result has a different `receipt_id`
- **THEN** exact child verification MUST fail

#### Scenario: Child subject or fingerprint differs
- **WHEN** the loaded child subject or independently computed result
  fingerprint differs from the frozen requirement
- **THEN** the parent MUST reject the child even if its terminal status passes

