---
name: flowguard-model-test-alignment
description: Align model obligations, CodeContracts, bindings, and test evidence.
---

# FlowGuard Model-Test Alignment

## Purpose
Compare model obligations, `CodeContract`, bindings, and current tests.

## Entrypoint Scope
This standalone FlowGuard satellite skill owns `model_test_alignment` (`public_owner`) rows and hands large evidence to TestMesh.

## Local Material Routing
After admission, read `references/model_test_alignment_protocol.md`; load `references/model_test_transition_protocol.md`, `references/model_test_field_protocol.md`, or `references/model_test_payload_protocol.md` only when triggered.

## Entrypoint Acceptance Map
Accept obligations/contracts/evidence; compare current bindings; block gaps and hand them to owners.

## Use When
- Use for model-code-test coverage, cells, field projections, code boundaries, targets, or payload evidence.

## Do Not Use When
- Do not split tests/code/models or make TestMesh a semantic owner; return undefined obligations to `flowguard`.

## Required Workflow
1. List obligations, stable plane/intent/commitment/path ids, fields, `ArtifactPayloadContract`, owner/delegating contracts, similarity, and evidence kinds.
2. Convert pre-code rows into obligations, contracts, targets, owner-declared cases, accepted checker designs, or scoped dispositions. A complete static design may remain `not_run`; only receipt-backed executed-evidence claims require `pass`.
3. Preserve system-property trace from request through component transition and optional current code/runtime evidence.
4. For explicit blueprint scope, consume independent inventory/bindings and check both model-to-implementation and behavior-bearing implementation-to-model/contract coverage. Pure helpers may support one owner without becoming external contracts.
5. Require source-independent semantics and oracles; paths/symbols are traceability only. Classify gaps and hand them to TestMesh, maturation, risk, or closure.

## Hard Gates
- Model-purpose gate: freeze task-specific failure(s); bind native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose: no mode/fallback; only FlowGuard-declared checks may support completion claims. Require the real FlowGuard check engine and AGENTS.md managed record; forbid a fake mini-framework. Full confidence requires one owner contract and current same-plane test per obligation.
- One intent cannot align to two primary paths. Opaque ids and missing/stale/skipped/audit-only evidence do not count.
- Ordinary alignment stays affected-only. Whole-software inventory requires explicit blueprint/export/qualification or release scope.
- Omitted surfaces, unresolved dispositions, orphan helpers, hidden writers, duplicate bindings, stale fingerprints, or missing semantics/oracles block blueprint alignment.
- Bind evidence and recommendations to exact current model, maturation, and admission identities; drift makes them stale.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, `typed_next_actions`, status, gaps, and a diagram whose edges mean covers, partially covers, or does not cover. Blueprint output adds depth/first gap, fingerprints, exact ids, and semantic/oracle gaps.


<!--VTP:target adapter/catalog;native validation;stale|ambiguous=block;preview!=proof;harvest-->
