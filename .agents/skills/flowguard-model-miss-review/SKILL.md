---
name: flowguard-model-miss-review
description: Use when runtime, tests, replay, logs, manual validation, or production evidence fails after FlowGuard passed, including model miss, false confidence, boundary missing, weak invariant, or root-cause backpropagation.
---

# FlowGuard Model Miss Review

Standalone FlowGuard satellite skill for bug repairs where real failure shows
the model, code contract, tests, or final claim is too narrow. Return to
`model-first-function-flow` only when there is no concrete failure evidence.

## First Read

- Route id: `model_miss_review`.
- Entry: `ROUTE_STARTER_API["model_miss_review"]`, `model-miss-template`, or
  full variant.
- Concepts: observed failure, contract-exhaustion same-class case or
  combination case, `boundary_missing`, root-cause backpropagation, owner code contract,
  old-path/field disposition, coverage receipt, defect-family gate, maturation.
- Reference: `references/model_miss_protocol.md`.

## Hard Gates

- Verify the real package, keep AGENTS.md managed records current, and do not
  create a fake mini-framework.
- A user-observed UI failure after a green claim is a model miss.
- Preserve previous claim, failure, affected/same-class surface, task/control/
  field gaps, tests, backpropagation, and code owner.
- The observed instance and bug-class responsibility are separate.
- Same-class generation is not hand-written canonical coverage. Abstract the
  miss into a boundary/family seed or interaction group, then route sibling
  cases through `flowguard-contract-exhaustion-mesh`.
- Root cause, model obligation, owner code contract, observed test, and
  same-class test must bind to the same repaired behavior.
- Old, fallback, compatibility, alternate paths, and field misses need
  disposition/projection instead of accidental reachability.
- A later green runtime check does not close a miss without current case,
  shard, receipt, and alignment evidence for the in-scope class.
- Deepened miss models need template harvest closure before broad claims.

## Minimum Workflow

1. Run existing-model preflight when the bug is inside a modeled system.
2. Classify the miss and backpropagate root cause into the model/test gap.
3. For UI misses, run `review_ui_model_misses()` before fixing only one control.
4. Add one family seed or interaction group, then use ContractExhaustionMesh.
5. Update the model or FieldLifecycleMesh and bind the owner code contract.
6. Add observed-regression and contract-exhaustion evidence, then rerun
   alignment, disposition, mesh, maturation, freshness, and risk gates.

## Snapshot

Show a miss-repair diagram with failure, boundary_missing, contract-exhaustion
case ids, root cause, field gap, code owner, tests, old-path disposition, gaps.
Status note: prior claim, failure, miss class, evidence/gap, next repair/check.

## Non-Goals

- Do not close the class by patching only the observed instance.
- Do not treat production prose or progress logs as closure evidence.

<!-- BEGIN SKILLGUARD CONTRACT LAYER -->
## Purpose
Bind each flowguard run to the declared integration mode, evidence, blockers, residual_risk, and claim_boundary.
## Entrypoint Scope
Covers flowguard-model-miss-review plus explicitly routed local materials; no unrelated repos, private files, external services, publication, or release claims unless requested and routed.
## Local Material Routing
Use workspace, skill directory, user files, or configured project paths; keep private machine paths local and public instructions portable.
## Entrypoint Acceptance Map
Use SkillGuard as the runtime contract executor attached to the native route/check owner: FlowGuard skill route map plus the real flowguard package/model checks. It enforces contract gates through that native owner before progress or closure; duplicate SkillGuard-owned execution paths are invalid. Declared gates/routes: model preflight, process review, evidence alignment, closure.
## Use When
Use when the request matches flowguard-model-miss-review and needs this governed workflow, materials, checks, or handoff behavior.
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
