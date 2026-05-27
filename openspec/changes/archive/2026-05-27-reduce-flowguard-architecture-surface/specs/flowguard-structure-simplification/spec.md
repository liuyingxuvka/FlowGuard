## MODIFIED Requirements

### Requirement: Public Facade Compatibility
FlowGuard SHALL keep the broad `flowguard.__init__` facade and declared
`API_SURFACE` groups stable during structure simplification, and SHALL derive
`flowguard.__all__` from those groups plus a small explicit public supplement
instead of maintaining a second full duplicate export list.

#### Scenario: Public imports remain available
- **WHEN** the API surface test iterates every name listed in `API_SURFACE`
- **THEN** each name MUST still be present in `flowguard.__all__` and as a
  package attribute.

#### Scenario: Public export snapshot remains stable
- **WHEN** the facade export declaration is simplified
- **THEN** the set of public names in `flowguard.__all__` MUST match the
  pre-simplification export set.

#### Scenario: Supplement exports stay explicit
- **WHEN** a public name is intentionally exported but is not part of an
  `API_SURFACE` group
- **THEN** it MUST be listed in the explicit export supplement and covered by
  an API-surface test.
