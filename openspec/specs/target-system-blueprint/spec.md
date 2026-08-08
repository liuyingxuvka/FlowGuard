# target-system-blueprint Specification

## Purpose
Define one provider-neutral blueprint contract that can describe software, workflows, services, agents, data pipelines, and mixed systems without making a source language the core authority.

## Requirements

### Requirement: Target-system blueprints are provider-neutral
FlowGuard SHALL identify a target by target-system id, target kind, subject revision, declared boundary, and required provider capabilities. The core blueprint contract SHALL NOT require a programming language, repository layout, or executable software target.

#### Scenario: Declared workflow has no source language
- **WHEN** a bounded workflow supplies current observation and authority providers without a programming-language identity
- **THEN** FlowGuard SHALL evaluate it through the same target-system blueprint contract
- **AND** it SHALL NOT classify the target kind as unsupported solely because no source language exists

#### Scenario: Mixed target uses several provider kinds
- **WHEN** a target combines source code, workflow declarations, documentation, traces, and external contracts
- **THEN** the blueprint SHALL compose the exact provider results under one target and subject revision
- **AND** each result SHALL retain its own claim boundary

### Requirement: Providers report evidence rather than readiness
Every provider result SHALL identify its provider role, provider id and version, target id, subject revision, consumed-input fingerprint, result fingerprint, status, findings, and claim boundary. Providers SHALL contribute observations or independent authority but SHALL NOT directly declare the canonical blueprint ready.

#### Scenario: Required provider is missing
- **WHEN** the descriptor requires a discovery or authority capability for which no current provider result exists
- **THEN** FlowGuard SHALL report the exact missing capability as a blueprint gap
- **AND** it SHALL NOT replace the missing provider with inferred shallow success

#### Scenario: Provider result targets another revision
- **WHEN** a supplied provider result names a different target or subject revision
- **THEN** FlowGuard SHALL reject it as stale or mismatched for the current blueprint

### Requirement: Blueprint readiness follows one ordered chain
FlowGuard SHALL calculate evidence qualification, static blueprint readiness, and task admission as distinct ordered results.

#### Scenario: Evidence qualifies but static blueprint has gaps
- **WHEN** inventories and identities qualify but a required semantic, portable, helper, resource, intent, or test binding is incomplete
- **THEN** evidence qualification MAY be complete
- **AND** static blueprint readiness SHALL remain incomplete or blocked
- **AND** a whole-target DNA claim SHALL remain unavailable

#### Scenario: Scoped task does not require whole-target readiness
- **WHEN** an affected-only task has current evidence for its complete affected neighborhood while unrelated whole-target gaps remain
- **THEN** task admission MAY allow only that declared scope
- **AND** the result SHALL continue to report the broader blueprint gaps

### Requirement: Every behavior has an implementation-independent contract
Every behavior block required by the declared boundary SHALL bind exact implementation surfaces, source-independent semantic rules, portable model and transition identities, field mappings, assumptions, guarantees, invariants, protected failure boundaries, and applicable or typed-not-applicable behavior dimensions.

#### Scenario: Owner text is copied to several behaviors
- **WHEN** multiple behavior blocks reuse generic owner text without an explicit shared rule, exact applicability rows, and independent provenance
- **THEN** those behavior blocks SHALL remain incomplete

#### Scenario: Portable binding is stale
- **WHEN** a behavior block cites a portable model, transition, property, or field mapping whose fingerprint no longer matches current authority
- **THEN** the exact behavior block and binding SHALL be reported stale

### Requirement: Supporting surfaces require evidence-bound ownership
A supporting surface SHALL close only through one or more explicit ownership edges whose kinds and current evidence establish how it calls, delegates, reads for, or writes for exact behavior blocks. Sorting order, lexical similarity, or shared owner identity SHALL NOT select a behavior owner.

#### Scenario: Helper has two possible owners
- **WHEN** a helper can be associated with multiple behavior blocks but no current evidence distinguishes the relation
- **THEN** FlowGuard SHALL report ambiguous supporting ownership
- **AND** it SHALL NOT choose the first behavior block

### Requirement: Test coverage binds real members and cases
Static blueprint readiness SHALL require every formal coverage edge to reference an existing behavior block, implementation surface, test node or native check, concrete case, oracle member, oracle identity, and covered dimensions. Test design and execution evidence SHALL be stored and reported separately.

#### Scenario: Synthetic identifiers imitate a real test
- **WHEN** a coverage row names a generated placeholder test, assertion, or universal case that is absent from the current test inventory
- **THEN** the row SHALL NOT satisfy static blueprint coverage

#### Scenario: Current test has not run in this cycle
- **WHEN** a real current test, case, and oracle edge exists but no current execution receipt exists
- **THEN** static test design MAY be complete
- **AND** execution status SHALL remain `not_run`

### Requirement: Compact understanding is an affected projection
FlowGuard SHALL expose a read-only compact summary containing the exact blueprint identity, layer statuses, deepest proven layer, first gap, gap count, and affected surface ids. Ordinary affected-only queries SHALL NOT require loading the whole blueprint.

#### Scenario: AI asks whether it understands enough
- **WHEN** an AI requests task admission for an affected scope
- **THEN** FlowGuard SHALL return the compact affected summary and exact unresolved boundary
- **AND** it SHALL NOT replace the result with a self-authored confidence statement

### Requirement: Provider qualification is externally frozen
The canonical target-system compiler SHALL consume a frozen provider registry, exact provider results, and one target snapshot whose identities are established before readiness aggregation. A provider result SHALL NOT create or replace the registry or snapshot that certifies that same result.

#### Scenario: Provider output changes after freeze
- **WHEN** a provider payload changes after the registry and target snapshot are frozen
- **THEN** the compiler SHALL report the exact provider identity as stale or mismatched
- **AND** it SHALL NOT rebuild authority inside the consumer step to restore success

#### Scenario: Provider kind or version is fabricated by the compiler
- **WHEN** a result omits its real provider kind or version
- **THEN** qualification SHALL be blocked
- **AND** a provider id or generic current label SHALL NOT substitute for the missing identity

### Requirement: The public target route derives readiness from native artifacts
The public target-system qualification entry SHALL accept only a strict current descriptor, frozen provider evidence, a native observation/authority report set, and an explicit scope. The entry SHALL derive every layer status and gap mechanically and SHALL NOT accept caller-authored layer status, gap, admission, or report rows.

#### Scenario: Caller injects a passing downstream layer
- **WHEN** a public request supplies `downstream_layers`, a pass status, an admission flag, or an arbitrary gap list
- **THEN** the request SHALL be rejected as non-current input
- **AND** the lower-level compiler API SHALL NOT make those fields a public qualification authority

#### Scenario: Native artifacts expose a semantic mismatch
- **WHEN** the observation and authority artifacts are current but their portable behavior refinement fails
- **THEN** the public route SHALL derive the semantic or workflow-transition gap
- **AND** the caller SHALL NOT be able to replace that result with a passing layer row

### Requirement: Core provider payloads are target-neutral
The target-system core SHALL accept typed observation, authority, implementation, test, resource, intent, and workflow results without requiring Python modules, symbols, paths, pytest ids, or another language-specific field. Language and workflow adapters SHALL declare their own capability and payload boundary.

#### Scenario: Non-Python provider supplies current surfaces
- **WHEN** a current provider uses non-Python surface ids and supplies every core-required identity and contract
- **THEN** the target-system compiler SHALL evaluate it through the same canonical layers
- **AND** Python-only fields SHALL NOT be required

#### Scenario: Required adapter is absent
- **WHEN** an exact target boundary requires observation capability for which no provider is registered
- **THEN** the compiler SHALL report that capability and boundary as missing
- **AND** zero discovered rows SHALL NOT be interpreted as a complete empty target

### Requirement: The frozen layer plan matches the target profile
Every whole-target compilation SHALL consume one exact frozen layer plan whose profile, ordered layer ids, claim boundary, and fingerprint match the target descriptor. The compiler SHALL evaluate the supplied plan rather than silently applying a software-only global layer list.

#### Scenario: A software target uses the canonical software plan
- **WHEN** the target profile is software
- **THEN** the frozen plan SHALL include the current software inventory, behavior, topology, model-code-test, resource, intent, and qualification layers in their declared order
- **AND** omitting a required software layer SHALL block the ordered prefix

#### Scenario: A non-code workflow uses its own real layers
- **WHEN** the target profile is a non-code workflow
- **THEN** its frozen plan MAY consist of workflow boundary, actors declared by that workflow, inputs, states, transitions, outputs, resources, intent, and verification layers
- **AND** it SHALL NOT need fabricated implementation-inventory, Python, or model-code-test pass rows

#### Scenario: A workflow is evaluated with a fabricated software plan
- **WHEN** the target descriptor and layer-plan profile differ or the supplied rows include undeclared substitute layers
- **THEN** qualification SHALL fail with the exact profile or layer mismatch
- **AND** extra passing rows SHALL NOT repair the mismatch

#### Scenario: A profile plan removes or reorders canonical layers
- **WHEN** a frozen software or workflow plan has the expected profile name but removes, reorders, renames, or substitutes a canonical layer
- **THEN** qualification SHALL fail against the registered canonical plan fingerprint
- **AND** a one-layer plan SHALL NOT qualify an implementation or whole target

### Requirement: Native behavior qualification is executable and boundary-bound
Every native report set SHALL bind the exact descriptor, target boundary, subject revision, and frozen provider evidence. Each observed and authority portable model SHALL pass its own structural, safety, progress, and temporal checks before refinement can support readiness. Every behavior or workflow transition member SHALL bind exact portable transition ids, and every supporting member relation SHALL point to an existing behavior in its own observation or authority denominator.

#### Scenario: A safe-looking refinement hides an unsafe model
- **WHEN** either portable model reaches a state forbidden by its own invariant or violates a declared temporal obligation
- **THEN** native qualification SHALL fail even if the observation-to-authority refinement otherwise passes

#### Scenario: A native report is replayed across a changed boundary
- **WHEN** its descriptor, boundary, or frozen-evidence fingerprint differs from the current target
- **THEN** evidence qualification SHALL be stale or blocked
- **AND** matching model/member names SHALL NOT restore success

#### Scenario: A behavior is not tied to the portable model
- **WHEN** a behavior has no exact model-transition binding, names an unknown transition, or a supporting member names an unknown behavior
- **THEN** the corresponding semantic, workflow, traceability, test, resource, or intent layer SHALL be incomplete or blocked

### Requirement: Blueprint success consumes every required native report
The canonical success result SHALL be true only when the complete ordered layer prefix reaches `static_blueprint` and every required binding, topology, resource, intent, behavior, and model-test report is current and passing.

#### Scenario: Inventory qualifies while model-test alignment fails
- **WHEN** inventory and target qualification pass but model-test alignment contains a blocker
- **THEN** the overall blueprint success result SHALL be false
- **AND** the passing lower layers and exact alignment gap SHALL remain visible

### Requirement: Parent-child closure uses real interface contracts
Every parent-child or producer-consumer edge used by blueprint topology SHALL bind exact current input classes, output classes, state/effect ownership, schema or portable-refinement identity, and the producer and consumer evidence that established the handoff.

#### Scenario: Child advertises a matching fingerprint but incompatible output
- **WHEN** a child fingerprint is current but its emitted output or schema is not accepted by the parent input contract
- **THEN** reattachment and static blueprint readiness SHALL be blocked

#### Scenario: Interface cycle lacks progress or termination evidence
- **WHEN** model handoffs form a reachable cycle with no repair token, progress rule, blocker, or finite bound
- **THEN** topology closure SHALL report the cycle and SHALL NOT qualify the parent

### Requirement: Completeness uses an independently observed denominator
Target completeness SHALL compare declared owners and bindings with an independently observed inventory of files, surfaces, transitions, workflow steps, test nodes, resources, and other boundary members applicable to the target kind.

#### Scenario: Declared inventory omits an observed behavior owner
- **WHEN** an observed behavior-bearing surface or workflow step is absent from the declared model and binding rows
- **THEN** inventory or traceability SHALL report the exact omitted member
- **AND** shrinking the declared set SHALL NOT make the target complete

### Requirement: Frozen provider payloads match the current native compilation
When a project convenience route qualifies frozen provider evidence, FlowGuard SHALL independently rederive the canonical provider results from the exact current preparation and compare provider identity, capability bindings, inputs, payloads, status, findings, and result fingerprints before readiness can advance.

#### Scenario: Counterfeit payload is internally refrozen
- **WHEN** a caller changes one provider payload, rebuilds the snapshot and receipt consistently, and presents that bundle beside an unchanged current project preparation
- **THEN** evidence qualification SHALL report the exact provider/capability divergence as stale or blocked
- **AND** internal consistency of the counterfeit bundle SHALL NOT license readiness

### Requirement: Semantic mesh identity is derived from reviewed topology
The semantic mesh content fingerprint used by a software blueprint SHALL be derived from the canonical reviewed topology content, including nodes, relations, refinements, reattachments, and their current evidence closure. A caller-supplied label or unrelated fingerprint SHALL NOT become mesh authority.

#### Scenario: Mesh fingerprint changes while topology does not
- **WHEN** the same reviewed topology is paired with a different caller-selected semantic mesh fingerprint
- **THEN** qualification SHALL reject the identity mismatch or normalize to the canonical topology-derived fingerprint
- **AND** the manifest SHALL NOT publish the caller-selected fingerprint as current topology evidence

### Requirement: Raw manifests are not an alternate blueprint authority
Whole-target or software-blueprint qualification SHALL enter through the canonical target-system compiler or its project convenience preset. A raw manifest plus caller-repeated current labels SHALL NOT independently produce a complete blueprint claim. Deterministic export SHALL consume the typed result of that canonical project/target chain, including its exact readiness status and gaps.

The project preset's compiler-owned static-manifest consistency report SHALL
remain one bounded child input. Its complete status SHALL NOT establish
whole-target readiness, sufficient understanding, executed evidence,
implementation admission, or release readiness.

#### Scenario: Caller repeats one arbitrary mesh fingerprint
- **WHEN** a raw manifest and a command argument contain the same caller-selected semantic mesh fingerprint without a reviewed current topology and provider chain
- **THEN** no public check or export SHALL report blueprint completion
- **AND** the caller SHALL use the canonical target/project qualification entry

#### Scenario: Canonically assembled project is exported
- **WHEN** the canonical project chain has produced every typed blueprint layer and the caller explicitly requests a bounded export
- **THEN** the export SHALL materialize the deterministic projection, including incomplete, stale, blocked, or not-run status where present
- **AND** export completion SHALL NOT be reported as model-completeness success or requalify a second raw-manifest authority

### Requirement: Project documents carry exact intent authority
The strict project blueprint document SHALL carry the complete typed intent inventory used by behavior, resource, and readiness review, including source kind, source and owner identity, expectation identity, target bindings, current fingerprints, provider capability, terminal disposition, the independently observed complete model-owner denominator, and any evidence-bound no-intent rationale. Loading the document SHALL rederive and verify the canonical intent-review fingerprint. Adding the required model-owner denominator SHALL advance both the intent-inventory schema and the enclosing project-document schema; the loader SHALL reject the former parent or child schema rather than reinterpret it, infer the denominator, or invoke a compatibility reader.

#### Scenario: Intent is supplied only beside the project document
- **WHEN** a caller supplies intent rows as an optional runtime argument but the strict project document does not contain them
- **THEN** whole-project qualification SHALL remain incomplete or reject the non-current document
- **AND** the optional argument SHALL NOT become a second intent authority

#### Scenario: Former project document omits the model-owner denominator
- **WHEN** a document uses the former project-document schema or embeds the former intent-inventory schema without `required_model_target_ids`
- **THEN** strict loading fails visibly before project qualification
- **AND** the loader SHALL NOT infer the denominator from the contributions, behaviors, manifest, or a root fallback

#### Scenario: Current project document round-trips exact intent ownership
- **WHEN** a current document embeds intent-inventory v5 and the complete required model-owner denominator
- **THEN** strict loading rederives the same intent-review, inventory, and enclosing document fingerprints
- **AND** every model-owner identity remains explicit after round-trip serialization

### Requirement: Canonical project export preserves every blueprint layer
The canonical project export SHALL bind the complete project-bundle fingerprint and emit deterministic content-addressed projections for project identity and definition, frozen provider evidence, independent implementation and test inventories, implementation audit, model/code bindings, source-independent semantics and oracles, behavior blocks and cases, parent-child topology and interfaces, resources, intent lineage, normalized and affected indexes, shared objects, and all readiness/depth/gap results.

#### Scenario: One layer is omitted from export
- **WHEN** an export lacks any required canonical projection kind or emits a shard whose fingerprint is not referenced by the manifest
- **THEN** export verification SHALL fail
- **AND** the smaller projection SHALL NOT be described as the portable project blueprint

#### Scenario: A partial model is exported for later growth
- **WHEN** every canonical layer is representable but readiness still contains declared gaps or not-run execution evidence
- **THEN** explicit export MAY succeed and SHALL preserve those exact statuses and gaps
- **AND** export success SHALL describe materialization only, not sufficient whole-target understanding

### Requirement: Canonical target export preserves the exact audited target
The provider-neutral target export SHALL load the same strict descriptor,
frozen provider evidence, and complete native report set as target audit,
invoke the same native qualifier, and mechanically project those typed inputs
and that exact qualification/readiness result through the existing
`CanonicalBlueprintProjection`, `BlueprintShard`, writer, and verifier. It SHALL
NOT define a second envelope, raw-manifest authority, status input, gap input,
or compatibility alias.

#### Scenario: TypeScript software or a non-code workflow is exported
- **WHEN** either target supplies its exact strict descriptor, frozen evidence, and native report set
- **THEN** export SHALL preserve the target profile and layer plan, observed and authority portable models, typed input/state/output and implementation or external-owner bindings, tests or verification, resources, intent, topology, receipts, and qualification/readiness identities
- **AND** no Python-specific field SHALL be required by the projection kernel

#### Scenario: Audit and export consume the same frozen artifacts
- **WHEN** audit and export receive byte-identical strict artifacts
- **THEN** the qualification fingerprint stored by export SHALL equal the audit report fingerprint
- **AND** repeated exports SHALL produce the same manifest, shard paths, shard bytes, and projection fingerprint

#### Scenario: The audited target remains blocked or execution is not run
- **WHEN** qualification contains `blocked`, `incomplete`, `stale`, or `not_run` evidence while every canonical export object remains representable
- **THEN** materialization MAY succeed and SHALL preserve those exact states and gaps
- **AND** `materialization_ok`, `materialization_status`, and `model_readiness_status` SHALL remain separate

#### Scenario: Export input or materialized content is invalid
- **WHEN** a strict input fingerprint is tampered, an artifact or shard is missing, the target profile differs, the frozen plan is non-canonical, or a materialized shard changes
- **THEN** strict loading, qualification, or projection verification SHALL fail or retain the exact blocked readiness gap at its native boundary
- **AND** no successful materialization SHALL hide the failure

#### Scenario: Content addressing is valid but target identity was rewritten
- **WHEN** an identity shard and manifest are changed and re-fingerprinted so the generic projection verifier remains green
- **THEN** the target-owned materialization verifier SHALL compare all exact target shards with a projection rebuilt from the descriptor, frozen evidence, native reports, and compiler qualification
- **AND** materialization SHALL remain blocked because generic directory and content integrity does not prove target identity or sufficient understanding

#### Scenario: Projection activation races with another writer
- **WHEN** the old projection was moved aside but activation fails or the output path is recreated before activation completes
- **THEN** the old exact projection SHALL be restored or preserved without deleting its backup
- **AND** extra files, empty directories, symlinks, junctions, other reparse points, and changes between validation and swap SHALL fail exact-tree validation
- **AND** failure to remove an obsolete backup after successful activation SHALL not report the activation itself as failed

### Requirement: One model owner preserves block-local child contracts
When one model owner governs several independently observed behavior surfaces, FlowGuard SHALL preserve each surface as its own behavior block with an exact portable binding, one good case, one boundary case, and only the protected-failure cases explicitly scoped to that surface. The owner-level model identity and shared semantics SHALL remain the parent authority and SHALL NOT substitute for any child's input, output, state, effect, implementation, model-member, failure, case, coverage owner, or execution binding. A module or class aggregate SHALL NOT become an independent behavior block solely because it contains those children or matches the owner path.

#### Scenario: One owner governs two different function shapes
- **WHEN** one model owner governs two behavior surfaces with different input, output, or state fields
- **THEN** each behavior block SHALL carry a portable binding whose fields exactly match that surface
- **AND** neither block SHALL inherit the other block's field mapping

#### Scenario: Sibling block cases are present
- **WHEN** an owner declares cases for two valid sibling behavior blocks
- **THEN** FlowGuard SHALL partition and evaluate the cases by their exact behavior block
- **AND** a case belonging to one sibling SHALL NOT be rejected merely because another sibling is being evaluated

#### Scenario: Case targets an unowned block
- **WHEN** an owner's case names a behavior block outside the owner's independently observed behavior surface set
- **THEN** FlowGuard SHALL reject the declaration as an ownership-boundary violation
- **AND** filtering the case out SHALL NOT restore readiness

#### Scenario: Parent failure has one exact child edge
- **WHEN** an owner has several behavior surfaces and one protected failure is explicitly bound to one surface
- **THEN** only that surface SHALL carry the failure member and corresponding bad case
- **AND** sharing the owner SHALL NOT copy the failure to sibling surfaces
- **AND** a parent test result or receipt SHALL NOT be copied as sibling execution evidence

#### Scenario: Parent model exposes a composite behavior surface
- **WHEN** a provider supplies one exact observed composite surface with an independent input, state/effect, output, completion, and semantic contract for the owner-level workflow
- **THEN** parent transitions and protected failures MAY bind to that composite block
- **AND** detailed child blocks SHALL remain separately bound without inheriting the composite member set

#### Scenario: Module or class merely contains child behavior
- **WHEN** a module or class matches an owner path or contains behavior-bearing functions but has no independent observed composite contract
- **THEN** the aggregate SHALL remain a supporting surface bound to the exact model owner
- **AND** FlowGuard SHALL NOT fabricate an aggregate behavior block, cases, failures, coverage, or execution evidence

### Requirement: The complete implementation map distinguishes behavior from support
FlowGuard SHALL retain every independently discovered current implementation surface in the target code map while requiring independent behavior contracts only for surfaces classified by the active observation provider as callable behavior, entrypoints, state/effect/dynamic writers, or explicit workflow transitions. A supporting disposition SHALL preserve one exact behavior/model owner and SHALL NOT remove the surface from the DNA.

#### Scenario: Structural helper remains in the DNA
- **WHEN** an observation provider discovers a module, class, nested function, or pure private helper that is not independently behavior-bearing
- **THEN** the surface SHALL remain in the implementation inventory with one exact supporting owner relation
- **AND** FlowGuard SHALL NOT fabricate a separate good, boundary, and bad case set merely because the structural surface exists

#### Scenario: Hidden writer cannot be demoted for size
- **WHEN** a private or nested surface performs an observed state write, external effect, dynamic dispatch, entry transition, or other provider-declared behavior
- **THEN** it SHALL remain in the behavior denominator
- **AND** a size or performance limit SHALL NOT authorize demotion to supporting

### Requirement: Target topology separates structural and cross-boundary parents
Every target-topology node SHALL expose one `structural_parent_id` and an independently ordered set of `cross_boundary_parent_ids`. The sole topology root SHALL use the declared root sentinel for `structural_parent_id`; every other in-scope node SHALL name exactly one current structural parent. Consumer, feedback, retry, repair, shared-resource, and other cross-boundary relations SHALL be represented through `cross_boundary_parent_ids` or their typed relation records and SHALL NOT create, replace, or multiply structural parentage.

#### Scenario: Non-root node has two structural parents
- **WHEN** one non-root topology node names two structural parents or its structural relation set resolves to more than one parent
- **THEN** target-topology qualification SHALL be blocked with the exact node and competing parent identities
- **AND** moving either parent to an untyped relation SHALL NOT restore readiness

#### Scenario: Cross-boundary consumer points to an ancestor
- **WHEN** a child model also consumes an output from an ancestor or another branch
- **THEN** that owner SHALL appear as a typed cross-boundary parent or relation
- **AND** the child's sole `structural_parent_id` SHALL remain unchanged
- **AND** the cross-boundary relation SHALL NOT become a structural cycle

#### Scenario: Structural parent is omitted
- **WHEN** a non-root node has only cross-boundary parents and no exact current structural parent
- **THEN** target-topology qualification SHALL report an orphan structural node
- **AND** cross-boundary connectivity SHALL NOT substitute for hierarchy closure

### Requirement: Provider-neutral blueprints carry exact path-quality subjects
A target-system blueprint SHALL bind each required behavior model to its compact path-quality subject identity, conclusion, trigger state, unresolved ids, and detailed-evidence fingerprint without assuming a programming language or provider. Parent blocks SHALL consume compact child summaries and exact interface identities rather than duplicate deep candidate payloads.

#### Scenario: Non-code workflow is modeled
- **WHEN** the target is a process, service graph, configuration workflow, or non-Python system
- **THEN** its path-quality rows use the same state, transition, input, output, effect, error, interface, obligation, and evidence semantics without requiring source-language-specific fields

#### Scenario: Child summary is stale
- **WHEN** a child path-quality subject or interface identity changes
- **THEN** the consuming parent summary and affected blueprint readiness become stale
