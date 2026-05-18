## Why

UI design work for workflow-heavy tools needs a model-first layer of its own.
Existing FlowGuard models can describe product behavior, but agents still need
a disciplined way to model the UI's initial state, controls, button effects,
state transitions, parent/child interaction nodes, and stage-dependent actions
before they derive layout or visual structure.

## What Changes

- Add a UI flow structure route that first builds or reviews a UI interaction
  FlowGuard model, then derives a UI structure blueprint from that model.
- Add public helper APIs for UI controls, events, state nodes, transitions,
  interaction models, structure derivations, findings, and review reports.
- Add a `ui-flow-structure-template` CLI scaffold that demonstrates the two
  stage workflow: UI interaction model review and structure derivation review.
- Add a standalone `flowguard-ui-flow-structure` Codex skill with concise
  trigger, hard gates, workflow, non-goals, and reference protocol.
- Update the FlowGuard Skill Kernel, AGENTS snippet, docs, README, changelog,
  API surface, release checklist, and installed skill set for the new route.
- Keep visual styling, Figma execution, and frontend implementation separate
  from the UI flow structure route.

## Capabilities

### New Capabilities

- `flowguard-ui-flow-structure`: Codex can model UI interaction behavior first
  and then derive stable UI topology, control hierarchy, persistent controls,
  contextual controls, state availability, and layout zones from that model.

### Modified Capabilities

- None.

## Impact

- Affected package helper modules under `flowguard/`.
- Affected public API exports, CLI template routing, and template tests.
- Affected skill assets under `.agents/skills/`.
- Affected global prompt guidance in `docs/agents_snippet.md` and README.
- Affected product boundary, skill trigger, release checklist, changelog,
  version, local installed skills, shadow workspace sync, tag, and GitHub
  Release.
