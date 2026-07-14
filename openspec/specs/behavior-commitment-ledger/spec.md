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
FlowGuard SHALL represent runtime commitment relationships as typed `relations` that reference registered commitments within the same ledger boundary and obey the declared same-plane/cross-plane relation matrix. Former `dependency_commitment_ids` input SHALL be rejected at every current entrypoint.

#### Scenario: Unknown relation target blocks
- **WHEN** a relation refers to an unknown commitment id
- **THEN** the ledger review SHALL report `commitment_relation_target_unknown`

#### Scenario: Cross-plane relation lacks rationale
- **WHEN** a relation crosses behavior planes without a non-empty rationale
- **THEN** the ledger review SHALL report `commitment_cross_plane_relation_missing_rationale`

#### Scenario: Relation direction is invalid
- **WHEN** a relation type and source/target plane pair is outside the declared relation matrix
- **THEN** the ledger review SHALL report `commitment_relation_plane_mismatch`

#### Scenario: Former dependency field is rejected
- **WHEN** a current ledger row carries `dependency_commitment_ids`
- **THEN** ledger loading SHALL reject the row rather than translating it

#### Scenario: Typed relation decision is explicit
- **WHEN** the desired dependency crosses planes or its direction is unclear
- **THEN** the current author SHALL choose an allowed typed relation and rationale before the ledger can pass

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

### Requirement: Each exact business intent has one active commitment
Behavior Commitment Ledger SHALL assign one stable exact
`business_intent_id` and exactly one active commitment to each in-scope
external behavior promise. Exact identity SHALL be determined from the actor,
trigger and preconditions, expected result and terminal, failure boundary, and
material externally relevant state writes and side effects. Different UI, API,
CLI, alias, adapter, wrapper, helper, or compatibility surfaces for that exact
intent SHALL map to the same commitment.

#### Scenario: Multiple surfaces expose one exact intent
- **WHEN** several declared surfaces have the same actor, trigger and preconditions, expected result and terminal, failure boundary, material state writes, and side effects
- **THEN** the ledger SHALL map every surface to one stable business-intent id and one active commitment id

#### Scenario: Duplicate active commitments cover one exact intent
- **WHEN** two active commitment rows claim the same exact business-intent identity
- **THEN** the ledger review SHALL report a duplicate exact-intent commitment blocker and SHALL NOT support broad confidence

#### Scenario: A genuinely different intent remains separate
- **WHEN** a candidate commitment has a material externally observable difference in actor, trigger or preconditions, expected result or terminal, failure boundary, state writes, side effects, or safety semantics
- **THEN** the ledger SHALL require the difference, owner, validation boundary, rationale, and current evidence before accepting a distinct business-intent id

### Requirement: Delegating surfaces do not create delegate commitments
An additional surface that only delegates to the selected primary path SHALL be
recorded through the existing source-surface mapping and PPA candidate or facade
disposition. Behavior Commitment Ledger SHALL NOT create a delegate commitment,
surface commitment, or compatibility commitment whose only promise is to invoke
the same exact business intent.

#### Scenario: Compatibility facade delegates to the primary path
- **WHEN** an API alias, UI control, CLI command, adapter, wrapper, or compatibility facade adds no independent validation, terminal, state write, side effect, or success decision and delegates to the selected primary path
- **THEN** the ledger SHALL map that surface to the existing commitment without creating another commitment row

#### Scenario: Surface owns material behavior
- **WHEN** a proposed surface performs independent business validation, terminal selection, material state writes, side effects, or success behavior
- **THEN** the ledger SHALL treat it as a duplicate-path or distinct-intent question for the existing BCL/PPA owners rather than legitimizing it through a delegate commitment

### Requirement: Path-sensitive commitment bindings are singular and green
Each path-sensitive commitment SHALL bind to exactly one singular
`primary_path_id` whose PPA decision is current and green for the same stable
business-intent id. A report id, risk-gate id, receipt id, or free-form evidence
reference without a green singular path binding SHALL NOT satisfy broad
commitment coverage.

#### Scenario: Current green singular binding passes
- **WHEN** a path-sensitive commitment carries one primary path id, matching exact business-intent identity, current green PPA decision, and current runtime and proof evidence
- **THEN** the ledger review SHALL accept the PPA binding for the declared commitment scope

#### Scenario: Legacy one-item path list migrates deterministically
- **WHEN** legacy input supplies exactly one distinct non-empty `primary_path_ids` value and no conflicting singular value
- **THEN** the ledger SHALL migrate that value to `primary_path_id` and SHALL emit the singular field in current output

#### Scenario: Ambiguous path list blocks broad confidence
- **WHEN** legacy input supplies zero, multiple, duplicate-conflicting, or singular/list-conflicting primary path values
- **THEN** the ledger review SHALL report an ambiguous primary-path binding and SHALL NOT support broad confidence

#### Scenario: Scoped or opaque PPA reference is insufficient
- **WHEN** a path-sensitive commitment carries a PPA reference but the decision is scoped, missing, stale, blocked, not current, or lacks the selected primary path and material proof
- **THEN** the ledger SHALL keep commitment coverage scoped or blocked instead of treating the reference as passed

### Requirement: Commitments declare one behavior plane
Every in-scope commitment SHALL declare exactly one production behavior plane: `product_runtime`, `agent_operation`, or `development_process`.

#### Scenario: Commitment form and plane are distinct
- **WHEN** a commitment declares a `commitment_kind` such as `ui`, `cli`, `workflow`, or `process`
- **THEN** ledger review SHALL still require a separate valid `behavior_plane`

#### Scenario: Unclassified row cannot pass
- **WHEN** a commitment declares `unclassified`
- **THEN** the current ledger SHALL reject the row until the source declares one production plane

### Requirement: Commitments declare structured actor kind
Every commitment SHALL declare one actor kind from `end_user`, `external_system`, `application`, `ai_agent`, `developer`, or `automation`, while retaining a human-readable actor label.

#### Scenario: Free-text actor lacks kind
- **WHEN** a commitment has an actor label but no valid actor kind
- **THEN** ledger review SHALL report `commitment_actor_kind_missing_or_invalid`

### Requirement: Commitments expose bounded lookup bindings
The ledger SHALL support task terms, path patterns, tool ids, error signatures, and workflow families as optional lookup bindings without making those bindings a second behavior authority.

#### Scenario: Model miss adds reusable error signature
- **WHEN** a same-plane Model Miss produces a stable observed error signature
- **THEN** the owning commitment MAY add that signature to its lookup binding
- **AND** the commitment id and primary owner model SHALL remain unchanged

### Requirement: Canonical project ledger is machine-readable
Project templates SHALL store behavior commitments in one canonical `.flowguard/behavior_commitment_ledger/ledger.json` artifact and SHALL treat generated check results as evidence rather than source data.

#### Scenario: Project model loads canonical ledger
- **WHEN** the generated project BCL model is imported
- **THEN** it SHALL load and validate `ledger.json`
- **AND** SHALL NOT reconstruct a separate embedded commitment inventory

#### Scenario: Result artifact cannot become source
- **WHEN** `run_checks.py` writes `result.json`
- **THEN** later ledger loading SHALL continue to read `ledger.json`, not the prior result

### Requirement: Former ledger shapes fail closed
FlowGuard SHALL accept only the canonical current ledger shape and SHALL NOT provide a migration reader, converter, upgrade command, alias, or second successful authority for former Python or JSON shapes.

#### Scenario: Former embedded Python inventory is presented
- **WHEN** a project presents commitments only through the former embedded Python inventory
- **THEN** current ledger loading SHALL fail closed
- **AND** SHALL NOT execute that file to obtain commitments

#### Scenario: Former JSON shape is presented
- **WHEN** a ledger uses a former field set or artifact shape
- **THEN** current ledger loading SHALL reject it with an actionable current-shape finding
- **AND** SHALL NOT translate it automatically

#### Scenario: Direct replacement activates one authority
- **WHEN** the project source is rewritten to the canonical current ledger
- **THEN** the project adapter SHALL load only that ledger
- **AND** the former embedded inventory SHALL remain a rejected negative fixture

### Requirement: New templates use plane-aware commitment ids
New generated commitments SHALL default to `commitment:product:*`, `commitment:agent:*`, or `commitment:development:*` ids. An existing semantic id MAY be authored directly in the current ledger when its current references remain valid; this is current authorship, not legacy translation.

#### Scenario: Current id remains stable
- **WHEN** a current commitment is rewritten without changing its semantic identity
- **THEN** the current source MAY retain its id while declaring all required plane-aware fields and relations
