## ADDED Requirements

### Requirement: Runtime gateway claims use structured writer inventory evidence
Runtime Gateway Adoption SHALL support structured writer inventory evidence and
SHALL require current passing structured inventory evidence for
`runtime_gateway` level claims that require complete inventory.

#### Scenario: Structured inventory is missing
- **WHEN** a plan claims `runtime_gateway`
- **AND** complete inventory is required
- **AND** no structured writer inventory evidence is supplied
- **THEN** the review SHALL report
  `missing_structured_writer_inventory_evidence`

#### Scenario: Structured inventory is stale or not passing
- **WHEN** structured writer inventory evidence exists
- **AND** it is stale or has a non-passing result status
- **THEN** Runtime Gateway Adoption SHALL reject it as complete inventory
  evidence

#### Scenario: Critical surface is not covered by inventory
- **WHEN** a critical state surface is declared
- **AND** no current passing structured inventory evidence covers that surface
- **THEN** the review SHALL report
  `writer_inventory_missing_critical_surface`

#### Scenario: Scoped writer has no reason
- **WHEN** a writer inventory evidence row scopes out a discovered writer
- **AND** it does not provide a reason for that scoped-out writer
- **THEN** the review SHALL report `writer_inventory_scoped_without_reason`

#### Scenario: Runtime inventory lacks proof artifact
- **WHEN** a runtime-gateway claim depends on structured writer inventory
- **AND** the inventory evidence has no proof artifact id
- **THEN** the review SHALL report
  `writer_inventory_missing_proof_artifact`
