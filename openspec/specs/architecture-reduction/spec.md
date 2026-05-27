# architecture-reduction Specification

## Purpose
TBD - created by archiving change add-architecture-reduction. Update Purpose after archive.
## Requirements
### Requirement: Observable architecture contract
FlowGuard SHALL require an architecture reduction review to declare the source model, source code boundary, observable public entrypoints, observable outputs, observable state, observable side effects, validation boundaries, and rationale before reporting a reduction as ready.

#### Scenario: Complete observable contract
- **WHEN** an architecture reduction review includes source model identity, source structure identity, observable behavior fields, validation boundaries, and rationale
- **THEN** the review may classify reduction candidates by proof status

#### Scenario: Missing observable contract blocks reduction
- **WHEN** an architecture reduction review omits the observable behavior contract or validation boundaries
- **THEN** the review reports missing-contract findings and does not return a ready decision

### Requirement: Code contraction candidates
FlowGuard SHALL represent model-backed code contraction opportunities as structured candidates with candidate type, target code node, source model element, rationale, affected public entrypoints, affected state, affected side effects, proof status, and required next route.

#### Scenario: Safe candidate is reported with proof status
- **WHEN** a handler, module, branch, adapter, or state field has a declared reduction candidate with behavior-preserving evidence
- **THEN** the review reports the candidate with a proof status and the next route needed before code changes

#### Scenario: Risky candidate is kept visible
- **WHEN** a candidate appears duplicate but lacks enough equivalence, facade, conformance, or ownership evidence
- **THEN** the review marks it as risky or blocked instead of treating it as safe to remove

### Requirement: Target structure handoff
FlowGuard SHALL produce a target architecture summary that can be consumed by Code Structure Recommendation or StructureMesh, including merge, collapse, remove, keep-facade, and manual-review actions.

#### Scenario: Reduction feeds target structure
- **WHEN** all ready candidates have required proof status and observable contract coverage
- **THEN** the review includes target actions that can be translated into module ownership, facade, and validation-boundary recommendations

#### Scenario: Public entrypoint requires facade gate
- **WHEN** a candidate affects a public entrypoint
- **THEN** the review requires a StructureMesh or equivalent public-entrypoint parity gate before code contraction can be claimed complete

### Requirement: Companion route triggers
FlowGuard SHALL define complexity-growth triggers that allow DevelopmentProcessFlow, Existing Model Preflight, Code Structure Recommendation, StructureMesh, ModelMesh, Model-Test Alignment, and UI Flow Structure to invoke architecture reduction without making it a universal gate.

#### Scenario: Development process complexity trigger
- **WHEN** staged development adds repeated phases, adapters, branches, or validation layers around the same behavior before implementation or done/release claims
- **THEN** DevelopmentProcessFlow guidance points to architecture reduction before more structure is added

#### Scenario: Existing boundary duplicate trigger
- **WHEN** Existing Model Preflight detects duplicate ownership or a proposed boundary overlaps an existing responsibility
- **THEN** the agent can route to architecture reduction to consider merging or deleting the duplicate structure

#### Scenario: Structure refactor trigger
- **WHEN** a large code refactor is proposed and the target structure may be smaller than the current module graph
- **THEN** StructureMesh or Code Structure Recommendation can consume architecture reduction output before implementation

### Requirement: No automatic code rewrite
FlowGuard SHALL treat architecture reduction as a review and handoff capability, not as automatic production code rewriting.

#### Scenario: Candidate requires implementation gate
- **WHEN** an architecture reduction report identifies safe code contraction candidates
- **THEN** production code changes still require the appropriate StructureMesh, DevelopmentProcessFlow, tests, and conformance evidence before completion is claimed
