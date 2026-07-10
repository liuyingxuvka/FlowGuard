---
name: flowguard-model-miss-review
description: Use when runtime, tests, replay, logs, manual validation, production evidence, or a user-visible UI failure exposes a missed behavior class after FlowGuard passed, or when a non-trivial repair needs generalized closure.
---

# FlowGuard Model Miss Review

## Purpose
Backpropagate a real post-green failure into the owning commitment, model boundary, owner code contract, canonical same-class cases, tests, and final claim.

## Entrypoint Scope
Route id: `model_miss_review`; role: `public_owner`; native owner: `model_miss_review`. This standalone FlowGuard satellite skill owns miss classification and repair closure, not ungrounded feature creation.

## Local Material Routing
Read `references/model_miss_protocol.md` for miss types, root-cause backpropagation, field/UI handling, same-class evidence, reattachment, and closure.

## Entrypoint Acceptance Map
Accept concrete failure evidence and prior claim state; classify and generalize the miss; block point-fix-only or stale closure; hand commitments, canonical cases, alignment, field, mesh, process, and risk work to typed owners.

## Use When
- Use after a FlowGuard-green runtime/test/replay/log/manual/UI failure or for a repair needing `boundary_missing`, root-cause backpropagation, and bug-class evidence.

## Do Not Use When
- Do not patch only the observed instance, invent a new feature commitment, or use without concrete failure evidence; return ordinary unclear modeling to `model-first-function-flow`.

## Required Workflow
1. Run existing-model preflight, identify the affected commitment/owner, and classify the miss.
2. Backpropagate root cause; add one family seed/finite boundary through ContractExhaustionMesh and bind fields/old paths where relevant.
3. Add observed and same-class owner-code evidence, rerun alignment/mesh/freshness/risk gates, and close or scope the class.

## Hard Gates
- Verify the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework.
- A later green command or point regression alone cannot close the class; target-aware replay and owner code binding remain required when applicable.
- Unknown old-path/field disposition, stale parent reattachment, open same-family scan, or missing template harvest closure blocks broad repair confidence.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, and `typed_next_actions`, plus a miss-repair diagram and generalized-case status.

## SkillGuard Maintenance
- Edit `.skillguard/contract-source.json`, then regenerate derived contracts; SkillGuard gates miss closure and cannot convert a patch or progress log into native evidence.
