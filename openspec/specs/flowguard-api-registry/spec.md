# flowguard-api-registry Specification
## Purpose

Define route-scoped API registry behavior for FlowGuard public helper grouping.
## Requirements
### Requirement: Route-scoped API groups
FlowGuard SHALL expose grouped helper registries that map stable route/group ids
to public helper names while preserving existing flat API lists.

#### Scenario: Starter registry names are public
- **WHEN** a helper name appears in `ROUTE_STARTER_API`
- **THEN** that helper name is also present in `flowguard.__all__`
- **AND** the helper is importable from `flowguard`

#### Scenario: Advanced route remains available
- **WHEN** a consumer needs full route control
- **THEN** `ROUTE_ADVANCED_API` maps the same route id to the route's full helper
  group or full route inventory

#### Scenario: Starter budgets are enforced
- **WHEN** API surface tests run
- **THEN** each route starter group stays within the configured compact budget
- **AND** broad flat groups are not embedded inside starter groups

### Requirement: New helper routes use grouped discovery
New FlowGuard route additions SHALL add grouped registry entries so future
callers do not need to scan a single flat helper list.

#### Scenario: Route addition records group ownership
- **WHEN** a new route-specific helper family is added
- **THEN** tests can assert the route group's required helper names without
  duplicating a long flat-list check

### Requirement: Agent-default API surface
FlowGuard SHALL expose a compact agent-default API group and route starter
registry that name the minimal route-first entry points an AI agent should
inspect before expanding into full route or helper groups.

#### Scenario: Agent starts FlowGuard maintenance
- **WHEN** an agent reads the public API registry
- **THEN** `AGENT_DEFAULT_API`, `ROUTE_STARTER_API`, and `ROUTE_ADVANCED_API` are
  available through `API_SURFACE`
- **AND** the existing full public API groups remain available behind full
  surface names

### Requirement: Risk template library is route-scoped public API
FlowGuard SHALL expose risk-template library helpers through a route-scoped API
group and compact starter group, while keeping them out of the core modeling API.

#### Scenario: Route group exposes template helpers
- **WHEN** `FLOWGUARD_ROUTE_API` is inspected
- **THEN** it includes a `risk_template_library` group with search, review, merge, and harvest helpers

#### Scenario: Core API remains model primitive only
- **WHEN** `CORE_API` is inspected
- **THEN** risk-template library helpers are not included in the core finite-state modeling primitives

### Requirement: Evidence API exposes template files and CLI surfaces
FlowGuard SHALL expose public template-library template files and CLI command
surfaces through the same template structure conventions as other routes.

#### Scenario: Template helper is discoverable
- **WHEN** public template helpers are inspected
- **THEN** a risk-template-library template helper is present and exports route-scoped starter files

### Requirement: Public API exposes harvest closure helpers
FlowGuard SHALL expose template harvest closure helpers through the
`risk_template_library` route-scoped API and starter API surfaces.

#### Scenario: API registry is inspected
- **WHEN** a consumer inspects route-scoped APIs
- **THEN** `RISK_TEMPLATE_LIBRARY_API` includes `TemplateHarvestReview` and `review_template_harvest_closure`

#### Scenario: Starter API is inspected
- **WHEN** an AI consumer reads `ROUTE_STARTER_API["risk_template_library"]`
- **THEN** it includes the helper needed to review harvest closure before final claims

