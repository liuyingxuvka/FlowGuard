## ADDED Requirements

### Requirement: Immutable Evidence Receipt Schema
Every governance evidence receipt SHALL identify its schema, receipt id, subject id and kind, producer id and version, claim scope, exact command, tokenized working directory, start/end time, exit code, environment fingerprint, contract/check/suite hashes, input snapshots, proof result and fingerprint, covered obligations, required and consumed child receipts, skipped checks, blockers, and claim boundary.

#### Scenario: Required identity field is absent
- **WHEN** a receipt lacks its subject, producer, claim scope, or covered obligations
- **THEN** receipt validation fails and the receipt cannot support any parent claim

#### Scenario: Receipt is serialized twice
- **WHEN** the same receipt data is serialized twice
- **THEN** canonical serialization and result fingerprint are identical

### Requirement: Freshness Is Derived From Current Inputs
The system SHALL derive receipt freshness at read time by comparing declared current inputs, contract/check/suite hashes, producer version, environment policy, proof artifact fingerprint, and required child receipts. Callers MUST NOT supply an authoritative `current` value.

#### Scenario: Input file changes
- **WHEN** a required input snapshot no longer matches the current raw or required semantic hash
- **THEN** the receipt is classified stale with the changed artifact id

#### Scenario: Caller sets current true
- **WHEN** legacy input includes `current=true` but a required hash mismatches
- **THEN** the derived status remains stale and the caller flag is ignored or rejected

### Requirement: Exact Parent Child Consumption
A parent receipt SHALL satisfy a child obligation only when the exact required child receipt id is present in `consumed_child_receipts`, validates, is current, covers the required obligation, and has an eligible claim scope. A newer required child or changed child fingerprint MUST invalidate parent closure until re-consumed.

#### Scenario: Parent consumes old child
- **WHEN** a newer required child receipt exists but the parent names the prior receipt
- **THEN** parent freshness fails with a superseded-child finding

#### Scenario: Child was not consumed
- **WHEN** a current child exists but its id is absent from the parent consumed list
- **THEN** the parent obligation remains unsatisfied

### Requirement: Receipt Privacy And Storage Boundary
Receipts SHALL store hashes and allowlisted normalized environment metadata rather than raw private inputs or machine paths. Current repository evidence SHALL be stored under the configured `.flowguard/evidence` root or explicit output directory and MUST NOT be packaged as universally current installed-skill evidence.

#### Scenario: Absolute user path is emitted
- **WHEN** a command uses a workspace path containing a user profile
- **THEN** canonical receipt output contains a path token and no raw private user path
