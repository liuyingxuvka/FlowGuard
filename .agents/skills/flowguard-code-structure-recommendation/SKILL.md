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
Bind this FlowGuard route to one work contract, native checks, current evidence, blockers, residual_risk, and claim_boundary.
## Entry Scope
Covers flowguard-code-structure-recommendation and explicitly routed local materials only; no unrelated repos, private paths, external services, publication, or release claims unless separately routed.
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
