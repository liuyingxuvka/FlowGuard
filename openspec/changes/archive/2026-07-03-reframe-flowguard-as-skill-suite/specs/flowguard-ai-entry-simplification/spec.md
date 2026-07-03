## ADDED Requirements

### Requirement: AI entry leads with the skill suite
FlowGuard AI entry guidance SHALL present skill-suite loading before any
package, CLI, or metadata command.

#### Scenario: README quick start is read
- **WHEN** an agent reads the first setup path in README
- **THEN** the first path MUST tell the agent to load `.agents/skills/` and
  start with `model-first-function-flow`
- **AND** package or CLI commands MUST appear only as check execution or
  compatibility details

#### Scenario: Package-first wording is present
- **WHEN** public AI guidance says to install the Python package before loading
  the skills
- **THEN** the guidance is stale and MUST be rewritten before local completion
  is claimed
