## ADDED Requirements

### Requirement: Canonical-relation-derived family provenance is materialized
When an obligation-family claim uses a bounded same-intent, affected-sibling, shared-owner, shared-mechanism, adapter-only, duplicate-boundary, or false-friend relation, the family SHALL preserve the canonical relation id and source authority and materialize every in-scope endpoint as a concrete expected member and obligation id. Relation provenance alone SHALL NOT prove family completeness.

#### Scenario: Canonical relation materializes expected members
- **WHEN** a current canonical relation identifies in-scope endpoints for a family-level claim
- **THEN** the family includes the relation id as provenance
- **AND** every required endpoint and its concrete obligation id appears in the expected and materialized member inventories

#### Scenario: Relation endpoint has no materialized member
- **WHEN** a family cites a canonical relation but one in-scope endpoint has no expected member, member obligation, or explicit scoped disposition
- **THEN** family parity reports unmaterialized relation provenance
- **AND** the relation id alone MUST NOT support completeness

#### Scenario: Relation provenance is stale
- **WHEN** the relation source, endpoints, affected-member set, behavior plane, or currentness changes after family members or evidence were produced
- **THEN** family provenance and dependent evidence become stale until rebound to the current relation identity

## MODIFIED Requirements

### Requirement: Same-class bad cases can be derived from a seed miss
FlowGuard SHALL allow an observed family-member miss to produce a bounded seed naming the current family, source member, shared mechanism, failure mode, and required canonical relation endpoints. ContractExhaustionMesh SHALL derive and own the stable finite sibling case ids and executable oracles.

#### Scenario: Seed miss generates sibling cases
- **WHEN** a seed miss names a family, source member, mechanism, failure mode, and current canonical sibling endpoints
- **THEN** ContractExhaustionMesh derives finite same-class cases for the other required members
- **AND** each case records the source case id, sibling member, mechanism, failure mode, and canonical relation id

#### Scenario: Exempt members are not generated
- **WHEN** a sibling member is not required, is explicitly excluded, or lacks a current canonical relation to the failed mechanism
- **THEN** FlowGuard does not generate a required same-class case for that member
- **AND** it preserves any unresolved relation or scope gap without widening into a free-form scan

### Requirement: Family seeds feed canonical bad-case expansion
FlowGuard obligation-family parity MUST provide bounded observed-miss seeds to ContractExhaustionMesh when current family declarations and canonical relations require finite sibling bad-case expansion. The family route MUST NOT own a second case generator or accept caller-supplied related surfaces as authoritative expansion scope.

#### Scenario: Seed expands through contract exhaustion
- **WHEN** a family bad-case seed names a required mechanism and current canonical sibling endpoints
- **THEN** ContractExhaustionMesh generates or requires canonical ContractMutationCase rows for those finite sibling cases

#### Scenario: Unmodeled sibling relation remains a gap
- **WHEN** a same-class claim lacks a declared family member, mechanism, or current canonical relation
- **THEN** FlowGuard reports a model or relation gap instead of treating the family as exhausted or searching arbitrary related surfaces

## REMOVED Requirements

### Requirement: Analogous defect scans disposition same-shape risk radius
**Reason**: Caller-supplied related surfaces and open-ended scan radii have no canonical denominator and duplicate affected-topology plus ContractExhaustionMesh ownership.
**Migration**: Expand only finite endpoints established by current family declarations and canonical relation handoffs; preserve unknown relations as explicit gaps.

### Requirement: Similarity-derived family provenance is materialized
**Reason**: The family materialization protection remains, but standalone Model Similarity relations and maintenance groups are retired.
**Migration**: Preserve current canonical relation provenance and materialize every in-scope endpoint into concrete family members and obligation ids.
