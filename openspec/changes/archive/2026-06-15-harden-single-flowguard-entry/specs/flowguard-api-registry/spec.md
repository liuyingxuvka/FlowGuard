## MODIFIED Requirements

### Requirement: Agent-default API surface
FlowGuard SHALL expose a compact agent-default API group and route starter registry that name the single formal route-first entry points an AI agent should inspect before expanding into full route or helper groups.

#### Scenario: Agent starts FlowGuard maintenance
- **WHEN** an agent reads the public API registry
- **THEN** `AGENT_DEFAULT_API`, `ROUTE_STARTER_API`, and `ROUTE_ADVANCED_API` are available through `API_SURFACE`
- **AND** the existing full public API groups remain available behind full surface names

#### Scenario: Agent-default entry uses hard model helpers
- **WHEN** `AGENT_DEFAULT_API` is inspected
- **THEN** it includes the formal risk intent, check plan, minimum model contract, known-bad proof review, and model-first runner helpers
- **AND** it does not include `Explorer`

#### Scenario: Explorer remains primitive, not entry
- **WHEN** `CORE_API` is inspected by advanced consumers
- **THEN** `Explorer` may remain discoverable as the finite exploration primitive
- **AND** the API registry MUST NOT describe it as the default AI entry
