## ADDED Requirements

### Requirement: Installed UI skills require human-operability routing
FlowGuard Codex skill satellites SHALL route UI completion, usability, and
human-operable claims through user task coverage and human-operability evidence
rather than treating visible inventory or functional chains as sufficient.

#### Scenario: Skill prompt omits task coverage
- **WHEN** the UI Flow skill is used for a complete UI claim
- **THEN** its guidance must require user task coverage, task-to-feature,
  task-to-UI, affordance, action grammar, dialog/window, keyboard/focus, and
  walkthrough evidence before human-operable confidence
