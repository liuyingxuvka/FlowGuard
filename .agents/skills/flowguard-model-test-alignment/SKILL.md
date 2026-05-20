---
name: flowguard-model-test-alignment
description: Use when a FlowGuard model's obligations, optional externally visible code contracts, and ordinary test evidence need direct comparison. Triggers include model-test alignment, missing test coverage for model scenarios or invariants, code contract evidence, Python source/test assertion audit, or checking whether tests actually cover FlowGuard obligations without invoking ModelMesh, TestMesh, or StructureMesh.
---

# FlowGuard Model-Test Alignment

This is a standalone FlowGuard satellite skill. Use it directly when the user
clearly asks whether model obligations, code contracts, and tests line up.

Return to `model-first-function-flow` when the FlowGuard applicability decision
is unclear, when several FlowGuard routes are needed, or when the work is
mostly core modeling rather than alignment.

## Hard Gates

- Verify the real package before claiming FlowGuard use:
  `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`.
- Do not create a fake mini-framework or prose-only substitute.
- Skipped, stale, or not-run evidence is not a pass.
- Preserve user and peer-agent changes; rerun or bound stale evidence.
- Keep helper APIs and templates as helpers, not skills.

## Workflow

1. Identify model obligations: scenarios, transitions, hazards, invariants,
   state writes, side effects, and allowed terminal states.
2. Add optional code contract rows only for externally visible code surfaces in
   scope.
3. Collect ordinary test evidence rows; include exact test ids and covered
   obligation ids.
4. When Python source and tests are available, use the conservative source/test
   audit helpers before the alignment review.
5. Run or update the relevant tests, then call or template
   `review_model_test_alignment(...)`.
6. Inspect missing, stale, unknown, or overclaimed coverage. Fix the model,
   code contracts, tests, or evidence rows before claiming alignment.
7. For non-trivial alignment reviews, default to a user-facing Mermaid diagram
   showing model obligations, optional code contracts, test evidence, and
   missing/stale/overclaimed gaps. Tiny evidence checks may stay concise. The
   diagram explains alignment and does not count as test or validation evidence.

## Owned Helpers

- `review_model_test_alignment(...)`
- `audit_python_code_contracts(...)`
- `audit_python_test_assertions(...)`
- `review_python_contract_source_audit(...)`
- `python -m flowguard model-test-alignment-template --output .`

## Non-Goals

- Do not split models; use `flowguard-model-mesh`.
- Do not split test suites; use `flowguard-test-mesh`.
- Do not split code structure; use `flowguard-structure-mesh`.
- Do not use this to close runtime failures after a model pass; use
  `flowguard-model-miss-review`.

For detailed route rules, read
`references/model_test_alignment_protocol.md`.
