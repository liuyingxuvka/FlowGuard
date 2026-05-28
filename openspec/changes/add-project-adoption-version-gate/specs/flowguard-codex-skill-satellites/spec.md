## ADDED Requirements

### Requirement: Satellite skills preserve target-project adoption
Every directly invokable FlowGuard satellite Skill SHALL preserve the target
project AGENTS/version adoption check so direct satellite use cannot bypass the
kernel's project adoption rule.

#### Scenario: Satellite runs in target project
- **WHEN** a standalone FlowGuard satellite Skill is used for real target
  project work
- **THEN** it tells the agent to ensure the project has a FlowGuard AGENTS
  managed block and project version record, or to record why that update was
  not performed
