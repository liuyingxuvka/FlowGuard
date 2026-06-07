## MODIFIED Requirements

### Requirement: Sync evidence covers local install, installed skills, shadow workspace, and git version
FlowGuard local release-quality synchronization SHALL verify all user-facing
local surfaces after guidance changes. Installed Codex skill verification SHALL
include content-level parity for affected repository-managed skills, including
critical route rows and handoff wording, rather than relying only on FlowGuard
package version, project audit, or source/shadow workspace sync.

#### Scenario: AI entry simplification is finalized
- **GIVEN** docs, skills, tests, and OpenSpec artifacts are updated
- **WHEN** the change is finalized locally
- **THEN** validation includes OpenSpec checks, focused docs/skill tests,
  practical model or regression checks, editable install verification,
  installed skill sync verification, shadow workspace import verification, and
  a scoped local git commit/tag when validation passes
- **AND** unrelated peer-agent changes remain unstaged unless they are part of
  this change

#### Scenario: Installed skill content drifts from repository source
- **WHEN** repository-managed FlowGuard skill prompts contain newer route or
  handoff guidance than the installed Codex skill root
- **THEN** completion evidence MUST report active AI behavior as unsynced until
  the installed skill files are refreshed and content parity is verified

#### Scenario: Version checks pass but skill text is stale
- **WHEN** package version, schema version, project audit, and shadow workspace
  checks pass
- **AND** an affected installed `SKILL.md` differs from the repository-managed
  `SKILL.md`
- **THEN** FlowGuard SHALL treat installed AI guidance evidence as incomplete
  for the affected skill until the text difference is resolved or explicitly
  scoped out
