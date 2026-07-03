## ADDED Requirements

### Requirement: Kernel identifies the skill-suite entrypoint
The `model-first-function-flow` skill SHALL identify itself as the default
entrypoint for the FlowGuard skill suite.

#### Scenario: Kernel SKILL is read first
- **WHEN** an AI agent opens `.agents/skills/model-first-function-flow/SKILL.md`
- **THEN** it MUST learn that the sibling FlowGuard skills under
  `.agents/skills/` are part of the same suite
- **AND** it MUST NOT treat a Python package import as proof that the AI-agent
  skill suite is installed

### Requirement: Kernel separates check execution from skill availability
The kernel SHALL distinguish skill availability from executable check
availability.

#### Scenario: Check engine is unavailable
- **WHEN** the agent can read FlowGuard skills but cannot run executable checks
- **THEN** it MUST report executable evidence as blocked or scoped
- **AND** it MUST still preserve the route decision and skill-suite handoff
  boundary
