## ADDED Requirements

### Requirement: ArchitectureReduction classifies old helper surfaces
ArchitectureReduction SHALL classify old helper prompts, route ids, aliases,
template commands, wrappers, and compatibility-like surfaces before they remain
reachable after a route-control-plane consolidation.

#### Scenario: Helper route is absorbed
- **WHEN** an old helper route duplicates a current public owner route
- **THEN** ArchitectureReduction MUST classify it as absorb, delete,
  internal-helper, or facade-review before implementation claims completion

#### Scenario: Fallback prompt is not retained
- **WHEN** an old prompt path only exists to keep a legacy route available
- **THEN** ArchitectureReduction MUST classify it as a prune candidate unless
  current public-contract evidence proves it is a facade

### Requirement: Retained facades require route evidence
ArchitectureReduction SHALL require current owner-route evidence before an old
helper surface can remain as a public facade.

#### Scenario: Public facade is kept
- **WHEN** a retained helper surface is user-facing or externally documented
- **THEN** ArchitectureReduction MUST require StructureMesh or equivalent
  public-entrypoint parity evidence before the facade remains public
