---
name: flowguard-structure-mesh
description: "Use when a large script, module, package, command, or public API split needs StructureMesh governance, including facade compatibility, dependency cycles, config boundaries, ownership, target structure derivation, parity evidence, and release refactor gates."
---

# FlowGuard Structure Mesh

Standalone FlowGuard satellite skill for existing code structure splits. Use it
for large modules, scripts, commands, packages, dependency cycles, config
boundaries, public entrypoints, facades, and parity evidence.

Return to `model-first-function-flow` when the behavior model is unclear. Use
Code Structure Recommendation before StructureMesh when target ownership still
needs derivation.

## First Read

- Route id: `structure_mesh_maintenance`.
- Core helpers: `review_structure_mesh()`, `StructurePartitionItem`,
  `ModuleStructureEvidence`, `PublicEntrypointEvidence`.
- Reference: `references/structure_mesh_protocol.md`.

## Hard Gates

- Verify the real package before claiming FlowGuard use.
- For real target-project work, keep the AGENTS.md managed block/version record
  current or record why it was not updated.
- Do not create a fake mini-framework.
- Existing public entrypoints need facade/parity evidence.
- Stale parity or facade gaps should remain maintenance obligations for later scans.
- Dependency cycles and config boundaries must stay visible.

## Minimum Workflow

1. Name the parent module/script/API and target structure derivation.
2. Partition child modules and ownership.
3. Preserve public entrypoints, facades, side effects, and config boundaries.
4. Attach parity evidence and route stale gaps back to validation.

## Snapshot

Show a structure mesh diagram with parent, child modules, public entrypoints,
facades, dependency cycles, ownership, parity evidence, and gaps.

## Non-Goals

- Do not derive behavior requirements from scratch.
- Do not claim parity from formatting-only or internal-path checks.
