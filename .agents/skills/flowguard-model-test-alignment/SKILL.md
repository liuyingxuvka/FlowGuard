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
- For real target-project use, ensure the FlowGuard AGENTS.md managed
  block/version record exists, or record why it was not updated.
- Do not create a fake mini-framework or prose-only substitute.
- Skipped, stale, or not-run evidence is not a pass.
- For model-miss repairs, an observed-bug regression test is not enough for
  full closure. A repaired in-scope model-miss obligation must have current
  observed-regression and same-class generalized test evidence, or the report
  must block full confidence.
- Recurring or high-risk same-class families are not closed by this route
  alone. Feed the aligned evidence to `review_defect_family_gates(...)` and the
  Risk Evidence Ledger when family-level confidence is required.
- When related obligations are claimed as one family, require
  `ObligationFamily` and `ObligationFamilyEvidence` rows. Missing sibling
  mechanism coverage, wrong provenance, stale evidence, non-passing evidence,
  or internal-only evidence must block or scope the family-level claim.
- If DevelopmentProcessFlow classifies a validation failure as model-test mismatch,
  this skill owns the obligation, optional code-contract, and test
  evidence comparison before alignment is claimed.
- If a model-backed code surface claims finite inputs/outputs, require
  code-boundary observations for allowed input cases, rejected input cases, and
  observed outputs/state writes/side effects/error paths before claiming the
  real code conforms to that boundary.
- If real-code progress is used as evidence, require runtime path rows that
  name the compared FlowGuard `model_id`, `model_path`, `node_id`, run id,
  status, and obligation/code contract. Anonymous progress logs are not
  alignment evidence.
- If the code surface belongs to a leaf model, require boundary-matrix evidence
  for every finite `Input x State` cell before claiming the leaf can support a
  parent model. If the matrix is too large, route to ModelMesh for a lower-level
  split instead of treating representative tests as full leaf proof.
- If one model obligation has multiple current primary `edge_path` evidence
  rows, do not fix it by downgrading one row to supporting evidence. Treat the
  obligation as too coarse: split child obligations or attach those tests to
  distinct leaf matrix cells, then record a model maturation signal.
- If alignment finds a missing model obligation, missing code-boundary
  observation, stale proof, or code-boundary mismatch, feed that row to
  `review_model_maturation_loop(...)` before broad confidence.
- If several tests or code contracts prove the same obligation because the
  implementation has duplicate paths, route to `flowguard-architecture-reduction`
  before expanding test evidence further.
- For final done/release/publish/full-confidence claims, hand the obligation,
  code-contract, evidence-status, freshness, and assertion-scope rows to the
  Risk Evidence Ledger; this skill produces coverage evidence, not the whole
  final confidence claim.
- For broad confidence, set `require_proof_artifacts=True` on the alignment
  plan or downstream ledger and attach `ProofArtifactRef` rows. Declaration-only
  `passed/current` test evidence is not enough without a result path,
  fingerprint, covered obligation, and external-contract scope when code
  contracts are being proved.
- Alignment can only prove declared obligations. If the plan or adapter may
  have omitted an in-scope surface, require plan-intake and adapter-conformance
  helper evidence before the result is promoted through the typed claim chain.
- Preserve user and peer-agent changes; rerun or bound stale evidence.
- Keep helper APIs and templates as helpers, not skills.

## Workflow

1. Identify model obligations: scenarios, transitions, hazards, invariants,
   state writes, side effects, and allowed terminal states.
2. Add optional code contract rows only for externally visible code surfaces in
   scope.
3. Add code-boundary contracts and runtime observations when a code surface
   must be closed around finite inputs and outputs.
4. Add `RuntimeNodeContract`, `RuntimeNodeObservation`, or recorder-produced
   `RuntimePathRun` rows when the real code path must be compared to modeled
   nodes. Use `RuntimeNodeObservation.format_progress_line()` for progress
   output so another AI can locate the corresponding FlowGuard model.
5. For leaf models, build a boundary matrix that maps each allowed input/state
   cell to observed outputs, next states, state writes, side effects, error
   paths, and exact evidence ids.
6. Collect ordinary test evidence rows; include exact test ids and covered
   obligation ids. Mark each row as primary boundary evidence, leaf matrix-cell
   evidence, supporting contract evidence, or integration smoke evidence.
   For strict confidence, attach the current proof artifact produced by the
   command or replay that generated the row.
6. For repaired model-miss obligations, mark which test row is the observed
   regression and which row is the same-class generalized evidence. Treat
   overclaimed, stale, skipped, or internal-path-only rows as blockers rather
   than closure evidence.
7. When sibling obligations share a confidence claim, add obligation-family
   parity rows and evidence provenance before the alignment review.
8. When Python source and tests are available, use the conservative source/test
   audit helpers before the alignment review.
9. Run or update the relevant tests, then call or template
   `review_model_test_alignment(...)`.
10. For DevelopmentProcessFlow `model_test_mismatch` handoffs, keep the failed
   validation visible until required obligations, optional code contracts, and
   current test evidence have been compared.
11. If same-class coverage is too large, slow, layered, stale-prone,
   background, or release-only, hand the validation hierarchy to TestMesh and
   consume its current evidence ids rather than expanding this route into a
   parent/child suite graph.
12. If duplicate evidence maps to duplicate implementation paths, hand the
   obligation/code-contract snapshot to Architecture Reduction before deciding
   whether to keep all paths.
13. Inspect missing, stale, unknown, overclaimed, incomplete leaf-matrix, wrong-provenance family, or boundary-crossing coverage.
    Fix the model, code contracts, boundary observations, tests, or evidence
    rows before claiming alignment.
14. Feed model-too-coarse, missing-obligation, stale, boundary-mismatch, or
    duplicate-primary-edge findings to `review_model_maturation_loop(...)`.
15. For broad confidence claims, pass the alignment report through Risk
    Evidence Ledger and `review_flowguard_claim_chain(...)`; do not let
    alignment evidence stand in for plan completeness, runtime replay, or
    production confidence.
16. For non-trivial alignment reviews, default to a user-facing Mermaid coverage
   diagram showing model obligations, optional code contracts, test evidence,
   code-boundary observations, and missing/stale/overclaimed/boundary-crossing
   gaps. Its edges mean covers, partially covers, observes boundary, misses, or
   stales; they are not execution order. Tiny evidence checks may stay concise.
   The diagram explains alignment and does not count as test or validation
   evidence.

## Owned Helpers

- `review_model_test_alignment(...)`
- `review_obligation_family_parity(...)`
- `derive_same_class_bad_cases(...)`
- `review_code_boundary_conformance(...)`
- `audit_python_code_contracts(...)`
- `audit_python_test_assertions(...)`
- `review_python_contract_source_audit(...)`
- `python -m flowguard model-test-alignment-template --output .`
- `python -m flowguard runtime-path-evidence-template --output .`

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
