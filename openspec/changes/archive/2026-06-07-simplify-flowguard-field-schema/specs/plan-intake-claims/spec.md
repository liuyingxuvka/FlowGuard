## ADDED Requirements

### Requirement: Plan Intake Uses One Evidence Id Shape
Plan Intake SHALL expose one canonical evidence id per mapping row and one
canonical source evidence id collection for completeness plans. It MUST NOT
expose singular/plural duplicates for the same relationship.

#### Scenario: Mapping evidence id
- **WHEN** an artifact maps to FlowGuard evidence
- **THEN** `EvidenceAdapterMapping` records the raw artifact id and one mapped
  evidence id

#### Scenario: Source evidence ids
- **WHEN** a completeness plan cites source evidence
- **THEN** it records source evidence ids without also requiring embedded source
  evidence objects for the same sources

### Requirement: Strict Adapter Fixture Fields Are Test-Owned
Plan Intake MUST keep known-bad fixture expectations in tests or dedicated
adapter conformance cases, not in normal mapping rows.

#### Scenario: Known-bad adapter fixture
- **WHEN** adapter rejection behavior must be proved
- **THEN** the proof is expressed as a test/conformance scenario rather than
  `known_bad_fixture` fields on normal mappings

## REMOVED Requirements

### Requirement: Duplicate Mapping Evidence Fields
**Reason**: `mapped_evidence_id` and `mapped_evidence_ids` encode the same
relationship and confuse agent-authored plans.

**Migration**: Use `mapped_evidence_id` for one mapping row per mapped evidence.
