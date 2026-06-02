## ADDED Requirements

### Requirement: UI transitions project to transition coverage cells
UI Flow Structure SHALL allow modeled UI transitions to be projected into transition coverage cells before runnable UI completion claims.

#### Scenario: UI transition becomes coverage cell
- **WHEN** a UI transition declares event id, source state, target state, output, and function block
- **THEN** FlowGuard can project it to a transition coverage cell with a stable target id

#### Scenario: Runnable UI evidence targets transition cells
- **WHEN** implemented UI completion is claimed
- **THEN** browser, desktop, or manual click-through evidence can be linked to projected transition cell ids
- **AND** missing failure, recovery, cancel, or terminal transition evidence remains visible

### Requirement: UI transition projection does not replace UI journey review
Transition coverage projection SHALL support UI implementation evidence but SHALL NOT replace UI journey coverage, structure derivation, text hierarchy, or residual blindspot reporting.

#### Scenario: Journey gap remains visible
- **WHEN** transition cells are generated but the UI journey coverage still misses a reachable event
- **THEN** the UI route reports the journey gap instead of accepting transition projection as complete UI coverage
