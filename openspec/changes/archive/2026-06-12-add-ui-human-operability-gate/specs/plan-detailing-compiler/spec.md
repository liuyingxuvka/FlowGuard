## ADDED Requirements

### Requirement: UI plans name human-operability evidence types
PlanDetailing SHALL require UI tasks that claim human-operable, usable, or
release-ready UI confidence to name evidence types for task coverage,
affordance, action grammar, dialog/window return, keyboard/focus, and
walkthrough validation.

#### Scenario: UI task checkbox has no operability evidence
- **WHEN** a UI plan step is marked complete
- **AND** its claim depends on human-operability
- **THEN** the plan review requires current passing evidence references for the
  relevant human-operability evidence types
