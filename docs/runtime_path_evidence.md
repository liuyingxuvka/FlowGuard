# Runtime Path Evidence

Runtime path evidence is the bridge between real code progress and a
FlowGuard model. It records which modeled node the real code actually reached,
which FlowGuard model owns that node, and which obligation or code contract the
node is supposed to prove.

Use it when tests, replay, a runtime gateway, a leaf boundary matrix, a parent
mesh, or a final closure claim needs to compare real execution with a
FlowGuard model.

## Required Row Shape

Every runtime node observation should carry:

- `model_id` and, when known, `model_path`;
- `node_id`;
- `run_id`;
- `leaf_model_id` or `child_model_id` when the node belongs to a model mesh;
- `model_obligation_id`, `code_contract_id`, or `boundary_id` when known;
- `business_path_id`, `business_intent`, and expected/observed terminal when a
  claim depends on a specific useful business route;
- input/state case and observed output, next state, writes, effects, or error
  path when relevant;
- status, freshness, assertion scope, and optional `ProofArtifactRef`.

Progress output should use `RuntimeNodeObservation.format_progress_line()` or
the recorder's `format_progress_lines()` so the line says which FlowGuard
model is being compared:

```text
flowguard.runtime_path model=checkout.leaf model_path=.flowguard/checkout_leaf/model.py node=validate_order run=run:1 status=passed obligation=accept_valid_order business_path=submit_order
```

That line is intentionally readable without the model already loaded. A human
or another AI can see which model file to inspect next.

## Review

Use `review_runtime_path_alignment(...)` with `RuntimeNodeContract`,
`RuntimeNodeObservation`, and `RuntimePathRun` rows. The review blocks when a
required node is missing, stale, non-passing, internal-path-only, out of order,
bound to the wrong model obligation, bound to the wrong business path, missing
a required business path binding, or emits behavior outside the node contract.

Runtime path evidence is not a replacement for conformance replay, tests,
ModelMesh, TestMesh, or closure review. It is the structured model/code path
evidence those routes can consume.
