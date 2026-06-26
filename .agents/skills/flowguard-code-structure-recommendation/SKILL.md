---
name: flowguard-code-structure-recommendation
description: Use when a FlowGuard model should drive pre-code architecture, module split planning, function/block ownership, facade design, implementation boundaries, or code structure recommendations before editing production code.
---

# FlowGuard Code Structure Recommendation

Standalone FlowGuard satellite skill for deriving target implementation
structure from a model before code edits. Use it for FunctionBlock-to-module
ownership, facade planning, adapter boundaries, and validation boundaries.
When fields matter, include FieldLifecycleMesh reader/writer/owner maps so code
structure has a single field owner and explicit field readers/writers.
When modules look like similar A/B/C workflows, consume Model Similarity
Consolidation maintenance groups and code obligations instead of inventing a
second shared-kernel rationale.

Return to `model-first-function-flow` when the behavior model is missing. Use
StructureMesh when refactoring existing large code or public APIs.

## First Read

- Route id: `code_structure_recommendation`.
- Core helper: `review_code_structure_recommendation()`.
- Required shape: FunctionBlock-to-module ownership, state owner map,
  field owner/reader/writer map when fields are in scope, public-entrypoint
  map, and validation boundaries.
- Similarity handoff: cite maintenance group ids, code obligation ids, shared
  kernel owner, and adapter owners when model similarity drives the split.
- Reference: `references/code_structure_recommendation_protocol.md`.

## Hard Gates

- Verify the real package before claiming FlowGuard use.
- For real target-project work, keep the AGENTS.md managed block/version record
  current or record why it was not updated.
- Do not create a fake mini-framework.
- Do not invent modules before model responsibilities are named.
- Public facades and validation boundaries must stay explicit.
- New/deepened models need template harvest closure before broad claims.

## Minimum Workflow

1. Name the source model and relevant FunctionBlocks.
2. Map state, fields, side effects, public entrypoints, and validation boundaries.
3. Recommend target modules and facades.
4. Mark refactor parity or StructureMesh needs before implementation.

## Snapshot

Show a code structure diagram with FunctionBlock-to-module ownership, state
owners, facade boundary, and validation boundaries.
When drawing the snapshot, edges mean owns, calls, adapts, exposes, or validates.
Status note: source model, FunctionBlock owner, state/side effect owner, boundary, next decision.

## Non-Goals

- Do not perform existing-code refactors; route those to StructureMesh.
- Do not replace Model-Test Alignment or runtime conformance evidence.


<!-- BEGIN SKILLGUARD CONTRACT LAYER -->
## Purpose

Use this skill for its declared flowguard workflow while binding each run to a route, evidence, checks, and a bounded completion claim.

## Entrypoint Scope

The entrypoint covers the installed flowguard-code-structure-recommendation skill and the local materials explicitly routed by its instructions. It does not expand to unrelated repositories, private files, external services, publication, or release claims unless the user request and skill workflow explicitly include them.

## Local Material Routing

Resolve local materials from the active workspace, this skill directory, user-provided files, or explicitly configured project paths. Treat private machine paths as local-only inputs and keep public-facing instructions portable.

## Entrypoint Acceptance Map

A valid run selects one declared route, follows the phase order, records direct evidence, runs required checks, reports blockers and failures, and closes only inside the claim boundary. Available routes: model preflight, process review, evidence alignment, closure.

## Use When

Use when the user request matches the flowguard-code-structure-recommendation activation boundary and needs this skill's governed workflow, source material, checks, or handoff behavior.

## Do Not Use When

Do not use when the task is outside this skill's domain, when required local materials are unavailable, when another more specific skill owns the request, or when the user asks only for a tiny direct answer.

## Required Workflow

Select the route, inspect local materials, perform the work in phase order, collect direct evidence, run the required checks, fix failures, and only then report progress or completion.

## Output Requirements

When reporting, include evidence, failures, blockers, skipped_checks with reasons, residual_risk, and claim_boundary. State clearly what was checked, what was not checked, and what remains blocked or uncertain.

## SkillGuard Maintenance

Keep the `.skillguard` control root, work contract, check manifest, check scripts, evidence records, and progress ledger current. Re-run SkillGuard checks after changing this entrypoint, route behavior, evidence rules, or closure wording.

<!-- END SKILLGUARD CONTRACT LAYER -->
