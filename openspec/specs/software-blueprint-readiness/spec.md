# Software Blueprint Readiness Specification

## Purpose
Define the exact evidence that lets FlowGuard distinguish owner structure, behavior closure, canonical blueprint depth, and unresolved gaps.

## Requirements

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

### Requirement: Behavior-bearing surfaces have reimplementable contracts
Every behavior-bearing implementation surface SHALL bind a source-independent contract expressed as `Input x State -> Set(Output x State)` with explicit input, output, state/effect, error, decision, completion, and applicable order, retry, and timeout meanings. Pure helpers MAY close through one unique supporting owner relation.

#### Scenario: Generic owner text is copied across unrelated behavior blocks
- **WHEN** several behavior-bearing surfaces share only one generic owner-level semantic statement without surface-specific applicability
- **THEN** behavior-block closure SHALL report the exact uncovered surfaces
- **AND** the generic text SHALL NOT satisfy those contracts

#### Scenario: A dimension is not applicable
- **WHEN** retry, timeout, ordering, state, effect, or another contract dimension does not apply to a behavior-bearing surface
- **THEN** that surface SHALL contain a typed not-applicable disposition with a reviewable reason

### Requirement: Blueprint readiness is read-only and gap-complete
FlowGuard SHALL provide a read-only blueprint-readiness decision with status `ready`, `incomplete`, `stale`, or `blocked`, bound to the exact blueprint fingerprint and the complete unresolved-gap set. The decision SHALL NOT modify the target project or execute a missing evidence owner.

#### Scenario: Several readiness gaps exist
- **WHEN** behavior, resource, test, or intent gaps coexist
- **THEN** the decision SHALL report every known gap in the declared denominator rather than stopping at the first gap

#### Scenario: Ordinary work requests status
- **WHEN** an AI asks whether understanding is deep enough before implementation
- **THEN** FlowGuard SHALL return compact depth, readiness, first gap, and gap-count information without materializing the full blueprint

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

### Requirement: Candidate blueprints are honest by construction
For a supported project, FlowGuard SHALL be able to discover candidate files, surfaces, tests, resources, and possible owners without treating inferred semantics or ownership as accepted. Candidate generation SHALL be read-only by default and SHALL expose unresolved rows for independent completion.

#### Scenario: Candidate semantics come only from source inspection
- **WHEN** candidate semantics are inferred from implementation source without an independent accepted intent, contract, or oracle
- **THEN** the candidate SHALL remain unresolved and SHALL NOT qualify behavior-block closure

#### Scenario: Unsupported language is encountered
- **WHEN** no registered deep discovery adapter exists for the project language
- **THEN** candidate generation SHALL return a visible missing-adapter blocker rather than shallow success

### Requirement: Blueprint projections are normalized and affected-loadable
FlowGuard SHALL store shared owner, semantic, oracle, test, and receipt identities once and SHALL use content-addressed references from behavior-surface rows. Ordinary work SHALL load only the affected owner/behavior neighborhood, while full qualification SHALL prove canonical equivalence to the complete logical blueprint.

#### Scenario: Shared test evidence covers several surfaces
- **WHEN** one exact test member legitimately covers several behavior surfaces
- **THEN** the shared evidence object SHALL be stored once
- **AND** every covered surface SHALL have its own explicit coverage edge

#### Scenario: Projection layout changes without semantic change
- **WHEN** normalized sharding changes physical layout but preserves canonical logical content
- **THEN** the logical blueprint fingerprint and qualification result SHALL remain stable

### Requirement: Independent semantics and oracles cannot self-license
Blueprint readiness SHALL report circular support when a behavior contract and its sole oracle are both derived only from the same implementation source without an independent intent, requirement, domain rule, counterexample, or witnessed behavior boundary.

#### Scenario: Code explains and validates itself
- **WHEN** source-derived semantics and a source-derived oracle are the only evidence for a behavior block
- **THEN** the block SHALL remain incomplete for static-blueprint readiness
- **AND** the report SHALL name the missing independent source role

### Requirement: Software blueprint readiness is a target-system specialization
Software-project discovery SHALL contribute provider results to the canonical target-system blueprint. Python, JavaScript, Rust, or another language adapter SHALL be selected by declared provider capability and SHALL NOT define the core target admission rule.

#### Scenario: Non-Python software provider is current
- **WHEN** a bounded software target supplies current observation and authority provider results without a Python provider
- **THEN** FlowGuard SHALL evaluate those results through the canonical blueprint compiler
- **AND** it SHALL NOT reject the blueprint because its language is not Python

#### Scenario: Software adapter is unavailable
- **WHEN** a required source boundary has no current deep-discovery provider
- **THEN** readiness SHALL report a missing-provider gap for that exact boundary
- **AND** candidate discovery SHALL remain incomplete rather than shallow-ready

### Requirement: Project success includes canonical blueprint readiness
A project blueprint success result used for a static DNA claim SHALL require both evidence qualification and canonical static blueprint readiness. An older owner-level or inventory-only qualification SHALL NOT produce success while behavior, binding, resource, intent, or test readiness is blocked.

#### Scenario: Qualification passes but behavior readiness is blocked
- **WHEN** project inventories qualify but behavior contracts, helper ownership, portable bindings, or real test coverage are incomplete
- **THEN** the project blueprint success result SHALL be false
- **AND** the response SHALL preserve the lower layer that passed

### Requirement: Candidate generation never manufactures closure
Software candidate generation SHALL keep inferred semantics, guessed helper ownership, placeholder case designs, and source-only oracle claims unresolved until admitted independent evidence supplies their exact identities.

#### Scenario: Candidate builder discovers a function
- **WHEN** discovery finds a behavior-bearing function but no current block-local semantic or concrete test-case binding exists
- **THEN** the candidate SHALL identify the missing rows
- **AND** it SHALL NOT create accepted generic semantics or a synthetic coverage edge

### Requirement: Missing language adapters are provider gaps
Candidate generation SHALL describe missing deep observation capability for an exact target boundary as a provider gap. It SHALL NOT classify a language or non-code target as globally unsupported by the target-system core.

#### Scenario: No adapter exists for one source boundary
- **WHEN** a software target declares a source boundary for which no current deep-discovery provider is registered
- **THEN** candidate generation SHALL return the exact missing observation capability and boundary
- **AND** another language, workflow, trace, or contract provider SHALL remain independently usable for its declared boundary

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
- **AND** an unknown evidence identity, a missing ordinary test node, or a mismatched model-regression owner SHALL block the witness rather than being treated as a missing test for every code surface

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

### Requirement: One governed observation can feed independent decisions
Within one blueprint build, source discovery SHALL produce one immutable observation bundle per provider input. Independent surface classification, implementation-denominator review, behavior compilation, and reduction analysis MAY consume that same observation, but each SHALL retain its own rules, findings, and result identity. Reusing the observation SHALL NOT reuse an old result or bypass a denominator check.

#### Scenario: Declaration and inventory inspect the same current file
- **WHEN** both declaration classification and implementation inventory require the same provider observation in one build
- **THEN** the provider SHALL observe and parse that file once for that build
- **AND** both consumers SHALL independently validate their complete obligations from the same immutable facts

#### Scenario: A later invocation sees changed content
- **WHEN** the file content or provider contract changes before a later build
- **THEN** the later build SHALL create a new observation and identity
- **AND** no invocation-local observation SHALL become a persistent cache authority

### Requirement: Large normalized reference views have one in-memory owner
One normalization invocation SHALL construct each complete logical reference view once and reuse that exact immutable value for its fingerprint, byte count, integrity checks, and physical projection. It SHALL NOT hold two independently reconstructed complete reference dictionaries for the same logical report.

#### Scenario: A behavior report contains many coverage edges
- **WHEN** the report is normalized into reference shards and shared objects
- **THEN** its complete normalized reference dictionary SHALL be produced once
- **AND** all downstream identity calculations SHALL consume that same value without changing canonical output

### Requirement: Affected shared objects are independently validated once
Affected-blueprint materialization SHALL compute the current fingerprint of every supplied shared object before accepting it. For a projection-declared base object, it SHALL compare that actual fingerprint with the declared fingerprint and fail on any difference. After successful validation, the exact computed fingerprint SHALL be reused in the final affected index; content-addressed objects created during the same invocation SHALL likewise be fingerprinted once and reused.

#### Scenario: A normalized object is current
- **WHEN** an affected-blueprint index materializes from a supplied object whose actual fingerprint matches the normalized projection
- **THEN** the materializer SHALL record that independently computed fingerprint in the final index
- **AND** it SHALL NOT hash the same immutable payload again during that invocation

#### Scenario: A supplied object drifts
- **WHEN** the supplied payload no longer matches its normalized projection fingerprint
- **THEN** materialization SHALL fail visibly after computing the actual payload fingerprint
- **AND** no declared fingerprint, cache, or fallback SHALL be accepted as a substitute for that check

### Requirement: Resource observation starts from one initialized current snapshot
Before any resource provider is observed, a blueprint builder SHALL obtain and validate the exact non-empty current observed-snapshot fingerprint. Every current resource observation created by that build SHALL bind its `subject_revision` to that same fingerprint. A missing snapshot identity SHALL block before observation; the builder SHALL NOT substitute an empty value, a later assignment, a source-file revision, or another authority lane.

#### Scenario: Current resources are observed for one blueprint build
- **WHEN** the builder has validated the current observed-snapshot fingerprint and begins resource observation
- **THEN** every current resource row SHALL carry that exact fingerprint as its subject revision
- **AND** resource observation SHALL NOT begin before the snapshot input exists

#### Scenario: Snapshot identity is missing
- **WHEN** the current model authority does not provide a non-empty observed-snapshot fingerprint
- **THEN** blueprint construction SHALL fail visibly before invoking the resource observer
- **AND** no empty, inferred, stale, or later-populated fingerprint SHALL enter the resource inventory

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

### Requirement: Self-blueprint readiness preserves topology and evidence reattachment gaps
Whole-self-blueprint readiness SHALL consume the exact current structural-parent projection, cross-boundary relations, feedback-component progress reports, child terminal receipts, full parent aggregation receipt, and model-test helper/coverage report. Static-blueprint readiness SHALL remain blocked when any required relation, progress contract, independent receipt, helper leaf, coverage owner, or execution disposition is incomplete, stale, foreign, self-generated, or `not_run`.

#### Scenario: Full parent is green while a child is not reattached
- **WHEN** the full model parent reports success but one current child lacks its exact terminal receipt or the parent does not consume that receipt
- **THEN** readiness SHALL expose the child reattachment gap and remain blocked
- **AND** parent green SHALL NOT advance the truthful ordered prefix past the missing child evidence

#### Scenario: Structural hierarchy passes while feedback progress is missing
- **WHEN** every node has one structural parent but a reachable feedback component lacks a current independently evidenced progress contract
- **THEN** structural topology MAY remain complete while feedback and static-blueprint readiness remain blocked
- **AND** cross-boundary connectivity SHALL NOT be reclassified as structure to hide the gap

#### Scenario: Qualification creates the evidence it consumes
- **WHEN** the self-blueprint build or readiness route generates or registers a passing receipt used by the same qualification
- **THEN** readiness SHALL report an independent-evidence gap
- **AND** deterministic generation or matching content fingerprints SHALL NOT make the receipt current evidence

#### Scenario: Planned helper coverage has not executed
- **WHEN** recursive helper resolution and coverage ownership are statically complete but one exact leaf execution receipt is absent
- **THEN** static checker design MAY remain complete
- **AND** execution SHALL remain `not_run` and whole executed-evidence readiness SHALL not pass

### Requirement: Current intent completeness uses the independent model-owner denominator
Project intent readiness SHALL compare one effective current-intent owner binding with the complete model-owner denominator independently derived from the exact current observed model snapshot. Every current model owner SHALL have one binding to its exact current realization relation and one or more active cumulative intent contributions. Missing, extra, duplicate, foreign, root-level, or unresolved bindings SHALL block intent readiness. Contributions and bindings SHALL NOT define or shrink their own denominator.

#### Scenario: Latest revision describes only two of sixty current model owners
- **WHEN** the current observed snapshot contains sixty model owners
- **AND** the latest delta directly changes only two owners
- **THEN** intent readiness still requires exact effective bindings for all sixty owners
- **AND** the two-member delta SHALL NOT be reported as complete current system intent

#### Scenario: A contribution tries to define its own smaller denominator
- **WHEN** the cumulative view or projected inventory supplies bindings for fewer owners than the independently observed snapshot
- **THEN** readiness reports the exact missing owner identities and remains blocked
- **AND** no no-intent rationale, root binding, or shared fallback owner may close those missing rows

#### Scenario: One intent source supports several owners without shared ownership
- **WHEN** one source artifact or design goal legitimately informs several exact model owners
- **THEN** each owner SHALL retain its own owner-specific contribution record, compact binding, and exact realization relation
- **AND** those records MAY reference the same source artifact so its body is not copied, but one active contribution SHALL NOT acquire several primary owners

### Requirement: Every current behavior block consumes effective model intent
Behavior readiness SHALL use the independently observed current behavior-block denominator and require every block to consume at least one active cumulative intent contribution through its exact current model owner. A behavior SHALL be blocked when its intent reference is empty, missing, inactive, foreign to its model owner, or derived only from implementation code. Shared intent MAY cover sibling blocks only through their exact owner binding; behavior coverage SHALL remain distinct from model-owner coverage.

#### Scenario: Model owners are complete but one behavior has no intent
- **WHEN** the current-intent view covers every model owner
- **AND** one independently observed behavior block has no effective intent reference
- **THEN** model-owner intent coverage may remain complete
- **BUT** behavior and static-blueprint readiness remain blocked with that exact behavior identity

#### Scenario: Sibling behaviors consume one owner intent
- **WHEN** several current behavior blocks belong to one exact model owner
- **AND** that owner binding references one active current contribution
- **THEN** every sibling may consume the shared contribution through that owner binding
- **AND** no copied intent body or second intent authority is required

#### Scenario: Behavior references another owner's intent
- **WHEN** a behavior block cites an active contribution that is not bound to its exact current model owner
- **THEN** behavior readiness reports a cross-owner intent binding and remains blocked
- **AND** matching words, implementation similarity, or a root-level relation SHALL NOT authorize the reference

### Requirement: Blueprint readiness includes model path-quality closure
Broad software-blueprint readiness SHALL require a current path-quality result for every new or materially changed required model in the independently observed denominator. Missing, stale, unresolved, or semantically mismatched rows SHALL remain exact readiness gaps and SHALL NOT be replaced by model executability, code binding, test presence, or parent aggregation alone.

#### Scenario: Model executes but path quality is unresolved
- **WHEN** a model is executable and bound to code and tests but retains an unresolved path-quality row
- **THEN** broad DNA readiness remains blocked or explicitly scoped for that model boundary

#### Scenario: Unaffected model remains current
- **WHEN** an affected-topology review proves that a prior model and its consumed identities are unchanged
- **THEN** its current path-quality result may remain reusable without deep re-execution
### Requirement: Statically finite dynamic selectors have one observed current contract
When a provider can derive a non-empty finite selector domain directly from current source structure, the self-blueprint SHALL materialize one exact dynamic-selector contract from that observation. The contract SHALL bind the exact operation, surface, effective owner, structure fingerprint, selector-source fingerprint, and sorted selector values. The authored blueprint definition SHALL NOT require or retain a second manual copy of the same mechanically derivable contract.

#### Scenario: A loop drives an attribute lookup from a finite literal domain
- **WHEN** current source proves every possible selector value for a dynamic operation
- **THEN** the provider SHALL emit one exact-current dynamic-selector contract for that operation
- **AND** the contract SHALL become stale automatically when the structure, selector source, owner, operation, or value set changes

#### Scenario: A selector domain is genuinely open
- **WHEN** the provider cannot derive a complete non-empty selector domain
- **THEN** the operation SHALL remain a visible implementation-inventory blocker unless source is made finite or one explicit exact allowance owns the bounded exceptional behavior
- **AND** no stale generated contract, empty value set, broad allowance, or authored fallback SHALL be accepted
### Requirement: Compact self-qualification exposes bounded actionable blocker classes
The compact self-qualification projection SHALL count actionable child findings by exact child report, finding code, and severity and SHALL include one bounded example for each emitted blocker class. It SHALL derive those summaries from already-materialized child findings without serializing a complete child report or rebuilding the blueprint.

#### Scenario: One upstream defect blocks several blueprint layers
- **WHEN** many child findings share one code and later readiness layers are blocked only by dependency order
- **THEN** compact output SHALL expose the shared child finding count and one bounded example
- **AND** an AI consumer SHALL NOT need a second full blueprint build merely to identify the upstream blocker class

### Requirement: Readiness distinguishes static closure from portable materialization
Blueprint readiness SHALL expose static closure, portable materialization, and execution evidence as separate ordered claims with separate fingerprints and claim boundaries.

#### Scenario: Static closure passes while execution is not run
- **WHEN** every static layer is current but one or more leaf execution owners are `not_run`
- **THEN** static readiness MAY be `ready`
- **AND** execution readiness SHALL remain visibly `not_run` or incomplete

#### Scenario: Portable materialization is absent
- **WHEN** static readiness is `ready` but no current manifest and shard bundle is available
- **THEN** portable readiness SHALL not be reported as ready
- **AND** the result SHALL name the missing materialization identity

### Requirement: Compact readiness is a projection, not a smaller denominator
Compact and candidate-detail readiness projections SHALL preserve the same complete observed denominator, fingerprints, unresolved ids, skipped/not-run statuses, and claim boundary as the full result.

#### Scenario: Caller requests a compact result
- **WHEN** a caller requests summary output
- **THEN** the system SHALL return summary identities and candidate indexes without duplicating full evidence payloads
- **AND** the caller SHALL be able to expand any listed candidate by exact id

#### Scenario: Compact output omits a gap
- **WHEN** a compact projection would hide an unresolved, skipped, stale, or `not_run` member
- **THEN** the projection SHALL remain non-ready or fail integrity validation rather than silently omitting the member
