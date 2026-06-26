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

Use this skill for its declared flowguard workflow while binding each run to a route, evidence, checks, and a bounded completion claim.

## Entrypoint Scope

The entrypoint covers the installed flowguard-model-miss-review skill and the local materials explicitly routed by its instructions. It does not expand to unrelated repositories, private files, external services, publication, or release claims unless the user request and skill workflow explicitly include them.

## Local Material Routing

Resolve local materials from the active workspace, this skill directory, user-provided files, or explicitly configured project paths. Treat private machine paths as local-only inputs and keep public-facing instructions portable.

## Entrypoint Acceptance Map

A valid run selects one declared route, follows the phase order, records direct evidence, runs required checks, reports blockers and failures, and closes only inside the claim boundary. Available routes: model preflight, process review, evidence alignment, closure.

## Use When

Use when the user request matches the flowguard-model-miss-review activation boundary and needs this skill's governed workflow, source material, checks, or handoff behavior.

## Do Not Use When

Do not use when the task is outside this skill's domain, when required local materials are unavailable, when another more specific skill owns the request, or when the user asks only for a tiny direct answer.

## Required Workflow

Select the route, inspect local materials, perform the work in phase order, collect direct evidence, run the required checks, fix failures, and only then report progress or completion.

## Output Requirements

When reporting, include evidence, failures, blockers, skipped_checks with reasons, residual_risk, and claim_boundary. State clearly what was checked, what was not checked, and what remains blocked or uncertain.

## SkillGuard Maintenance

Keep the `.skillguard` control root, work contract, check manifest, check scripts, evidence records, and progress ledger current. Re-run SkillGuard checks after changing this entrypoint, route behavior, evidence rules, or closure wording.

<!-- END SKILLGUARD CONTRACT LAYER -->
