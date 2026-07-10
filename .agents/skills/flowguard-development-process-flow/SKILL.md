---
name: flowguard-development-process-flow
description: Use as the FlowGuard process-simulator front door for non-trivial rough plans, multi-skill workflows, staged edits, evidence freshness, install/sync, release/archive/publish, peer writes, revalidation, or final lifecycle claims.
---

# FlowGuard Development Process Flow

## Purpose
Model the development lifecycle and evidence freshness across plan, execution, validation, synchronization, and final claims without replacing specialist routes.

## Entrypoint Scope
Route id: `development_process_flow`; role: `public_owner`; native owner: `development_process_flow`. This front-door FlowGuard satellite skill owns the simulator and `execution_freshness`; it may delegate `plan_detailing` and `agent_workflow`.

## Local Material Routing
Read `references/development_process_flow_protocol.md` for simulator modes, artifact/evidence rows, triage classes, freshness rules, and completion gates.

## Entrypoint Acceptance Map
Accept non-trivial process intent; select `plan_detailing`, `agent_workflow`, `execution_freshness` in order; block out-of-order/stale/progress-only evidence; hand detailed modes to delegated skills and gaps to native owners.

## Use When
- Use for rough plans, cross-skill order, plan/edit/test/fix/verify work, background checks, install/shadow sync, version/release/archive/publish, or broad done claims.

## Do Not Use When
- Do not replace ModelMesh, TestMesh, StructureMesh, Model-Test Alignment, ContractExhaustionMesh, or product behavior modeling; return unclear FlowGuard routing to `model-first-function-flow`.

## Required Workflow
1. Select simulator modes and register artifact versions, ordered actions, writes, invalidations, peer changes, and evidence ids.
2. Triage every failed/stale/skipped/running/ambiguous result and invoke the owning route for non-ordinary gaps.
3. Derive minimum revalidation and close only after current proof artifacts support the requested scope.

## Hard Gates
- Verify the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework.
- Skipped, stale, failed, running, progress-only, `pass_with_gaps`, or release-only evidence is not current pass evidence.
- Broad behavior needs current ledger/PPA/coverage/risk gates; background liveness is not completion; new/deepened process models require template harvest closure.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, and `typed_next_actions`, plus modes, artifact versions, invalidations, triage, and minimum revalidation.

## SkillGuard Maintenance
- Edit `.skillguard/contract-source.json`, then regenerate derived contracts; SkillGuard validates lifecycle gates and cannot manufacture specialist evidence or release authority.
