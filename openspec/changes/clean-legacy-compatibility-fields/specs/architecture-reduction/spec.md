## MODIFIED Requirements

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
