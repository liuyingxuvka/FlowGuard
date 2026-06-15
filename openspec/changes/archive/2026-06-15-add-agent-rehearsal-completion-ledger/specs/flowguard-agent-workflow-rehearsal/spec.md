## ADDED Requirements

### Requirement: Agent workflow rehearsal completion ledger
AgentWorkflowRehearsal SHALL include a compact completion ledger in its report
for non-trivial plans.

#### Scenario: Plan is reviewed
- **WHEN** an `AgentWorkflowPlan` is reviewed
- **THEN** the report includes `planned_steps`, `completed_steps`,
  `blocked_steps`, `skipped_steps`, `required_rechecks`, `handoff_points`, and
  `final_claim_boundary`

#### Scenario: A step-level finding blocks execution
- **WHEN** a blocked finding names a workflow step
- **THEN** that step id appears in `blocked_steps`

#### Scenario: Candidate skill is skipped
- **WHEN** a candidate skill is skipped with a disposition row
- **THEN** that skill appears in `skipped_steps`

### Requirement: Rehearsal ledger is not execution proof
The completion ledger SHALL distinguish pre-execution rehearsal from actual
implementation completion evidence.

#### Scenario: Rehearsal passes
- **WHEN** rehearsal status is `pass`
- **THEN** `final_claim_boundary` states that the plan may proceed but downstream
  route evidence is still required for done, release, or publish claims
