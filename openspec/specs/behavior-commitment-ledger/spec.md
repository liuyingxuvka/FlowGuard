# behavior-commitment-ledger Specification

## Purpose
Define the canonical external-promise ledger, source coverage, single-owner accounting, typed behavior-plane relationships, and path-authority handoff required for broad confidence.
## Requirements
### Requirement: Ledger records all in-scope behavior commitments
FlowGuard SHALL provide a Behavior Commitment Ledger that records every
in-scope external behavior promise for the selected project, work package, or
release boundary.

#### Scenario: Complete commitment is accepted
- **WHEN** a commitment names a stable id, label, actor, trigger, expected result, failure boundary, source refs, primary owner model id, validation boundary, and rationale
- **THEN** the ledger review SHALL treat the commitment as registered

#### Scenario: Missing commitment blocks full coverage
- **WHEN** an expected in-scope commitment id is absent from the ledger
- **THEN** the ledger review SHALL report `expected_commitment_missing`
- **AND** the report SHALL NOT support broad confidence

### Requirement: Source surfaces and commitments map both ways
FlowGuard SHALL require in-scope source surfaces to map to commitments and
in-scope commitments to trace back to source surfaces.

#### Scenario: Source surface has no commitment
- **WHEN** a public source surface is in scope and has no commitment ids
- **THEN** the ledger review SHALL report `source_surface_missing_commitment`

#### Scenario: Commitment has no source evidence
- **WHEN** a commitment is in scope and has no source refs
- **THEN** the ledger review SHALL report `commitment_missing_source_ref`

### Requirement: Each commitment has one primary owner model
FlowGuard SHALL require exactly one primary owner model for each in-scope
commitment and SHALL treat supporting or child models as subordinate coverage.

#### Scenario: Missing primary owner blocks
- **WHEN** an in-scope commitment has no primary owner model id
- **THEN** the ledger review SHALL report `commitment_missing_primary_owner`

#### Scenario: Primary owner overlaps supporting owner
- **WHEN** a commitment lists the same model as both primary and supporting or child
- **THEN** the ledger review SHALL report `primary_owner_also_supporting`

### Requirement: Dependencies remain explicit and closed
FlowGuard SHALL require commitment dependencies to refer to registered
commitments within the same ledger boundary unless they are explicitly
externalized.

#### Scenario: Unknown dependency blocks
- **WHEN** a commitment depends on an unknown commitment id
- **THEN** the ledger review SHALL report `commitment_dependency_unknown`

### Requirement: Scoped-out behavior remains accountable
FlowGuard SHALL require scoped-out, deferred, removed, deprecated, or replaced
behavior rows to record owner, reason, validation boundary, and rationale.

#### Scenario: Scoped-out row lacks reason
- **WHEN** a commitment or source surface is scoped out without reason, owner, validation boundary, or rationale
- **THEN** the ledger review SHALL report `scoped_out_behavior_missing_disposition`

### Requirement: Path-sensitive commitments consume Primary Path Authority
FlowGuard SHALL require each path-sensitive behavior commitment to carry
Primary Path Authority evidence and SHALL treat blocked PPA decisions as
blocked commitment coverage.

#### Scenario: Path-sensitive commitment lacks PPA evidence
- **WHEN** a commitment is marked `path_sensitive=true` and has no PPA report, decision, receipt, or risk gate id
- **THEN** the ledger review SHALL report `commitment_missing_primary_path_authority`

#### Scenario: PPA blocked result blocks commitment
- **WHEN** a path-sensitive commitment carries a blocked PPA decision
- **THEN** the ledger review SHALL report `commitment_primary_path_blocked`
- **AND** the report SHALL NOT support broad confidence

### Requirement: Ledger exposes downstream evidence ids
FlowGuard SHALL expose commitment coverage case ids, test shard ids, risk gate
ids, and PPA evidence ids so downstream routes consume the same boundary.

#### Scenario: Report includes downstream ids
- **WHEN** a ledger review includes registered commitments with evidence bindings
- **THEN** the report SHALL expose covered commitment ids, path-sensitive commitment ids, PPA-blocked commitment ids, and required risk gate ids

### Requirement: Ledger supports finite Cartesian coverage planning
FlowGuard SHALL provide canonical ContractExhaustionMesh axes and interaction
groups for behavior commitment coverage.

#### Scenario: Coverage universe includes PPA axis
- **WHEN** a ledger coverage plan is generated
- **THEN** the plan SHALL include source mapping, owner state, evidence state, dependency state, path sensitivity, PPA result, and release gate axes

### Requirement: Ledger classifies behavior change mode
FlowGuard SHALL classify behavior-ledger work as bootstrap, add, change,
remove/replace, historical gap backfill, or model-miss check before broad
behavior claims.

#### Scenario: Unknown change mode blocks
- **WHEN** a ledger carries an unknown change mode
- **THEN** the ledger review SHALL report `ledger_unknown_change_mode`

### Requirement: Source freshness blocks stale broad claims
FlowGuard SHALL require in-scope behavior source surfaces to be current before
broad behavior confidence.

#### Scenario: Source changed after ledger review
- **WHEN** an in-scope source surface is marked changed, missing, or unchecked
- **THEN** the ledger review SHALL report `source_surface_freshness_not_current`

### Requirement: Replaced behavior has no alternate success surface
FlowGuard SHALL require replaced or removed behavior to be explicitly disposed
instead of preserved as an alternate successful path.

#### Scenario: Replaced behavior lacks replacement disposition
- **WHEN** a commitment is marked replaced without a replacement commitment id or excluded behavior ids
- **THEN** the ledger review SHALL report `commitment_replacement_disposition_missing`

### Requirement: Model miss backfeed checks existing commitments first
FlowGuard SHALL treat model misses as a backfeed check against existing
commitments and SHALL only backfill a commitment when no existing commitment
covers the observed external behavior.

#### Scenario: Model miss backfeed lacks current owner or DCAR coverage
- **WHEN** a commitment records a model miss origin without current model-sync and coverage-case evidence
- **THEN** the ledger review SHALL report `commitment_model_miss_backfeed_incomplete`

### Requirement: Process strategy selection has one development-process commitment
The Behavior Commitment Ledger SHALL preserve exactly one `development_process` commitment, intent id, and executable child-model owner for conditional process optimization. Its precondition SHALL be an explicit optimization request, multiple outcome-equivalent viable routes, material repeated-work risk, or a real diagnostic-boundary choice. Its expected result SHALL be one evidence-grounded diagnostic boundary and execution mode, visible hard blockers/not-run work, traceable repair groups, affected revalidation, and material-change freshness; DPF/API/agent guidance SHALL remain typed source surfaces of this one commitment without merging product or agent-operation ownership.

#### Scenario: Public DPF guidance references optimization
- **WHEN** DPF skill guidance promises conditional process optimization
- **THEN** its source surface maps to the existing single commitment and not to a new or duplicate commitment

#### Scenario: Ordinary lifecycle work has no optimizer precondition
- **WHEN** a non-trivial task has one clear route and no material optimization reason
- **THEN** the commitment remains registered but is not activated for that plan

### Requirement: Active commitments bind exact observed model instances
Every in-scope active behavior commitment SHALL resolve to exactly one primary
model instance in the observed-head snapshot. Supporting and child owners SHALL
also use immutable instance references.

#### Scenario: Owner model artifact changes
- **WHEN** a commitment names a logical model id whose artifact or purpose fingerprint no longer matches the observed snapshot member
- **THEN** the commitment is stale and cannot satisfy current behavior coverage

### Requirement: Replaced and retired commitments do not rank as current
Behavior commitment lookup SHALL exclude replaced and retired commitments from
primary current results while preserving them as historical context.

#### Scenario: Retired commitment text matches exactly
- **WHEN** a retired commitment has a stronger lexical match than an active commitment
- **THEN** lookup selects the active same-plane commitment and reports the retired match only as historical context

### Requirement: Expected behavior-source inventory is derived independently
Before claiming broad behavior coverage, the system SHALL derive one immutable expected behavior-source inventory from the declared project boundary and the current native source inventories, independently of Behavior Commitment Ledger rows and caller-selected candidates. The expected inventory SHALL record its boundary, revision, fingerprint, exact item identities, source roles, source kinds, content references, and native owner references.

#### Scenario: A source is absent from an otherwise green ledger
- **WHEN** the independent expected inventory contains an in-scope item that is absent from the ledger reconciliation
- **THEN** broad behavior coverage SHALL remain blocked and SHALL identify the missing expected item

#### Scenario: An expected source changes after reconciliation
- **WHEN** the identity, content, role, or native owner of an expected source item changes
- **THEN** the previous reconciliation SHALL become stale and SHALL NOT support a current coverage claim

### Requirement: Every expected item has exactly one coverage disposition
The system SHALL reconcile every item in the expected behavior-source inventory with exactly one disposition: `modeled`, `delegated`, or `scoped`. A `modeled` item SHALL reference its Behavior Commitment, exactly one primary owner model, and current evidence. A `delegated` item SHALL reference exactly one native owner inventory, a typed delegation relation, and current native evidence. A `scoped` item SHALL record its scope owner, reason, and validation boundary. Missing, duplicate, or conflicting dispositions SHALL block broad coverage.

#### Scenario: One expected item has no disposition
- **WHEN** an expected item is present in the independent inventory but has no modeled, delegated, or scoped disposition
- **THEN** the reconciliation SHALL fail and SHALL report that exact item as uncovered

#### Scenario: One expected item is claimed twice
- **WHEN** two successful dispositions claim the same expected item
- **THEN** the reconciliation SHALL fail instead of accepting two independent success paths

#### Scenario: A specialist-owned item is delegated
- **WHEN** a UI, field, provider, or other specialist inventory remains the native semantic owner of an expected item
- **THEN** the ledger SHALL preserve that ownership through a typed delegated disposition and SHALL NOT recreate the specialist's classification

### Requirement: Source roles and normative conflicts remain explicit
The system SHALL preserve the role and authority lane of every expected source, including normative requirements, observed behavior, generated inventories, and contextual work artifacts. It SHALL detect and expose incompatible normative sources and normative-to-observed mismatches instead of silently choosing the last or most convenient source.

#### Scenario: Two normative sources disagree
- **WHEN** two current normative sources declare incompatible behavior for the same business intent
- **THEN** the ledger SHALL record a visible conflict and SHALL block a singular current commitment until the conflict has one owned disposition

#### Scenario: Observed behavior disagrees with the normative source
- **WHEN** current observed behavior differs from the selected normative commitment
- **THEN** the system SHALL preserve both roles, route the mismatch through the existing miss or repair owner, and SHALL NOT treat the observed behavior as an implicit normative replacement

