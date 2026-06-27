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
Bind this FlowGuard route to one work contract, native checks, evidence, blockers, residual_risk, and claim_boundary.
## Entrypoint Scope
Covers flowguard-structure-mesh and routed local materials only; no unrelated repos, private paths, services, publication, or release claims unless separately routed.
## Local Material Routing
Use FlowGuard's native router, package/model checks, `.skillguard/work-contract.json`, check_manifest, and run records; keep public text portable.
## Entrypoint Acceptance Map
Mode is native-integrated/hybrid as declared; SkillGuard executes gates around the native owner and must not add a second execution route.
## Use When
Use when this skill is selected and the task needs governed route, evidence, check, handoff, or closure behavior.
## Do Not Use When
Do not use outside the skill domain, without required materials, when a more specific skill owns the work, or for tiny direct answers.
## Required Workflow
Select the FlowGuard-owned route, open/compile the contract, start/update run record, run native model/check gates, refresh evidence, fix blockers, then close from current checks.
## Hard Gates
Block skipped phases, stale/prose-only evidence, hollow contracts, quality downgrades, native-route conflicts, and completion claims with blockers.
## Output Requirements
Report target, route, evidence, failures, blockers, skipped_checks, residual_risk, and claim_boundary; separate checked facts from judgment.
## SkillGuard Maintenance
Refresh contracts, checks, evidence, and installed copies after entrypoint, route, evidence, or closure changes.
<!-- END SKILLGUARD CONTRACT LAYER -->
