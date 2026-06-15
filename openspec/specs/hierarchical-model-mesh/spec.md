# hierarchical-model-mesh Specification

## Purpose
This capability defines FlowGuard's Hierarchical Model Mesh behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: Parent partition maps
FlowGuard SHALL allow a parent model boundary to declare coverage items for
functions, state fields, inputs, outputs, side effects, invariants, and failure
modes, and SHALL assign each item to a parent owner, child owner, read-only
shared use, or explicit shared-kernel owner.

#### Scenario: Complete parent coverage
- **WHEN** every parent coverage item has a valid owner
- **THEN** the mesh review reports no coverage-gap finding for that parent

#### Scenario: Missing parent coverage
- **WHEN** a parent coverage item has no owner
- **THEN** the mesh review reports a coverage-gap finding and does not return a green continue decision

### Requirement: Sibling independence review
FlowGuard SHALL review sibling child models for unsafe overlap and SHALL
distinguish permitted shared reads or shared-kernel declarations from duplicate
ownership of functional areas, state writes, side effects, or risk boundaries.

#### Scenario: Permitted shared read
- **WHEN** two child models read the same state field but only one owns the write responsibility
- **THEN** the mesh review treats the overlap as allowed

#### Scenario: Duplicate ownership conflict
- **WHEN** two sibling child models both own the same state write or side effect
- **THEN** the mesh review reports an ownership-conflict finding and does not return a green continue decision

### Requirement: Multi-level hierarchy review
FlowGuard SHALL support hierarchy review at any parent/child boundary so a child
model can itself become a parent model with its own partition map and mesh
review.

#### Scenario: Nested parent boundary
- **WHEN** a child model declares its own children
- **THEN** the mesh review evaluates that child boundary separately from the top-level parent boundary

### Requirement: Mesh activation triggers
FlowGuard SHALL trigger hierarchical mesh review when a project has three or
more models, when a single model crosses a configured large-model threshold,
when a budgeted model group remains incomplete, or when a model contains
several unrelated functional areas.

#### Scenario: Quantity trigger
- **WHEN** a project has three or more local FlowGuard models
- **THEN** the mesh review reports that architecture review is required

#### Scenario: Large-model trigger
- **WHEN** a model has an estimated or observed state count above the configured threshold
- **THEN** the mesh review reports that large-model split review is required

### Requirement: Large-model split decisions
FlowGuard SHALL produce an explicit split-review decision for oversized models,
including keeping the model, splitting into children, extracting a shared child,
merging with an existing model, promoting a cross-cutting rule to the parent, or
continuing only with budgeted execution.

#### Scenario: Oversized model kept as single model
- **WHEN** a large model is structurally cohesive and has complete evidence
- **THEN** the split review can return a keep-as-single-model decision with the reason recorded

#### Scenario: Oversized model split candidate
- **WHEN** a large model contains separable functional areas
- **THEN** the split review returns candidate child boundaries and requires coverage and overlap review before green continuation

### Requirement: Legacy model compatibility
FlowGuard SHALL classify discovered legacy models before trusting them in a
hierarchical mesh and SHALL allow compatibility contracts that describe risk
boundary, owned coverage, outputs, freshness, skipped checks, and evidence
authority without rewriting the legacy model.

#### Scenario: Legacy model without contract
- **WHEN** a legacy model has no compatibility contract
- **THEN** the mesh review registers the model but does not treat it as strong child evidence

#### Scenario: Large legacy model
- **WHEN** a legacy model crosses the large-model threshold
- **THEN** the mesh review marks it for split review before it can be used as complete hierarchy evidence

### Requirement: Evidence authority remains explicit
FlowGuard SHALL keep abstract, hazard, live, conformance, skipped, not-run,
stale, and incomplete evidence distinctions visible in hierarchical mesh review
results.

#### Scenario: Abstract-only evidence
- **WHEN** a child model has only abstract model evidence but production confidence is required
- **THEN** the mesh review does not report production-confidence authority

#### Scenario: Hidden skipped check
- **WHEN** a child model has skipped or not-run checks
- **THEN** the mesh review reports them explicitly instead of hiding them in a green summary

### Requirement: Parent mesh consumes child runtime path evidence
Hierarchical ModelMesh SHALL allow parent models to consume current child
runtime path evidence ids as part of child reattachment and whole-flow
confidence without inlining every child node.

#### Scenario: Parent consumes current child path evidence
- **WHEN** a child model provides current runtime path evidence for the child
  handoff consumed by a parent
- **AND** the child evidence id matches the parent reattachment contract
- **THEN** the parent mesh SHALL accept that child path evidence for the
  reattachment decision

#### Scenario: Parent consumes stale child path evidence
- **WHEN** a parent consumes a child runtime path evidence id that is stale or
  no longer matches the child boundary
- **THEN** the parent mesh SHALL block parent confidence with a stale child
  runtime path finding

#### Scenario: Child path output has no consumer
- **WHEN** a child runtime path emits an output required by the parent workflow
- **AND** no parent, sibling, terminal, or out-of-scope disposition consumes it
- **THEN** the mesh closure review SHALL block whole-flow confidence

### Requirement: Self-maintenance child model freshness
Hierarchical Model Mesh SHALL include self-maintenance child model freshness when a parent FlowGuard confidence claim depends on route graph, field, structure, validation, or closure child models.

#### Scenario: Child model is stale
- **WHEN** a child self-maintenance model has stale, skipped, partial, or blocked evidence
- **THEN** the parent mesh SHALL downgrade broad confidence and name the child route that must be refreshed

### Requirement: Parent mesh green requires handoff closure when child outputs exist
Hierarchical ModelMesh SHALL block broad parent green confidence when a parent
mesh contains child model outputs or reattachment contracts but no closure
model that consumes those handoffs.

#### Scenario: Child output without closure model
- **WHEN** a parent mesh has a child model that declares emitted outputs
- **AND** the parent mesh has no closure model
- **THEN** the mesh review SHALL report a missing closure finding
- **AND** the mesh review SHALL NOT return `mesh_green_can_continue`

#### Scenario: Reattachment contract without closure model
- **WHEN** a parent mesh has a child reattachment contract
- **AND** the parent mesh has no closure model
- **THEN** the mesh review SHALL report a missing closure finding
- **AND** broad parent confidence SHALL remain blocked

#### Scenario: Partition-only mesh remains scoped
- **WHEN** a parent mesh only records partition ownership and has no child
  outputs or reattachment contracts
- **THEN** the mesh review MAY remain a partition confidence review
- **AND** it MUST NOT be described as whole-flow closure evidence

### Requirement: Mesh closure hazards feed contract exhaustion
FlowGuard ModelMesh MUST be able to project parent-child stale evidence,
missing reattachment, unknown child output consumption, and retry/no-delta
closure hazards into canonical contract-exhaustion cases.

#### Scenario: Stale child evidence becomes mutation case
- **WHEN** a parent consumes an old child evidence id after a child boundary
  changed
- **THEN** FlowGuard can create a canonical stale-child-evidence mutation case

#### Scenario: Retry loop without repair feedback becomes mutation case
- **WHEN** a loop-like parent/child handoff repeats an input or packet shape
  without repair feedback, blocker, progress, bound, or no-delta disposition
- **THEN** FlowGuard can create a canonical repeat-without-delta mutation case

