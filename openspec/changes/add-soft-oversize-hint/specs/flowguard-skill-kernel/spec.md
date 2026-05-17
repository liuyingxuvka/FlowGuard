## MODIFIED Requirements

### Requirement: Skill Kernel remains compact and route-oriented
The `model-first-function-flow` Skill SHALL keep its main `SKILL.md` focused on
triggering, hard gates, route selection, workflow skeleton, and resource
mapping.

#### Scenario: Oversized work receives a soft split hint
- **WHEN** a model, test, script, module, or command is becoming large, slow, or
  hard to follow
- **THEN** the Skill suggests considering whether a parent/child split would
  improve maintainability or verification
- **AND** the Skill does not require fixed runtime thresholds or mandatory
  splitting

#### Scenario: External planning artifacts remain optional
- **WHEN** a compatible planning or specification artifact exists
- **THEN** the Skill may inspect it as optional context
- **AND** FlowGuard remains usable without any external planner
