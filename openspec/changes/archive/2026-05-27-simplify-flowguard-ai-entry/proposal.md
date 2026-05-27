## Why

FlowGuard's core model remains small, but the AI-facing guidance now exposes too
many peer routes, proof terms, and helper layers at the default entry point.
Agents can miss the simple path, choose the wrong satellite skill, or skip
FlowGuard entirely because the first instructions feel heavier than the task.

## What Changes

- Add a thin default AI entry path that foregrounds the smallest useful
  FlowGuard workflow: identify the risky boundary, model `Input x State ->
  Set(Output x State)`, add one meaningful invariant or scenario, run the
  check, inspect counterexamples, then escalate only when a named risk requires
  it.
- Reframe advanced routes as explicit escalation paths instead of default
  reading material for every task.
- Update public and agent-facing docs so the public product surface separates
  the minimal path from internal maintenance and high-risk release evidence.
- Keep all satellite skills and package helper APIs available, but make the
  route table easier to scan and reduce repeated terminology in the kernel and
  AGENTS snippet.
- Add prompt/documentation tests that protect the thin-entry contract and catch
  stale satellite-count wording.
- Sync installed skills, editable install, shadow workspace, package version,
  changelog, and local git version after validation.

## Capabilities

### New Capabilities

- `flowguard-ai-entry-simplification`: Defines the default AI entry path,
  escalation boundaries, and public/internal surface separation for FlowGuard
  guidance.

### Modified Capabilities

None. Existing route semantics stay intact; this change modifies guidance,
discoverability, and synchronization behavior rather than checker behavior.

## Impact

- Affected docs: README, API surface docs, product architecture, AGENTS
  snippet, and related OpenSpec artifacts.
- Affected skills: `model-first-function-flow` and, where needed, concise
  satellite wording that points back to the thin default path.
- Affected tests: skill/docs tests that assert the minimal path, advanced-route
  escalation, and current satellite topology.
- Affected release surfaces: pyproject version, changelog, installed Codex
  skills, local editable install, the local shadow workspace, and local git
  tag/commit.
