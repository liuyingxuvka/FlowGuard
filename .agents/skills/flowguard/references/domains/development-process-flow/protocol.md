# FlowGuard Development Process Flow

## Purpose
Order.

## Entrypoint Scope
Owner `public_owner`; covers freshness.

## Local Material Routing
After selecting the subject, read `references/development_process_flow_protocol.md`; load
`references/plan_detailing_protocol.md`,
`references/agent_workflow_protocol.md`, or
`references/distribution_release_protocol.md` only for named triggers.


## Operation routing
- `read`: load this protocol only when the selected subject is requested; use accepted current model and evidence, with zero producers and zero writes.
- `change`: load this protocol when the selected subject's model, relation, field, contract, or obligation changes; execute only its affected owner closure.
- `release`: reuse accepted subject evidence and load this protocol only for a missing release obligation in the declared scope.

## Use When
- Use for staged work, artifact versions, sync, and release claims.

## Do Not Use When
- Keep specialists; unclear routing goes to `flowguard`.

## Required Workflow
1. Register stages/writes/evidence/peers. Use internal `plan_detailing_compiler` only for rough plans. Admit internal `agent_workflow_rehearsal` only for explicit rehearsal, cross-owner/shared write, post-validation-invalidating write, route change, or multiple-owner irreversible effects; otherwise record `not_triggered`. Multiple skills/tools or public entry alone do not trigger it; it is not a standalone public skill. Optimize `diagnostic_boundary_choice`; isolate `safe_parallel`.
2. Freeze owners `execute|reuse_current|blocked`; plan-only starts none. Revalidate affected obligations. One invocation shares observation, source check, leaf publication, and receipt reconciliation.
3. Order: owner/intent -> lightweight path quality -> deep review -> implementation -> affected validation -> revision -> activation; refresh drift.
4. Verify one ModelMaturation receipt; user choice cannot close missing evidence.
5. Ordinary work loads affected shards; whole qualification freezes profile/projection identities and freshness.
6. Accept one `ModelRevisionSet` atomically; delta is not complete `CurrentEffectiveIntentView`. Write evidence before pointer; freeze release identities before final gate.

## Hard Gates

- `single_clear_path` proceeds directly; an exact deep trigger blocks implementation/activation until closed. Unchanged models reuse exact current results.
- ModelMaturation owns path quality; DPF verifies order/currentness. No
  target-generation step belongs to validation or release.
- Preserve provider, model/path-quality, binding, resource, test, projection, and observed/normative identities. Success is artifact-backed; non-pass is visible.
- Source/model, consumer, install, commit, tag, GitHub Release are separate claims.
- Invocation-local reuse is not authority. Never repeat semantics or scan receipts per leaf; missing freshness/reconciliation is `not_run`.

## Output Requirements
- Return phases, and freshness; edges mean order, invalidation, or required revalidation. Freeze source/model/install/release; keep static and execution status separate.
