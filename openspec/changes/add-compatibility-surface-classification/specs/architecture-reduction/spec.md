## MODIFIED Requirements

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

### Requirement: Compatibility surface classification
FlowGuard SHALL let Architecture Reduction classify old aliases, alternate
paths, migration branches, pass-through compatibility adapters, public facades,
retired validation artifacts, and legacy rejection tests before contraction is
claimed ready.

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
