## ADDED Requirements

### Requirement: ContractExhaustionMesh consumes commitment coverage axes
FlowGuard SHALL let ContractExhaustionMesh generate finite commitment coverage
cases for source mapping, owner uniqueness, evidence freshness, dependency
closure, scoped-out disposition, path sensitivity, PPA result, and release gate
state.

#### Scenario: Cartesian universe is generated
- **WHEN** a behavior commitment coverage universe is requested
- **THEN** ContractExhaustionMesh SHALL expose axes, interaction groups, case ids, and oracle ids for the commitment boundary

#### Scenario: Missing oracle blocks coverage
- **WHEN** a generated commitment case has no oracle
- **THEN** ContractExhaustionMesh SHALL report the case as not covered
