## ADDED Requirements

### Requirement: Missing promised UI capability is a model miss
Post-runtime Model Miss Review SHALL treat user-observed missing UI functionality after green UI evidence as a model miss, not as a local visual or button-only defect.

#### Scenario: Required UI function was never modeled
- **WHEN** a user reports that a UI lacks a promised or expected function after prior FlowGuard evidence was green or used for a completion claim
- **THEN** Model Miss Review records a `boundary_missing` miss against the capability inventory, previous claim, affected feature/task/control/output, root cause, same-class capability candidates, and required repair evidence

#### Scenario: Function had only weak evidence
- **WHEN** a function was represented by label, screenshot, API existence, empty chart/table container, or prose but lacked output contract and implementation binding evidence
- **THEN** Model Miss Review records `evidence_overclaimed` and requires same-class capability/output evidence before broad closure
