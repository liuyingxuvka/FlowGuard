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
- New/deepened models need template harvest closure before broad claims.

## Minimum Workflow

1. Name the parent module/script/API and target structure derivation.
2. Partition child modules and ownership.
3. Preserve public entrypoints, facades, side effects, and config boundaries.
4. Attach parity evidence and route stale gaps back to validation.

## Snapshot

Show a structure mesh diagram with parent, child modules, public entrypoints,
facades, dependency cycles, ownership, parity evidence, and gaps.
Status note: parent structure, entrypoints, parity evidence, gaps, next check.

## Non-Goals

- Do not derive behavior requirements from scratch.
- Do not claim parity from formatting-only or internal-path checks.

<!-- BEGIN SKILLGUARD CONTRACT LAYER -->
## Purpose
Bind this FlowGuard route to one work contract, native checks, current evidence, blockers, residual_risk, and claim_boundary.
## Entry Scope
Covers flowguard-structure-mesh and explicitly routed local materials only; no unrelated repos, private paths, external services, publication, or release claims unless separately routed.
## Runtime Binding
SkillGuard is the contract executor around FlowGuard's native router/checker/model surface. Use native-integrated or hybrid mode when a route already exists; do not add a second execution path.
## Required Workflow
Select the FlowGuard-owned route, open or compile `.skillguard/work-contract.json`, start or update the run record, execute native model/check gates, refresh evidence, fix blockers, then close only from current checks.
## Hard Gates
Block skipped phases, stale or prose-only evidence, hollow contracts, quality downgrades, unresolved native-route conflicts, and completion claims with remaining blockers.
## Output
Report checked target, route, evidence, failures, blockers, skipped_checks, residual_risk, and claim_boundary; separate checked facts from judgment.
## Maintenance
Refresh contracts, checks, evidence, and installed copies after entrypoint, route, evidence, or closure changes.
<!-- END SKILLGUARD CONTRACT LAYER -->
