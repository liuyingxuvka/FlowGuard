## ADDED Requirements

### Requirement: Project integration separates skill setup from check commands
Project integration guidance SHALL separate AI skill-suite setup from executable
check command setup.

#### Scenario: Target project integration is read
- **WHEN** a user or agent reads `docs/project_integration.md`
- **THEN** it MUST first explain how the target agent can access the FlowGuard
  skill suite
- **AND** project adoption, audit, upgrade, import, and CLI commands MUST be
  described as project-record or check-execution commands, not as the skill
  install surface

### Requirement: Package metadata does not prove skill setup
FlowGuard project adoption/version guidance SHALL not treat package metadata as
proof that AI-agent skills are available.

#### Scenario: Package metadata is current but skills are missing
- **WHEN** package version, schema version, or project audit passes
- **AND** `.agents/skills/` is not available to the AI agent
- **THEN** FlowGuard skill setup MUST be reported as incomplete or scoped
