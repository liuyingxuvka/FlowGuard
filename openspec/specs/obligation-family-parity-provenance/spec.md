# obligation-family-parity-provenance Specification

## Purpose
TBD - created by archiving change add-obligation-family-parity-provenance. Update Purpose after archive.
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

