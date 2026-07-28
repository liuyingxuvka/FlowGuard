# existing-model-preflight Specification

## Purpose
This capability defines FlowGuard's Existing Model Preflight behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: Existing modeled system changes are grounded in current models
FlowGuard guidance SHALL require Codex to ground non-trivial discussion,
analysis, proposal, feature, bug fix, refactor, UI flow change, test change,
prompt change, skill change, or agent-workflow change in existing FlowGuard
models before choosing a technical route when the work affects an existing
modeled system.

#### Scenario: Discussion uses a light model-grounding note
- **WHEN** a user asks whether or how to change behavior in an existing modeled
  system
- **THEN** Codex identifies the likely existing model boundary and reuse path
  before recommending a technical direction

#### Scenario: Trivial work skips the preflight
- **WHEN** the task is a typo, formatting-only edit, direct command answer,
  pure explanation, or greenfield work with no existing model context
- **THEN** Codex may skip existing-model preflight with a reason

### Requirement: A companion Codex skill performs existing-model preflight
The repository SHALL provide a directly invokable
`flowguard-existing-model-preflight` Codex skill. The skill SHALL be a peer
companion, not a replacement for downstream FlowGuard satellite skills.

#### Scenario: Implementation pairs preflight with a downstream route
- **WHEN** a task will implement, propose, or restructure behavior in an
  existing modeled system
- **THEN** Codex uses existing-model preflight to identify relevant model
  ownership and then selects the specific downstream FlowGuard route such as
  ModelMesh, StructureMesh, UI Flow Structure, Model-Miss Review, Model-Test
  Alignment, Code Structure Recommendation, or DevelopmentProcessFlow

### Requirement: Full preflight evidence is reviewable
FlowGuard SHALL expose a structured review helper for full existing-model
preflight reports. The helper SHALL block reports that claim preflight without
model search, ownership evidence, reuse/new-boundary rationale, or duplicate
risk handling.

#### Scenario: Full report blocks parallel ownership
- **WHEN** a preflight report proposes a new boundary that overlaps an existing
  state owner, side-effect owner, FunctionBlock, public entrypoint, or model
  responsibility without rationale
- **THEN** the review reports a blocking duplicate-risk finding

#### Scenario: No model found remains explicit
- **WHEN** no relevant FlowGuard model can be found
- **THEN** the report records `no_model_found` and explains the search path
  before allowing downstream route selection

### Requirement: Full preflight requires ownership evidence

Full Existing Model Preflight SHALL preserve enough existing model ownership
evidence for the downstream FlowGuard route to reuse, extend, add a child
model, or create a new boundary without duplicating responsibility.

#### Scenario: Parent model layered proof status is unknown
- **WHEN** a full preflight finds an existing model with child models
- **AND** the downstream route depends on parent/child confidence
- **THEN** the preflight MUST record parent coverage, child disjointness, child
  reattachment, leaf boundary-matrix status, and layered proof evidence id
- **AND** missing layered status MUST block the preflight from claiming that the
  existing boundary is fully understood

### Requirement: Project inventory can build existing-model preflight input
FlowGuard SHALL provide a project inventory helper that creates an
`ExistingModelPreflight` object from a project root, task summary, optional
changed paths, and optional downstream routes.

#### Scenario: Existing model files are found
- **WHEN** the project root contains FlowGuard model files or adoption records
  that mention model ownership
- **THEN** the helper SHALL return relevant `ModelContextHit` rows and record
  the searched paths

#### Scenario: No model is found
- **WHEN** the project root has no relevant FlowGuard model inventory
- **THEN** the helper SHALL return the existing `no_model_found` reuse decision
  with a visible no-model-found reason rather than claiming model ownership

#### Scenario: Helper output remains reviewable
- **WHEN** the helper returns an `ExistingModelPreflight`
- **THEN** callers SHALL be able to pass it to
  `review_existing_model_preflight(...)` without converting to a separate
  schema

### Requirement: Self-maintenance preflight handoff
Existing model preflight SHALL feed the self-maintenance mesh before new FlowGuard route boundaries are added.

#### Scenario: Similar existing route exists
- **WHEN** the preflight finds a similar existing model, route, or maintenance group
- **THEN** it SHALL recommend reuse, extension, child model, or duplicate-boundary review before creating a new self-maintenance boundary

### Requirement: Existing model preflight consumes model angle deliberation
Existing Model Preflight SHALL consume model-angle deliberation rows when a
task requires open-ended review of whether one model is enough.

#### Scenario: Required deliberation is missing
- **WHEN** a full preflight marks model-angle review as required
- **AND** no deliberation rows are supplied
- **THEN** preflight MUST report a blocking model-angle gap before broad confidence

#### Scenario: Deliberation row has unresolved gap
- **WHEN** a deliberation row reports an unresolved required angle, missing disposition rationale, or human-review question
- **THEN** preflight MUST keep that gap visible and route downstream work without claiming the current model is sufficient

#### Scenario: Deliberation supports continuation
- **WHEN** each required model angle is reused, extended, created, scoped, deferred, or sent to human review with sufficient rationale
- **THEN** preflight MAY continue with scoped or full confidence according to the row decisions and evidence

### Requirement: Existing model preflight includes field ownership
Existing model preflight SHALL include field lifecycle model ownership and
field projection status when a task changes fields, schemas, flags, modes,
payloads, persisted data, prompts, or configuration surfaces.

#### Scenario: Existing field model is reused
- **WHEN** a task touches fields already covered by a field lifecycle mesh
- **THEN** preflight MUST report the existing field group owner and reuse or
  extend decision before adding a parallel field model

#### Scenario: No field model exists
- **WHEN** a task changes behavior-bearing fields and no field lifecycle mesh
  covers them
- **THEN** preflight MUST report a field model gap and route the work to create
  or extend field lifecycle coverage

### Requirement: Similarity evidence in full preflight
Full Existing Model Preflight SHALL be able to consume current model-similarity
relations before deciding to reuse, extend, add a child model, create a family
variant, extract a shared kernel, route to Architecture Reduction, or keep a
new boundary separate.

#### Scenario: Similarity relation supports reuse decision
- **WHEN** a full preflight includes a current model-similarity relation that
  recommends reuse or extension of an existing model boundary
- **THEN** the preflight review may use that relation as reuse rationale while
  preserving the downstream route requirements

#### Scenario: Required similarity evidence is missing
- **WHEN** a full preflight declares that model similarity review is required
  for the boundary decision but does not include current similarity relation
  evidence
- **THEN** the preflight review reports a blocking similarity-evidence finding

#### Scenario: False friend keeps boundaries separate
- **WHEN** a full preflight includes a false-friend model-similarity relation
- **THEN** the preflight may keep the proposed boundary separate only if the
  false-friend rationale remains visible in the report

#### Scenario: Similarity maintenance group preserves sibling review
- **WHEN** a full preflight includes model-similarity relations for a changed
  workflow that belongs to a maintenance group
- **THEN** the preflight records the maintenance group ids, change-impact ids,
  and impacted sibling model ids before claiming the existing boundary review
  covered all similar workflows

### Requirement: ExistingModelPreflight consumes angle and similarity helpers
ExistingModelPreflight SHALL consume model-angle deliberation rows and
model-similarity relations as structured evidence before it decides reuse,
extension, child-model creation, shared-kernel extraction, ArchitectureReduction
handoff, or separate-boundary creation.

#### Scenario: Model angle is required
- **WHEN** the current model may be too narrow for the task
- **THEN** ExistingModelPreflight MUST include angle rows or report a
  model-angle gap
- **AND** the angle helper MUST NOT be selected as a separate public first stop

#### Scenario: Model similarity is required
- **WHEN** the task resembles another model, workflow, sibling test, shared
  kernel, adapter, or business path
- **THEN** ExistingModelPreflight MUST include similarity relation evidence or
  report a similarity-evidence gap
- **AND** the similarity helper MUST NOT be selected as a separate public first
  stop

### Requirement: Preflight output names downstream owner
ExistingModelPreflight SHALL name the downstream public owner route that must
act on consumed helper evidence.

#### Scenario: Duplicate boundary found
- **WHEN** similarity or ownership evidence indicates duplicate responsibility
- **THEN** ExistingModelPreflight MUST route the decision to
  ArchitectureReduction, StructureMesh, ModelMesh, Model-Test Alignment, or
  another public owner route instead of creating a parallel helper route

### Requirement: Existing model lookup resolves commitment ownership
FlowGuard SHALL make existing-model preflight identify affected commitment ids,
primary owner models, and sibling commitments before non-trivial planning or
changes in an existing modeled system.

#### Scenario: Existing commitment is reused
- **WHEN** a request touches behavior already registered in a ledger
- **THEN** existing-model preflight SHALL reuse the registered commitment id and primary owner model before proposing new behavior

#### Scenario: Duplicate boundary is suspected
- **WHEN** a request appears to create behavior overlapping a sibling commitment
- **THEN** existing-model preflight SHALL route to Behavior Commitment Ledger review before implementation

#### Scenario: Model miss maps to existing owner first
- **WHEN** a model miss is observed for a previously green modeled behavior
- **THEN** existing-model preflight SHALL identify the existing commitment id and owner model when one exists
- **AND** it SHALL route to coverage-gap backfill only when no registered commitment covers the observed external behavior

### Requirement: Preflight discovers executable composition context
Full existing-model preflight SHALL report current component fingerprints, existing system-definition references, candidate typed relations, business identities, shared-resource readers/writers, transaction/atomicity observations, queue/cache/external-confirmation owners, affected system properties, candidate changed roots, discovery-evidence identity, and unresolved dependency disposition when cross-model composition is relevant. Candidate relations SHALL remain proposed preflight findings until accepted into the strict portable-system definition by its owner; preflight SHALL NOT duplicate that definition's authoritative schema.

#### Scenario: Existing models should be composed
- **WHEN** a change affects two or more current models connected by an event, shared resource, retry, cache, external confirmation, or system property
- **THEN** preflight emits a `compose_existing_models` handoff with exact current owners, proposed relations, and unresolved items and does not create a duplicate system-model owner

#### Scenario: Dependency discovery is incomplete
- **WHEN** a required binding, identity, resource owner, or freshness fact is missing or ambiguous
- **THEN** preflight blocks executable-composition confidence or widens the candidate slice rather than assuming no impact

### Requirement: Preflight resolves authority before relevance
Existing Model Preflight SHALL validate the project observed-head snapshot
before selecting current model context. Lexical, path, class-name, ledger, or
filesystem discovery MAY identify candidates but MUST NOT make them current.

#### Scenario: Discovered file is not in the observed snapshot
- **WHEN** a model-like file matches the task text but is absent from the validated observed-head snapshot
- **THEN** preflight labels it non-authoritative discovery context and does not select it as the current primary model

#### Scenario: Observed head is missing or stale
- **WHEN** the project pointer is missing, its snapshot fingerprint differs, or its subject revision differs from the software revision
- **THEN** preflight blocks current-model confidence and reports the exact authority defect

### Requirement: Preflight reports the selected system context
Preflight SHALL report the observed source revision, observed snapshot
fingerprint, bounded coverage status, selected same-plane primary model ids,
candidate snapshot fingerprint when present, affected closure ids, unresolved
gap ids, and claim boundary.

#### Scenario: Target proposal is discussed
- **WHEN** a task has an observed base and a separate target snapshot
- **THEN** preflight reports both identities without presenting the target as the current software model

### Requirement: ExistingModelPreflight consumes WorkContexts after plane lookup
ExistingModelPreflight SHALL perform canonical Behavior Commitment Ledger
plane-first lookup before consuming an explicit collection of zero, one, or
many reviewed WorkContexts. It SHALL preserve every context's adapter, native
work, native owner, subject lane, artifact, behavior-source-surface, and
fingerprint identities separately from behavior ownership. WorkContext SHALL
remain read-only source and process context, and the selected primary behavior
plane SHALL be determined by the matching commitment rather than forced to
`development_process`.

#### Scenario: OpenSpec task mentions a product behavior
- **WHEN** an OpenSpec WorkContext artifact describes a product-runtime
  behavior and plane-first lookup selects its existing product commitment
- **THEN** preflight SHALL keep the product-runtime commitment and current
  primary model as behavior owner and preserve the WorkContext only as a typed
  source and process-context relation

#### Scenario: Provider context is stale or unmapped
- **WHEN** any required WorkContext lacks a current fingerprint, registered
  adapter, bounded root, native owner, required artifact role, or typed BCL
  source mapping for a claimed behavior
- **THEN** preflight SHALL report the exact scoped context gap and SHALL NOT use
  the artifact or provider status as complete model evidence

#### Scenario: Several current contexts inform one task
- **WHEN** OpenSpec, declared planning files, and release material are all
  configured for the same preflight
- **THEN** preflight SHALL preserve every distinct context and artifact
  identity, reconcile their typed commitment targets, and SHALL NOT select the
  first adapter as an implicit primary source

#### Scenario: A context targets another behavior plane
- **WHEN** a development planning artifact targets an existing
  `agent_operation` or `product_runtime` commitment
- **THEN** preflight SHALL allow that commitment's plane to remain primary and
  SHALL connect the WorkContext only through a typed source or target relation

#### Scenario: A WorkContext is declared as a runtime surface
- **WHEN** a caller attempts to classify WorkContext itself as a UI, API, CLI,
  alias, adapter, wrapper, helper, or compatibility behavior surface
- **THEN** preflight SHALL reject the ownership merge because WorkContext is
  external planning context rather than a same-intent runtime entrypoint

#### Scenario: A target context is presented as current implementation
- **WHEN** a `normative_target` or `counterfactual_experiment` WorkContext is
  presented as observed current-model authority
- **THEN** preflight SHALL keep the lanes separate and SHALL require the
  existing ModelRevisionSet activation path before observed ownership changes

#### Scenario: Normative contexts conflict
- **WHEN** two current normative WorkContexts map incompatible semantics to the
  same commitment or business intent
- **THEN** preflight SHALL report the BCL conflict and SHALL NOT resolve it by
  adapter order, provider preference, or fallback

### Requirement: Preflight inventories the affected same-intent surface family
Full Existing Model Preflight SHALL inventory the affected declared UI, API,
CLI, alias, adapter, wrapper, helper, and compatibility surfaces before it
admits a new model or implementation boundary for an existing business intent.
The inventory SHALL preserve known commitment ids, stable business-intent ids,
business path ids, expected terminals, material state writes and side effects,
owners, current evidence, and explicit unknown or scoped surfaces.

#### Scenario: Affected same-intent family is complete
- **WHEN** a proposed change adds or changes a surface for an existing business intent and every affected declared surface has a materialized ownership and evidence row
- **THEN** Existing Model Preflight SHALL use that inventory when deciding reuse, extension, duplicate-boundary review, or a separate intent boundary

#### Scenario: Known family member is omitted
- **WHEN** a known UI, API, CLI, alias, adapter, wrapper, helper, or compatibility surface for the affected intent is absent without an explicit scoped disposition
- **THEN** Existing Model Preflight SHALL report an incomplete same-intent inventory and SHALL NOT support broad reuse or new-boundary confidence

#### Scenario: A new surface is not a new behavior boundary
- **WHEN** a proposed page, control, API entrypoint, command, alias, or adapter has the same actor, trigger and preconditions, expected terminal, failure boundary, material state writes, and side effects as an existing intent
- **THEN** Existing Model Preflight SHALL recommend reuse or extension of the existing commitment and primary path rather than a new behavior boundary

### Requirement: Preflight reuses existing commitment and path owners
Existing Model Preflight SHALL hand the existing commitment id and
selected primary path candidate to Behavior Commitment Ledger and Primary Path
Authority when the affected-family evidence identifies an equivalent current
business intent. Preflight SHALL NOT create a Product Design Language route, intent
ledger, delegate commitment, path-reuse owner, or parallel runtime controller.

#### Scenario: Equivalent current path exists
- **WHEN** the affected-family inventory contains an existing path with the same exact intent semantics and current passing runtime evidence
- **THEN** Existing Model Preflight SHALL preserve the existing commitment and primary-path identities in its reuse handoff

#### Scenario: Material external semantics differ
- **WHEN** the proposed behavior differs in actor, trigger or preconditions, expected result or terminal, failure boundary, material state writes, side effects, safety boundary, or another externally observable contract
- **THEN** Existing Model Preflight SHALL preserve the typed difference and route it to the existing BCL and downstream owners for a distinct-intent decision rather than silently merging or creating a parallel same-intent path

#### Scenario: Evidence cannot prove equivalence
- **WHEN** similarity, runtime, source, or ownership evidence is missing, stale, skipped, not run, progress-only, or opaque
- **THEN** Existing Model Preflight SHALL keep the reuse or separate-boundary decision scoped and SHALL name the missing existing-owner evidence

### Requirement: Project preflight queries commitments before path discovery
Full Existing Model Preflight SHALL query the canonical Behavior Commitment Ledger from the task summary, canonical terms, paths, tools, and error signatures before supplementing results with path-based model inventory.

#### Scenario: Registered AI operation is recalled
- **WHEN** a non-trivial task matches an `agent_operation` commitment lookup binding
- **THEN** preflight SHALL include that commitment and its primary owner model in the primary hit set before path-only model hits

#### Scenario: Path scan supplements commitment owner
- **WHEN** changed paths identify additional current models after a commitment owner is selected
- **THEN** preflight SHALL add those models as supplementary context without replacing the primary commitment owner

### Requirement: Preflight separates primary and related planes
Preflight output SHALL record lookup status, primary behavior plane, primary commitment hits, typed related commitment hits, plane ambiguity, and ledger fingerprint.

#### Scenario: Product target is related to agent operation
- **WHEN** an agent-operation commitment invokes a product-runtime commitment
- **THEN** preflight SHALL show the agent commitment as primary and the product commitment as an invoked target
- **AND** SHALL NOT present the product row as an AI instruction

#### Scenario: Development process governs operation
- **WHEN** a development-process commitment governs the selected agent operation
- **THEN** preflight SHALL show it as governing context rather than a second primary operation

### Requirement: Missing ledger fallback remains explicit
Existing Model Preflight MAY use its current project inventory scan when commitment lookup is missing, not applicable, or blocked, but SHALL preserve that status and confidence boundary.

#### Scenario: Ledger missing but models exist
- **WHEN** no canonical ledger can be loaded and path inventory finds relevant models
- **THEN** preflight SHALL return `fallback` lookup status with the model hits
- **AND** SHALL NOT claim that registered behavior commitments were searched successfully

### Requirement: Plane ambiguity blocks unsafe consolidation
Preflight SHALL NOT choose one cross-plane owner solely from shared words when the primary behavior plane remains ambiguous.

#### Scenario: Download appears in all planes
- **WHEN** task terms match product, agent, and development commitments with no selected plane or typed relation path
- **THEN** preflight SHALL report separated plane candidates and an ambiguity finding
- **AND** downstream full-confidence work SHALL require a selected plane

