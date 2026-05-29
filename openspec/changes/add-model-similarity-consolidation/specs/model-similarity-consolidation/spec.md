## ADDED Requirements

### Requirement: Model signatures
FlowGuard SHALL represent a comparable model signature with model identity,
workflow family, variant identity, FunctionBlocks, inputs, outputs, state
ownership, state reads, side effects, invariants, failure modes, contracts,
public entrypoints, child models, evidence ids, freshness status, and known
blindspots.

#### Scenario: Complete signature can be compared
- **WHEN** a model signature includes model identity plus at least one modeled
  behavior element such as a FunctionBlock, state owner, side effect, invariant,
  failure mode, contract, or public entrypoint
- **THEN** the similarity review may use that signature in pairwise relation
  classification

#### Scenario: Empty signature is reported
- **WHEN** a model signature omits every comparable behavior element
- **THEN** the similarity review reports an incomplete-signature finding for
  that model

### Requirement: Typed model relation classification
FlowGuard SHALL classify model-to-model relations using typed relation ids,
including same workflow, same-family variant, symmetric flow, shared-kernel
candidate, duplicate boundary, overlapping ownership, parent/child candidate,
sibling overlap, adapter-only difference, evidence duplicate, false friend,
unrelated, and manual review.

#### Scenario: Same workflow is classified
- **WHEN** two model signatures share workflow family, FunctionBlocks, state or
  side-effect ownership, and failure-mode responsibility without material
  conflicting differences
- **THEN** the review reports a same-workflow relation and recommends reuse or
  extension rather than a parallel boundary

#### Scenario: Family variant is classified
- **WHEN** two model signatures share workflow family but have different
  variant ids or policy-specific differences
- **THEN** the review reports a same-family-variant relation and recommends a
  family or variant structure rather than merging all behavior into one model

#### Scenario: False friend blocks unsafe advice
- **WHEN** two model signatures share names or labels but materially differ in
  state ownership, side-effect ownership, contracts, invariants, or failure
  modes
- **THEN** the review reports a false-friend relation and does not recommend
  consolidation

### Requirement: Evidence-gated recommendations
FlowGuard SHALL attach recommendations to relation findings only with
matched elements, different elements, risk-if-merged, risk-if-kept-separate,
required next route, and required evidence.

#### Scenario: Missing required evidence scopes confidence
- **WHEN** a relation recommends consolidation but required evidence is missing,
  stale, skipped, not run, running, or progress-only
- **THEN** the review does not return full confidence for that relation and
  reports the evidence gap

#### Scenario: Current evidence allows route handoff
- **WHEN** a relation has current evidence for its required model, test, code,
  and public-entrypoint boundaries
- **THEN** the review may report the relation as ready for its downstream route
  handoff

### Requirement: Downstream FlowGuard route handoffs
FlowGuard SHALL produce downstream route recommendations for Existing Model
Preflight, ModelMesh, Architecture Reduction, Code Structure Recommendation,
StructureMesh, Model-Test Alignment, and manual review.

#### Scenario: Duplicate boundary routes to architecture reduction
- **WHEN** a relation identifies duplicate ownership, adapter-only difference,
  or duplicate validation around the same observable behavior
- **THEN** the review recommends Architecture Reduction and records the source
  relation as candidate provenance

#### Scenario: Shared kernel routes to structure recommendation
- **WHEN** a relation identifies a shared core flow with variant-specific
  adapters or policy branches
- **THEN** the review recommends Code Structure Recommendation with a shared
  kernel, variant adapter, facade, and validation-boundary handoff

#### Scenario: Parent or sibling relation routes to ModelMesh
- **WHEN** a relation identifies parent-child candidates, sibling overlap, or
  shared-kernel ownership across model boundaries
- **THEN** the review recommends ModelMesh before a broad parent or sibling
  confidence claim

### Requirement: No automatic rewrite
FlowGuard SHALL treat model similarity consolidation as a review and handoff
capability, not as automatic model merging or production code rewriting.

#### Scenario: Recommendation requires downstream implementation gate
- **WHEN** a relation recommends reuse, shared-kernel extraction, or code
  contraction
- **THEN** implementation still requires the appropriate downstream FlowGuard
  route, tests, conformance evidence, and completion claim evidence

### Requirement: Public template and CLI
FlowGuard SHALL provide a model-similarity-consolidation template and CLI entry
that print or write example review artifacts without requiring production code
changes.

#### Scenario: Template command prints review artifact
- **WHEN** a user runs the model-similarity template command without an output
  directory
- **THEN** FlowGuard prints a JSON template envelope for the model similarity
  consolidation template

#### Scenario: Template command writes files
- **WHEN** a user runs the model-similarity template command with an output
  directory
- **THEN** FlowGuard writes a runnable example model-similarity review and
  refuses to overwrite existing files unless forced
