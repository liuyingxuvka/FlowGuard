# architecture-reduction Specification

## Purpose
This capability defines FlowGuard's Architecture Reduction behavior and the evidence required to use it safely in AI-agent maintenance workflows.
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
FlowGuard SHALL represent model-backed code contraction opportunities as
structured candidates with candidate type, target code node, source model
element, rationale, affected public entrypoints, affected state, affected side
effects, proof status, required next route, and current lifecycle disposition.
When a candidate is linked to an old, alternate, or compatibility-like surface,
Architecture Reduction SHALL classify that surface before reporting the
candidate as ready.

#### Scenario: Safe candidate is reported with proof status
- **WHEN** a handler, module, branch, adapter, or state field has a declared
  reduction candidate with behavior-preserving evidence and no completed
  implementation evidence
- **AND** any linked compatibility surface has a classification that permits
  contraction
- **THEN** the review reports the candidate with a proof status and the next
  route needed before code changes

#### Scenario: Current contract blocks removal
- **WHEN** a reduction candidate removes or collapses a surface classified as a
  current contract
- **THEN** the review blocks the candidate instead of treating it as safe code
  contraction

#### Scenario: Negative legacy test remains visible
- **WHEN** a reduction candidate removes a surface classified as negative
  legacy test evidence
- **THEN** the review blocks or downgrades the candidate unless replacement
  rejection evidence is cited

#### Scenario: Evidence-needed surface blocks readiness
- **WHEN** a reduction candidate is linked to a compatibility surface whose
  classification is evidence-needed
- **THEN** the review does not report that candidate as ready

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

### Requirement: Compatibility surface classification
FlowGuard SHALL let Architecture Reduction classify old aliases, alternate
paths, migration branches, pass-through compatibility adapters, public facades,
retired validation artifacts, and legacy rejection tests before contraction is
claimed ready. Compatibility-only fields, aliases, wrappers, or guidance MAY be
removed when the classification proves they are obsolete and not a current
contract, safety classifier, public facade, runtime-authoritative archive, or
negative legacy test without replacement evidence.

#### Scenario: Boundary adapter is kept at the edge
- **WHEN** a compatibility surface is classified as a boundary adapter
- **AND** it affects a public entrypoint
- **THEN** the review requires StructureMesh or equivalent public-entrypoint
  parity before contraction can be claimed complete

#### Scenario: Archive-only surface has runtime authority
- **WHEN** a compatibility surface is classified as archive-only
- **AND** the surface still has runtime authority
- **THEN** the review blocks the classification until the authority is removed
  or the classification changes

#### Scenario: Prune candidate follows proof status
- **WHEN** a compatibility surface is classified as a prune candidate
- **AND** the linked reduction candidate has safe equivalence or public-facade
  proof status
- **THEN** Architecture Reduction may report the candidate as ready subject to
  the ordinary next-route requirements

#### Scenario: Classification appears in report
- **WHEN** Architecture Reduction reviews compatibility surfaces
- **THEN** the report includes the surface classifications, recommendations,
  evidence references, and missing evidence so downstream routes can preserve
  the decision boundary

#### Scenario: Obsolete compatibility field is removed
- **WHEN** a field, alias, wrapper, or prompt instruction exists only to
  preserve an old FlowGuard surface
- **AND** the current route-first API or `SimilarityHandoff` covers the same
  maintenance obligation
- **AND** the surface is not a current contract, safety classifier, public
  facade, runtime-authoritative archive, or unreplaced negative legacy test
- **THEN** FlowGuard may remove the old surface instead of preserving parallel
  compatibility paths

#### Scenario: Safety classifier is not removed as compatibility bloat
- **WHEN** a rule classifies current contracts, public facades,
  runtime-authoritative archives, negative legacy tests, or unknown
  compatibility surfaces before deletion
- **THEN** the rule remains part of Architecture Reduction unless a newer
  current guard provides equivalent protection and tests prove the handoff
  boundary

### Requirement: Architecture Reduction classifies old fields
Architecture Reduction SHALL classify old fields, field aliases, compatibility
field adapters, migration field branches, and retired field validation evidence
before contraction or replacement cleanup is claimed ready.

#### Scenario: Old field is a prune candidate
- **WHEN** an old field exists only for a replaced behavior
- **AND** current field lifecycle and model-code-test evidence prove the new
  field covers the behavior
- **THEN** Architecture Reduction MAY classify the old field as a prune
  candidate subject to implementation and validation gates

#### Scenario: Old field has runtime authority
- **WHEN** an archive-only or compatibility field can still affect runtime
  behavior
- **THEN** Architecture Reduction MUST block removal readiness until runtime
  authority is removed, delegated, migrated, or explicitly preserved with
  evidence

### Requirement: Similarity relation provenance
Architecture Reduction SHALL be able to consume model-similarity relations as
candidate provenance for duplicate-boundary, adapter-only, shared-kernel, and
duplicate-validation contraction candidates.

#### Scenario: Similarity relation feeds reduction candidate
- **WHEN** an Architecture Reduction candidate cites a model-similarity
  relation that identifies duplicate ownership or adapter-only difference
- **THEN** the review includes the relation id as candidate provenance while
  still requiring observable architecture contract coverage

#### Scenario: Similarity code obligation feeds reduction candidate
- **WHEN** an Architecture Reduction candidate is motivated by a
  duplicate-boundary or adapter-only model-similarity obligation
- **THEN** the candidate records the code obligation id as provenance while
  Architecture Reduction still owns the contraction readiness decision

#### Scenario: Similarity is not proof by itself
- **WHEN** a reduction candidate only cites a similarity relation and lacks
  safe equivalence, public facade, conformance, or validation-boundary evidence
- **THEN** the review does not report the candidate as ready

