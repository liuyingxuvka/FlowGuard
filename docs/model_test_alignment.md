# Model-Test Alignment

Model-Test Alignment compares a FlowGuard model's explicit obligations with
ordinary test evidence and, when supplied, code external contracts. It is still
a direct alignment helper: it does not split tests, refactor source code, or
read TestMesh, StructureMesh, or ModelMesh reports.

Use it before claiming that model coverage, code behavior, and test coverage
describe the same behavioral surface.

## Code Boundary Conformance

When a model-backed code surface claims a finite input/output boundary, add
code-boundary conformance evidence before trusting the claim. The model and
`CodeContract` rows declare the boundary; `CodeBoundaryContract` narrows that
boundary into runtime cases, and `CodeBoundaryObservation` records what the real
code actually did for those cases.

This checks the code, not the model. A passing boundary review means current
observations show that:

- allowed input cases are accepted by the real code;
- rejected input cases hit the input gate and do not enter the modeled core;
- accepted code paths only produce declared outputs;
- observed error paths, state writes, and side effects stay inside the declared
  boundary;
- stale, skipped, failed, timeout, not-run, running, error, or internal-path
  observations do not count as current boundary evidence.

Use `review_code_boundary_conformance(...)` directly for a focused boundary
review, or include `boundary_contracts` and `boundary_observations` in
`ModelTestAlignmentPlan` so `review_model_test_alignment(...)` blocks green
alignment when real code crosses the model-declared boundary.

This is runtime boundary evidence, not exhaustive semantic proof. It should not
replace conformance replay when ordered production traces, durable state,
external systems, or adapter projection are part of the confidence claim.

## Conservative Source Audit

When real Python source and tests are available, add a conservative source
audit before relying on hand-authored `CodeContract` and `TestEvidence` rows.
The audit reads Python ASTs and asks whether observable code structure and
observable test assertions support the declared external contracts.

Use `audit_python_code_contracts(...)` to produce
`PythonCodeContractEvidence`, `audit_python_test_assertions(...)` to produce
`PythonTestAssertionEvidence`, and `review_python_contract_source_audit(...)`
to report source-level findings before trusting the declared rows.

The source audit can support or challenge alignment rows by recording:

- code-contract evidence for public functions, classes, methods, CLIs, facades,
  adapters, and persisted outputs;
- AST-visible external inputs, outputs, state reads, state writes, side effects,
  and error paths;
- test-assertion evidence from real Python tests, including assertions,
  expected exceptions, output checks, state checks, call checks, and persisted
  output checks;
- assertion scope: `external_contract`, `mixed`, `internal_path`, or
  `unknown`;
- confidence boundaries such as partial support, missing symbols, dynamic
  behavior, internal-only tests, stale execution evidence, or required manual
  review.

This is deliberately conservative. It is not a perfect Python semantic prover,
does not infer arbitrary dynamic behavior, and does not replace conformance
replay or production-facing checks. If behavior depends on runtime values,
reflection, monkeypatching, generated attributes, framework lifecycle hooks,
concurrency, external services, durable side effects, or trace projection, keep
the audit result as ambiguous or manual-review-required until stronger evidence
exists.

## Inputs

List model obligations with `ModelObligation`:

- obligation id, type, description, and required flag;
- required test kinds such as `happy_path`, `failure_path`, `edge_path`,
  `negative_path`, or `replay`;
- external inputs and outputs;
- state reads and writes;
- side effects and error paths;
- `exact_external_contract=True` when code-visible extras should block
  confidence.

List code external contracts with `CodeContract` when model-to-code alignment
is in scope. These rows may be hand-authored, generated from conservative source
audit, or hand-authored and then checked against source audit evidence:

- code contract id, path, symbol, and surface type;
- role: owner, helper, adapter, facade, or read-only support;
- implemented model obligation ids;
- external inputs and outputs;
- state reads and writes;
- side effects and error paths.

List runtime boundary rows when the code surface must be closed:

- boundary id, code contract id, and model obligation id;
- allowed input cases and rejected input cases;
- allowed outputs, state writes, side effects, and error paths;
- whether the boundary is exact;
- current observations from real code tests, replay adapters, or harnesses.

For a lowest-level FlowGuard leaf, these boundary rows should be complete
enough to populate the layered proof leaf matrix: every finite input/state
cell has declared outputs, next states, state writes, side effects, error
paths, evidence ids, and freshness status.

List test evidence with `TestEvidence`:

- evidence id, test name, path, and command;
- result status and freshness;
- test kind;
- evidence role: primary boundary evidence, primary edge-path evidence,
  supporting contract evidence, integration smoke evidence, or leaf matrix-cell
  evidence;
- evidence target id when a row supports a child obligation, code contract, or
  leaf matrix cell;
- covered model obligation ids;
- covered code contract ids;
- assertion scope, especially whether the test proves the external contract or
  only an internal path.
- optional source-audit notes when real tests were inspected: asserted symbols,
  assertion forms, status/freshness source, and manual-review reasons.

## Findings

The review keeps these gaps visible:

- model obligations with no current passing test evidence;
- missing required test kinds;
- stale, skipped, failed, timeout, not-run, running, or error evidence;
- orphan tests, unknown obligation references, and duplicate same-kind test
  evidence owners;
- duplicate current primary `edge_path` evidence for the same obligation, which
  means the obligation is too coarse and should split or reattach evidence to
  leaf matrix cells;
- supporting or leaf matrix-cell evidence without a target id;
- model obligations with no code external contract owner;
- code contracts that miss model-declared external behavior;
- exact code contracts that add model-forbidden external behavior;
- code-boundary observations that accept forbidden inputs, accept unknown
  inputs, reject allowed inputs, miss required input-gate evidence, or emit
  undeclared output, state writes, side effects, or error paths;
- tests that cover a model obligation without binding the code contract they
  are meant to prove;
- tests that bind a code contract but only inspect internal implementation
  paths;
- audited source evidence that is partial, ambiguous, dynamic, or requires
  manual review;
- model, code, and test bindings that do not refer to the same obligation.

## Boundary

This helper is not TestMesh and not StructureMesh. Use TestMesh when the
validation flow itself needs parent/child suite ownership. Use StructureMesh
when a large script, module, command, or API surface is being split. Model-Test
Alignment stays focused on declared obligations, optional code external
contracts, and the tests that prove them. Layered boundary proof may consume
the aligned boundary evidence for leaf matrices, but it owns the parent
coverage, child disjointness, and child reattachment decision.

Conservative source audit is also not conformance replay. Use replay when the
claim depends on real production state, side effects, external systems,
trace-level behavior, or adapter projection between model traces and runtime
observations.

Model-Test Alignment produces the rows that a Risk Evidence Ledger can consume:
model obligation IDs, code contract IDs, test evidence IDs, result status,
freshness, and assertion scope. It should not claim final done or release
confidence by itself when other risk rows, mesh evidence, UI journeys, or
process freshness can still invalidate the broader claim. Feed those rows into
`review_risk_evidence_ledger(...)` before saying the modeled risk is fully
covered.
