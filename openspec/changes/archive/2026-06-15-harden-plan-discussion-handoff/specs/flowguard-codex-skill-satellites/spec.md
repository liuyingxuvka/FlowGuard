## ADDED Requirements

### Requirement: Plan detailing is a delegated simulator mode owner
FlowGuard Codex skill guidance SHALL present `flowguard-plan-detailing-compiler`
as the delegated `plan_detailing` owner for non-trivial plan discussions and
rough AI outlines after the DevelopmentProcessFlow simulator front door records
the mode.

#### Scenario: Plan detailing appears as delegated owner
- **WHEN** a Codex agent reads FlowGuard skill topology or reusable AGENTS guidance
- **THEN** `flowguard-plan-detailing-compiler` appears as the delegated
  `plan_detailing` owner under `flowguard-development-process-flow`

#### Scenario: Plan discussion records mode before delegation
- **WHEN** the task is a non-trivial plan discussion before implementation
- **THEN** Codex skill guidance selects DevelopmentProcessFlow first and records
  `plan_detailing` before any delegated PlanDetailing pass

### Requirement: Installed skills include updated plan-detailing guidance
Installed FlowGuard Codex skill synchronization SHALL refresh the local installed `flowguard-plan-detailing-compiler`, `flowguard-agent-workflow-rehearsal`, and `flowguard-development-process-flow` guidance when repository routing changes.

#### Scenario: Installed guidance is synchronized
- **WHEN** repository skill guidance is updated for plan discussion handoff
- **THEN** local installed skill copies are synchronized or an explicit unsynced boundary is reported before local Codex behavior is claimed
