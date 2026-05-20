---
name: flowguard-structure-mesh
description: "Use when a large script, module, package, command, or public API split needs StructureMesh governance, including facade compatibility, dependency cycles, config boundaries, ownership, target structure derivation, parity evidence, and release refactor gates."
---

# FlowGuard StructureMesh

This is a standalone FlowGuard satellite skill for large code-structure
refactors. Use it directly when production code is being split or reorganized
and compatibility, dependencies, facades, or parity evidence are the main risk.

Return to `model-first-function-flow` when the work is only a pre-code
structure recommendation or when route selection is ambiguous.

## Hard Gates

- Verify the real package before claiming FlowGuard use:
  `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`.
- Do not create a fake mini-framework or prose-only substitute.
- Existing public entrypoints need compatibility evidence before green
  confidence.
- Target structure must be model-derived for existing large refactors.
- Dependency cycles, config drift, missing facades, and parity gaps are release
  blockers until addressed or explicitly bounded.

## Workflow

1. Inventory current modules/scripts/commands/public entrypoints and ownership.
2. Derive target structure from FunctionBlocks, state ownership, side effects,
   contracts, and compatibility requirements.
3. Define parent facade and child module responsibilities.
4. Check dependency direction, config ownership, public entrypoint parity, and
   routine/release evidence.
5. Use `review_structure_mesh(...)` or the template before claiming refactor
   confidence.
6. For non-trivial StructureMesh reviews, default to a user-facing Mermaid
   structure mesh diagram showing current public entrypoints, target child
   modules, facades, dependency direction, config/parity evidence, and release
   blockers. Its edges mean exposes, preserves, adapts, depends, or validates
   parity; they are not task order. Tiny structure checks may stay concise. The
   diagram explains the split and does not replace parity evidence or release
   sync.

## Owned Helpers

- `review_structure_mesh(...)`
- `python -m flowguard structure-mesh-template --output .`
- `references/structure_mesh_protocol.md`

## Non-Goals

- Do not use this for early architecture advice only; use
  `flowguard-code-structure-recommendation`.
- Do not split tests or models.
- Do not bypass conformance/release sync when public behavior changes.

For detailed route rules, read `references/structure_mesh_protocol.md`.
