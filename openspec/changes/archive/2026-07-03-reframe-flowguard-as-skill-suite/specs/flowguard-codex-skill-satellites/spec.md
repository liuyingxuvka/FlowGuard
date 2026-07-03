## ADDED Requirements

### Requirement: Skill sync verifies the whole FlowGuard suite
Installed FlowGuard skill synchronization SHALL verify the complete current
suite of repository-managed FlowGuard skills rather than only package import or
one kernel skill.

#### Scenario: Local installed skills are checked
- **WHEN** local installed Codex skills are inspected after this guidance change
- **THEN** every repository-managed FlowGuard skill directory under
  `.agents/skills/` MUST have a corresponding installed skill directory or an
  explicit unsynced finding
- **AND** affected installed skill files MUST include the current skill-suite
  and check-script guidance markers before active behavior is claimed

### Requirement: Satellite wording does not imply package-first use
FlowGuard satellite skill wording SHALL preserve executable evidence gates
without teaching agents that package installation is the skill installation.

#### Scenario: Satellite hard gate is read
- **WHEN** a satellite skill mentions real executable FlowGuard checks
- **THEN** it MUST keep fake-framework rejection and skipped-evidence honesty
- **AND** it MUST NOT say that Python package setup alone completes the
  AI-agent skill setup
