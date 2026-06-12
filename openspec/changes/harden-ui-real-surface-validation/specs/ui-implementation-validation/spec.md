## ADDED Requirements

### Requirement: Enabled controls prove a real functional chain
UI Implementation Validation SHALL require every in-scope enabled actionable
control to have a real functional chain or an explicit pure-UI/deferred
blindspot classification. A functional chain MUST bind visible control, UI
event, code owner, backend/local/native function, observed UI state or display
update, evidence reference, result, and current revision.

#### Scenario: Button click produces observed UI result
- **WHEN** an enabled button is part of a runnable or complete UI claim
- **THEN** implementation validation requires evidence that clicking the
  visible control triggered the modeled UI event, reached the declared code
  owner/function, and produced the expected observed UI state or display update

#### Scenario: API existence is insufficient
- **WHEN** a control only cites an API route, handler name, or local function
  without click evidence and observed UI result
- **THEN** implementation validation blocks runnable/complete UI confidence

#### Scenario: Label match is insufficient
- **WHEN** a control only proves that its label, accessible name, or DOM text is
  correct
- **THEN** implementation validation treats the evidence as render evidence,
  not functional-chain evidence

#### Scenario: Native dialog branch is manually bounded
- **WHEN** a functional chain enters a native dialog, file picker, permission
  prompt, or OS shell action that cannot be fully automated
- **THEN** the chain must include structured manual/native evidence,
  observable result or blindspot, owner, validation boundary, and rationale

### Requirement: UI completion claims require implementation validation
FlowGuard SHALL require `UIImplementationValidation` for claims that an
implemented UI is runnable, complete, or has buttons wired to real behavior.

#### Scenario: Runnable claim has no implementation validation
- **WHEN** an agent claims a UI is runnable, complete, or button wiring is
  finished
- **AND** no current implementation validation exists for the relevant target
  revision
- **THEN** the claim is blocked or downgraded to design/model-only confidence
