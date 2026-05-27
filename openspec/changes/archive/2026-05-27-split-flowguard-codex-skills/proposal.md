## Why

FlowGuard's `model-first-function-flow` Skill has grown from a compact kernel
into a router for many mature sub-protocols. Codex should be able to invoke
the high-frequency routes directly while the kernel remains the canonical
entrypoint for applicability, hard gates, and ambiguous routing.

## What Changes

- Keep `model-first-function-flow` as the FlowGuard Skill Kernel and global
  entrypoint.
- Add seven standalone Codex skills as peers to the kernel:
  `flowguard-model-test-alignment`, `flowguard-development-process-flow`,
  `flowguard-model-miss-review`, `flowguard-code-structure-recommendation`,
  `flowguard-model-mesh`, `flowguard-test-mesh`, and
  `flowguard-structure-mesh`.
- Update the global AGENTS snippet so repositories describe the new
  "kernel plus satellite skills" architecture instead of treating all routes
  as internal-only sub-protocols.
- Keep package helper APIs and CLI templates explicitly separate from Codex
  skills.
- Add validation that the repository skill set, installed skill set, and public
  documentation stay in sync.
- Publish a new GitHub release after version, changelog, tests, installed
  skills, local shadow workspace, tag, and GitHub Release are aligned.

## Capabilities

### New Capabilities

- `flowguard-codex-skill-satellites`: Codex can directly discover and use the
  seven route-specific FlowGuard skills while preserving the kernel as the
  canonical router and hard-gate owner.

### Modified Capabilities

- None.

## Impact

- Affected skill assets under `.agents/skills/`.
- Affected global prompt guidance in `docs/agents_snippet.md` and related
  public documentation.
- Affected tests for skill documentation and release/install consistency.
- Version, changelog, local editable installation, shadow workspace sync, git
  tag, and GitHub Release must be updated together.
