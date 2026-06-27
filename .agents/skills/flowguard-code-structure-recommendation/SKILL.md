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
Bind each flowguard run to the declared integration mode, evidence, blockers, residual_risk, and claim_boundary.
## Entrypoint Scope
Covers flowguard-code-structure-recommendation plus explicitly routed local materials; no unrelated repos, private files, external services, publication, or release claims unless requested and routed.
## Local Material Routing
Use workspace, skill directory, user files, or configured project paths; keep private machine paths local and public instructions portable.
## Entrypoint Acceptance Map
Use SkillGuard as the runtime contract executor attached to the native route/check owner: FlowGuard skill route map plus the real flowguard package/model checks. It enforces contract gates through that native owner before progress or closure; duplicate SkillGuard-owned execution paths are invalid. Declared gates/routes: model preflight, process review, evidence alignment, closure.
## Use When
Use when the request matches flowguard-code-structure-recommendation and needs this governed workflow, materials, checks, or handoff behavior.
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
