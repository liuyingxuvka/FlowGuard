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

### Requirement: Route registry separates public and internal surfaces
The FlowGuard API registry SHALL separate public owner route discovery from
advanced/internal helper discovery.

#### Scenario: Public route API excludes feeders
- **WHEN** callers inspect `FLOWGUARD_ROUTE_API`
- **THEN** the registry MUST include only public owner route groups and
  explicitly proven public facades
- **AND** internal feeder groups MUST be discoverable only through advanced or
  full helper inventories

#### Scenario: Starter API is direct-entry only
- **WHEN** callers inspect `ROUTE_STARTER_API`
- **THEN** each key MUST represent a direct public owner route or a documented
  direct public facade
- **AND** delegated modes, feeders, and data helpers MUST NOT appear as starter
  keys

### Requirement: Advanced helper availability does not imply route ownership
The API registry SHALL keep advanced helper exports distinct from public route
ownership.

#### Scenario: Helper remains exported
- **WHEN** an internal feeder helper remains in `MODELING_HELPER_API`,
  `REPORTING_HELPER_API`, `EVIDENCE_API`, or `ROUTE_ADVANCED_API`
- **THEN** tests MUST NOT infer that the helper is a public route starter

### Requirement: Route profile metadata drives public discovery
The API registry SHALL derive or validate public route discovery against
route-profile role metadata.

#### Scenario: Role mismatch is blocked
- **WHEN** a route is listed as public but its route profile is not
  `public_owner`
- **THEN** FlowGuard self-maintenance MUST report a route registry mismatch

### Requirement: Primary path route is discoverable
FlowGuard SHALL expose primary-path authority helpers through route-scoped API
groups, route starter APIs, templates, and CLI surfaces.

#### Scenario: Starter API exposes review helper
- **WHEN** callers inspect `ROUTE_STARTER_API["primary_path_authority"]`
- **THEN** the group SHALL include the public plan/report types and
  `review_primary_path_authority`

#### Scenario: API surface exports route helpers
- **WHEN** callers import the public FlowGuard package
- **THEN** primary-path authority helper names SHALL be present in
  `flowguard.__all__` and importable from `flowguard`

### Requirement: Primary path route does not expose internal helpers as owners
The API registry SHALL keep primary-path authority public owner helpers
separate from any internal coverage or formatting helpers.

#### Scenario: Internal helper is not starter route
- **WHEN** an internal coverage helper exists
- **THEN** it SHALL NOT appear as a direct public starter route owner unless it
  has explicit facade evidence

