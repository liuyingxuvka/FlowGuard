## ADDED Requirements

### Requirement: Project adoption is FlowGuard-only
FlowGuard project adoption, audit, and upgrade SHALL operate without discovering, installing, validating, or modifying SkillGuard, SkillGuard Global Router, `.skillguard`, or SkillGuard managed prompt blocks.

#### Scenario: Ordinary project is adopted
- **WHEN** `project-adopt` runs in a repository with no SkillGuard
- **THEN** it SHALL create only the FlowGuard-managed AGENTS block, `.flowguard/project.toml`, and FlowGuard adoption logs

#### Scenario: SkillGuard is absent
- **WHEN** `project-audit` or `project-upgrade` runs
- **THEN** missing SkillGuard packages, skills, contracts, router state, or prompts SHALL NOT create a finding or block FlowGuard readiness

#### Scenario: Zero-write path fails
- **WHEN** project adoption fails before its FlowGuard transaction commits
- **THEN** it SHALL leave no `.skillguard` directory, SkillGuard marker, or SkillGuard process evidence

### Requirement: Project upgrade validates the installed consumer suite
FlowGuard project audit and upgrade SHALL validate the current installed
consumer suite against the canonical suite map owned by the current FlowGuard
package source. The ordinary target repository SHALL NOT be treated as either
suite authority.

#### Scenario: Ordinary project has no author controls
- **WHEN** an ordinary project has no `.skillguard` directory or local FlowGuard skill suite and the current installed consumer suite is valid
- **THEN** project audit and upgrade SHALL pass suite reconciliation without writing author controls or a local skill suite into the project

#### Scenario: Installed consumer suite is unresolved
- **WHEN** the current installed consumer suite is missing, mismatched, or contains an unregistered reserved FlowGuard member
- **THEN** project upgrade SHALL block visibly before mutation and SHALL NOT consult a target-local suite map as a fallback

## MODIFIED Requirements

### Requirement: Shadow workspace sync helper
FlowGuard SHALL provide a tracked shadow sync helper that copies complete author source sets only into explicitly registered FlowGuard maintainer worktrees, optionally refreshes editable install metadata, and verifies import path, package version, schema version, and a named helper in that registered workspace. It MUST reject ordinary project and consumer installation roots before writing.

#### Scenario: Registered shadow verification succeeds
- **WHEN** the shadow sync helper targets a registered maintainer worktree and verification succeeds after copying source sets
- **THEN** it reports the registry identity, target import path, metadata version, schema version, and helper availability

#### Scenario: Shadow verification fails
- **WHEN** the registered target import path, package version, schema version, or helper availability does not match expectations
- **THEN** the helper exits non-zero and reports the mismatched field

#### Scenario: Ordinary project is supplied
- **WHEN** the requested target is not an explicitly registered maintainer worktree
- **THEN** the helper exits non-zero before copying FlowGuard or SkillGuard author material
