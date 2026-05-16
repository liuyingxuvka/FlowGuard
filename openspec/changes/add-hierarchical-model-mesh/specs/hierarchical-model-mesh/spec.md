## ADDED Requirements

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
