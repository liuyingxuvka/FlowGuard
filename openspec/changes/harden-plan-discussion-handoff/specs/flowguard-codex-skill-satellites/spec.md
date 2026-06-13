## ADDED Requirements

### Requirement: Plan detailing is a peer Codex satellite route
FlowGuard Codex skill guidance SHALL present `flowguard-plan-detailing-compiler` as a directly invokable peer satellite route for non-trivial plan discussions and rough AI outlines, not as a hidden child step under DevelopmentProcessFlow.

#### Scenario: Plan detailing appears beside peer satellites
- **WHEN** a Codex agent reads FlowGuard skill topology or reusable AGENTS guidance
- **THEN** `flowguard-plan-detailing-compiler` appears beside `flowguard-development-process-flow`, `flowguard-agent-workflow-rehearsal`, UI Flow Structure, TestMesh, ModelMesh, StructureMesh, Model-Test Alignment, and Model-Miss Review

#### Scenario: Plan discussion does not route only to development process
- **WHEN** the task is a non-trivial plan discussion before implementation
- **THEN** Codex skill guidance selects PlanDetailing before DevelopmentProcessFlow unless the task is already a structured lifecycle freshness review

### Requirement: Installed skills include updated plan-detailing guidance
Installed FlowGuard Codex skill synchronization SHALL refresh the local installed `flowguard-plan-detailing-compiler`, `flowguard-agent-workflow-rehearsal`, and `flowguard-development-process-flow` guidance when repository routing changes.

#### Scenario: Installed guidance is synchronized
- **WHEN** repository skill guidance is updated for plan discussion handoff
- **THEN** local installed skill copies are synchronized or an explicit unsynced boundary is reported before local Codex behavior is claimed
