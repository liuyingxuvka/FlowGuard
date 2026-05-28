## Why

FlowGuard can already guide agents once they know to use it, but an external
project that adopts FlowGuard does not yet get a durable project-local rule
that names the FlowGuard GitHub repository, records the adopted version, and
forces future agents to refresh stale FlowGuard evidence before maintenance.
That leaves later agents guessing where FlowGuard comes from and when an old
project record must be upgraded.

## What Changes

- Add a project adoption/version gate for target repositories that use
  FlowGuard.
- Add a managed `AGENTS.md` FlowGuard project block that includes the GitHub
  repository URL, install/verification commands, version comparison policy,
  and evidence logging expectations.
- Add a `.flowguard/project.toml` manifest that records the adopted FlowGuard
  package version, schema version, repository URL, and last verification time.
- Add CLI helpers to audit, adopt, and upgrade project FlowGuard records without
  deleting existing project rules.
- Update FlowGuard Skill prompts, satellite Skill hard gates, project
  integration docs, templates, README, tests, and release/version metadata.

## Capabilities

### New Capabilities

- `project-adoption-version-gate`: Provides project-local FlowGuard adoption
  rules, version manifest records, AGENTS managed-block updates, and audit /
  adopt / upgrade commands for target repositories.

### Modified Capabilities

- `flowguard-skill-kernel`: Requires real target-project FlowGuard usage to
  check or update the target project's FlowGuard `AGENTS.md` block.
- `flowguard-codex-skill-satellites`: Requires directly invoked satellite
  skills to preserve the same target-project adoption rule instead of bypassing
  the kernel.
- `development-process-flow`: Treats project adoption/upgrade records,
  installed package version, and adoption evidence as versioned process
  artifacts for done/release claims.

## Impact

- Public API: new project adoption helper module, report/finding objects, and
  managed AGENTS/manifest helpers.
- CLI/templates: new `project-audit`, `project-adopt`, and `project-upgrade`
  commands plus project adoption template files.
- Skill/docs: update the kernel Skill, satellite Skills, reusable
  `docs/agents_snippet.md`, project integration docs, README, API surface, and
  changelog.
- Tests: add project adoption helper/CLI tests and update Skill/docs/template
  tests to require repository URL, version policy, and managed AGENTS behavior.
- Dependencies: none; keep the helper standard-library-only.
