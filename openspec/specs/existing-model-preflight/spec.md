# existing-model-preflight Specification

## Purpose
TBD - created by archiving change add-existing-model-preflight. Update Purpose after archive.
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
