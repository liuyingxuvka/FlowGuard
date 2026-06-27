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
Bind each flowguard run to the declared integration mode, evidence, blockers, residual_risk, and claim_boundary.
## Entrypoint Scope
Covers flowguard-structure-mesh plus explicitly routed local materials; no unrelated repos, private files, external services, publication, or release claims unless requested and routed.
## Local Material Routing
Use workspace, skill directory, user files, or configured project paths; keep private machine paths local and public instructions portable.
## Entrypoint Acceptance Map
Use SkillGuard as the runtime contract executor attached to the native route/check owner: FlowGuard skill route map plus the real flowguard package/model checks. It enforces contract gates through that native owner before progress or closure; duplicate SkillGuard-owned execution paths are invalid. Declared gates/routes: model preflight, process review, evidence alignment, closure.
## Use When
Use when the request matches flowguard-structure-mesh and needs this governed workflow, materials, checks, or handoff behavior.
## Do Not Use When
Do not use outside the domain, without required materials, when a more specific skill owns the work, or for tiny direct answers.
## Required Workflow
Select the target-owned native route/check surface, run the SkillGuard contract gates around the native workflow, collect evidence, run checks, fix failures, then report.
## Hard Gates
Do not skip phases, do not replace required evidence with prose, do not treat stale reports as current, do not weaken validation to pass, and do not claim completion when blockers remain.
## Output Requirements
Report evidence, failures, blockers, skipped_checks with reasons, residual_risk, and claim_boundary; distinguish checked, unchecked, blocked, and uncertain.
## SkillGuard Maintenance
Keep `.skillguard` contracts, checks, evidence, and ledger current; rerun SkillGuard after entrypoint, route, evidence, or closure changes.
<!-- END SKILLGUARD CONTRACT LAYER -->
