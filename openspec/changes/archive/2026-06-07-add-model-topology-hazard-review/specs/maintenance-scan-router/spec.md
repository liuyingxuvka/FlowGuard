## ADDED Requirements

### Requirement: Maintenance scan routes topology hazard gaps

FlowGuard SHALL treat unresolved model-topology hazard review gaps as model
maturation or final-risk evidence signals after non-trivial FlowGuard-managed
project work.

#### Scenario: Topology hazard gap becomes required model maturation action

- **GIVEN** a maintenance scan receives
  `MAINTENANCE_SIGNAL_TOPOLOGY_HAZARD_GAP`
- **WHEN** `review_maintenance_scan(...)` runs
- **THEN** the scan MUST return a required `model_maturation_loop` action
- **AND** unresolved broad completion confidence MUST remain scoped or blocked
  until current owner-route evidence resolves the action.
