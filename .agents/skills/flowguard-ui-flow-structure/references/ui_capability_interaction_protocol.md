# UI Capability And Interaction Protocol

Use this protocol for non-trivial UI work and every implemented/runnable/complete capability claim.

## Capability coverage

Build `UIFunctionalCapabilityInventory` from accepted user/product tasks for greenfield work or declared source authority for source-based/mixed work. For every required capability, record:

- `UIFeatureContract` and `UIUserTaskFrame` or task ledger id;
- journey/control/event path and functional/code owner;
- implementation/test evidence boundary;
- `UICapabilityOutputContract` for charts, tables, files, generated artifacts, saved/deleted items, refreshed lists, status changes, or navigation results;
- owner, reason, validation boundary, and rationale for scoped/deferred/blocked/manual/pure-UI items.

Use `review_ui_functional_capability_coverage(...)`. A button inventory, label, route, API, empty container, or self-selected small task list cannot prove capability coverage.

## Interaction model

Represent the behavior as:

```text
UI event x UI state -> Set(UI output x UI state)
```

Build `UIControl`, `UIDisplayElement`, `UIStateNode`, and `UITransition` rows with initial/terminal/failure states, recovery/cancel/retry events, destructive-action prominence, visible/enabled/disabled/hidden availability per state, display ownership, and redundancy rationale.

Block or scope unknown states/controls, unowned events, missing initial state, recoverable failures without recovery, destructive actions promoted as ordinary primary progress, implied-only availability, duplicate same-level controls, or repeated semantic information with no rationale.

## Handoff

Complete app claims continue to journey coverage. Local component claims may scope journeys with reason. Implemented claims continue to functional-chain validation. Transition-test claims continue to geometry/transition projection; the interaction model itself is not test evidence.
