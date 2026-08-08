## ADDED Requirements

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
The strict project blueprint document SHALL carry the complete typed intent inventory used by behavior, resource, and readiness review, including source kind, source and owner identity, expectation identity, target bindings, current fingerprints, provider capability, terminal disposition, and any evidence-bound no-intent rationale. Loading the document SHALL rederive and verify the canonical intent-review fingerprint.

#### Scenario: Intent is supplied only beside the project document
- **WHEN** a caller supplies intent rows as an optional runtime argument but the strict project document does not contain them
- **THEN** whole-project qualification SHALL remain incomplete or reject the non-current document
- **AND** the optional argument SHALL NOT become a second intent authority

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
