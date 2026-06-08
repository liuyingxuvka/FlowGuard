## ADDED Requirements

### Requirement: Satellite skill guidance teaches validation gates
FlowGuard Codex satellite skills SHALL surface the new UI and artifact payload
validation evidence gates in their concise route shells or reference protocols.

#### Scenario: UI satellite is read
- **WHEN** an agent reads `flowguard-ui-flow-structure`
- **THEN** the guidance MUST say runnable UI completion requires reachable
  actionable controls/events to have run evidence, pure-UI classification, or
  scoped blindspots

#### Scenario: Alignment and TestMesh satellites are read
- **WHEN** an agent reads Model-Test Alignment or TestMesh guidance
- **THEN** the guidance MUST route artifact payload contracts to Model-Test
  Alignment and large payload evidence matrices to TestMesh

### Requirement: Installed skill sync covers validation gate changes
Installed FlowGuard skill synchronization SHALL verify that local installed
skills include validation gate guidance before active installed behavior is
claimed.

#### Scenario: Installed skill is stale
- **WHEN** repository skill content includes validation gate guidance
- **AND** the installed skill copy does not
- **THEN** release or local sync confidence MUST remain scoped until the
  installed skill is refreshed or the mismatch is reported
