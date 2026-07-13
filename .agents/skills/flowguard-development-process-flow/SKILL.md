---
name: flowguard-development-process-flow
description: Use as the FlowGuard process-simulator front door for non-trivial rough plans, multi-skill workflows, staged edits, evidence freshness, install/sync, release/archive/publish, peer writes, revalidation, or final lifecycle claims.
---

# FlowGuard Development Process Flow

## Purpose
Run the development-process simulator for lifecycle order and evidence freshness without replacing specialists.

## Entrypoint Scope
Front-door FlowGuard satellite skill; route/native `development_process_flow` (`public_owner`). It delegates `plan_detailing` and `agent_workflow`, and owns `execution_freshness`.

## Local Material Routing
Read `references/development_process_flow_protocol.md` for modes, rows, triage, freshness, and closure.

## Entrypoint Acceptance Map
Accept process intent; order three modes; block stale/progress-only evidence; delegate details and route gaps.

## Use When
- Use for rough plans, cross-skill/staged work, background checks, sync, version/release/archive/publish, or broad claims.

## Do Not Use When
- Do not replace mesh/alignment/exhaustion/product owners; return unclear routing to `model-first-function-flow`.

## Required Workflow
1. Select modes; classify the change subject as `skill_runtime` or `ordinary_software`; register artifact versions, ordered `development_process` actions, typed targets, writes, peer changes, payload schemas, and evidence.
2. Triage non-pass results and invoke their native owners.
3. Post-change, run `review_auto_mesh_splits`, scan owners, and derive minimum revalidation.
4. Track source/shadow/repository/package/skills/Git separately; merge peer writes without rollback.
5. Close only with current terminal proof per in-scope domain/owner.

## Hard Gates
- Use the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework. Non-pass/progress/release-only evidence is not current pass.
- Broad claims need owner gates; liveness is not completion; one domain receipt proves only that domain.
- Projection preserves receipts/continue/rework. Peer writes stale evidence but are merged, not rolled back; target refs never transfer behavior ownership.
- A `skill_runtime` upgrade has one current authority: replace the former shape directly and reject it in negative fixtures; do not add a fallback, compatibility reader, migration command, converter, alias, or parallel success path.
- An `ordinary_software` compatibility branch is admitted only by an explicit requirement naming the historical document/data/interface and its bounded reader owner; otherwise use direct current replacement.

## Output Requirements
- Return evidence, failures, blockers, skipped_checks, residual_risk, claim_boundary, typed_next_actions, modes, versions, and a diagram whose edges mean order, invalidation, or required revalidation.

## SkillGuard Maintenance
- Edit contract source, regenerate; SkillGuard cannot manufacture evidence.
