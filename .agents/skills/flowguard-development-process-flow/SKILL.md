---
name: flowguard-development-process-flow
description: Order staged work, freshness, sync, release, and process claims.
---

# FlowGuard Development Process Flow

## Purpose
Order work, freshness, validation, sync, and release; specialists keep semantics.

## Entrypoint Scope
Public owner `public_owner`; simulator owns freshness, conditional optimization, plan detailing, and workflow rehearsal.

## Local Material Routing
Read `references/development_process_flow_protocol.md`; load `references/distribution_release_protocol.md` only when distribution or release is requested.

## Entrypoint Acceptance Map
Accept stages, versions, owners, and evidence; return order/revalidation.

## Use When
- Use for plans, staged/multi-skill work, artifact/payload versions, or sync/release claims.

## Do Not Use When
- Keep specialists; unclear routing goes to `flowguard`.

## Required Workflow
1. Register stages, writes, evidence, peers, WorkContexts; `plan_detailing_compiler` and `agent_workflow_rehearsal` detail order. Optimize only `diagnostic_boundary_choice`; isolate `safe_parallel`.
2. Freeze owners `execute|reuse_current|blocked`; plan-only starts none. Revalidate affected obligations. One invocation shares one observation, source check, leaf publication, and receipt reconciliation.
3. Model order: owner/intent -> lightweight path quality -> triggered deep review -> implementation -> affected validation -> candidate revision -> activation. Refresh drift minimally.
4. Verify one ModelMaturation receipt. User choice cannot close missing evidence.
5. Ordinary work loads affected blueprint shards; whole qualification freezes profile-to-projection identities and freshness.
6. Accept one `ModelRevisionSet` atomically; delta is not complete `CurrentEffectiveIntentView`. Write evidence before pointer; freeze release identities before one final gate.

## Hard Gates
- Model-purpose gate: freeze task-specific failure(s)/claim boundary; bind native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose: no mode/fallback; only FlowGuard-declared checks may support completion claims. Require real FlowGuard check engine and AGENTS.md managed record; forbid a fake mini-framework. Activation/reverse share lock/CAS; stale head stops.
- Authorization bounds attempts, not confidence. Unknown owner/impact, active lease, or missing revalidation blocks.
- `single_clear_path` proceeds directly; an exact deep trigger blocks implementation/activation until closed. Unchanged models reuse exact current results.
- ModelMaturation owns path quality; DPF verifies order/currentness. Reimplementation is explicit target work, not routine validation.
- Preserve provider, model/path-quality, binding, resource, test, projection, and observed/normative identities. Success is artifact-backed; non-pass is visible.
- Source, model/intent, consumer, install, commit, tag, and GitHub Release are separate currentness claims.
- Invocation-local reuse is not authority. Never repeat semantics, rebuild currentness per leaf, or scan receipts per leaf; missing final freshness/reconciliation is `not_run`.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, `typed_next_actions`, phases/modes, freshness; edges mean order, invalidation, or required revalidation. Blueprint adds depth/first gap.
