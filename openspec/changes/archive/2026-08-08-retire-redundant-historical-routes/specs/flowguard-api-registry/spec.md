## ADDED Requirements

### Requirement: Retired historical routes leave no public or compatibility surface
When a route or behavior is intentionally retired, FlowGuard SHALL remove its route registry entry, starter/advanced group, top-level exports, template helper, CLI command, documentation cohort, and public commitment. A compact shared data type may remain only under its canonical consuming owner and MUST NOT preserve the retired route identity.

#### Scenario: Public registry is inspected after retirement
- **WHEN** a retired Model Angle, Maintenance Scan, standalone Model Similarity, duplicate non-canonical route template, or retired model owner name is inspected
- **THEN** it is absent from public route discovery and package exports

#### Scenario: Retired name is invoked
- **WHEN** a caller imports or invokes a retired name
- **THEN** the operation fails visibly without aliasing, forwarding, translating, or falling back to a current owner

#### Scenario: Advanced consumer needs an internal type
- **WHEN** a small typed relation or maintenance-obligation carrier remains necessary
- **THEN** it is available through the canonical owner module only and does not recreate the retired public route

#### Scenario: Explicit risk-template work is inspected
- **WHEN** a caller explicitly requests risk-template reuse, publication, harvest, or harvest review
- **THEN** the current risk-template library APIs, template surface, and CLI commands remain available
- **AND** their presence MUST NOT reintroduce them into the universal modeling hot path

## MODIFIED Requirements

### Requirement: Risk template library is route-scoped public API
FlowGuard SHALL retain risk-template search, review, merge, harvest, and harvest-review helpers in the route-scoped risk_template_library API cohort and advanced discovery surface. They SHALL remain outside CORE_API and ROUTE_STARTER_API so ordinary modeling does not inherit a universal template gate.

#### Scenario: Route group exposes template helpers
- **WHEN** FLOWGUARD_ROUTE_API or advanced route discovery is inspected
- **THEN** the current risk_template_library group remains available for explicitly scoped template operations

#### Scenario: Core API remains model primitive only
- **WHEN** CORE_API or ROUTE_STARTER_API is inspected
- **THEN** risk-template search and harvest helpers are absent from the universal model primitives and direct starter path

### Requirement: Evidence API exposes template files and CLI surfaces
FlowGuard SHALL retain the public risk-template-library template and the explicit risk-template search, harvest, and harvest-review CLI surfaces under the existing template and CLI conventions. Their discoverability SHALL NOT make them mandatory for ordinary model, repair, maintenance, or release completion.

#### Scenario: Template helper is discoverable
- **WHEN** a caller requests template reuse, publication, harvest, or harvest review
- **THEN** the current risk-template-library-template, risk-template-harvest, and risk-template-harvest-review command surfaces remain discoverable

#### Scenario: Ordinary work inspects its required commands
- **WHEN** no accepted template trigger is present
- **THEN** ordinary FlowGuard completion has no required template CLI command or receipt

### Requirement: Public API exposes harvest closure helpers
FlowGuard SHALL retain TemplateHarvestReview, review_template_harvest_closure, and the current harvest helpers in the route-scoped RISK_TEMPLATE_LIBRARY_API and advanced risk-template discovery surface. FlowGuard SHALL also retain the explicit risk-template-library-template, risk-template-harvest, and risk-template-harvest-review CLI commands. These surfaces SHALL run only for explicit reuse, publication, harvest, or current stable cross-project-pattern work and SHALL NOT be required by CORE_API, the universal kernel hot path, ROUTE_STARTER_API, ordinary model completion, or unrelated maintenance.

#### Scenario: API registry is inspected
- **WHEN** a consumer inspects RISK_TEMPLATE_LIBRARY_API or the advanced risk-template route group
- **THEN** TemplateHarvestReview, review_template_harvest_closure, and the current harvest helpers remain discoverable
- **AND** they are absent from the core finite-state modeling primitives and universal starter path

#### Scenario: Explicit harvest CLI is invoked
- **WHEN** a caller invokes risk-template-harvest or risk-template-harvest-review for an explicitly scoped template operation
- **THEN** FlowGuard executes the current strict harvest or review behavior
- **AND** missing or invalid operation-local evidence remains a visible failure

#### Scenario: Ordinary model work has no template trigger
- **WHEN** a bounded model, repair, maintenance, or release task contains no explicit template reuse or publication scope and no accepted stable cross-project-pattern trigger
- **THEN** its completion does not invoke or require the harvest API, template command, or CLI receipt

#### Scenario: Starter API is inspected
- **WHEN** a consumer inspects ROUTE_STARTER_API or the universal model-first kernel entry
- **THEN** template harvest and harvest-review helpers are absent from that starter surface
- **AND** explicitly scoped callers continue to use the route-scoped risk-template owner
