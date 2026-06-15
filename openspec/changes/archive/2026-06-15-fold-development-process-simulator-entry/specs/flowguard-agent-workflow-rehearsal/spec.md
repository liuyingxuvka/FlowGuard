## ADDED Requirements

### Requirement: AgentWorkflowRehearsal acts as simulator workflow mode
AgentWorkflowRehearsal SHALL act as the `agent_workflow` internal mode for the
development-process simulator while preserving explicit direct use when a user
names `flowguard-agent-workflow-rehearsal`.

#### Scenario: Simulator delegates multi-skill workflow
- **WHEN** the development-process simulator selects `agent_workflow`
- **THEN** AgentWorkflowRehearsal SHALL review selected skills, skipped
  candidates, skill order, side effects, continue gates, rework gates,
  validation guidance, and final claim boundaries

#### Scenario: Direct explicit use remains available
- **WHEN** a user explicitly asks to use `flowguard-agent-workflow-rehearsal`
- **THEN** AgentWorkflowRehearsal SHALL remain directly invokable with a fresh
  current-machine skill inventory and its existing hard gates

#### Scenario: Generic automatic use enters simulator
- **WHEN** a user generically asks for a non-trivial workflow involving
  multiple skills, tools, plugins, background validations, external actions,
  install sync, git sync, release, archive, or publish steps
- **THEN** AgentWorkflowRehearsal guidance SHALL point the automatic route to
  `flowguard-development-process-flow` and `agent_workflow` mode rather than
  presenting itself as the ordinary first entry
