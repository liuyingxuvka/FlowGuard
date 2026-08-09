---
name: flowguard-model-test-alignment
description: Align model obligations, CodeContracts, bindings, and tests.
---

# FlowGuard Model-Test Alignment

## Purpose
Compare obligations, bindings, `CodeContract`, and tests; never decide path quality.

## Entrypoint Scope
A standalone FlowGuard satellite skill; owns model_test_alignment rows; hands large evidence to TestMesh.

## Local Material Routing
After admission read `references/model_test_alignment_protocol.md`; load transition, field, or payload details from `references/model_test_transition_protocol.md`, `references/model_test_field_protocol.md`, or `references/model_test_payload_protocol.md` only when triggered.

## Entrypoint Acceptance Map
Compare obligations, contracts, and evidence; route gaps.

## Use When
- Use for model-code-test coverage, fields, boundaries, or payloads.

## Do Not Use When
- Do not split artifacts or make TestMesh a semantic owner; return undefined obligations to `flowguard`.

## Required Workflow
1. List obligations, owner/path ids, current-intent bindings, `ArtifactPayloadContract`, relations, and evidence kinds.
2. Bind affected semantics/witnesses to one owner, code contract, exact test/native member, oracle, and evidence. Verify identities; never re-rank candidates.
3. Convert pre-code rows into obligations, contracts, targets, cases, checker designs, or dispositions. Keep static/executed status separate; pass needs current leaf receipts.
4. Trace system properties through runtime transitions. Blueprint consumes independent inventory/bindings both ways; helpers remain internal.
5. Paths/symbols prove traceability only. Hand semantic/path gaps to ModelMaturation, large evidence to TestMesh, broad claims to risk.

## Hard Gates
- Model-purpose gate: freeze task-specific failure(s) and claim_boundary; bind the candidate to native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose: no mode/fallback; only FlowGuard-declared checks may support completion claims. Require real FlowGuard check engine and AGENTS.md managed record; forbid a fake mini-framework. Full confidence requires one owner contract and current same-plane test per obligation.
- One intent cannot align to two primary paths. Opaque, stale, skipped, cross-owner, or normative-as-observed evidence does not count.
- Existing intent resolves only through the exact owner in complete `CurrentEffectiveIntentView`; delta/history/word/path matches are not authority.
- Ordinary alignment is affected-only; whole-target needs explicit scope. Omitted surfaces, orphan helpers, hidden writers, duplicate bindings, or missing semantics/oracles block.
- Path quality cannot license its own witness. Bind exact model, path-quality, maturation, and admission identities; drift is stale.
- Each row binds semantics, owner code/contract, oracle/checker, exact test/native member, and execution owner. Parent success cannot invent a leaf or relabel receipts.

## Output Requirements
- Return evidence, failures, blockers, skipped_checks, residual_risk, claim_boundary, typed_next_actions, rows/gaps, diagram; edges mean covers, partially covers, or misses. Blueprint adds depth/gap and ids; rows retain one owner and fingerprinted model/code/test; compact output keeps denominator and not-run gaps.
