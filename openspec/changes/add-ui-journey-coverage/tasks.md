## 1. OpenSpec And FlowGuard Model

- [x] 1.1 Create the `add-ui-journey-coverage` proposal, design, specs, and task list.
- [x] 1.2 Add a FlowGuard adoption model for app-level UI journey coverage and known-bad hazards.
- [x] 1.3 Validate the OpenSpec change and local FlowGuard model before production edits are trusted.

## 2. Package Helper API

- [x] 2.1 Add UI journey coverage dataclasses and report/reviewer helpers to `flowguard/ui_structure.py`.
- [x] 2.2 Export journey coverage helpers from `flowguard/__init__.py` and API surface groups.
- [x] 2.3 Add focused tests for passing app coverage and broken launch, entry, reachability, terminal, recovery, and blindspot hazards.

## 3. Templates And CLI

- [x] 3.1 Update the UI flow structure template with launch, new-project, load-existing, failure/recovery, terminal, and residual-blindspot coverage.
- [x] 3.2 Extend public template tests so generated UI journey coverage checks execute.

## 4. Codex Skill And Documentation

- [x] 4.1 Update `flowguard-ui-flow-structure` skill and protocol with the app-level journey coverage gate.
- [x] 4.2 Update `model-first-function-flow`, `docs/agents_snippet.md`, API docs, and UI Flow Structure docs.
- [x] 4.3 Update README, CHANGELOG, release checklist, and version references for the new capability.

## 5. Sync, Validation, And Release

- [x] 5.1 Sync repository-managed skills into the installed Codex skill directory.
- [x] 5.2 Sync the real Git checkout back to the shadow workspace after validation.
- [x] 5.3 Run skill validation, OpenSpec validation, FlowGuard model checks, focused tests, full regression, privacy scans, and install/shadow import checks.
- [x] 5.4 Commit, push, tag, create the GitHub Release, and verify release/version/readme alignment.
