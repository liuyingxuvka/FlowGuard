## MODIFIED Requirements

### Requirement: Route-first AI surface exposes basic and full paths
FlowGuard SHALL present route-scoped starter discovery and compact route
templates before flat helper inventories when documenting routine AI use.

#### Scenario: Agent starts route maintenance
- **WHEN** an AI consumer reads API docs or uses public template commands for a
  route covered by this change
- **THEN** the documented first path is the route starter API and compact
  template for that route
- **AND** the full helper list and full template remain discoverable as explicit
  advanced paths

#### Scenario: Compact path preserves safety gates
- **WHEN** the AI uses a compact template for model miss, model-test alignment,
  or UI-flow structure
- **THEN** the generated files still include the route's required gate, test,
  replay, validation, or implementation evidence boundaries

### Requirement: Flat helper inventory is not first-read guidance
FlowGuard SHALL document `MODELING_HELPER_API`, `REPORTING_HELPER_API`, and
`__all__` as complete indexes rather than preferred first-read surfaces for AI
agents.

#### Scenario: API documentation is read from top to bottom
- **WHEN** an agent reads `docs/api_surface.md`
- **THEN** `AGENT_DEFAULT_API` and `ROUTE_STARTER_API` appear before full helper
  inventory discussion
- **AND** the full helper inventories are labeled as full or fallback indexes

### Requirement: Guidance compression preserves local synchronization evidence
FlowGuard guidance compression SHALL be finalized only after repository source,
editable install behavior, installed Codex skills, shadow workspace imports,
formal local repository sync, and local git evidence are aligned or explicitly
scoped out.

#### Scenario: Compressed guidance is finalized locally
- **WHEN** compact AI entry guidance is ready to claim done
- **THEN** validation includes OpenSpec checks, FlowGuard self-checks, focused
  API/template tests, broader regression, editable install verification, shadow
  workspace verification, formal repository sync verification, and local git
  status or commit/tag evidence
