# obligation-family-parity-provenance Specification

## Purpose
This capability defines FlowGuard's Obligation Family Parity Provenance behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: Obligation families declare sibling mechanisms

FlowGuard SHALL provide a helper for declaring same-class obligation families whose members are expected to share one or more mechanisms unless a member has an explicit exception.

#### Scenario: Complete family declaration
- **WHEN** a family lists required members and required mechanism ids
- **THEN** FlowGuard records the family id, member ids, mechanism ids, and allowed provenance values
- **AND** the review can build a member-by-mechanism coverage matrix.

#### Scenario: Exempt member stays scoped
- **WHEN** a family member is not required and carries an exception reason
- **THEN** FlowGuard does not require mechanism evidence for that member
- **AND** the exception remains visible in the coverage matrix.

### Requirement: Family parity requires current evidence for each required cell

FlowGuard SHALL block a family-wide confidence claim when any required member lacks current passing evidence for any required mechanism.

#### Scenario: Missing sibling evidence blocks
- **WHEN** one family member has current evidence for a mechanism
- **AND** another required member in the same family has no evidence for that mechanism
- **THEN** the family parity report is not OK
- **AND** it reports the missing member and mechanism.

#### Scenario: Full matrix passes
- **WHEN** every required member has current passing evidence for every required mechanism
- **AND** each evidence row has acceptable provenance
- **THEN** the family parity report is OK with full confidence.

### Requirement: Evidence provenance is checked before accepting coverage

FlowGuard SHALL distinguish how evidence was produced before accepting it for a required mechanism.

#### Scenario: Manual event does not prove durable reconciliation
- **WHEN** a family requires durable reconciliation provenance
- **AND** the only evidence for a member is manual event or test-injected evidence
- **THEN** FlowGuard reports an invalid provenance finding
- **AND** the family parity report is blocked.

#### Scenario: Runtime observed evidence can satisfy a runtime-observed mechanism
- **WHEN** a family accepts runtime-observed provenance
- **AND** a current passing evidence row uses that provenance
- **THEN** FlowGuard may count the row as coverage for that member and mechanism.

### Requirement: Same-class bad cases can be derived from a seed miss

FlowGuard SHALL provide a helper that turns an observed family-member miss into sibling same-class bad cases for the remaining required members.

#### Scenario: Seed miss generates sibling cases
- **WHEN** a seed miss names a family, source member, mechanism, and failure mode
- **THEN** FlowGuard derives same-class bad cases for the other required family members
- **AND** each case records the source case id, sibling member, mechanism, and failure mode.

#### Scenario: Exempt members are not generated
- **WHEN** a seed miss is expanded
- **AND** a sibling member is not required or is explicitly excluded
- **THEN** FlowGuard does not generate a required same-class bad case for that member.

### Requirement: Analogous defect scans disposition same-shape risk radius

FlowGuard SHALL provide a helper that turns an observed miss into an analogous defect scan over same-family siblings and caller-supplied related surfaces.

#### Scenario: Unreviewed mandatory sibling blocks closure
- **WHEN** an observed miss seed has a required sibling member sharing the failed mechanism
- **AND** no disposition has been recorded for that sibling candidate
- **THEN** the analogous defect scan reports a blocker
- **AND** broad model-miss closure remains unavailable.

#### Scenario: Covered sibling can close with evidence
- **WHEN** a mandatory sibling candidate is marked covered by current evidence
- **AND** the candidate names at least one evidence id
- **THEN** the analogous defect scan can treat that candidate as dispositioned.

#### Scenario: Wider-radius surfaces can be scoped
- **WHEN** a related but non-identical surface is marked `should_scan` or `record_only`
- **AND** it is assigned to a separate change or excluded with a concrete reason
- **THEN** FlowGuard keeps the scope visible without requiring the current repair to edit that surface.

### Requirement: Family confidence is scoped to matrix coverage

FlowGuard SHALL make the family confidence boundary explicit so downstream routes cannot promote one-member evidence to a family-wide claim.

#### Scenario: Partial family evidence is scoped or blocked
- **WHEN** family evidence covers only a subset of required members
- **THEN** FlowGuard does not report full confidence for the family
- **AND** the report names the uncovered cells.

#### Scenario: Family report exposes coverage matrix
- **WHEN** a family parity report is produced
- **THEN** it includes one coverage cell per required member and mechanism, with status and evidence ids.

### Requirement: Family seeds feed canonical bad-case expansion
FlowGuard obligation-family parity MUST provide same-class family seeds to
ContractExhaustionMesh when an observed miss or family mechanism requires
canonical sibling bad-case expansion.

#### Scenario: Seed expands through contract exhaustion
- **WHEN** a family bad-case seed names a required mechanism and sibling
  members
- **THEN** canonical ContractMutationCase rows are generated or required for
  the sibling cases

#### Scenario: Unmodeled sibling relation remains a gap
- **WHEN** a same-class claim lacks a declared sibling relation or mechanism
- **THEN** FlowGuard reports a model gap instead of treating the family as
  exhausted

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

