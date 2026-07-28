## ADDED Requirements

### Requirement: Behavior fields project contract-exhaustion dimensions
FlowGuard MUST allow behavior-bearing field lifecycle rows and old-field
disposition rows to project declared contract-exhaustion dimensions.

#### Scenario: Required behavior field projects missing-field mutation
- **WHEN** a field lifecycle row marks a field as behavior-bearing and required
- **THEN** FlowGuard can project that row into a contract dimension that
  generates missing, empty, wrong-type, or unknown-value mutation cases

#### Scenario: Old field disposition projects legacy mutation
- **WHEN** an old, replaced, alias, fallback, or compatibility-like field
  remains reachable
- **THEN** FlowGuard records its disposition and can project legacy-field
  mutation cases or cleanup blockers into ContractExhaustionMesh
