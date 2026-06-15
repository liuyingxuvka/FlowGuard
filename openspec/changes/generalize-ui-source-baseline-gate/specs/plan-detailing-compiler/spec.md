## ADDED Requirements

### Requirement: UI plans name work mode and source obligations
PlanDetailingCompiler SHALL require UI plans to name UI work mode, source scope when present, target UI scope, allowed differences, evidence types, and must-fail counterexamples before implementation-ready claims.

#### Scenario: Source-based plan lacks source scope
- **WHEN** a UI plan declares source-based or mixed work
- **AND** it lacks source authority, source item/task scope, target mapping obligations, or allowed-difference evidence
- **THEN** plan detailing reports the plan as incomplete

#### Scenario: Greenfield plan has no user task rationale
- **WHEN** a UI plan declares greenfield work
- **AND** it lacks user goals, supported tasks, target UI rationale, or must-fail counterexamples for label-only validation
- **THEN** plan detailing reports the plan as incomplete
