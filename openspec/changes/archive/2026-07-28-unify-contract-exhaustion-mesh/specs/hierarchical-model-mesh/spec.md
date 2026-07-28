## ADDED Requirements

### Requirement: Mesh closure hazards feed contract exhaustion
FlowGuard ModelMesh MUST be able to project parent-child stale evidence,
missing reattachment, unknown child output consumption, and retry/no-delta
closure hazards into canonical contract-exhaustion cases.

#### Scenario: Stale child evidence becomes mutation case
- **WHEN** a parent consumes an old child evidence id after a child boundary
  changed
- **THEN** FlowGuard can create a canonical stale-child-evidence mutation case

#### Scenario: Retry loop without repair feedback becomes mutation case
- **WHEN** a loop-like parent/child handoff repeats an input or packet shape
  without repair feedback, blocker, progress, bound, or no-delta disposition
- **THEN** FlowGuard can create a canonical repeat-without-delta mutation case
