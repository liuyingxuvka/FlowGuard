## Why

FlowGuard satellite skills are installed globally, but the global AGENTS prompt
still routes many coding and maintenance tasks through `model-first-function-flow`
as the first stop. That makes specialized routes such as
`flowguard-development-process-flow` under-trigger even when their direct
conditions are clear.

## What Changes

- Add a global FlowGuard skill routing rule that treats installed FlowGuard
  skills as peer routes and prefers the most specific direct satellite skill
  when the task clearly matches it.
- Reposition `model-first-function-flow` as the kernel for ordinary
  behavior/state modeling, unclear route selection, and cross-route
  coordination, not as the mandatory first stop for every FlowGuard task.
- Update the global Codex AGENTS prompt, repository AGENTS snippet, README, and
  model-first skill guidance to use the same route table.
- Add route-priority tests so staged development, UI interaction, model/test
  alignment, test mesh, structure mesh, model mesh, and model-miss tasks do not
  regress to model-first-only routing.
- Publish a patch release after synchronizing installed global skills, local
  editable install, shadow workspace, git tag, and GitHub Release.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `model-first-function-flow`: Clarifies that the kernel owns general
  model-first applicability, ordinary behavior/state modeling, unclear
  FlowGuard route selection, and cross-route coordination.
- `flowguard-global-routing`: Establishes global priority for direct
  FlowGuard satellite skills before falling back to the model-first kernel.

## Impact

- Global prompt: `<codex-home>\AGENTS.md`.
- Repository prompt material: `docs/agents_snippet.md`, README, and
  `.agents/skills/model-first-function-flow`.
- Tests: focused skill-doc route-priority assertions.
- Sync surfaces: installed Codex skills, local shadow workspace,
  local editable install, version/changelog/README, git tag, and GitHub
  Release.
