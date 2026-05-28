## 1. OpenSpec And FlowGuard Preflight

- [x] 1.1 Create the `add-project-adoption-version-gate` OpenSpec change.
- [x] 1.2 Write proposal, design, capability specs, and tasks.
- [x] 1.3 Add a FlowGuard rollout model for project adoption/version gate behavior.
- [x] 1.4 Run the rollout model before implementation claims.

## 2. Project Adoption API And CLI

- [x] 2.1 Add a standard-library project adoption helper with managed AGENTS block, manifest, audit, adopt, and upgrade reports.
- [x] 2.2 Export the helper API through `flowguard.__init__` and API grouping constants.
- [x] 2.3 Add `project-audit`, `project-adopt`, and `project-upgrade` CLI commands.

## 3. Templates, Skills, And Docs

- [x] 3.1 Add project adoption template files and include the GitHub repository URL.
- [x] 3.2 Update the kernel Skill and all FlowGuard satellite Skills with the target-project adoption gate.
- [x] 3.3 Update `docs/agents_snippet.md`, project integration docs, README, API surface, and changelog.
- [x] 3.4 Keep installed/readme-facing copy clear that adoption logs and manifests do not replace executable checks.

## 4. Tests And Validation

- [x] 4.1 Add project adoption helper and CLI tests for missing/existing AGENTS, manifest writes, audit drift, and explicit upgrade.
- [x] 4.2 Update Skill/docs/template/API tests to require repository URL, version policy, and adoption gate wording.
- [x] 4.3 Run targeted tests, OpenSpec validation, FlowGuard rollout model, template/CLI checks, and full practical regression.

## 5. Synchronization And Closure

- [x] 5.1 Bump local package version and update public release notes.
- [x] 5.2 Sync editable install, installed FlowGuard skills, and the shadow workspace.
- [x] 5.3 Verify source and shadow imports report the new version/schema and that installed skills validate.
- [x] 5.4 Record adoption and KB postflight evidence without reverting peer-agent work.
