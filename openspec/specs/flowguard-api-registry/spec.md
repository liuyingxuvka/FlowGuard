# flowguard-api-registry Specification
## Purpose

Define route-scoped API registry behavior for FlowGuard public helper grouping.
## Requirements
### Requirement: Route-scoped API groups
FlowGuard SHALL expose a grouped helper registry that maps stable route/group
ids to public helper names while preserving the existing flat API lists.

#### Scenario: Registry names are public
- **WHEN** a helper name appears in a grouped registry entry
- **THEN** that helper name is also present in `flowguard.__all__`

#### Scenario: Flat compatibility remains intact
- **WHEN** existing callers inspect `MODELING_HELPER_API`, `EVIDENCE_API`, or
  direct public imports
- **THEN** the current public names remain available

### Requirement: New helper routes use grouped discovery
New FlowGuard route additions SHALL add grouped registry entries so future
callers do not need to scan a single flat helper list.

#### Scenario: Route addition records group ownership
- **WHEN** a new route-specific helper family is added
- **THEN** tests can assert the route group's required helper names without
  duplicating a long flat-list check

### Requirement: Agent-default API surface
FlowGuard SHALL expose a compact agent-default API group that names the minimal route-first entry points an AI agent should inspect before expanding into full route or helper groups.

#### Scenario: Agent starts FlowGuard maintenance
- **WHEN** an agent reads the public API registry
- **THEN** `AGENT_DEFAULT_API` is available through `API_SURFACE` and includes core modeling, route map, self-maintenance default plan, project audit, OpenSpec-facing release evidence helpers, and aggregate maintenance helpers

#### Scenario: Public API compatibility remains
- **WHEN** `AGENT_DEFAULT_API` is added
- **THEN** existing public API groups and names remain exported
