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

