## ADDED Requirements

### Requirement: User-observed UI confusion is a model miss
Model Miss Review SHALL treat user-observed confusion after green UI evidence
as a UI model miss, even when controls exist and click-through evidence passes.

#### Scenario: User cannot understand the intended operation
- **WHEN** a user reports that visible controls, text, keyboard behavior,
  regions, dialogs, or path-selection options are confusing
- **AND** prior FlowGuard evidence was green or used for a completion claim
- **THEN** the miss review records a human-operability miss class, previous
  claim, affected task/control/region, same-class candidates, root cause, and
  required same-class evidence
