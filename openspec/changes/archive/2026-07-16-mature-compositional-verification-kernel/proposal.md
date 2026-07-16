## Why

FlowGuard can execute Python-authored finite models, but its model meaning is still coupled to Python objects and its parent/child checks do not yet share one portable semantic contract. That makes independent tooling, durable model interchange, cross-model refinement, and reproducible checking harder than they should be.

## What Changes

- Introduce a canonical, versioned, JSON-serializable model IR for finite function-block models, invariants, temporal obligations, and parent/child refinement bindings.
- Add a reference interpreter that executes the IR deterministically and emits bounded, typed traces and findings without importing project model code.
- Add compositional verification that checks child contracts, parent abstractions, refinement mappings, assume/guarantee compatibility, progress, and fairness under one report model.
- Add a narrow CLI and Python API for validating, checking, and comparing portable model artifacts.
- Deepen the model-first, model-mesh, and topology-hazard skill prompts so they produce or consume portable semantic artifacts when that evidence boundary is active.
- Preserve the existing Python FunctionBlock API as the authoring/runtime surface; the IR is a canonical projection, not a second product workflow or a future application backend.
- **BREAKING**: a portable-model claim requires the canonical schema and checker receipt; ad hoc JSON, prompt prose, or Python-only execution cannot satisfy that claim.

## Capabilities

### New Capabilities

- `flowguard-portable-model-ir`: Versioned semantic schema, canonical serialization, validation, and stable identity for finite FlowGuard models.
- `flowguard-compositional-verification`: Parent/child refinement, assume/guarantee compatibility, progress, fairness, and counterexample obligations over portable models.
- `flowguard-portable-checker`: Reference interpreter, typed report/trace output, CLI/API surface, and deterministic execution boundaries.

### Modified Capabilities

- `hierarchical-model-mesh`: Bind mesh closure and child reattachment claims to explicit portable semantic mappings when model interchange is requested.
- `flowguard-route-topology-governance`: Bind liveness/fairness claims to executable portable obligations instead of descriptive topology metadata alone.
- `flowguard-api-registry`: Register the portable schema, checker, and composition APIs as one owned public surface.

## Impact

Affected surfaces include new `flowguard` model/checker modules, package exports, CLI dispatch, hierarchy/topology integration points, three primary skill prompts and references, SkillGuard contracts for affected skills, OpenSpec and FlowGuard models, tests, README/concept documentation, model-regression inventory, and release/version evidence.
