## ADDED Requirements

### Requirement: AI hot paths prefer structured handoff outputs
FlowGuard AI-facing hot paths SHALL instruct agents to read structured
SummaryReport ledger, maintenance obligations, maintenance scan actions, and
revalidation recommendations before manually inferring the next route from
prompt prose.

#### Scenario: Summary report has route-owned gaps
- **WHEN** an agent finishes a model-first check and the summary report has
  route-owned gaps
- **THEN** the hot-path guidance SHALL direct the agent to the structured
  action hints and maintenance scan handoff before broad confidence claims

#### Scenario: No structured handoff is available
- **WHEN** a legacy report lacks structured handoff fields
- **THEN** the agent may fall back to the compact route table without treating
  the missing structure as validation evidence
