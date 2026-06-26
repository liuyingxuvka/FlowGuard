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

Use this skill for its declared flowguard workflow while binding each run to a route, evidence, checks, and a bounded completion claim.

## Entrypoint Scope

The entrypoint covers the installed flowguard-structure-mesh skill and the local materials explicitly routed by its instructions. It does not expand to unrelated repositories, private files, external services, publication, or release claims unless the user request and skill workflow explicitly include them.

## Local Material Routing

Resolve local materials from the active workspace, this skill directory, user-provided files, or explicitly configured project paths. Treat private machine paths as local-only inputs and keep public-facing instructions portable.

## Entrypoint Acceptance Map

A valid run selects one declared route, follows the phase order, records direct evidence, runs required checks, reports blockers and failures, and closes only inside the claim boundary. Available routes: model preflight, process review, evidence alignment, closure.

## Use When

Use when the user request matches the flowguard-structure-mesh activation boundary and needs this skill's governed workflow, source material, checks, or handoff behavior.

## Do Not Use When

Do not use when the task is outside this skill's domain, when required local materials are unavailable, when another more specific skill owns the request, or when the user asks only for a tiny direct answer.

## Required Workflow

Select the route, inspect local materials, perform the work in phase order, collect direct evidence, run the required checks, fix failures, and only then report progress or completion.

## Output Requirements

When reporting, include evidence, failures, blockers, skipped_checks with reasons, residual_risk, and claim_boundary. State clearly what was checked, what was not checked, and what remains blocked or uncertain.

## SkillGuard Maintenance

Keep the `.skillguard` control root, work contract, check manifest, check scripts, evidence records, and progress ledger current. Re-run SkillGuard checks after changing this entrypoint, route behavior, evidence rules, or closure wording.

<!-- END SKILLGUARD CONTRACT LAYER -->
