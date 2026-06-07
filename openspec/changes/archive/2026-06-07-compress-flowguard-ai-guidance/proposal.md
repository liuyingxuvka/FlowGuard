## Why

FlowGuard's AI-facing guidance has accumulated repeated hard gates, route
tables, workflow detail, and helper inventories across AGENTS snippets and
repository-managed skills. This makes routine AI use slower and easier to
misroute even though the intended product direction is already a thin default
path with explicit escalation.

## What Changes

- Compress the default AI hot path so agents first see task-size triage, a
  single FlowGuard routing decision, and the smallest useful model/check loop.
- Move route-specific long-form workflow detail out of `SKILL.md` hot paths and
  into reference docs that are loaded only after the route is selected.
- Keep direct satellite skills discoverable, but make each satellite's
  `SKILL.md` a concise route shell instead of a repeated protocol document.
- Add explicit documentation/test budgets that prevent the kernel, satellite
  skills, and AGENTS snippet from growing back into monolithic prompts.
- Preserve FlowGuard hard gates, adoption/version checks, evidence honesty,
  OpenSpec traceability, and local install/shadow/git synchronization.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `flowguard-ai-entry-simplification`: Add prompt-budget, hot-path/reference
  layering, and local sync acceptance requirements for guidance compression.
- `flowguard-codex-skill-satellites`: Require satellite `SKILL.md` files to be
  concise route shells that delegate detailed protocol content to references.
- `flowguard-global-routing`: Centralize routing into a compact decision table
  and prevent duplicate route inventories across AGENTS and skill prompts.

## Impact

- Affected prompts/docs: `.agents/skills/*/SKILL.md`,
  `docs/agents_snippet.md`, README/API wording if needed, and this OpenSpec
  change.
- Affected tests: skill documentation tests that assert current topology,
  budget limits, route-shell wording, and installed/shadow sync expectations.
- Affected validation/sync: OpenSpec status, focused skill docs tests,
  practical FlowGuard model/regression checks, editable install refresh,
  installed skill sync, shadow workspace sync, and local git commit/tag
  evidence when validation passes.
