## ADDED Requirements

### Requirement: Obsolete case-generation surfaces are cleanup candidates
FlowGuard ArchitectureReduction MUST classify old same-class generators,
fallback prompt paths, aliases, wrappers, and compatibility-like case surfaces
as cleanup candidates unless they are current public contracts, safety
classifiers, public facades, archives, or negative legacy tests with current
evidence.

#### Scenario: Old generator is not current contract
- **WHEN** an old same-class generator duplicates ContractExhaustionMesh and is
  not a public contract or safety classifier
- **THEN** ArchitectureReduction can classify it as a prune candidate

#### Scenario: Public facade routes through structure proof
- **WHEN** an old surface must stay reachable as a public facade
- **THEN** FlowGuard requires StructureMesh or equivalent parity evidence
  instead of treating the facade as a fallback generator
