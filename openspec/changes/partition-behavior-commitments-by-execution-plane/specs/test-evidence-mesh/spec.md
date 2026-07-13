## ADDED Requirements

### Requirement: Plane-change validation has explicit owner receipts
The parent validation gate SHALL track focused schema/lookup tests, former-shape rejection tests, model regressions, skill/install parity, OpenSpec receipt consumption, and the one frozen full suite as explicit owner-receipt partitions. It SHALL NOT copy a native test command into a consumer or create an equivalent wrapper test.

#### Scenario: Focused receipts pass before the full gate
- **WHEN** focused plane owner receipts pass before source freeze
- **THEN** routine implementation MAY continue using those exact current receipts
- **AND** the full gate SHALL remain not-run until source/tool identities freeze

### Requirement: Native model regressions have one execution owner
Each native model regression SHALL retain its existing FlowGuard owner. SkillGuard/TestMesh MAY request a missing owner receipt and aggregate it, but SHALL NOT clone, wrap, or independently reschedule the native command.

#### Scenario: Consumer carries the owner command
- **WHEN** a receipt consumer or parent mesh declares the native command already owned by a child
- **THEN** contract validation SHALL fail before execution

#### Scenario: Functional input changes after an owner receipt
- **WHEN** an exact declared functional input changes
- **THEN** only the mapped owner receipt and its downstream aggregation SHALL become stale
- **AND** reports, receipts, logs, timestamps, installation bookkeeping, or task checkmarks SHALL NOT invalidate native test evidence

### Requirement: Installation parity is a distinct validation child
Canonical skill source, compiled contracts, and formal installed component projection SHALL have explicit parity evidence separate from skill source tests.

#### Scenario: Source skill passes but installed hash differs
- **WHEN** source checks pass and installed content differs from canonical content
- **THEN** the installation child SHALL fail or block parent completion

### Requirement: Parent completion consumes every required child
The parent plane-change validation gate SHALL read current passing evidence for every required child partition and SHALL preserve failures, timeouts, skips, not-run states, and stale results without reissuing equivalent child receipts.

#### Scenario: One affected model regression fails
- **WHEN** the full parent test command is green but an affected registered model child has a current failure
- **THEN** the parent SHALL remain blocked until the owning failure is repaired and rerun
