---
name: flowguard-model-test-alignment
description: Use when a FlowGuard model's obligations, optional externally visible code contracts, code-boundary runtime observations, and ordinary test evidence need direct comparison. Triggers include model-test alignment, missing test coverage for model scenarios or invariants, code contract evidence, code-boundary conformance evidence, Python source/test assertion audit, or checking whether tests actually cover FlowGuard obligations without invoking ModelMesh, TestMesh, or StructureMesh.
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
- If DevelopmentProcessFlow classifies a validation failure as model-test mismatch,
  this skill owns the obligation, optional code-contract, and test
  evidence comparison before alignment is claimed.
- If a model-backed code surface claims finite inputs/outputs, require
  code-boundary observations for allowed input cases, rejected input cases, and
  observed outputs/state writes/side effects/error paths before claiming the
  real code conforms to that boundary.
- If the code surface belongs to a leaf model, require boundary-matrix evidence
  for every finite `Input x State` cell before claiming the leaf can support a
  parent model. If the matrix is too large, route to ModelMesh for a lower-level
  split instead of treating representative tests as full leaf proof.
- If one model obligation has multiple current primary `edge_path` evidence
  rows, do not fix it by downgrading one row to supporting evidence. Treat the
  obligation as too coarse: split child obligations or attach those tests to
  distinct leaf matrix cells.
- If several tests or code contracts prove the same obligation because the
  implementation has duplicate paths, route to `flowguard-architecture-reduction`
  before expanding test evidence further.
- For final done/release/publish/full-confidence claims, hand the obligation,
  code-contract, evidence-status, freshness, and assertion-scope rows to the
  Risk Evidence Ledger; this skill produces coverage evidence, not the whole
  final confidence claim.
- Preserve user and peer-agent changes; rerun or bound stale evidence.
- Keep helper APIs and templates as helpers, not skills.

## Workflow

1. Identify model obligations: scenarios, transitions, hazards, invariants,
   state writes, side effects, and allowed terminal states.
2. Add optional code contract rows only for externally visible code surfaces in
   scope.
3. Add code-boundary contracts and runtime observations when a code surface
   must be closed around finite inputs and outputs.
4. For leaf models, build a boundary matrix that maps each allowed input/state
   cell to observed outputs, next states, state writes, side effects, error
   paths, and exact evidence ids.
5. Collect ordinary test evidence rows; include exact test ids and covered
   obligation ids. Mark each row as primary boundary evidence, leaf matrix-cell
   evidence, supporting contract evidence, or integration smoke evidence.
6. When Python source and tests are available, use the conservative source/test
   audit helpers before the alignment review.
7. Run or update the relevant tests, then call or template
   `review_model_test_alignment(...)`.
8. For DevelopmentProcessFlow `model_test_mismatch` handoffs, keep the failed
   validation visible until required obligations, optional code contracts, and
   current test evidence have been compared.
9. If duplicate evidence maps to duplicate implementation paths, hand the
   obligation/code-contract snapshot to Architecture Reduction before deciding
   whether to keep all paths.
10. Inspect missing, stale, unknown, overclaimed, incomplete leaf-matrix, or boundary-crossing coverage.
   Fix the model, code contracts, boundary observations, tests, or evidence
   rows before claiming alignment.
11. For non-trivial alignment reviews, default to a user-facing Mermaid coverage
   diagram showing model obligations, optional code contracts, test evidence,
   code-boundary observations, and missing/stale/overclaimed/boundary-crossing
   gaps. Its edges mean covers, partially covers, observes boundary, misses, or
   stales; they are not execution order. Tiny evidence checks may stay concise.
   The diagram explains alignment and does not count as test or validation
   evidence.

## Owned Helpers

- `review_model_test_alignment(...)`
- `review_code_boundary_conformance(...)`
- `audit_python_code_contracts(...)`
- `audit_python_test_assertions(...)`
- `review_python_contract_source_audit(...)`
- `python -m flowguard model-test-alignment-template --output .`

## Non-Goals

- Do not split models; use `flowguard-model-mesh`.
- Do not split test suites; use `flowguard-test-mesh`.
- Do not split code structure; use `flowguard-structure-mesh`.
- Do not decide code contraction from duplicate test coverage alone; use
  `flowguard-architecture-reduction` for model-to-code shrink decisions.
- Do not use this to close runtime failures after a model pass; use
  `flowguard-model-miss-review`.

For detailed route rules, read
`references/model_test_alignment_protocol.md`.
