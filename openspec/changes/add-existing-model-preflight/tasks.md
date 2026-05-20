## 1. OpenSpec And FlowGuard Modeling

- [x] 1.1 Capture the change proposal, design, tasks, and specs.
- [x] 1.2 Add a local FlowGuard model covering light discussion grounding,
  full implementation preflight, skip cases, and known-bad duplicate ownership.
- [x] 1.3 Run the local FlowGuard model checks.

## 2. Package Helper And Template

- [x] 2.1 Add existing-model preflight data structures and review helper.
- [x] 2.2 Export the helper in the public API.
- [x] 2.3 Add template files and CLI support.
- [x] 2.4 Add unit tests for pass, skip, missing model search, duplicate risk,
  stale evidence, and new-boundary rationale.

## 3. Codex Skill And Routing Guidance

- [x] 3.1 Add `flowguard-existing-model-preflight` skill, agent metadata, and
  reference protocol.
- [x] 3.2 Update model-first kernel guidance to list the companion skill and
  explain light/full model grounding.
- [x] 3.3 Update `docs/agents_snippet.md`, README, and skill collaboration docs.
- [x] 3.4 Update skill-doc tests and route-trigger tests.

## 4. Validation And Sync

- [x] 4.1 Validate the OpenSpec change.
- [x] 4.2 Run focused tests for the helper, docs, skill trigger model, and local
  FlowGuard model.
- [x] 4.3 Run full regression in the background and verify final exit evidence.
- [x] 4.4 Bump patch version and update changelog.
- [x] 4.5 Sync installed Codex skills.
- [x] 4.6 Sync the configured shadow workspace.
- [x] 4.7 Refresh local editable install and verify imports from both
  workspaces.
- [x] 4.8 Verify git state locally; do not push, tag, or create GitHub Release
  until the user resumes publishing.
