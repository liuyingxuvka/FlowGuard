## Why

FlowGuard already asks agents to show route-specific model snapshots and
Mermaid diagrams for non-trivial work, but users can still miss the immediate
answer to "what is FlowGuard doing right now?" This change makes existing
visibility guidance more concrete without creating a new workflow or changing
runtime behavior.

## What Changes

- Add a lightweight "current situation" explanation requirement before or with
  non-trivial FlowGuard model snapshots.
- Keep the explanation short: what is being checked, why it matters, current
  evidence or gaps, and the next step.
- Update the shared kernel and high-value satellite skills so users see the
  current FlowGuard route and evidence boundary in ordinary conversation.
- Preserve existing diagram guidance, validation gates, runtime semantics, API
  behavior, and schema version.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `flowguard-model-visibility`: require a short current-situation explanation
  as part of non-trivial user-visible FlowGuard snapshots.
- `user-facing-model-diagrams`: clarify that diagrams are optional aids and
  should be paired with plain-language current status when they are used for
  non-trivial work.

## Impact

- Affected docs and prompts: `docs/agents_snippet.md` and FlowGuard skill
  guidance under `.agents/skills/`.
- Affected validation: existing model visibility and user-facing diagram model
  checks, OpenSpec validation, focused prompt/skill tests, and install/shadow
  workspace sync checks.
- No public Python API, dependency, runtime semantic, or schema-version impact.
