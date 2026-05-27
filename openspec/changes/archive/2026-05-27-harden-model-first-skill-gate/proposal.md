## Why

Agents repeatedly need explicit user prompting before complex FlowGuard-backed
optimizations: list the intended changes, enumerate likely regressions, upgrade
the model until those regressions are visible, run known-bad coverage, then edit
code incrementally. This should be a default skill gate so model-first work does
not degrade into code-first changes plus after-the-fact prose.

## What Changes

- Add a pre-implementation model-hardening gate to the
  `model-first-function-flow` Skill for complex optimizations, repeated bug
  repairs, stateful refactors, and model-miss-sensitive work.
- Require a concrete change inventory and risk catalog before model updates.
- Require a risk-to-model coverage matrix that maps each important risk to
  modeled state, inputs, invariants, known-bad hazards, check evidence, and
  residual blindspots.
- Require known-bad hazards or scenarios to fail before the agent trusts a
  model as covering the target bug class.
- Clarify that expensive project-specific model groups should be handled by a
  tiered cost policy: run the smallest sufficient boundary first, background
  long checks with artifact evidence, and only skip or defer heavy models with
  an explicit boundary and residual-risk note.
- Require incremental validation after each optimization slice and preservation
  of user or peer-agent changes.
- Update the reusable AGENTS snippet and focused tests so downstream projects
  inherit the same gate.

## Capabilities

### New Capabilities
- `pre-implementation-model-hardening`: Covers the skill-level behavior that
  agents must follow before complex FlowGuard-backed changes: inventory,
  risk catalog, coverage matrix, known-bad validation, tiered heavy-model
  handling, incremental verification, and peer-change preservation.

### Modified Capabilities

## Impact

- `.agents/skills/model-first-function-flow/SKILL.md`
- `docs/agents_snippet.md`
- Focused tests that pin the new skill/snippet requirements
- Changelog and package version for the release
- Installed local skill copy and shadow workspace sync after validation
