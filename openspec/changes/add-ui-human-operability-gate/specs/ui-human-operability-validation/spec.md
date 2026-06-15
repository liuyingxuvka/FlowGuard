## ADDED Requirements

### Requirement: Human-operability validation distinguishes wired UI from usable UI
The system SHALL provide a human-operability validation surface that distinguishes
technically wired UI from UI that a user can understand and operate.

#### Scenario: Wired but confusing UI
- **WHEN** functional chain evidence passes
- **AND** user task coverage, affordance, action grammar, dialog/window,
  keyboard/focus, or walkthrough evidence is missing or failed
- **THEN** the system may claim technically wired confidence but not
  human-operable or release-ready UI confidence

#### Scenario: Task walkthrough supplies evidence
- **WHEN** a walkthrough validates a task
- **THEN** each step records visible prompt, user action, expected feedback,
  actual feedback, evidence reference, and confusion status
