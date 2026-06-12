## ADDED Requirements

### Requirement: UI workflow rehearsal separates evidence roles
AgentWorkflowRehearsal SHALL model non-trivial UI validation work with distinct
evidence roles when multiple agents or workstreams are used: UI inventory,
baseline callback semantics, implementation validation, and main-agent
integration.

#### Scenario: UI roles are all present
- **WHEN** a multi-agent UI workflow claims full runnable UI confidence
- **THEN** the rehearsal requires evidence packets for real UI inventory,
  baseline semantics when relevant, implementation click/function-chain
  validation, and integration review

#### Scenario: Agents only edit code
- **WHEN** a multi-agent UI plan assigns all agents to code edits and no agent
  or step owns inventory, semantics, or implementation evidence
- **THEN** rehearsal returns needs-revision or scoped confidence

#### Scenario: Main agent integrates role evidence
- **WHEN** subagents or peer agents produce UI evidence packets
- **THEN** the main agent must consume their evidence ids, current status, and
  blindspots before making a final claim
