## ADDED Requirements

### Requirement: Satellite skills use concise route shells
Each directly invokable FlowGuard satellite skill SHALL keep its `SKILL.md`
first-read surface to a concise route shell while preserving standalone hard
gates and a clear reference handoff.

#### Scenario: Satellite route shell is inspected
- **WHEN** a repository-managed satellite `SKILL.md` is read by an agent
- **THEN** it contains the skill name, route trigger, skip/return guidance, hard
  gates, a minimum workflow, validation/claim boundary notes, non-goals, and a
  route-specific reference path without embedding the full protocol inline

#### Scenario: Standalone use keeps hard gates
- **WHEN** a satellite skill is copied or installed outside the FlowGuard repo
- **THEN** it still tells the agent to use the real FlowGuard package, preserve
  AGENTS/version adoption checks for real project use, keep skipped evidence
  visible, and avoid fake mini-frameworks

### Requirement: Installed satellite sync is content-aware
Installed FlowGuard satellite skill synchronization SHALL verify repository and
installed skill content rather than only checking that a directory exists.

#### Scenario: Existing installed skill is refreshed
- **WHEN** a repository-managed satellite skill already exists in the local
  installed Codex skills directory
- **THEN** synchronization refreshes changed content or reports an explicit
  mismatch before local installed behavior is claimed
