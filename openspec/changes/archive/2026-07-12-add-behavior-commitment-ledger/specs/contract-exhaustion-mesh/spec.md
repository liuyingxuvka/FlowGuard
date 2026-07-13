## ADDED Requirements

### Requirement: ContractExhaustionMesh consumes commitment coverage axes
FlowGuard SHALL let ContractExhaustionMesh generate finite commitment coverage
cases for source mapping, owner uniqueness, evidence freshness, dependency
closure, scoped-out disposition, path sensitivity, PPA result, and release gate
state.

#### Scenario: Cartesian universe is generated
- **WHEN** a behavior commitment coverage universe is requested
- **THEN** ContractExhaustionMesh SHALL expose axes, interaction groups, case ids, and oracle ids for the commitment boundary

#### Scenario: Change-mode and model-miss DCAR axes are generated
- **WHEN** a behavior commitment coverage plan is generated
- **THEN** ContractExhaustionMesh SHALL include change mode, source freshness, replacement state, model sync, TestMesh state, and model-miss origin axes
- **AND** it SHALL include interaction groups for change/source freshness, replacement/model sync, and model-miss backfeed

#### Scenario: Missing oracle blocks coverage
- **WHEN** a generated commitment case has no oracle
- **THEN** ContractExhaustionMesh SHALL report the case as not covered
