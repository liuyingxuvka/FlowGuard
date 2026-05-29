## ADDED Requirements

### Requirement: Route-first AI surface exposes basic and full paths
FlowGuard SHALL present route-scoped discovery and basic constructors before the
flat helper inventory when documenting routine AI use.

#### Scenario: Agent handles similar workflow maintenance
- **WHEN** an agent needs to compare similar A/B/C model families for
  maintenance, code, or test drift
- **THEN** the documented first path MUST be Model Similarity Consolidation
  route group discovery, lightweight signature or plan helper construction, and
  a `SimilarityHandoff` to downstream routes
- **AND** the full dataclass schema MUST remain discoverable as the advanced
  full path

#### Scenario: Agent needs full control
- **WHEN** a model-similarity review requires advanced evidence, explicit pair
  selection, stale-evidence status, false-friend details, or metadata
- **THEN** FlowGuard MUST keep the full dataclass constructors documented after
  the basic path

### Requirement: Flat helper inventory is not first-read guidance
FlowGuard SHALL document `MODELING_HELPER_API` as a complete index rather than
the preferred first-read surface for AI agents.

#### Scenario: API documentation is read from top to bottom
- **WHEN** an agent reads `docs/api_surface.md`
- **THEN** route-scoped API groups and route-specific helper lists MUST appear
  before the flat `MODELING_HELPER_API` discussion
- **AND** the flat inventory MUST be described as a fallback or full index

### Requirement: Existing similarity route remains the owner
FlowGuard SHALL extend the existing Model Similarity Consolidation route instead
of adding a second similarity-maintenance capability.

#### Scenario: A/B/C maintenance similarity is reviewed
- **WHEN** a workflow has similar variants, shared kernels, adapters,
  duplicate boundaries, tests, or false-friend risks
- **THEN** the review MUST use Model Similarity Consolidation as the owning
  route and pass handoff evidence to downstream FlowGuard routes
