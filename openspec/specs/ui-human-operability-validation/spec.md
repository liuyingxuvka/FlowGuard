# ui-human-operability-validation Specification

## Purpose
Define the evidence surface that separates technically wired UI from UI a human
can understand and operate, including task coverage, affordance, action grammar,
dialog/window behavior, keyboard/focus behavior, and walkthrough evidence.
## Requirements
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

### Requirement: Human-operability task coverage is capability-complete
Human-operability validation SHALL treat the user task coverage ledger as complete only when every required UI functional capability maps to an in-scope user task or an explicitly scoped capability row.

#### Scenario: Capability has user task
- **WHEN** a capability is required and user-visible
- **THEN** the human-operability ledger links that capability through the existing feature/task rows to task frames, primary controls, feedback, cancel/error behavior, keyboard/focus, and walkthrough evidence

#### Scenario: Capability has no task
- **WHEN** a required capability has no user task and no bounded scoped-out row
- **THEN** human-operability confidence is blocked even if visible controls and functional chains pass

### Requirement: On-demand disclosure remains human-operable
Human-operability validation SHALL require every in-scope `user_on_demand` item to bind to an in-scope user task, a visible/enabled reveal control with a discoverable affordance contract, an action grammar whose feedback item resolves to that revealed content, a close or collapse path, and keyboard/focus-equivalent operation for hover-based disclosure.

#### Scenario: Hover detail has no keyboard equivalent
- **WHEN** optional details can be revealed by pointer hover but not by keyboard focus or an equivalent explicit control
- **THEN** human-operability validation blocks a complete or usable UI claim

#### Scenario: Expanded details cannot be dismissed
- **WHEN** a user reveals optional details and no close, collapse, blur, Escape, or equivalent return path exists
- **THEN** human-operability validation reports an incomplete on-demand interaction

#### Scenario: Reveal control has no content-bound feedback
- **WHEN** a reveal control is visible but its task grammar does not name the content item that appears
- **THEN** human-operability validation blocks the claim instead of treating generic feedback as proof

