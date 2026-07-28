## ADDED Requirements

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
