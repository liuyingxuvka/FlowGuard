## ADDED Requirements

### Requirement: Business path hazards route through existing maintenance owners
Maintenance scan routing SHALL recognize unresolved duplicate, conflict,
unproven, and legacy-disposition business-path signals and route them to
existing FlowGuard owner routes.

#### Scenario: Duplicate path signal routes to reduction and similarity owners
- **WHEN** maintenance scan receives a duplicate business-path signal
- **THEN** the recommended route includes existing architecture reduction or model similarity ownership rather than a new workflow family

#### Scenario: Conflict or unproven path signal routes to evidence owners
- **WHEN** maintenance scan receives a conflicting or unproven business-path signal
- **THEN** the recommended route includes existing model maturation, model-test alignment, runtime evidence, or risk evidence ownership

### Requirement: Business path scan output preserves skipped evidence
Maintenance scan output SHALL keep unresolved business-path evidence gaps
visible when downstream validation was skipped, stale, or blocked.

#### Scenario: Skipped downstream review stays visible
- **WHEN** a business-path hazard is detected but the owning downstream route was not run
- **THEN** the maintenance scan result records the skipped route and does not treat the hazard as resolved
