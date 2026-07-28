## ADDED Requirements

### Requirement: Obligation families prove expected member completeness
FlowGuard SHALL let an obligation family declare an expected member inventory independently from the materialized family-member rows, and SHALL reconcile the expected and materialized sets before granting family confidence.

#### Scenario: Expected member is omitted
- **WHEN** an expected family member has no materialized `ObligationFamilyMember` row and no explicit scoped exclusion
- **THEN** the family parity review SHALL report the missing expected member
- **AND** it SHALL NOT build a passing matrix from the smaller caller-supplied member set

#### Scenario: Unexpected member is materialized
- **WHEN** a family contains a materialized member that is absent from the expected inventory
- **THEN** the family parity review SHALL report the unexpected member
- **AND** the member SHALL remain visible until the expected inventory or the family boundary is corrected

#### Scenario: Scoped expected member remains visible
- **WHEN** an expected member is intentionally excluded with a reason, owner, validation boundary, and current evidence reference
- **THEN** the family parity report SHALL preserve the exclusion as scoped
- **AND** it SHALL NOT count the excluded member as current passing coverage

### Requirement: Family evidence binds the actual obligations owned by each member
FlowGuard SHALL require every accepted `ObligationFamilyEvidence.covered_obligations` entry to resolve to an obligation declared for the same family member and required mechanism.

#### Scenario: Evidence covers every required member obligation
- **WHEN** a required family member declares one or more obligation ids for a mechanism
- **AND** current passing evidence for that member and mechanism lists every required obligation id in `covered_obligations`
- **THEN** the family parity review MAY count that evidence for the corresponding member-mechanism cell

#### Scenario: Evidence names an unknown obligation
- **WHEN** a family evidence row lists a `covered_obligations` id that is not declared by its family member
- **THEN** the family parity review SHALL report an unknown or mismatched covered-obligation finding
- **AND** the evidence row SHALL NOT satisfy that member-mechanism cell

#### Scenario: Evidence covers only a sibling obligation
- **WHEN** evidence is attached to one family member but its `covered_obligations` resolve only to another member's obligations
- **THEN** the family parity review SHALL report a member-obligation binding mismatch
- **AND** it SHALL NOT promote sibling evidence to the uncovered member

#### Scenario: Required member obligation is only partially covered
- **WHEN** a required member has multiple obligations for a mechanism and current evidence covers only a subset
- **THEN** the family parity report SHALL expose the uncovered obligation ids
- **AND** full family confidence SHALL remain unavailable

### Requirement: Similarity-derived family provenance is materialized
FlowGuard SHALL require same-workflow, same-family, duplicate-boundary, or related model-similarity provenance used by an obligation family to materialize as concrete family members and obligation ids rather than remain only as opaque relation ids.

#### Scenario: Similarity relation materializes expected members
- **WHEN** a current similarity handoff identifies impacted models or same-intent sibling surfaces for a family-level claim
- **THEN** the family SHALL include the relevant similarity relation ids as provenance
- **AND** the impacted members and their required obligation ids SHALL appear in the expected and materialized member inventories

#### Scenario: Relation id has no materialized member
- **WHEN** an obligation family cites a similarity relation id but no expected member or member obligation represents one of the relation's in-scope sides
- **THEN** the family parity review SHALL report unmaterialized similarity provenance
- **AND** the relation id alone SHALL NOT support family completeness

#### Scenario: Similarity provenance is stale
- **WHEN** the similarity relation or impacted-model inventory changes after family members or evidence were produced
- **THEN** the family provenance SHALL be treated as stale
- **AND** current family confidence SHALL require regenerated member and obligation bindings
