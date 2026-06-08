## ADDED Requirements

### Requirement: Visible UI surface is reviewed
The UI Flow Structure route SHALL provide a visible-surface review that accounts
for user-facing controls, status text, helper copy, placeholders, metadata, and
disabled-state reasons when those items are in scope for a modeled UI.

#### Scenario: Visible surface has user-facing purpose
- **WHEN** a UI route records visible controls, status text, helper copy,
  placeholders, metadata, or disabled controls
- **THEN** the review verifies that each item has a state or owner, a
  user-facing purpose, and a rationale before accepting the visible surface

#### Scenario: Internal terminology is rejected
- **WHEN** a visible UI item exposes internal implementation terminology such as
  mock, backend, hydration, debug route, dataset id, or render strategy without
  an explicit user-facing reason
- **THEN** the visible-surface review reports an internal-terminology finding

#### Scenario: Disabled control explains availability
- **WHEN** a visible disabled control is part of the UI surface
- **THEN** the review requires a user-understandable disabled reason or reports
  the disabled control as incomplete

### Requirement: UI route can review universal layout evidence
The UI Flow Structure route SHALL provide a universal geometry/layout evidence
surface for text overflow, control overlap, viewport bounds, dialog or popover
bounds, focus reachability, keyboard reachability, and scroll ownership.

#### Scenario: Layout issue blocks clean geometry evidence
- **WHEN** geometry evidence records text overflow, overlapping controls,
  out-of-bounds UI, missing focus reachability, missing keyboard reachability,
  or unclear scroll ownership
- **THEN** the geometry review reports the affected item as a layout evidence
  finding

#### Scenario: Passing geometry evidence supports handoff
- **WHEN** geometry evidence records checked bounds, no overflow, no overlap,
  focus reachability, keyboard reachability, and scroll ownership
- **THEN** the geometry review can pass for the declared UI surface boundary

### Requirement: UI route can model hot and cold interaction paths
The UI Flow Structure route SHALL provide a responsiveness contract that names
hot-path user feedback, cold-path work, stale-result guards,
cancellation/coalescing behavior, and stable regions when responsiveness claims
are in scope.

#### Scenario: Hot path has immediate feedback
- **WHEN** a UI interaction is modeled as a hot-path action
- **THEN** the responsiveness review requires a feedback target or reports the
  hot path as missing immediate feedback

#### Scenario: Cold result cannot overwrite newer state
- **WHEN** a UI interaction starts cold-path work that may finish after later
  user input
- **THEN** the responsiveness review requires a stale-result guard,
  cancellation, or coalescing rule before accepting the contract

#### Scenario: Stable region is preserved
- **WHEN** a UI region is marked stable across unrelated input changes
- **THEN** the responsiveness review requires a preservation rule or reports the
  stable region as unprotected
