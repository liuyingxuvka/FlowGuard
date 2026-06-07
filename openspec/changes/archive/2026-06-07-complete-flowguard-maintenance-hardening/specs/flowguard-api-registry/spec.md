## ADDED Requirements

### Requirement: Agent-default API surface
FlowGuard SHALL expose a compact agent-default API group that names the minimal route-first entry points an AI agent should inspect before expanding into full route or helper groups.

#### Scenario: Agent starts FlowGuard maintenance
- **WHEN** an agent reads the public API registry
- **THEN** `AGENT_DEFAULT_API` is available through `API_SURFACE` and includes core modeling, route map, self-maintenance default plan, project audit, OpenSpec-facing release evidence helpers, and aggregate maintenance helpers

#### Scenario: Public API compatibility remains
- **WHEN** `AGENT_DEFAULT_API` is added
- **THEN** existing public API groups and names remain exported

