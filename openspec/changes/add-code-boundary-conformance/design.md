## Context

Model-Test Alignment has two existing evidence layers:

- declared rows: `ModelObligation`, `CodeContract`, and `TestEvidence`;
- conservative source audit: AST-visible support for Python code and tests.

Those layers can show that the model, contract, and tests are talking about the
same surface. They cannot by themselves prove that the running code rejected
forbidden inputs or avoided undeclared outputs and side effects.

## Goals / Non-Goals

**Goals:**

- Represent model-backed code boundaries as exact runtime contracts.
- Record real-code observations from tests, replay adapters, manual harnesses,
  or other production-facing validation.
- Report boundary gaps as first-class blockers in Model-Test Alignment.
- Keep the feature small, standard-library-only, and compatible with existing
  plans.

**Non-Goals:**

- Do not build a property-based testing engine.
- Do not claim mathematical proof over all Python runtime behavior.
- Do not replace conformance replay for trace-level production behavior.
- Do not add a new FlowGuard skill or mesh route.
- Do not split code, tests, or models.

## Decisions

1. **Add a helper layer, not a new skill.**
   Code-boundary conformance belongs inside Model-Test Alignment because it
   answers whether a declared code surface conforms to the model-backed
   external contract.

2. **Separate declarations from observations.**
   `CodeBoundaryContract` declares the finite allowed boundary. Runtime tests
   or replay harnesses produce `CodeBoundaryObservation` rows. The review
   compares the two.

3. **Treat input closure as a gate-evidence problem.**
   Tests cannot enumerate every possible bad value. The practical requirement
   is that forbidden or unknown inputs are shown to hit an input gate and not
   enter the modeled core. Missing rejected-input evidence remains a blocker
   when the boundary says a gate is required.

4. **Treat outputs broadly.**
   Outputs include return values, error paths, state writes, and side effects.
   Exact boundaries block any observed output, error path, state write, or side
   effect that the boundary did not declare.

5. **Feed findings into existing alignment decisions.**
   A separate `review_code_boundary_conformance(...)` report is available for
   focused checks. `ModelTestAlignmentPlan` can also include boundary contracts
   and observations so `review_model_test_alignment(...)` blocks green
   alignment on boundary failures.

## Risks / Trade-offs

- [Risk] Agents may overclaim boundary observations as exhaustive proof. ->
  Mitigation: docs state that input closure depends on an input gate and that
  conformance observations are current evidence, not a complete semantic proof.
- [Risk] This duplicates conformance replay. -> Mitigation: replay remains the
  right route for ordered trace behavior; boundary conformance checks one code
  surface's input/output closure.
- [Risk] Tests may record final return values but miss side effects. ->
  Mitigation: side effects are explicit observation fields and undeclared
  observed side effects block exact boundary confidence.
