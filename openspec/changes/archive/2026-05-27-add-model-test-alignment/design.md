## Context

Current FlowGuard routes cover core modeling, ModelMesh for parent/child model partitioning, TestMesh for large or slow test hierarchy ownership, StructureMesh for large script/module refactors, and model-miss review after runtime or test evidence contradicts a passed model. The missing layer is a direct, low-friction reconciliation between model obligations and test evidence for ordinary projects that already have both a FlowGuard model and tests.

The user clarified that this layer must not depend on TestMesh or StructureMesh. Optional mesh adapters would make the first version too complex and blur responsibilities.

## Goals / Non-Goals

**Goals:**
- Provide a small structured API for model obligations and test evidence.
- Detect missing tests for model obligations, tests with no model obligation, duplicate test ownership, stale or not-current evidence, and risky obligations covered only by happy-path tests.
- Document `model_test_alignment` as a Skill Kernel sub-protocol adjacent to `core_modeling`.
- Provide a public template and CLI for project-local adoption.

**Non-Goals:**
- Do not split large tests into child suites.
- Do not split large modules or scripts.
- Do not read or depend on TestMesh, StructureMesh, or ModelMesh reports.
- Do not infer coverage from pytest automatically.
- Do not replace conformance replay or model-miss review.

## Decisions

1. **Standalone helper, not mesh dependency**

   Implement `review_model_test_alignment(plan)` in a new module that consumes only `ModelObligation` and `TestEvidence`. This keeps the feature usable for any project with a model and tests.

   Alternative considered: make TestMesh or StructureMesh optional evidence providers. Rejected because even optional provider language increases coupling and makes users think mesh partitioning is required.

2. **Obligation ids are explicit**

   Tests bind to model obligations by declared `covered_obligations`. The helper reports tests with no binding and obligations without current evidence.

   Alternative considered: infer bindings from names or source paths. Rejected for v1 because heuristic inference would be noisy and repository-specific.

3. **Risk paths are visible**

   Obligations carry `risk_level` and `required_test_kinds`; tests carry `test_kind`. The review can flag edge, failure, negative, or replay obligations that only have happy-path evidence.

   Alternative considered: hard-code one universal coverage matrix. Rejected because domains differ; the model author should declare required kinds.

4. **Templates teach the boundary**

   The starter template must explicitly say it does not invoke TestMesh or StructureMesh and must use plain obligation/test rows.

## Risks / Trade-offs

- [Risk] Projects may omit obligation ids and get noisy orphan findings. -> Mitigation: document a small stable id convention in the template and protocol.
- [Risk] Users may overclaim from alignment findings. -> Mitigation: reports classify skipped, stale, failed, timeout, and not-run evidence as gaps, not passes.
- [Risk] API surface grows too broadly. -> Mitigation: export as Modeling Helper, not Core API.
- [Risk] Alignment review becomes another broad workflow. -> Mitigation: no automatic test discovery and no mesh report ingestion in v1.
