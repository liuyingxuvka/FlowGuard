## Why

FlowGuard now has strong plan-detail, agent-workflow, and development-process
checkers, but Codex still sees them as three peer development-process entry
points. That leaves the user-facing behavior ambiguous: an AI can discuss a
detailed plan in one route, then execute later through another route without
carrying the same evidence and claim boundary forward.

## What Changes

- Add one AI-facing development-process simulator entry that covers rough plan
  detailing, multi-skill/tool workflow rehearsal, and execution/release
  freshness.
- Fold `flowguard-plan-detailing-compiler` and
  `flowguard-agent-workflow-rehearsal` into internal or delegated modes for the
  development-process simulator hot path while keeping their standalone helpers
  and explicit named-skill use available.
- Update global routing, reusable AGENTS guidance, satellite skill guidance,
  route tests, and API/docs so rough-plan, multi-skill, and staged execution
  tasks enter `flowguard-development-process-flow` first and then select a
  mode.
- Add route evidence that prevents the old three-peer hot path from returning:
  rough-plan and multi-skill cases must not auto-select their old direct
  satellites as the first AI-facing entry.
- Bump package/version metadata and sync installed skills, the shadow
  workspace, editable install, and local Git evidence after validation.

## Capabilities

### New Capabilities
- `development-process-simulator`: One AI-facing FlowGuard development-process
  entry that classifies plan-detailing, agent-workflow, and execution-freshness
  modes while preserving downstream route evidence boundaries.

### Modified Capabilities
- `flowguard-global-routing`: Collapse rough-plan, multi-skill workflow, and
  staged execution triggers into the development-process simulator hot path.
- `flowguard-codex-skill-satellites`: Reclassify PlanDetailing and
  AgentWorkflowRehearsal as discoverable delegated/internal modes for the
  development-process simulator, not ordinary competing first-entry routes.
- `development-process-flow`: Upgrade the skill and protocol wording so
  DevelopmentProcessFlow is the front-door simulator for plan discussion,
  workflow rehearsal, execution, validation freshness, install sync, and
  release/publish claims.
- `plan-detailing-compiler`: Preserve PlanDetailing as the detailed plan mode
  and projection helper consumed by the simulator.
- `flowguard-agent-workflow-rehearsal`: Preserve AgentWorkflowRehearsal as the
  skill/tool orchestration mode consumed by the simulator.

## Impact

- Affected package code: route API exports and a small simulator helper module.
- Affected examples/tests: FlowGuard skill trigger model, API surface tests,
  skill-doc tests, and focused simulator tests.
- Affected prompt surfaces: `AGENTS.md`, `docs/agents_snippet.md`,
  `.agents/skills/flowguard-development-process-flow/*`,
  `.agents/skills/flowguard-plan-detailing-compiler/*`,
  `.agents/skills/flowguard-agent-workflow-rehearsal/*`, and installed Codex
  skill copies.
- Affected rollout: package version, local editable install, shadow workspace
  sync, OpenSpec validation, FlowGuard route checks, focused tests, project
  audit, adoption log, and local Git commit/tag evidence.
