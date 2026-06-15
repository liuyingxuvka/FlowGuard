## ADDED Requirements

### Requirement: User task coverage ledger precedes human-operable UI claims
FlowGuard UI Flow Structure SHALL require a user task coverage ledger before a
UI can be called human-operable, release-ready, or fully covered for user-facing
functionality. The ledger MUST account every in-scope user-visible functional
capability, user task, task flow, UI journey/control path, functional chain, and
evidence boundary.

#### Scenario: Feature maps to task
- **WHEN** a user-visible feature or functional capability is in scope
- **THEN** the ledger requires at least one mapped user task or an explicit
  out-of-scope reason

#### Scenario: Task maps to UI path
- **WHEN** a user task is in scope
- **THEN** it requires a task frame with entry, main, alternate, cancel, error,
  success, feedback, and UI journey/control links

#### Scenario: UI primary control has no task owner
- **WHEN** a visible primary control is in scope
- **AND** it maps to no user task
- **THEN** UI Flow Structure blocks human-operable and release-ready claims

### Requirement: Human-operability contracts align perceived UI with actual UI
FlowGuard UI Flow Structure SHALL model perceived role, actual role, visual
cue, expected action, expected result, region ownership, action grammar,
dialog/window return, keyboard/focus behavior, and walkthrough evidence before
human-operable UI claims.

#### Scenario: Static item looks actionable
- **WHEN** a visible item is perceived as a button, input, or link
- **AND** its actual role is readonly, status, display, or container
- **THEN** the operability review requires a safe mismatch disposition or
  blocks broad UI confidence

#### Scenario: Action grammar has duplicate primary controls
- **WHEN** two same-state same-level controls express the same semantic action
- **THEN** the review requires one primary action and a rationale for alternates
  or duplicate groups

#### Scenario: Dialog return semantics are incomplete
- **WHEN** a task enters a native dialog, file picker, save dialog, OS shell, or
  modal window
- **THEN** the review requires success, cancel, error, focus-return, feedback,
  and manual/native boundary semantics

#### Scenario: Keyboard path is undefined
- **WHEN** a task is claimed human-operable
- **THEN** Tab order, default Enter behavior, Escape behavior, disabled-skip
  policy, and focus return must be defined or explicitly out of scope

#### Scenario: Walkthrough reports confusion
- **WHEN** a walkthrough step marks user confusion
- **THEN** the review blocks human-operable confidence unless mitigation,
  rationale, or a scoped blindspot is recorded
