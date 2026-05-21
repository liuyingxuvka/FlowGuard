## 1. FlowGuard Model And Design Evidence

- [x] 1.1 Add a focused FlowGuard self-model for architecture reduction route safety and run its checks.
- [x] 1.2 Ground the route against existing model/structure helpers and keep skipped or partial evidence visible.

## 2. Core Helper API

- [x] 2.1 Add architecture reduction data structures, proof statuses, candidate types, target actions, report decisions, and serialization helpers.
- [x] 2.2 Implement review logic for missing observable contracts, candidate evidence, public-entrypoint gates, target structure actions, and companion route triggers.
- [x] 2.3 Export the public helper API without changing core `FunctionBlock`, `Workflow`, or `Explorer` semantics.

## 3. Tests

- [x] 3.1 Add unit tests for complete ready reviews, missing observable contract blockers, risky/blocked candidates, public-entrypoint StructureMesh gates, target actions, and companion route trigger reporting.
- [x] 3.2 Run focused tests for architecture reduction and neighboring structure helpers.

## 4. Docs And Codex Skill Routing

- [x] 4.1 Document architecture reduction in the API surface and route guidance.
- [x] 4.2 Add a Codex skill for `flowguard-architecture-reduction`.
- [x] 4.3 Update related FlowGuard skills so DevelopmentProcessFlow, Existing Model Preflight, Code Structure Recommendation, StructureMesh, ModelMesh, Model-Test Alignment, and UI Flow Structure know when to invoke architecture reduction.

## 5. Validation And Sync

- [x] 5.1 Run OpenSpec validation for `add-architecture-reduction`.
- [x] 5.2 Run broader pytest/regression checks, using background execution for long model regressions where practical.
- [x] 5.3 Sync the completed files to the real git repository and refresh the editable local install.
- [x] 5.4 Check local package version/import path, git status, and final evidence before reporting completion.
