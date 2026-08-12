# authoritative-model-system Specification

## Purpose
Define the sole project-level authority that identifies which exact model
system describes the software that exists now. The capability separates
observed implementation, normative target, and counterfactual experiment
snapshots; binds them to exact source, model, relation, coverage, and evidence
identities; and prevents a proposed or locally green model from being reported
as the current software model.
## Requirements
### Requirement: Model-system snapshots declare one subject lane
Every model-system snapshot SHALL declare exactly one subject lane:
`observed_implementation`, `normative_target`, or
`counterfactual_experiment`. The subject lane SHALL remain independent from
the snapshot lifecycle, and neither lifecycle labels nor validation success
SHALL change which subject the snapshot describes.

#### Scenario: Observed snapshot describes a concrete software revision
- **WHEN** a snapshot declares the `observed_implementation` subject lane
- **THEN** it identifies the exact source or deployment revision whose behavior
  it describes
- **AND** its observed status is derived from the project authority pointer and
  current evidence rather than from an editable current flag

#### Scenario: Target and experiment remain non-current
- **WHEN** a `normative_target` or `counterfactual_experiment` snapshot passes
  all of its declared checks
- **THEN** the snapshot remains non-authoritative for the software that exists
  now
- **AND** it is reported as target or experimental context rather than as the
  current observed system

### Requirement: A project has one observed model-system head
The project SHALL expose exactly one model-authority pointer for the current
`observed_implementation` snapshot. The pointer SHALL identify the snapshot by
content fingerprint and subject revision, and no registry label, file
discovery result, model-id suffix, target snapshot, experiment snapshot, or
alternate pointer SHALL act as a fallback current authority.

#### Scenario: Current-model lookup resolves the sole observed head
- **WHEN** a consumer asks which model system describes the software now
- **THEN** the system resolves and validates the project model-authority
  pointer before performing relevance lookup
- **AND** only active members of that observed snapshot are eligible as current
  model owners

#### Scenario: Missing or invalid head fails visibly
- **WHEN** the project model-authority pointer is missing, ambiguous, refers to
  a non-observed lane, or does not match the referenced snapshot fingerprint
- **THEN** current-model lookup reports observed authority as unavailable
- **AND** it does not infer a replacement from discovered files, registry
  entries, lexical matches, or historical evidence

### Requirement: Model-system snapshots are immutable and content-addressed
A model-system snapshot SHALL be an immutable, canonical, content-addressed
record. Its fingerprint SHALL cover its subject lane, subject revision,
coverage universe, model-instance references, typed relations, native-owner
references, evidence references, unresolved rows, and claim boundary.

#### Scenario: Snapshot content changes
- **WHEN** any fingerprinted snapshot member, relation, coverage row, evidence
  reference, unresolved row, or claim boundary changes
- **THEN** the system creates a new snapshot with a new fingerprint
- **AND** the previous snapshot remains unchanged and addressable

#### Scenario: Referenced content does not match
- **WHEN** a snapshot reference resolves to content whose fingerprint differs
  from the recorded fingerprint
- **THEN** the snapshot is invalid for lookup, activation, reuse, and coverage
  claims

### Requirement: Model instances have exact immutable identities
Every model instance in a snapshot SHALL bind a stable logical model id and
model kind to the exact model content, runner content, purpose closure,
subject source revision, and resolved input inventory that it represents.
Mutable names such as a `:current` suffix SHALL NOT establish instance identity
or authority.

#### Scenario: Input selector resolves to concrete files
- **WHEN** a runner uses a pattern or selector to choose model inputs
- **THEN** the model-instance identity and its evidence record the resolved
  paths and content hashes
- **AND** a later change to that resolved inventory produces a different
  instance or makes the prior evidence stale

#### Scenario: Mutable current name conflicts with observed membership
- **WHEN** a discovered model uses a current-looking name but its immutable
  instance fingerprint is not an active member of the observed snapshot
- **THEN** the model is reported as non-authoritative candidate or drift
- **AND** it is not selected as a current owner

### Requirement: Local intent sources are exact model inputs
Every active `project_file` intent contribution SHALL have one exact owner-local source-path binding on its declared logical model. The binding SHALL participate in that model instance's resolved immutable input inventory and focused validation contract. For each model owner, the bound path set SHALL equal the active local intent-source set for that owner: missing, extra, duplicate, unsafe, unresolved, or foreign-owner paths SHALL block candidate construction and current-authority audit. A broad input selector, matching text, shared source file, or system-level stale finding SHALL NOT substitute for the exact owner-local binding.

#### Scenario: One model's local design source changes
- **WHEN** an active local intent source changes after the observed snapshot was accepted
- **THEN** fresh model observation changes the exact input identity of every logical model owner that declares that source
- **AND** affected-owner planning selects those models without treating unrelated models as changed

#### Scenario: Active local contribution has no owner-local input
- **WHEN** a current or candidate project-file contribution names a logical model but that model does not declare the exact source path
- **THEN** revision construction and current-authority audit block with the missing owner/source pair
- **AND** a broad glob, root owner, or inferred textual match cannot close the binding

#### Scenario: Model keeps an unused historical intent path
- **WHEN** a model declares an intent-source path that no active project-file contribution for that exact owner uses
- **THEN** current binding review reports the extra path and remains blocked
- **AND** the path must be deliberately removed instead of accumulating as a historical fallback input

#### Scenario: Several models consume one design source
- **WHEN** one local source legitimately informs several logical models
- **THEN** every model declares its own exact path binding and includes the same file identity in its own input inventory
- **AND** the shared file does not create a shared primary model owner

#### Scenario: Intent comes from WorkContext
- **WHEN** an active contribution is owned by a declared external WorkContext artifact
- **THEN** its exact context, native owner, source reference, and artifact fingerprint remain bound through the cumulative current-intent view
- **AND** FlowGuard does not convert the external artifact into a repository path or require a particular programming language or provider

### Requirement: Snapshots connect existing owners through typed references
A snapshot SHALL connect model instances and existing governance artifacts
through declared typed relations. Supported relation meanings SHALL include
containment, refinement, dependency, delegation, consumption, production,
realization, supersession, validation, and shared-kernel association. A
relation SHALL NOT transfer the native validation responsibility of the
referenced commitment, field, side effect, contract, test, hierarchy, or
process owner.

#### Scenario: Cross-owner relation is evaluated
- **WHEN** a snapshot relates a model instance to a commitment, field
  inventory, code contract, test obligation, or parent closure
- **THEN** the relation identifies both endpoints, its declared type, and the
  exact referenced fingerprints
- **AND** current evidence from the native owner remains required

#### Scenario: Shared kernel does not prove replacement
- **WHEN** two instances declare a shared-kernel or other similarity relation
- **THEN** the relation alone does not authorize deletion, substitution,
  authority transfer, or evidence reuse

### Requirement: Coverage claims use a finite fingerprinted universe
Every broad model-system coverage claim SHALL name a finite, immutable
coverage universe derived from the live model regression manifest and its
currently resolved source inventory. The universe SHALL independently
enumerate required ids for external API, CLI, UI, schema or file, skill or
agent, and documented surfaces; active behavior commitments; model instances
and system properties; behavior-bearing fields, state, and side effects; code
contracts; tests; and evidence obligations. A stored snapshot's previously
recorded universe SHALL NOT substitute for rebuilding this live universe at a
currentness gate.

#### Scenario: Complete bounded coverage is proven
- **WHEN** a snapshot claims `complete_within_declared_boundary`
- **THEN** the live required ids and snapshot covered ids are equal in every
  declared coverage dimension
- **AND** every referenced evidence obligation is current and passing
- **AND** the claim identifies the live coverage-universe fingerprint and
  boundary

#### Scenario: Coverage has an unresolved or stale row
- **WHEN** any live required id is missing, unknown, excluded without an
  accepted disposition, stale, blocked, skipped, or not run
- **THEN** the system keeps that row visible
- **AND** it reports bounded partial coverage rather than complete coverage

#### Scenario: No finite universe is declared
- **WHEN** a snapshot has no finite fingerprinted coverage universe derived
  from the live manifest and current source inventory
- **THEN** the system rejects claims of full software coverage
- **AND** it may report only the explicitly evidenced local scope

#### Scenario: Stored universe omits a newly available required model
- **WHEN** the live regression manifest and current source inventory resolve a
  required model instance that is absent from the observed snapshot
- **THEN** authority audit reports `observed_source_inventory_stale`
- **AND** the stored snapshot's internally complete coverage rows do not
  satisfy current coverage

### Requirement: Observed authority remains revision truthful
An observed snapshot SHALL be current only while a fresh live re-observation and derivation from the model regression manifest and current source inventory exactly matches the observed head's subject revision, model-instance identities, resolved input inventories, required source-surface identities and fingerprints, referenced owner-artifact identities, coverage-universe fingerprint, and required evidence. Pointer-to-snapshot self-consistency SHALL be necessary but SHALL NOT be sufficient for a current authority result.

#### Scenario: Live inventory exactly matches the observed snapshot
- **WHEN** authority audit re-derives the current source and model inventory
- **AND** every required live identity and fingerprint exactly equals the corresponding observed-snapshot identity and fingerprint
- **THEN** the observed head may remain current subject to its native evidence gates
- **AND** the audit records the re-derived live-inventory fingerprint used for reconciliation

#### Scenario: Software changes without a matching observed snapshot
- **WHEN** source, deployment, configuration, a required source surface, an owner artifact, or another fingerprinted implementation input changes after the observed snapshot was validated
- **THEN** the system reports the observed authority as stale or blocked
- **AND** it does not relabel an existing target or experiment as observed

#### Scenario: Stored authority is internally consistent but live inventory differs
- **WHEN** the project pointer, stored snapshot fingerprint, stored subject revision, and stored coverage status agree with one another
- **AND** a fresh live re-observation has a different subject revision, model-instance set, source-surface set, owner-artifact fingerprint, resolved input inventory, or coverage fingerprint
- **THEN** authority audit reports `observed_source_inventory_stale`
- **AND** project audit, preflight, activation, release, and broad model coverage claims remain blocked until one accepted `ModelRevisionSet` updates the observed head

#### Scenario: A target is implemented
- **WHEN** implementation work realizes a validated normative target
- **THEN** the system builds and validates a new `observed_implementation` snapshot from the resulting live source inventory
- **AND** it links the new observed snapshot to the target through typed realization and supersession relations instead of changing the target's subject lane

<<<<<<< HEAD
### Requirement: Published observed authority is reproducible from the release tree
The release verifier SHALL require every file in the selected snapshot's resolved model input inventory to be reachable from the exact committed source tree when a project publishes an observed model-system head. A local working-tree file, ignored file, untracked file, alternate checkout, or historical evidence artifact SHALL NOT satisfy release authority.
=======
### Requirement: Published observed authority is reconstructable from the release tree
The release verifier SHALL require every file in the selected snapshot's
resolved model input inventory to be reachable from the exact committed source
tree when a project publishes an observed model-system head. A local
working-tree file, ignored file, untracked file, alternate checkout, or
historical evidence artifact SHALL NOT satisfy release authority.
>>>>>>> agent/harden-currentness-validation

#### Scenario: Every authority input is committed
- **WHEN** release validation examines the selected observed snapshot
- **AND** the snapshot and every declared model input path resolve to the exact committed tree with matching content
- **THEN** the release may treat model-authority Git reachability as satisfied
- **AND** ordinary model currentness and evidence gates remain separately required

#### Scenario: Model input exists only in the local working tree
- **WHEN** the observed snapshot references a model file that exists locally but is ignored or untracked
- **THEN** release validation reports the exact missing path and blocks publication
- **AND** it does not drop that model from the live inventory or infer another authority

#### Scenario: Runner input exists only in the local working tree
<<<<<<< HEAD
- **WHEN** the observed snapshot references a runner input that is absent from the exact committed source tree
- **THEN** release validation reports the exact missing input and blocks publication
- **AND** local presence does not satisfy the published authority claim

### Requirement: Affected authority is relationship-complete
For an upgraded behavior surface, the authoritative model system SHALL identify its model owner, source owner, test or check owner, runtime entry when applicable, and explicit gaps; an inventory row alone SHALL NOT prove this relationship coverage.

#### Scenario: Model exists without a validating owner edge
- **WHEN** an affected model is inventoried but no current test/check owner or declared gap is attached
- **THEN** the authority audit reports incomplete affected coverage

### Requirement: Whole-system authority is semantic rather than inventory-only
A whole-system understanding claim SHALL be licensed only when every member of the finite current model universe has a semantic disposition and all required inter-model and consumer relations are current. Presence in the inventory alone SHALL NOT license the claim.

#### Scenario: All model files exist without consumer relations
- **WHEN** the finite universe contains every current model file but required consumer relations are absent
- **THEN** whole-system understanding remains unresolved

#### Scenario: Semantic relation changes after verification
- **WHEN** a model disposition or required relation changes after the whole-system receipt
- **THEN** every consuming whole-system claim becomes stale

### Requirement: Blueprint closure uses an independently discovered implementation universe
The authoritative model system SHALL consume fingerprinted implementation and resource inventories derived independently from declared models, code contracts, and tests before it licenses a whole-software blueprint claim. Every admitted inventory item SHALL have one explicit disposition, and unresolved files, parse failures, hidden state or effect writers, duplicate primary owners, and omitted required resources SHALL block static blueprint completion.

#### Scenario: Undeclared helper exists in production source
- **WHEN** independent discovery finds a behavior-bearing helper that is absent from the declared model and contract bindings
- **THEN** static blueprint closure is incomplete and identifies the helper

#### Scenario: Every admitted item has a current disposition
- **WHEN** the current inventory, bindings, resources, and owner fingerprints cover every item inside the declared boundary
- **THEN** the system may report static blueprint complete within that boundary

### Requirement: Blueprint projection remains derived from the sole observed authority
Any portable software-blueprint projection SHALL bind the exact current observed model-system snapshot and existing owner fingerprints. It SHALL NOT create another observed head, copy owner semantics into a competing authority, or remain current after a consumed owner changes.

#### Scenario: Observed snapshot changes after export
- **WHEN** the observed model-system snapshot changes after a blueprint projection is produced
- **THEN** the projection becomes stale until deterministically regenerated

### Requirement: Project-neutral blueprint qualification preserves one model authority
The authoritative model system SHALL qualify a software blueprint from one exact current `observed_implementation` snapshot plus independently identified implementation, semantic, test, resource, oracle, and intent-lineage evidence. The qualification SHALL remain a derived view and SHALL NOT create another model-system head, relabel a target as current, or let a project-specific preset own generic blueprint semantics.

#### Scenario: Another Python project requests blueprint qualification
- **WHEN** a Python project supplies a bounded project definition, a current observed model-system snapshot, and supported discovery inputs
- **THEN** FlowGuard qualifies the project through the project-neutral blueprint path
- **AND** no FlowGuard-repository preset or FlowGuard-specific owner is required for the generic result

#### Scenario: A target contribution is present
- **WHEN** a future-intent contribution describes a candidate behavior that is not implemented by the current observed source
- **THEN** the contribution remains attached to a non-current candidate revision in the same logical model lineage
- **AND** the current observed head remains unchanged

#### Scenario: A project-specific preset attempts to become authority
- **WHEN** a project preset supplies inventory or binding defaults for the generic builder
- **THEN** the resulting blueprint continues to derive authority from the exact observed snapshot and native evidence owners
- **AND** the preset cannot create an alternate model head or evidence owner

### Requirement: Blueprint depth is licensed one independent layer at a time
Blueprint qualification SHALL report the status of implementation inventory, traceability, independent semantics, model-code-test binding, resource/oracle closure, and static blueprint closure separately. It SHALL expose the deepest proven layer and the exact missing, stale, or blocked owner and evidence for every higher layer.

#### Scenario: Source scanning produced model and binding text
- **WHEN** the same production-source scan supplies an implementation surface, its claimed intended semantics, and its binding description without independent semantic evidence
- **THEN** inventory and traceability MAY pass
- **AND** independent-semantic and deeper blueprint layers remain incomplete

#### Scenario: One required evidence layer is stale
- **WHEN** model, semantic, code, test, resource, oracle, or intent-lineage evidence does not match the current consumed identity
- **THEN** the qualification reports the deepest lower layer that remains proven
- **AND** it names the stale layer, owner, subject, and fingerprint rather than collapsing the result into one broad boolean

#### Scenario: No discovery adapter supports a required source language
- **WHEN** the declared software boundary contains a behavior-bearing source for which no current discovery adapter is registered
- **THEN** static blueprint closure is blocked with the exact unsupported boundary member
- **AND** FlowGuard does not substitute a FlowGuard-specific fallback owner

### Requirement: Observed authority binds behavior-level blueprint evidence
The sole observed model-system authority SHALL reference the exact owner-level, behavior-block, resource, intent, test-binding, and canonical blueprint-readiness identities used for a self-qualification claim. A later layer SHALL NOT hide an earlier incomplete or stale layer.

#### Scenario: Current model snapshot points to an owner-level-only blueprint
- **WHEN** the observed snapshot is current but its behavior-block or readiness evidence is incomplete
- **THEN** observed model authority SHALL remain current for its declared model boundary
- **AND** the stronger software-DNA readiness claim SHALL remain incomplete

### Requirement: Observed authority binds target-system provider lineage
The sole observed model-system authority SHALL bind the exact target-system descriptor, provider-result identities, canonical intent inventory, behavior semantics, portable bindings, resource inventory, test inventory, and blueprint-readiness identity consumed by a broad DNA claim.

#### Scenario: Provider result changes after blueprint compilation
- **WHEN** a consumed provider input or result fingerprint changes after a blueprint was compiled
- **THEN** the affected blueprint layers and broad DNA claim SHALL become stale
- **AND** the observed model head SHALL remain truthful for its separately declared model boundary

### Requirement: Target kinds do not create alternate model heads
Composing software, workflow, service, agent, data-pipeline, or mixed target providers SHALL remain a derived projection of the current observed and target authorities. Target kind and provider selection SHALL NOT create a second observed model-system head.

#### Scenario: Workflow authority joins software observations
- **WHEN** a mixed target combines an observed software snapshot with an independently governed workflow contract
- **THEN** the blueprint SHALL preserve both authority identities and claim boundaries
- **AND** neither provider SHALL silently replace the observed model-system head

### Requirement: The affected authority inventory has one existing model-system owner
An affected authority inventory that binds governed source, runtime, and test
endpoints into the model-system snapshot, together with the inventory root that
owns its identity, SHALL be owned by the existing authoritative model-system
model for revision-evidence purposes. Neither route SHALL create a second
authority model, inherit a generic owner, or pass solely because the complete
model-regression parent is green.

#### Scenario: Inventory endpoints enter an affected revision closure
- **WHEN** a governed source, runtime, or test endpoint owned by the affected authority inventory enters the exact revision closure
- **THEN** its native-owner evidence SHALL consume the exact-current authoritative model-system child evidence
- **AND** missing or ambiguous inventory ownership SHALL block model-authority activation

#### Scenario: Inventory root identity changes
- **WHEN** the affected authority inventory root itself enters the exact revision closure
- **THEN** the root's authoritative model-system route SHALL consume the same exact-current authoritative model-system child evidence
- **AND** it SHALL NOT inherit the default model-mesh owner

### Requirement: Current topology evidence is independently produced and registered
Evidence used to activate or qualify the observed model-system head SHALL originate from an exact supervised terminal execution owned by the declared child or progress-contract evidence owner. A self-blueprint compiler, full model parent, ModelMesh consumer, or qualification call SHALL NOT generate, relabel, or register a passing current receipt for itself or for a child while evaluating the claim that consumes that receipt. Registration SHALL admit and verify an already terminal immutable receipt without launching or simulating its producer.

#### Scenario: Parent manufactures a child pass during aggregation
- **WHEN** the full model parent or blueprint compiler creates a passing child receipt or execution row inside the same aggregation that consumes it
- **THEN** observed authority SHALL reject the evidence as self-generated
- **AND** matching source, model, test, or snapshot fingerprints SHALL NOT make it independent

#### Scenario: Qualification registers its own current evidence
- **WHEN** a qualification or audit route executes, synthesizes, or rewrites an evidence result and registers that result as current before completing the same claim
- **THEN** registration and qualification SHALL be blocked
- **AND** the route SHALL require a separately supervised terminal producer receipt

#### Scenario: Existing terminal receipt is registered directly
- **WHEN** an immutable terminal receipt already names the exact producer owner, subject snapshot, covered child or progress contract, inputs, environment, result, and fingerprint
- **THEN** the authority store MAY verify and register that receipt without running its producer
- **AND** later parent aggregation SHALL consume the unchanged registered identity

### Requirement: Full model parent authority remains aggregation-only
The full model parent receipt SHALL prove only the declared aggregation over current child, reattachment, feedback-progress, and interface receipts. It SHALL NOT project its own terminal result onto a child, replace a missing child receipt, or become a second evidence producer for a child-owned obligation.

#### Scenario: Parent pass is reused as every child pass
- **WHEN** a full parent terminal receipt is assigned to two or more child obligations that lack their own terminal producer receipts
- **THEN** observed authority SHALL reject the child coverage and parent closure
- **AND** the full parent MAY remain only a failed or blocked aggregation result

### Requirement: Intentional model-owner retirement leaves a complete current authority
The authoritative model system SHALL accept removal of an obsolete model owner only when the current semantic mesh, software blueprint, behavior commitments, model regression manifest, code/test bindings, and observed authority all agree on the same reduced owner universe and preserve each migrated protection under a current owner.

#### Scenario: Obsolete self-model owner is retired
- **WHEN** an old model owner has no independent current responsibility and its retained obligations have exact current owners
- **THEN** the owner is absent from the current model universe and all current references
- **AND** historical archived evidence may remain explicitly non-current

#### Scenario: A current artifact still references the old owner
- **WHEN** any current mesh relation, blueprint block, commitment, regression child, code binding, test binding, intent contribution, or observed snapshot references the retired owner
- **THEN** authority construction and audit MUST fail with the dangling identity

### Requirement: Current self-model owners describe continuing software responsibility
The authoritative FlowGuard self-model universe SHALL contain only continuing current product, agent-operation, or development-process responsibilities. A model whose guarded purpose is bounded to one completed version, dated task, local-only request, or historical release operation SHALL be classified as historical and removed from current authority after every reusable protection and implementation responsibility has one exact current disposition.

#### Scenario: Dated task model remains in current DNA
- **WHEN** a current self-model owner is explicitly scoped to one completed release version, dated documentation task, or already-finished cleanup operation
- **AND** its reusable obligations are already owned by continuing current models
- **THEN** current authority construction MUST report the historical owner as unresolved until it is retired
- **AND** renaming the model or replacing its version literal does not satisfy the disposition

#### Scenario: Historical task model is retired completely
- **WHEN** every current protection, code/test binding, consumer, commitment, topology relation, and negative case has one exact continuing owner or explicit retirement disposition
- **THEN** the historical model and runner are absent from current manifest, mesh, blueprint, intent denominator, and observed authority
- **AND** immutable archived source, changelog, and old receipts remain non-current historical evidence

### Requirement: Current observed authority binds model path quality
Every new or materially changed model in current observed authority SHALL bind one current compact path-quality summary and detailed-evidence fingerprint from ModelMaturation. Observed authority SHALL remain faithful to current implementation behavior and SHALL NOT promote an unimplemented normative improvement.

#### Scenario: Changed model lacks a current summary
- **WHEN** a changed model has no current path-quality summary or has a stale or unresolved result for the claimed boundary
- **THEN** current authority activation fails for that affected model set
- **AND** no prior revision or parent result acts as fallback

#### Scenario: Whole-self qualification is explicitly requested
- **WHEN** FlowGuard explicitly qualifies its complete current self blueprint rather than an ordinary affected revision
- **THEN** the accepted authority SHALL bind one exact-current path-quality result for every current model owner under the same candidate snapshot
- **AND** changed-model-only coverage SHALL remain valid for ordinary revisions but SHALL NOT close the whole-self qualification claim

#### Scenario: Normative path is not observed
- **WHEN** a normative target proposes a different path that is not yet implemented and evidenced
- **THEN** current observed authority retains the implemented path and its current result

### Requirement: Model-revision evidence shares one bounded child closure
One model-revision evidence operation SHALL freeze the affected model set, mapped validation owners, exact-current child receipts, repository input manifest, and receipt inventory into one immutable invocation-local observation. All owner aggregates in that revision SHALL be derived from the same verified child closure, and the operation SHALL NOT reconstruct the complete closure independently for every owner aggregate.

#### Scenario: Six affected owners share current model children
- **WHEN** one revision requires six owner aggregates over overlapping exact-current model child receipts
- **THEN** every aggregate SHALL cite the same frozen observation identity and its own exact child subset
- **AND** each child SHALL be natively verified once for that frozen operation rather than once per consuming aggregate

#### Scenario: Two owners require different child subsets
- **WHEN** owner A and owner B consume different declared subsets of the frozen child closure
- **THEN** each aggregate SHALL preserve its own obligations, subject, and child identities
- **AND** sharing the observation SHALL NOT merge owners, copy one aggregate result to another, or widen either subset

### Requirement: Revision evidence receives one final fail-closed freshness check
Before a revision-evidence bundle can support candidate construction or observed-head activation, the system SHALL make one fresh observation of every frozen source, model, owner, receipt, dependency, toolchain, and environment identity. Matching identities authorize reuse of the already verified frozen closure; any difference SHALL block the bundle without patching individual aggregates in place.

#### Scenario: Source remains stable through bundle production
- **WHEN** the final observation exactly matches the frozen observation
- **THEN** the verified bundle MAY support candidate construction without repeating complete owner-closure collection or child semantic verification

#### Scenario: One governed source changes during bundle production
- **WHEN** any affected source identity differs at the final observation
- **THEN** the entire revision-evidence bundle SHALL be stale for activation
- **AND** unchanged sibling aggregates MAY remain historical evidence but SHALL NOT make the mixed bundle current

### Requirement: Frozen observation reuse cannot create model authority
An invocation-local observation SHALL be a transient verification input only. It SHALL NOT be persisted as a current model head, receipt alias, compatibility record, alternate owner store, or reusable cross-invocation success result.

#### Scenario: A later revision starts with the same repository content
- **WHEN** a second revision operation begins after the first operation has ended
- **THEN** the second operation SHALL create its own fresh frozen observation
- **AND** equality with the prior observation MAY explain reuse but SHALL NOT replace current receipt and owner verification
=======
- **WHEN** the model file is tracked but its snapshot-declared runner or another resolved input is ignored or untracked
- **THEN** the same authority-input reachability gate blocks publication
- **AND** a locally passing runner execution does not substitute for committed reachability
>>>>>>> agent/harden-currentness-validation
