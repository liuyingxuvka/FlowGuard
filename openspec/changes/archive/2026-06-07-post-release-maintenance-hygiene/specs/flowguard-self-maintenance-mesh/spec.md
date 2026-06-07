## ADDED Requirements

### Requirement: Self-maintenance default plan folds common fields
FlowGuard SHALL provide a public helper that builds the common
`SelfMaintenancePlan` from route profiles, public route API groups, AI entry
profiles, and field layer defaults while preserving explicit advanced plan
construction.

#### Scenario: Default plan is reviewable
- **WHEN** a caller provides only a plan id and current child closure reports
- **THEN** the helper returns a `SelfMaintenancePlan` that
  `review_flowguard_self_maintenance(...)` can validate without requiring the
  caller to manually fill the route graph fields

#### Scenario: Full fields remain available
- **WHEN** a specialist route needs to override route profiles, AI profiles,
  field layers, or API group ids
- **THEN** direct `SelfMaintenancePlan` construction remains supported
