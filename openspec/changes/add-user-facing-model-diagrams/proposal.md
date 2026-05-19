## Why

FlowGuard's model checks can be correct but hard for users to value when the
answer only reports the final result. A lightweight user-facing diagram prompt
helps explain what the model checked, why a new gate matters, and what the
result can or cannot claim without turning every task into a formal report.

## What Changes

- Add a lightweight expectation that FlowGuard skills may show a user-facing
  Mermaid diagram or compact flow sketch when model value would otherwise be
  unclear.
- Keep the rule optional and judgment-based: no mandatory diagram for tiny,
  obvious, or purely mechanical tasks.
- Encourage richer diagrams when they are used, showing major states, branches,
  gates, evidence, and claim boundaries instead of only a four-box chain.
- Add focused route guidance for UI Flow Structure, ModelMesh, and
  DevelopmentProcessFlow, where model value is often abstract to a user.
- Update public docs and release metadata without adding new runtime APIs or
  changing executable FlowGuard check semantics.

## Capabilities

### New Capabilities

- `user-facing-model-diagrams`: Lightweight guidance for explaining non-trivial
  FlowGuard modeling work with user-facing Mermaid diagrams or compact flow
  sketches when useful.

### Modified Capabilities

- None.

## Impact

- Affected surfaces: FlowGuard Codex skill prompts, focused skill references,
  README/API documentation, changelog, version metadata, OpenSpec artifacts, and
  local installation/sync records.
- No public Python API changes.
- No runtime dependency changes.
- Release type: patch release, source-only.
