## Why

FlowGuard's AI-facing prompts have already been compressed, but the repository
still has structure bloat in template bodies, flat public helper exports,
repeated tests, and overloaded evidence dataclasses. That bloat makes future
FlowGuard route additions harder to maintain and easier for agents to
misunderstand.

## What Changes

- Split the large template implementation surface into route-scoped internal
  modules while preserving the existing `flowguard.templates` public facade and
  CLI template commands.
- Add a route-scoped public API registry so callers can discover helper groups
  without relying only on the flattened `MODELING_HELPER_API` list.
- Refactor repeated template/API tests toward table-driven coverage while
  preserving current public-contract assertions.
- Introduce lightweight compatibility structures for overloaded evidence
  fields so future code can use smaller gate/detail objects without breaking
  existing dataclass constructors.
- Keep FlowGuard skill prompts as concise satellite route shells; this change
  does not remove satellite skills or weaken hard gates.
- Add FlowGuard structure/evidence modeling, adoption records, editable install
  refresh, shadow workspace sync, and local git synchronization.

## Capabilities

### New Capabilities
- `flowguard-template-structure`: Route-scoped internal template ownership with
  legacy facade compatibility.
- `flowguard-api-registry`: Route-scoped API registry for helper discovery
  while preserving existing exports.
- `flowguard-evidence-field-structure`: Lightweight evidence gate/detail
  objects that can coexist with legacy wide dataclass fields.

### Modified Capabilities
- `flowguard-ai-entry-simplification`: Keep prompt budgets stable while
  simplifying implementation and test surfaces behind the prompt layer.
- `flowguard-codex-skill-satellites`: Preserve satellite discoverability and
  hard gates while avoiding renewed prompt growth.

## Impact

- Affected package code: `flowguard/templates.py`, new internal template text
  modules, `flowguard/__init__.py`, and evidence helper modules.
- Affected tests: public template tests, API surface tests, focused evidence
  model tests, and skill documentation checks.
- Affected process: OpenSpec validation, FlowGuard structure/development
  evidence, focused tests, background full regression, editable install
  refresh, shadow workspace validation, and local git commit.
