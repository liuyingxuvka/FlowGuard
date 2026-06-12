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

### Requirement: MATLAB baseline callback semantics are modeled for migration parity
FlowGuard UI Flow Structure SHALL require MATLAB migration parity claims to
model baseline callback semantics, not only visible control names. The baseline
gate MUST cover relevant `uigetfile`, `uigetdir`, `winopen`, no-callback
buttons, choose/cancel/path/error/load-result branches, and native/manual
boundaries.

#### Scenario: File picker baseline covers choose and cancel
- **WHEN** a migrated UI claims parity with a MATLAB `uigetfile` callback
- **THEN** the baseline callback gate requires choose-file, cancel, selected
  path, load-result, and error-path semantics unless a branch is explicitly
  out of scope

#### Scenario: No-callback button remains visible
- **WHEN** a MATLAB baseline has a visible enabled button with no callback
- **THEN** the migrated UI must either model it as non-functional/disabled with
  a user-facing reason or provide a replacement functional chain

#### Scenario: Native opener has scoped evidence
- **WHEN** a migrated UI uses or replaces MATLAB `winopen`
- **THEN** the baseline semantics gate requires structured evidence for the
  visible trigger, native/local action, observable result or manual boundary,
  and any scoped blindspot
