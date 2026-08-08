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

### Requirement: ModelMesh requires all in-scope coverage receipts
Hierarchical ModelMesh SHALL require every in-scope model in a parent/child
model tree to provide a current model-scoped Cartesian coverage receipt before
broad parent or root confidence can be claimed.

#### Scenario: Missing child coverage receipt blocks parent confidence
- **WHEN** a parent mesh declares an in-scope child model
- **AND** no current coverage receipt exists for that child model
- **THEN** ModelMesh reports a missing coverage receipt finding
- **AND** parent confidence remains blocked or scoped

#### Scenario: All child receipts are current and consumed
- **WHEN** every in-scope child model has a current passing coverage receipt
- **AND** the parent receipt or parent interface plan consumes those child
  receipt ids
- **THEN** ModelMesh may treat the child coverage layer as closed for the
  parent boundary

### Requirement: Child-local green is not parent coverage
Hierarchical ModelMesh SHALL reject broad parent confidence when a child model
coverage receipt is current but the parent model did not consume it.

#### Scenario: Parent omits current child receipt
- **WHEN** a child coverage receipt is passing
- **AND** the parent coverage receipt does not list that child receipt id
- **THEN** ModelMesh reports unconsumed child coverage
- **AND** the parent cannot claim full all-model coverage

### Requirement: Cross-model misses backpropagate into model coverage
Hierarchical ModelMesh SHALL keep cross-model combination misses visible until
the affected child receipts and parent interface receipt are refreshed.

#### Scenario: Cross-model miss changes child and parent boundaries
- **WHEN** a model miss affects a child model axis and a parent consumption axis
- **THEN** ModelMesh requires refreshed child coverage and parent interface
  coverage before closing the parent mesh

### Requirement: Portable Mesh Semantic Binding
When a hierarchical mesh makes a portable interchange or cross-process verification claim, the system SHALL bind each active child model and parent refinement edge to current portable model identities and explicit refinement bindings.

#### Scenario: Portable mesh evidence is complete
- **WHEN** every active parent and child node has a current portable identity and every refinement edge has a passing binding receipt
- **THEN** the mesh may support the portable semantic closure claim

#### Scenario: Descriptive edge is insufficient
- **WHEN** a mesh edge has ownership metadata but no executable refinement binding
- **THEN** portable semantic closure remains blocked

### Requirement: ModelMesh hands off bounded composite candidates without executing them
For parent/child, sibling reattachment, or hierarchical closure/freshness work, ModelMesh SHALL be able to emit a typed composite-candidate handoff containing exact child ids/fingerprints, proposed event/resource relations, affected siblings, a referenced current system-property owner or `owner_missing` gap, unresolved relations, proposed changed roots, and any current system-definition reference. It SHALL consume a composite receipt only when the referenced definition, exact slice, and component fingerprints match. Ordinary peer-model composition SHALL route directly to the portable-system owner without requiring ModelMesh.

#### Scenario: Candidate packet is complete
- **WHEN** a parent/child or sibling relationship creates an executable interaction risk
- **THEN** ModelMesh hands the packet to the canonical portable-composition owner without expanding or executing child graphs

#### Scenario: Composite receipt is stale
- **WHEN** any component, relation, property, or slice fingerprint differs from the receipt
- **THEN** ModelMesh reports stale composite evidence and cannot infer parent green from child-local passes

### Requirement: Project mesh snapshot closes all reachable model relations
ModelMesh SHALL persist a content-addressed project snapshot whose model
members and typed relations are reachable from declared roots. It SHALL report
orphan, unknown, stale, historical-only, and unresolved members without
promoting them into current authority.

#### Scenario: Candidate replaces a child and changes a sibling dependency
- **WHEN** a revision replaces one child model and changes a relation consumed by a sibling
- **THEN** ModelMesh includes the parent, changed child, affected sibling, relation, and required reattachment evidence in one affected closure

#### Scenario: Historical model remains in storage
- **WHEN** a historical model is preserved but is not a member of the observed-head snapshot
- **THEN** ModelMesh keeps its historical disposition visible and excludes it from current-system coverage

### Requirement: Self topology records semantic model relationships
The FlowGuard self topology SHALL record affected parent/child, refinement, sibling-impact, and consumer relationships between models rather than representing the model set only as a flat inventory.

#### Scenario: Child behavior changes
- **WHEN** an affected child model changes an obligation consumed by a parent or sibling
- **THEN** the topology identifies the dependent relationship and its freshness impact

### Requirement: ModelMesh activation follows affected topology
ModelMesh SHALL activate for affected related models, parent/child changes, stale child evidence, oversized model partitioning, cross-model refinement, or whole-flow claims. The mere presence of three or more unrelated models in a repository SHALL NOT require mesh execution.

#### Scenario: Repository contains many unrelated models
- **WHEN** a task affects one bounded model with no dependent topology and no stale child evidence
- **THEN** ModelMesh is recorded as not triggered with that reason

### Requirement: Whole-flow claims require semantic disposition of every current model
For a whole-flow claim, the system SHALL bind every current model to a semantic disposition of connected, intentional-leaf, delegated-or-supporting, or explicitly scoped-out, with a rationale and current consumer relationship where applicable. Raw model count SHALL NOT activate or satisfy ModelMesh review.

#### Scenario: Inventory is complete but one model has no semantic disposition
- **WHEN** every current model is listed but one model lacks a semantic disposition and rationale
- **THEN** the whole-flow mesh is incomplete

#### Scenario: Model count crosses a threshold
- **WHEN** the number of models changes without any semantic topology change
- **THEN** the count alone neither activates nor satisfies ModelMesh review

### Requirement: Whole-software blueprint topology includes meaningful realization paths
For a whole-software blueprint claim, every in-scope model SHALL have a declared purpose and either a current consumer, an intentional-leaf disposition, or a realization path into implementation and verification references. ModelMesh SHALL preserve model semantics and SHALL NOT absorb implementation details merely to satisfy this relation.

#### Scenario: Model is semantically connected but has no realization or consumer
- **WHEN** a model has parent relations but no consumer, intentional-leaf disposition, or implementation realization path
- **THEN** whole-software blueprint topology is incomplete

#### Scenario: Every model has meaningful owned relations
- **WHEN** each in-scope model has current purpose, consumer or leaf disposition, and applicable realization references
- **THEN** topology may contribute current evidence to blueprint closure without creating an all-to-all graph

### Requirement: Blueprint hierarchy proves exact child reattachment
For every child consumed by a parent or sibling, ModelMesh SHALL verify the current child evidence identity, accepted inputs, emitted outputs, state and side effects, guarantees, schema or portable refinement, and exact consumer acknowledgement.

#### Scenario: Parent consumes a stale child identity
- **WHEN** a changed child is locally green but the parent still names an older child fingerprint or receipt
- **THEN** reattachment and parent confidence SHALL be blocked

#### Scenario: Fake input-output labels match by text only
- **WHEN** a child and parent use matching textual labels without compatible typed members, schema, or refinement evidence
- **THEN** the edge SHALL remain unresolved

### Requirement: Child reattachment consumes current owner-bound evidence
Every validation or runtime evidence id used by a child, relation, or reattachment SHALL exist in the current target evidence registry, carry the current artifact fingerprint, and belong to that exact child/owner evidence binding.

#### Scenario: Child, edge, and reattachment repeat one ghost id
- **WHEN** all three rows repeat the same nonexistent, stale, cross-revision, or other-owner evidence id
- **THEN** topology review SHALL report the exact evidence failure
- **AND** agreement among the three declarations SHALL NOT count as proof

### Requirement: Whole-flow hierarchy rejects unclosed cycles and joins
A whole-flow hierarchy SHALL account for required joins, every consumed output, normal and failure exits, retry or repeated-input loops, and terminal pending obligations.

#### Scenario: Required child output has no consumer
- **WHEN** a current child emits a required output that no parent, sibling, or typed external owner consumes
- **THEN** whole-flow closure SHALL fail with the exact unconsumed output

### Requirement: Structural hierarchy and cross-boundary feedback close independently
ModelMesh SHALL validate an acyclic, singly parented structural graph independently from the typed cross-boundary relation graph. Cross-boundary consumers, feedback, retry, repair, and shared-resource relations SHALL remain non-structural even when they connect an ancestor, descendant, or sibling, and SHALL be evaluated for interface compatibility and closure without changing `structural_parent_id`.

#### Scenario: Cross-boundary relation is counted as a second parent
- **WHEN** one node has a valid structural parent and a cross-boundary consumer or feedback owner is also counted as structural
- **THEN** ModelMesh SHALL reject the topology classification
- **AND** the relation SHALL be reclassified or the node SHALL remain blocked rather than accepting multi-parent structure

#### Scenario: Structural graph is acyclic but feedback graph has a cycle
- **WHEN** structural parent edges form a valid tree or forest rooted at the declared root while typed cross-boundary relations contain a reachable cycle
- **THEN** structural closure MAY remain valid
- **AND** feedback closure SHALL be evaluated independently without rewriting the structural graph

### Requirement: Every real feedback component has current progress closure
Every reachable strongly connected component in the typed feedback graph with more than one member or an explicit self-loop SHALL bind one current progress contract and independent current evidence. The contract SHALL identify the repeated token or packet boundary and at least one verified blocker, repair-token change, decreasing ranking measure, monotone progress rule, or finite iteration bound that prevents unchanged unbounded circulation.

#### Scenario: Feedback SCC has only descriptive labels
- **WHEN** a reachable feedback component is labeled retry, repair, wait, or progress but has no current progress contract and independent evidence
- **THEN** mesh closure SHALL be blocked with the exact component and missing progress obligation
- **AND** member-local green results or an acyclic structural graph SHALL NOT close the feedback loop

#### Scenario: Progress contract is stale or self-certified
- **WHEN** the progress contract targets another snapshot, its evidence is stale, or the same mesh qualification result manufactures the evidence it consumes
- **THEN** the feedback component SHALL remain stale or blocked
- **AND** the contract text alone SHALL NOT license parent confidence

#### Scenario: Finite feedback closure is independently proven
- **WHEN** every member and relation in a reachable feedback component is current and an independent receipt proves the declared repair-token change, ranking decrease, blocker, or finite bound
- **THEN** ModelMesh MAY close that component for the exact current snapshot
- **AND** the closure SHALL NOT generalize to another component, snapshot, or unbound repeated input

### Requirement: Full parent closure consumes every exact-current child receipt
The current full model parent SHALL aggregate hierarchy, reattachment, feedback, and evidence results without replacing child-owned validation. Every declared in-scope child SHALL have one exact-current terminal receipt produced by its declared child execution owner, and the parent receipt SHALL list and consume that exact receipt identity and fingerprint.

#### Scenario: Full parent is green without one child receipt
- **WHEN** the full model parent reports success while any declared child receipt is missing, stale, foreign, non-terminal, or absent from the parent consumed-receipt set
- **THEN** parent closure SHALL be blocked
- **AND** parent execution, source hashes, or another child's receipt SHALL NOT substitute for the missing child result

#### Scenario: Parent consumes every current child receipt
- **WHEN** every in-scope child has one exact-current terminal receipt and the full parent binds each receipt through the current reattachment and interface contracts
- **THEN** the parent MAY report aggregate closure for that exact snapshot
- **AND** each child receipt SHALL retain its original producer, subject, scope, and result identity

### Requirement: ModelMesh propagates compact path-quality freshness
ModelMesh SHALL propagate the current path-quality subject, conclusion, unresolved state, and detailed-evidence fingerprint across affected parent/child and sibling relations. It SHALL reopen only topology-required neighbors and SHALL NOT copy deep candidate bodies into every mesh node or independently rejudge single-model path quality.

#### Scenario: Child model path changes
- **WHEN** a child's path-quality subject or consumed interface identity changes
- **THEN** every parent or sibling whose contract consumes that identity becomes stale until its affected handoff is reviewed

#### Scenario: Child deep details are not required
- **WHEN** a parent claim needs only the child's current compact result
- **THEN** the mesh carries the summary and fingerprint without loading or duplicating deep details
