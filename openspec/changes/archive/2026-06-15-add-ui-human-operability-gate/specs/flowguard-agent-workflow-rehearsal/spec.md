## ADDED Requirements

### Requirement: Multi-agent UI workflows include human-operability role evidence
AgentWorkflowRehearsal SHALL require a human-operability evidence role for
multi-agent UI workflows that claim complete, usable, or release-ready UI
confidence.

#### Scenario: Human-operability role is missing
- **WHEN** a multi-agent UI workflow claims broad UI confidence
- **AND** role evidence lacks `ui_human_operability`
- **THEN** rehearsal blocks the broad claim or records it as scoped
