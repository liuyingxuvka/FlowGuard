## REMOVED Requirements

### Requirement: Blueprint depth distinguishes four claims
**Reason**: The old fourth claim was a separate empirical product branch. Canonical blueprint depth is now expressed by the single ordered readiness ladder and its exact gaps.

**Migration**: Read owner closure, behavior closure, per-layer statuses, `deepest_proven_layer`, and static-blueprint readiness from the canonical report.

### Requirement: Reconstruction readiness is read-only and gap-complete
**Reason**: The same information belongs to canonical blueprint readiness; retaining a separately named readiness surface duplicated the model-depth decision.

**Migration**: Consume the canonical blueprint-readiness status, complete gap set, deepest proven layer, and first gap.

## MODIFIED Requirements

### Requirement: Resource completeness uses an independent denominator
Blueprint qualification SHALL use an independently derived project resource inventory covering build, runtime, dependency, configuration, schema, data, asset, migration, external-service, and behavioral-oracle categories. Every required member SHALL be `current`, `external`, `scoped_out`, or `blocked`.

#### Scenario: A caller omits an entire resource category
- **WHEN** project evidence indicates a required database, service, configuration, migration, or build input that is absent from the supplied resource rows
- **THEN** resource closure and static-blueprint readiness SHALL be incomplete

### Requirement: Intent lineage participates in readiness
Blueprint readiness SHALL bind the current intent inventory fingerprint and terminal disposition of every admitted intent contribution. A non-trivial revision with an empty contribution set SHALL require a typed, evidence-bound no-declared-intent rationale.

#### Scenario: A change claims historical intent with no contributions
- **WHEN** a non-trivial blueprint revision describes intent lineage but its current intent inventory is empty and has no accepted no-intent rationale
- **THEN** intent closure and static-blueprint readiness SHALL be incomplete

### Requirement: Independent semantics and oracles cannot self-license
Blueprint readiness SHALL report circular support when a behavior contract and its sole oracle are both derived only from the same implementation source without an independent intent, requirement, domain rule, counterexample, or witnessed behavior boundary.

#### Scenario: Code explains and validates itself
- **WHEN** source-derived semantics and a source-derived oracle are the only evidence for a behavior block
- **THEN** the block SHALL remain incomplete for static-blueprint readiness
- **AND** the report SHALL name the missing independent source role

## ADDED Requirements

### Requirement: Blueprint depth distinguishes layered claims
FlowGuard SHALL distinguish owner-level structural closure, behavior-block closure, and canonical static-blueprint readiness as ordered claims with separate evidence identities.

#### Scenario: Owner map is complete but behavior contracts are coarse
- **WHEN** every implementation surface has one model owner but one or more behavior-bearing surfaces lack independent behavior contracts
- **THEN** owner-level structural closure SHALL be complete
- **AND** behavior-block closure and static-blueprint readiness SHALL remain incomplete

#### Scenario: Every static layer is current
- **WHEN** owner, behavior, model-code-test, topology, resource, intent, and oracle obligations are current and complete
- **THEN** static-blueprint readiness SHALL be `ready`
- **AND** the deepest proven layer SHALL be `static_blueprint`

### Requirement: Blueprint readiness is read-only and gap-complete
FlowGuard SHALL provide a read-only blueprint-readiness decision with status `ready`, `incomplete`, `stale`, or `blocked`, bound to the exact blueprint fingerprint and the complete unresolved-gap set. The decision SHALL NOT modify the target project or execute a missing evidence owner.

#### Scenario: Several readiness gaps exist
- **WHEN** behavior, resource, test, or intent gaps coexist
- **THEN** the decision SHALL report every known gap in the declared denominator rather than stopping at the first gap

#### Scenario: Ordinary work requests status
- **WHEN** an AI asks whether understanding is deep enough before implementation
- **THEN** FlowGuard SHALL return compact depth, readiness, first gap, and gap-count information without materializing the full blueprint

### Requirement: Readiness is a truthful ordered prefix
Software blueprint readiness SHALL compute each canonical layer from its native report and SHALL derive `deepest_proven_layer`, `first_gap`, and overall success mechanically from the longest exact-current complete prefix. A later passing report SHALL NOT mask an earlier incomplete, stale, or blocked layer.

#### Scenario: Self wrapper omits a failing child report
- **WHEN** a project or self wrapper receives a failing required native report but omits it from a convenience success expression
- **THEN** the canonical readiness review SHALL still return false
- **AND** the omitted report identity SHALL be named as an integrity finding

### Requirement: Semantic closure detects same-shape wrong behavior
Behavior-block closure SHALL require source-independent boundary rules and falsifiable cases that distinguish allowed and forbidden outcomes even when implementation signatures, surface ids, and data shapes remain unchanged.

#### Scenario: Boundary operator changes without shape change
- **WHEN** an implementation changes a semantic boundary such as `>=` to `>` while retaining the same path, symbol, inputs, outputs, and fingerprinted inventory shape
- **THEN** the applicable boundary case or oracle SHALL fail semantic closure

#### Scenario: Same-shape outputs are swapped
- **WHEN** two behavior surfaces retain the same signatures but exchange their declared outcomes or owners
- **THEN** exact behavior coverage SHALL report the semantic or owner mismatch

### Requirement: Compact affected readiness is directly projected
An ordinary understanding or admission query SHALL compute its compact result from the normalized blueprint identity and exact affected neighborhood without constructing, serializing, or converting the complete blueprint first.

#### Scenario: One behavior owner is affected
- **WHEN** a task names one current behavior owner and its declared neighborhood
- **THEN** the compact result SHALL contain only that neighborhood, required ancestors, and exact gaps
- **AND** the full project projection builder SHALL remain uncalled

### Requirement: Manifest consistency is a bounded child of readiness
FlowGuard SHALL derive static manifest consistency through one internal compiler-owned report with `static_manifest_status`, `static_manifest_ready`, exact layers and findings, and a negative claim boundary. The report SHALL NOT expose a generic success field or completion sentence and SHALL NOT independently license whole readiness.

#### Scenario: Manifest consistency passes while a parent layer is unresolved
- **WHEN** the manifest child report is complete but topology, behavior, intent, execution, or target qualification remains incomplete, stale, blocked, or not run
- **THEN** the child status SHALL remain visible as partial evidence
- **AND** project and target readiness SHALL remain non-successful

### Requirement: Affected readiness follows every semantic topology relation
The affected neighborhood SHALL compile directionally defined invalidation edges for parent-child, producer-consumer, delegation, and support relations, and SHALL include the relation object that caused propagation. Cycles and duplicate declarations SHALL converge deterministically.

#### Scenario: A producer changes outside a parent-child edge
- **WHEN** model A `produces_for` model B and A is selected as the change seed
- **THEN** B and the exact relation SHALL enter the affected closure
- **AND** unrelated or reverse-only nodes SHALL remain outside according to the relation contract
