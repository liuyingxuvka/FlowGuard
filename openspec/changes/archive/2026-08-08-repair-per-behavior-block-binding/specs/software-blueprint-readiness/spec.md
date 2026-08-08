## ADDED Requirements

### Requirement: Portable member closure is exact across sibling behavior blocks
For a portable model realized by several behavior blocks, blueprint readiness SHALL compare each block's exact portable binding with its implementation surface and SHALL compare the union of all block-local portable members and protected failures with the independently supplied model member catalog. A block SHALL NOT be required to pretend that it implements sibling-only fields or failures, and the union SHALL NOT omit or invent model members.

#### Scenario: Sibling blocks bind different fields
- **WHEN** two behavior blocks under one portable model bind disjoint input or state fields
- **THEN** each block SHALL be checked against its own implementation surface
- **AND** the model member catalog SHALL close only when the union of both exact bindings matches the declared catalog

#### Scenario: One sibling omits its own cases
- **WHEN** one behavior block has its exact required cases but a sibling lacks its required good case, boundary case, or explicitly scoped bad case
- **THEN** the incomplete sibling SHALL report the exact behavior-case design gap
- **AND** cases from the complete sibling SHALL NOT satisfy that gap

#### Scenario: Two blocks reuse one case identity
- **WHEN** two behavior blocks declare the same materialized case id
- **THEN** blueprint readiness SHALL reject the duplicate identity
- **AND** block-local grouping SHALL NOT make the duplicate acceptable

#### Scenario: Owner failures are sparse across children
- **WHEN** an owner has `S` behavior blocks, `F` protected failures, and `E` explicit block-to-failure edges
- **THEN** readiness SHALL require exactly `2S + E` good, boundary, and bad cases
- **AND** it SHALL reject any automatically manufactured sibling failure edge

#### Scenario: A required parent member is not bound
- **WHEN** the independent parent catalog contains a transition, protected failure, or other member absent from the union of exact child and composite bindings
- **THEN** readiness SHALL report the exact unbound member
- **AND** neither a lexical primary surface nor all sibling surfaces SHALL receive it as a fallback

#### Scenario: A parent result is presented for all siblings
- **WHEN** an owner-level or composite failure result, test result, or execution receipt is presented as evidence for several child behavior blocks without exact child coverage contracts
- **THEN** readiness SHALL keep every unbound child incomplete or `not_run`
- **AND** parent ownership SHALL NOT copy the result or protected failure to sibling blocks

### Requirement: Block-local materialization does not duplicate owner neighborhoods
Each behavior dimension SHALL name its exact implementation surface as its applicability boundary. Shared owner semantic rules SHALL be referenced once by identity rather than copied into every block as an owner-wide surface list. Exact binding, case, coverage, and reduction joins SHALL be resolved through identity indexes without omitting any denominator member.

#### Scenario: One owner contains many surfaces
- **WHEN** one model owner contains several behavior blocks and supporting surfaces
- **THEN** each block's dimension applicability SHALL contain only that block's exact implementation surface
- **AND** the owner-level semantic rule identity MAY be shared without copying all sibling surface ids into every dimension

#### Scenario: Source lineage differs from planned checker identity
- **WHEN** several block-local planned cases derive from one owner-level known-good or known-bad case
- **THEN** each planned checker SHALL use the materialized block-local case id as its parameter-case identity
- **AND** the common owner-level origin SHALL remain separately available as source-case lineage

#### Scenario: Supporting code realizes a direct behavior owner
- **WHEN** a helper, adapter, serializer, or storage surface supports one direct behavior implementation
- **THEN** the direct implementation binding SHALL own the exact behavior-block obligation
- **AND** the supporting binding SHALL reference that same obligation and the same required semantic dimensions without entering the primary-obligation denominator as another owner
- **AND** a missing, ambiguous, or mismatched direct owner SHALL block readiness rather than create a helper-local fallback obligation

#### Scenario: One implementation binding carries ordinary tests and model validation
- **WHEN** one current implementation binding cites both ordinary test nodes and the model-regression result for its owning model element
- **THEN** ordinary test identities SHALL be validated against the current test inventory and model-regression identities SHALL be validated against the exact current model/path-quality owner
- **AND** both evidence classes SHALL remain separately typed while jointly supporting the same implementation-necessity witness
- **AND** an unknown evidence identity, a declared ordinary test node that is missing from the current inventory, or a mismatched model-regression owner SHALL block the witness rather than being treated as a missing test for every code surface

#### Scenario: No ordinary test binding is not silently upgraded into one
- **WHEN** a current implementation binding cites only its exact model-regression/path-quality evidence and no ordinary test node
- **THEN** the blueprint SHALL preserve the empty ordinary-test binding while retaining the model-validation identity in its separate namespace
- **AND** model-test alignment SHALL continue to report the missing ordinary execution evidence instead of treating the model regression as code-test completion

### Requirement: Current intent identity and semantic lineage are exact
The project intent inventory SHALL bind the current observed model-snapshot fingerprint as its subject and observed subject. A source-inventory revision SHALL remain a separate build-input identity and SHALL NOT substitute for the model-snapshot identity. For each accepted intent disposition, every exact `relation:model-realizes-purpose:<owner>` relation present in both the contribution targets and accepted changed relations SHALL project to the corresponding current model owner. Every owner semantic specification used by an intent-consuming behavior SHALL bind the exact accepted intent source id and source fingerprint.

#### Scenario: Source inventory identity is used as the intent subject
- **WHEN** an intent inventory names a current source-inventory revision as its subject while the observed target is a model-snapshot fingerprint
- **THEN** intent readiness SHALL be stale or blocked with the exact mixed identities
- **AND** freshness of both identities SHALL NOT make them interchangeable

#### Scenario: An accepted realized-purpose owner is omitted
- **WHEN** a contribution declares several purpose relations and its accepted disposition changes an exact subset of those `model-realizes-purpose` relations
- **THEN** the projected intent owner set SHALL equal that exact accepted subset, including every accepted sibling owner
- **AND** a merely declared but unrealized owner SHALL NOT be projected
- **AND** a missing, foreign, or ambiguous accepted owner SHALL block readiness rather than be silently dropped

#### Scenario: Behavior intent lacks exact semantic provenance
- **WHEN** a behavior consumes an accepted contribution but every referenced owner semantic specification omits its exact source id and source fingerprint or binds another fingerprint
- **THEN** behavior and intent readiness SHALL be blocked
- **AND** current model, runner, declaration, closure, test, or contribution ids SHALL NOT substitute for the missing source pair

#### Scenario: Shared owner semantics serve several behavior blocks
- **WHEN** several behavior blocks under one owner consume the same accepted contribution
- **THEN** the exact intent source pair SHALL be stored once on the shared owner semantic specification
- **AND** each behavior SHALL reference the semantic and contribution identities without copying the intent body

### Requirement: Normalized coverage payload has one complete physical owner
The native typed behavior report SHALL remain self-contained for readiness review. In normalized, affected-read, and canonical physical projections, each complete coverage-edge payload SHALL exist only in the content-addressed shared-object store under its exact coverage id. Normalized behavior reports and coverage shards SHALL bind exact fingerprints or ordered object references without repeating the full edge payload.

#### Scenario: Reference shards and object store close exactly
- **WHEN** a behavior report is normalized
- **THEN** the report coverage-id set, the shared coverage-object id set, and the union of ordered shard references SHALL be identical
- **AND** every shared coverage payload SHALL exactly match the current typed edge with the same id
- **AND** missing, extra, duplicated, reordered, or changed rows SHALL block normalization

#### Scenario: Legacy full-payload shard is supplied
- **WHEN** a shard contains a complete coverage row or any shape other than the strict current reference envelope
- **THEN** the normalizer and affected reader SHALL reject it even if its outer content fingerprint is internally consistent
- **AND** neither reader SHALL fall back to the whole behavior report or another shard format

#### Scenario: Canonical project DNA is exported
- **WHEN** a qualified project blueprint is projected to canonical shards
- **THEN** the behavior-model and behavior-shard categories SHALL contain only report identities, coverage fingerprints, and reference envelopes
- **AND** complete coverage rows SHALL appear only in the shared-object category

### Requirement: Full self-audit publication uses an exact lightweight currentness comparator
The FlowGuard self-architecture review SHALL materialize one complete self blueprint and SHALL independently recompute its exact build-input identity before publication. The build-input identity SHALL cover current model authority, accepted intent revision, observed snapshot, complete classified file-content inventory, semantic mesh, and provider contracts. It SHALL NOT reconstruct the complete behavior and reduction object graphs a second time.

#### Scenario: Inputs remain unchanged during a full review
- **WHEN** the before-build and before-publication identities are exactly equal
- **THEN** the deterministic in-memory self blueprint and reduction denominator MAY be published without a second whole-blueprint materialization
- **AND** candidate discovery SHALL occur once when no proof registry changes its dispositions

#### Scenario: Any build input changes during review
- **WHEN** any covered source, test, model-authority, semantic-mesh, intent-revision, or provider-contract identity changes
- **THEN** publication SHALL fail visibly
- **AND** the prior in-memory blueprint, candidate inventory, and evidence SHALL NOT be reused as current
