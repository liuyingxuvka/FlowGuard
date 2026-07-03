## ADDED Requirements

### Requirement: FlowGuard is distributed as an AI-agent skill suite
FlowGuard public onboarding SHALL present `.agents/skills/` as the primary
AI-agent install and read surface.

#### Scenario: Agent reads public onboarding
- **WHEN** an AI agent reads the README or project integration guide
- **THEN** it MUST learn that complete agent setup means access to
  `AGENTS.md` and every FlowGuard `SKILL.md` under `.agents/skills/`
- **AND** it MUST NOT treat Python package installation as the skill install
  surface

#### Scenario: Default skill entry is visible
- **WHEN** an AI agent loads the FlowGuard skill suite
- **THEN** `model-first-function-flow` MUST be identified as the default
  entrypoint
- **AND** sibling FlowGuard skills MUST be described as part of the same suite

### Requirement: Executable checks are presented as skill-attached scripts
FlowGuard documentation SHALL describe executable checks as scripts or check
engine support for the skills rather than as the primary installation product.

#### Scenario: User needs executable evidence
- **WHEN** a user or agent needs to run FlowGuard checks
- **THEN** the docs MUST route to local check scripts, examples, or
  `python -m flowguard` compatibility commands as execution paths
- **AND** those commands MUST be described as check execution, not as the
  FlowGuard skill installation

### Requirement: Local active behavior requires installed skill sync
FlowGuard SHALL verify local installed AI-agent skill content after repository
skill guidance changes before claiming that active local AI behavior is
synchronized.

#### Scenario: Repository skill wording changes
- **WHEN** repository-managed FlowGuard skill files change
- **THEN** local installed Codex skill copies MUST be refreshed or reported as
  unsynced
- **AND** verification MUST compare guidance markers from the affected skill
  files rather than relying only on package version or directory existence
