## ADDED Requirements

### Requirement: Maintenance scan routes state closure gaps to model maturation

FlowGuard SHALL treat state/input closure confidence gaps as model maturation
signals after non-trivial FlowGuard-managed project work.

#### Scenario: Closure gap becomes required model maturation action

- **GIVEN** a maintenance scan receives `MAINTENANCE_SIGNAL_STATE_CLOSURE_GAP`
- **WHEN** `review_maintenance_scan(...)` runs
- **THEN** the scan MUST return a required `model_maturation_loop` action
- **AND** unresolved broad completion confidence MUST remain scoped or blocked
  until current owner-route evidence resolves the action.
