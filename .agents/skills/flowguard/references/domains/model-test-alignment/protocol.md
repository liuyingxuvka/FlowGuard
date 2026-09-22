# FlowGuard Model-Test Alignment

## Purpose
Compare obligations, bindings, `CodeContract`, and tests; never decide path quality.

## Entrypoint Scope
Owner model-test alignment rows; hands large evidence to TestMesh.

## Local Material Routing
After selecting the subject read `references/model_test_alignment_protocol.md`; load transition, field, or payload details from `references/model_test_transition_protocol.md`, `references/model_test_field_protocol.md`, or `references/model_test_payload_protocol.md` only when triggered.


## Operation routing
- `read`: load this protocol only when the selected subject is requested; use accepted current model and evidence, with zero producers and zero writes.
- `change`: load this protocol when the selected subject's model, relation, field, contract, or obligation changes; execute only its affected owner closure.
- `release`: reuse accepted subject evidence and load this protocol only for a missing release obligation in the declared scope.

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

- One intent cannot align to two primary paths. Opaque, stale, skipped, cross-owner, or normative-as-observed evidence does not count.
- Existing intent resolves only through the exact owner in complete `CurrentEffectiveIntentView`; delta/history/word/path matches are not authority.
- Ordinary alignment is affected-only; whole-target needs explicit scope. Omitted surfaces, orphan helpers, hidden writers, duplicate bindings, or missing semantics/oracles block.
- Path quality cannot license its own witness. Bind exact model, path-quality, maturation, and admission identities; drift is stale.

## Output Requirements
- Return rows/gaps, diagram; edges mean covers, partially covers, or misses. Blueprint adds depth/gap and ids; rows retain one owner and fingerprinted model/code/test; compact output keeps denominator and not-run gaps.
