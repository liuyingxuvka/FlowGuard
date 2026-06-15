## ADDED Requirements

### Requirement: Observed UI inventory is the first hard gate
FlowGuard UI Flow Structure SHALL require a rendered or observed UI inventory
before an existing, migrated, runnable, or complete UI can be called modeled.
The inventory MUST list real visible controls, inputs, selects, tables,
display fields, status text, native-dialog triggers, and visible commands for
the observed target and revision.

#### Scenario: Observed item maps to model owner
- **WHEN** an observed inventory item is visible in an in-scope UI state
- **THEN** the UI review requires it to map to a `UIControl`,
  `UIDisplayElement`, or `UIVisibleSurfaceItem`
- **AND** the mapped owner must be registered in the reviewed UI model or
  visible surface

#### Scenario: Observed item is missing from model
- **WHEN** an observed inventory includes an in-scope visible button, input,
  select, table, display field, status text, native-dialog trigger, or command
  with no mapped model owner and no scoped blindspot
- **THEN** UI Flow Structure blocks model-complete and runnable-UI claims

#### Scenario: Model-only surface cannot prove real UI coverage
- **WHEN** a UI model declares controls and visible items but no observed
  inventory evidence exists for an existing or runnable UI claim
- **THEN** the claim remains design-only or scoped

### Requirement: Source-baseline interaction semantics are modeled for source-based parity
FlowGuard UI Flow Structure SHALL require source-based parity claims to model
source-baseline interaction semantics, not only visible control names. The
baseline gate MUST cover relevant native pickers, external opens, save/custom
dialogs, no-handler controls, trigger/confirm/cancel/value/result/error
branches, and native/manual boundaries.

#### Scenario: File picker baseline covers choose and cancel
- **WHEN** a source-based UI claims parity with a source file picker
- **THEN** the source interaction gate requires trigger, confirm, cancel,
  selected value, result feedback, and error-path semantics unless a branch is
  explicitly out of scope

#### Scenario: No-handler button remains visible
- **WHEN** a source baseline has a visible enabled button with no handler
- **THEN** the target UI must either model it as non-functional/disabled with
  a user-facing reason or provide a replacement functional chain

#### Scenario: Native opener has scoped evidence
- **WHEN** a source-based UI uses or replaces an external opener
- **THEN** the source-baseline interaction gate requires structured evidence for the
  visible trigger, native/local action, observable result or manual boundary,
  and any scoped blindspot
