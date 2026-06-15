## ADDED Requirements

### Requirement: Rehearsal reports include completion ledger fields
AgentWorkflowRehearsal SHALL expose a completion ledger in its report with planned step ids, completed step ids, blocked step ids, skipped step ids, required recheck ids, handoff evidence ids, and final claim boundary.

#### Scenario: Passing rehearsal reports ledger
- **WHEN** a coherent workflow plan is reviewed
- **THEN** the report includes `planned_steps`, `completed_steps`, `blocked_steps`, `skipped_steps`, `required_rechecks`, `handoff_points`, and `final_claim_boundary`
- **AND** the handoff points include produced, continue, and final evidence ids declared by the plan

#### Scenario: Blocked findings appear in ledger
- **WHEN** a workflow plan has blocking findings for a step or skill
- **THEN** the report lists the affected step or skill in the completion ledger's blocked or required-recheck fields

### Requirement: Rehearsal consumes plan-detail handoff for plan discussions
AgentWorkflowRehearsal SHALL treat a PlanDetail projection as the structured workflow handoff when a non-trivial plan discussion selects multiple skills, tools, agents, side effects, or validation routes.

#### Scenario: Multi-skill plan uses projected steps
- **WHEN** a PlanDetail projection supplies selected skills, ordered steps, evidence gates, side effects, and rework targets
- **THEN** AgentWorkflowRehearsal reviews the projected workflow using those rows rather than a new free-form summary

#### Scenario: Missing projected gate blocks broad claim
- **WHEN** a projected workflow lacks required evidence, continue evidence, final evidence, or a rework target
- **THEN** AgentWorkflowRehearsal reports a finding and the completion ledger prevents full confidence

### Requirement: Completion ledger is not implementation proof
AgentWorkflowRehearsal SHALL identify planned and blocked workflow completion boundaries without claiming that implementation, tests, release, or production validation have completed.

#### Scenario: Ledger does not replace downstream evidence
- **WHEN** a rehearsal report includes completed planned steps and handoff points
- **THEN** the report still requires downstream route evidence before done, release, publish, or production-confidence claims
