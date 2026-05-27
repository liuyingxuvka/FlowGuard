## Context

FlowGuard's current core records trace labels and metadata, but it does not give workflow authors a reusable way to declare "step B cannot count unless step A's receipt exists" or "this claim is illegal after evidence was invalidated." Existing examples hand-code these gates as model-specific state fields and invariants, which works but is easy to omit in a new model.

## Goals / Non-Goals

**Goals:**
- Add a small public API for reusable step/receipt contracts.
- Keep the implementation compatible with the existing Explorer and invariant model.
- Make violations visible in runner summaries and focused trace reviews.
- Let DevelopmentProcessFlow and Model-Test Alignment reuse the same contract declarations instead of duplicating step lists.
- Let conformance replay compare step-contract receipts when adapters expose them.

**Non-Goals:**
- Do not replace `Workflow`, `FunctionBlock`, or `TraceStep`.
- Do not force every model to use step contracts.
- Do not turn DevelopmentProcessFlow or Model-Test Alignment into a new process engine.
- Do not add external dependencies or broad code generation.

## Decisions

- Introduce `flowguard.step_contracts` as a helper module rather than changing the core `FunctionBlock` protocol. This keeps existing models source-compatible and lets users opt in step by step.
- Represent state progress as named receipts rather than mandatory custom state fields. Receipts are easier to compare across model traces, process evidence, tests, and replay observations.
- Compile contracts into invariant objects consumed by Explorer and runner. This reuses existing counterexample and minimization behavior instead of adding a second exploration engine.
- Use trace/observation metadata keys for replay comparison. Production adapters can expose the same receipt data without changing their projected state type.
- Provide projection helpers into `ValidationRequirement` and `ModelObligation`, keeping those routes independent while sharing the contract source.

## Risks / Trade-offs

- Contracts rely on labels or metadata being attached consistently to model steps. Mitigation: provide metadata helper functions and tests for both label-driven and metadata-driven usage.
- Receipt names are strings and can be mistyped. Mitigation: keep serialized reports explicit and expose contract ids and receipt ids in findings.
- A contract can be too coarse if one receipt covers several independent guarantees. Mitigation: users can split receipts without changing FlowGuard core.
- Conformance metadata is optional. Mitigation: the replay rule only checks expected metadata that exists, so old adapters remain compatible while stricter adapters can opt in.

## Migration Plan

1. Add the new module and exports.
2. Add `FlowGuardCheckPlan.step_contracts` and runner integration.
3. Add process and alignment projection helpers.
4. Add conformance metadata rule helper.
5. Update docs, README, template command, and tests.
6. Bump package version and sync editable install plus shadow workspace.
