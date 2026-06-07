## ADDED Requirements

### Requirement: Hot-path prompt budgets are enforced
FlowGuard AI guidance SHALL enforce explicit size budgets for first-read prompt
surfaces so the thin default path remains operational rather than aspirational.

#### Scenario: Skill docs tests inspect first-read surfaces
- **WHEN** repository skill documentation tests run
- **THEN** they verify the kernel skill, satellite skill shells, and reusable
  AGENTS snippet remain within their configured hot-path budgets

#### Scenario: Prompt detail moves to references
- **WHEN** guidance needs route-specific protocol detail, helper inventories, or
  long examples
- **THEN** the first-read prompt points to a reference document instead of
  duplicating that detail inline

### Requirement: Guidance compression preserves local synchronization evidence
FlowGuard guidance compression SHALL be finalized only after repository source,
editable install behavior, installed Codex skills, shadow workspace imports,
and local git evidence are aligned.

#### Scenario: Compressed guidance is finalized locally
- **WHEN** compressed prompt or skill guidance is ready to claim done
- **THEN** validation includes focused skill docs tests, practical FlowGuard
  model/regression checks, editable install verification, installed skill sync
  verification, shadow workspace import verification, and local git status
  evidence

#### Scenario: Repository-only prompt edit is not installed behavior
- **WHEN** a repository-managed skill prompt changes but installed Codex skills
  have not been refreshed or checked
- **THEN** completion evidence MUST report the installed behavior as unsynced or
  scoped instead of claiming active local behavior
