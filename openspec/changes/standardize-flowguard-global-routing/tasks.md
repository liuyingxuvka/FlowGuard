## 1. Routing Contract

- [x] 1.1 Update global `<codex-home>\AGENTS.md` to route FlowGuard
  tasks through a peer satellite skill table before using the model-first
  kernel.
- [x] 1.2 Update repository `docs/agents_snippet.md` with the same peer route
  table.
- [x] 1.3 Update `model-first-function-flow` skill guidance so it is framed as
  the kernel for ordinary behavior/state modeling, unclear routes, and
  cross-route coordination.
- [x] 1.4 Update README skill architecture language to describe FlowGuard
  skills as global peers.

## 2. OpenSpec And FlowGuard Evidence

- [x] 2.1 Validate the OpenSpec change.
- [x] 2.2 Run a DevelopmentProcessFlow review for the prompt, skill, docs,
  validation, install sync, version, git, tag, and GitHub Release lifecycle.
- [x] 2.3 Run the relevant existing FlowGuard self-model checks.

## 3. Tests And Validation

- [x] 3.1 Add route-priority tests for direct satellite selection and kernel
  fallback.
- [x] 3.2 Run focused skill-doc tests and relevant FlowGuard route tests.
- [x] 3.3 Run skill validators for modified installed/source skills.
- [x] 3.4 Run full regression in the background and verify final exit evidence.

## 4. Sync And Release

- [x] 4.1 Sync global installed skills and global AGENTS prompt.
- [x] 4.2 Sync `<shadow-workspace>`.
- [x] 4.3 Refresh local editable install and verify imports from both local
  workspaces.
- [x] 4.4 Bump patch version, update changelog and README release table.
- [x] 4.5 Commit scoped changes, tag the release, push branch and tag, and
  create the GitHub Release.
- [x] 4.6 Verify GitHub Release, tag, README version, local install, global
  prompt, and shadow workspace are aligned.
