## ADDED Requirements

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
