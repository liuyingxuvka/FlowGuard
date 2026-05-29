## Context

FlowGuard currently has several adjacent evidence layers:

- model traces (`Trace` / `TraceStep`) describe expected abstract execution;
- conformance replay compares representative traces to projected real behavior;
- Model-Test Alignment compares obligations, code contracts, boundary
  observations, and tests;
- ModelMesh and layered boundary proof connect parent/child model evidence;
- Runtime Gateway Adoption checks whether critical writes are mediated;
- Closure Contract coordinates final confidence evidence.

The missing layer is a reusable runtime path evidence contract. Real tests and
project runs should be able to emit structured node observations that identify
which model, child model, leaf model, obligation, code contract, boundary, and
workflow node actually executed. FlowGuard can then compare the expected node
path with the observed path and feed that result into existing alignment and
closure helpers.

The upgrade is intentionally standard-library only and compatible with the
current helper style: immutable dataclasses, `to_dict()` methods, text reports,
and review functions that consume rows collected by project adapters.

## Goals / Non-Goals

**Goals:**

- Add a public runtime path evidence API for node contracts, node
  observations, observed runs, expected paths, and alignment reports.
- Make runtime path evidence usable by leaf model boundary matrices and
  parent/child model confidence without flattening child internals into the
  parent.
- Let model-test alignment, runtime gateway adoption, layered proof, and
  closure contract block broad confidence when required runtime nodes are
  missing, stale, non-passing, out of order, or bound to the wrong model
  obligation.
- Provide a template and documentation so projects can add small instrumentation
  hooks to their code/tests instead of using ad hoc logs.
- Update Codex/FlowGuard skill guidance so future agents know this is a
  first-class evidence route, not a prose checklist.

**Non-Goals:**

- Do not require every private helper function to emit a node.
- Do not make runtime path evidence a replacement for conformance replay,
  ordinary tests, TestMesh, ModelMesh, or Risk Evidence Ledger.
- Do not introduce tracing backends, OpenTelemetry, async collectors, network
  sinks, or external dependencies.
- Do not infer complete production correctness from a single observed path.
- Do not force parent models to inline every child model's internal graph.

## Decisions

### Runtime path evidence is a helper route, not core modeling

Add `flowguard/runtime_path.py` and export its APIs through
`MODELING_HELPER_API`, not `CORE_API`. The core `Workflow`/`Explorer` path stays
small. Runtime path evidence is used when real code, tests, parent/child mesh
confidence, or production confidence is in scope.

Alternative considered: add node ids directly to `TraceStep` and force all
models to use them. That would make simple model-first work heavier and would
not cover real-code observation rows by itself.

### Node contracts and observations use stable ids

Use explicit string ids:

- `node_id`: stable workflow node id;
- `model_id`, `child_model_id`, and `leaf_model_id`: hierarchy bindings;
- `model_path`: a human-readable file or package path for the corresponding
  FlowGuard model so another AI or machine can find the model being compared;
- `model_obligation_id`, `code_contract_id`, and `boundary_id`: alignment
  bindings;
- `input_case` and `state_case`: leaf matrix cell bindings;
- `evidence_id` and optional `ProofArtifactRef`: concrete proof bindings.

This keeps path evidence readable, serializable, and easy to feed into existing
helpers.

### Progress output identifies the compared model

Runtime node progress output must be structured enough for a reader that does
not already have the FlowGuard context loaded. `RuntimePathRecorder` emits
observations that include model ids and model paths, and each observation can
format a compact progress line naming the FlowGuard model, node, obligation,
code contract, boundary, run, and status. This makes progress printing usable
as model/code comparison evidence instead of ordinary logs.

### Path alignment compares three things

`review_runtime_path_alignment(...)` should check:

1. Coverage: every required node contract has a current passing observation.
2. Behavior: observed outputs, next states, state writes, side effects, and
   error paths stay inside the declared node contract.
3. Path structure: ordered contracts appear in order and observed runs do not
   include forbidden or unknown nodes when exact path matching is requested.

This is narrower than full semantic replay and broader than a single
code-boundary observation.

### Leaf models own real-code node observations

The lowest leaf model boundary is where real code must prove it follows the
model. A leaf boundary matrix cell can reference runtime node evidence ids and
optionally proof artifacts. If a leaf cannot produce complete finite runtime
path evidence, the model should split further or the parent confidence stays
scoped.

### Parent models consume child evidence ids

Parent ModelMesh confidence consumes child runtime path evidence ids and
reattachment contracts. The parent checks that child outputs are consumed,
child evidence is current, and child boundaries still match parent
expectations. It does not read every child node unless a specific handoff is
being reviewed.

### Existing helpers consume runtime path reports as evidence

- Model-Test Alignment consumes runtime path contracts and observations to
  block missing real-code path evidence.
- Layered Boundary Proof consumes runtime path evidence ids in leaf matrix
  cells.
- Runtime Gateway Adoption binds critical write observations to runtime node
  ids.
- Closure Contract adds `runtime_path_alignment` as a report kind and blocks
  full confidence when runtime path mapping is required but missing.
- Risk Evidence Ledger consumes runtime path alignment through proof evidence
  and route report rows rather than becoming the runtime path checker itself.

## Risks / Trade-offs

- [Risk] Node instrumentation becomes noisy or too fine-grained. -> Require
  runtime nodes only at model-owned external boundaries, state writes, side
  effects, handoffs, error paths, and claim points.
- [Risk] A green observed path is overclaimed as exhaustive proof. -> Reports
  keep missing required nodes, exact-path mismatches, scoped leaf matrices, and
  proof artifact gaps visible.
- [Risk] Parent models become too large by reading all child internals. -> The
  parent consumes child evidence ids and handoff contracts; child internals
  remain child-owned.
- [Risk] Projects emit logs but not structured evidence. -> Provide
  `RuntimePathRecorder` plus JSONL-friendly `to_dict()` rows and templates.
- [Risk] Existing projects without runtime path evidence break unexpectedly. ->
  Make runtime path evidence opt-in unless plans explicitly require it or a
  broad closure claim depends on real code path confidence.
- [Risk] Parallel agents modify adjacent files while this work is active. ->
  Keep edits scoped, do not revert unrelated changes, and re-check git/status
  before syncing to the source repository.

## Migration Plan

1. Add the new runtime path evidence helper and focused tests.
2. Add OpenSpec, docs, templates, and CLI support.
3. Integrate runtime path evidence as optional rows in existing helper plans.
4. Update skill guidance to require runtime path evidence only for in-scope
   leaf code boundaries and broad runtime/parent confidence claims.
5. Validate with focused tests, template execution, OpenSpec validation,
   FlowGuard self-model checks, and full regression.
6. Sync the current workspace to the local git source repository and refresh
   editable install/version checks.
