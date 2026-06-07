## ADDED Requirements

### Requirement: Agent workflow rehearsal accepts plan-detail handoff
AgentWorkflowRehearsal SHALL treat a plan-detail record as the structured workflow handoff for selected skills, skipped candidates, ordered steps, evidence gates, rework gates, and final claim scope.

#### Scenario: Detailed handoff rehearses cleanly
- **WHEN** a plan-detail projection supplies selected skills, ordered steps, continue gates, rework gates, side effects, and final evidence ids
- **THEN** AgentWorkflowRehearsal can review the projected workflow plan

#### Scenario: Missing plan-detail gate remains unsafe
- **WHEN** a projected workflow step lacks required evidence, continue evidence, or rework target
- **THEN** AgentWorkflowRehearsal reports the same gate finding as for a hand-written AgentWorkflowPlan
