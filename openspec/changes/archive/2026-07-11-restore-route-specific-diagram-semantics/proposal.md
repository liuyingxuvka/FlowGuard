## Why

The v0.54.0 compact skill-shell rewrite removed route-specific diagram edge meanings that had been present through v0.53.1. That regression lets future agents flatten process, UI, coverage, architecture, and model-mesh relationships into a generic flowchart, and it now breaks the cross-Guard installed-skill regression in LogicGuard.

## What Changes

- Restore the kernel-level FlowGuard diagram intent gate without adding a diagram router or changing executable model semantics.
- Restore concise, route-owned edge meanings for DevelopmentProcessFlow, UI Flow Structure, Model-Test Alignment, Code Structure Recommendation, and ModelMesh.
- Keep every skill inside the existing compact prompt budget and ten-section entrypoint contract.
- Add FlowGuard-owned regression coverage, regenerate deterministic SkillGuard contracts affected by prompt changes, and verify source-to-installed suite parity.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `user-facing-model-diagrams`: Preserve route-specific node and edge semantics in compact FlowGuard skill prompts and forbid generic diagram flattening across Guard families.

## Impact

Affected surfaces are six `.agents/skills/*/SKILL.md` prompts, their deterministic SkillGuard generated contracts, FlowGuard skill-documentation tests, the installed Codex FlowGuard skill suite, and downstream vendored FlowGuard suites. There is no Python API, schema, or executable model behavior change.
