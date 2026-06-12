## ADDED Requirements

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
