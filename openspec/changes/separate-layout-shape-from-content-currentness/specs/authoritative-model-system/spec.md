## MODIFIED Requirements

### Requirement: Current model authority includes layout identity

The current observed model head SHALL bind a compact layout-shape identity and the exact governed source, model, test, configuration, and toolchain identities consumed by its accepted `ModelRevisionSet`. Evidence, audit output, transient work, and non-authoritative history SHALL NOT become model freshness inputs merely because their bytes change. A shape or governed-input change SHALL make the affected authority stale until one accepted current `ModelRevisionSet` rebuilds the affected snapshot, owner evidence, and pointer.

#### Scenario: Runtime evidence changes without a governed-input change

- **WHEN** an evidence object is added or replaced under a valid evidence root while the layout shape and governed inputs remain unchanged
- **THEN** the model authority SHALL remain current with respect to those governed inputs
- **AND** evidence lifecycle SHALL determine whether the object is current, pinned, or collectible

#### Scenario: Governed source changes

- **WHEN** a model, source, test, configuration, or toolchain input bound by the current revision changes
- **THEN** authority audit SHALL block the affected owner closure with stale governed-input identity
- **AND** it SHALL not select an older snapshot as fallback

#### Scenario: Stored model points at a changed layout

- **WHEN** the live layout identity differs from the identity bound by the
  accepted model revision
- **THEN** authority audit SHALL block with a stale layout/model identity and
  SHALL not select an older snapshot

#### Scenario: Direct model rebuild follows layout rewrite

- **WHEN** a current layout and affected source/model inputs are frozen
- **THEN** one accepted revision set MAY replace the observed head and produce a new current snapshot and activation receipt
