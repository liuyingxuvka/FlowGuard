## ADDED Requirements

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
