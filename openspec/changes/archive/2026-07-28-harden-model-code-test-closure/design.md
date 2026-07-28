## Context

FlowGuard already stores the pieces needed for model-code-test binding:
`ModelObligation`, `CodeContract`, `TestEvidence`, code-boundary contracts and
observations, runtime path rows, payload rows, field projections, and
conservative Python source audit reports. The weak point is not missing data; it
is that a real-code claim can still assemble those pieces loosely and overstate
closure.

This change hardens the existing path without creating another top-level route.
Model-Test Alignment remains the route that decides whether one behavior is
closed. Runtime Gateway Adoption remains the route that decides whether critical
state writes have a complete writer inventory and gateway evidence.

## Goals / Non-Goals

**Goals:**

- Let `ModelTestAlignmentPlan` consume source audit reports as first-class
  evidence and block real-code claims when required source audit is missing or
  red.
- Make each binding row summarize the full behavior chain in one place:
  obligation, owner code, file/symbol, tests, boundary/runtime/payload evidence,
  source audit decision, and open gaps.
- Require counterexample and known-bad obligations to cite concrete target ids
  and close through current external tests bound to owner code contracts.
- Replace opaque runtime writer-inventory claims with structured current
  inventory evidence for runtime-gateway claims.
- Update skills, docs, prompts, models, and tests to make the hardened path the
  default for real code.

**Non-Goals:**

- Do not add a new Model-Code Binding skill or route.
- Do not turn conservative source audit into semantic conformance proof.
- Do not make all abstract examples require source audit or runtime inventory.
- Do not refactor unrelated FlowGuard route ownership.

## Decisions

1. Source audit stays optional but becomes a hard gate when requested.

   `ModelTestAlignmentPlan.require_source_audit=True` means the final alignment
   report must have a green source audit covering the plan's required code
   contracts and test evidence. Abstract examples can keep the flag false.

2. Binding rows are extended, not replaced.

   Existing scalar fields (`code_contract_id`, `test_evidence_id`, `gaps`) stay
   available for compatibility. New tuple fields carry the dense closure
   summary so agents can cite one row instead of stitching evidence from several
   reports.

3. Counterexample and known-bad closure use target-aware evidence.

   Existing `TestEvidence.closure_evidence_role` and `evidence_target_id` are
   reused. A small obligation-level closure target structure records the role
   and target id that must be closed. This avoids a separate object graph while
   preventing happy-path tests from closing an observed bad trace.

4. Writer inventory belongs to Runtime Gateway Adoption.

   Runtime Gateway is the owner of complete critical-state writer inventory.
   Model-Test Alignment can cite runtime observations, but it should not own
   repository-wide writer discovery. A structured inventory evidence row makes
   the inventory auditable while keeping the existing inventory-id field as a
   compatibility receipt.

## Risks / Trade-offs

- Source audit is conservative and can miss dynamic behavior -> The docs and
  findings keep source audit scoped to evidence support; conformance replay and
  runtime observations remain separate gates.
- More fields can make examples noisy -> The new hard gates are opt-in except
  where runtime-gateway claims already require strong evidence.
- Runtime Gateway changes may break older runtime-gateway examples -> Existing
  inventory ids remain serializable, but runtime-gateway-level confidence now
  requires structured inventory evidence.
- Other active agents may be changing nearby docs or tests -> Edits are scoped
  to this change and no unrelated files are reverted.

## Migration Plan

1. Add new data shapes and gate logic with focused tests.
2. Update public exports and docs/templates.
3. Update local FlowGuard model regressions and OpenSpec verification.
4. Run focused tests first, then broader test and model regressions.
5. Sync local editable/install state where available and clearly report that
   this workspace is not a Git checkout if Git operations remain unavailable.

## Open Questions

- None blocking. Exact future automation for generating writer inventory from
  source scan can be added later under Runtime Gateway or a source-audit helper.
