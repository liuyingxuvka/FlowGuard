# Model-Test Alignment

Model-Test Alignment compares a FlowGuard model's explicit obligations with
ordinary test evidence and, when supplied, code external contracts. It is still
a direct alignment helper: it does not split tests, refactor source code, or
read TestMesh, StructureMesh, or ModelMesh reports.

Use it before claiming that model coverage, code behavior, and test coverage
describe the same behavioral surface.

For post-runtime model-miss repairs, use Model-Test Alignment after
Model-Miss Review updates the model. The repaired in-scope obligation should
mark that it originated from a model miss and require closure evidence roles:
one current observed-regression test and one current same-class generalized
test. A green exact regression test is necessary, but it is not enough for full
closure.

If the same-class miss recurs or is high risk, Model-Test Alignment still only
proves the obligation/test rows. The recurring family itself is handled by
`review_defect_family_gates(...)` and then consumed by the Risk Evidence Ledger.

When the claim spans a family of related obligations, add obligation-family
parity evidence to the same plan. Alignment can prove that each declared
obligation has tests, but family parity proves that sibling obligations all
have the required mechanism evidence from an allowed provenance source. A
manual event or controller receipt cannot prove a family requirement that says
the evidence must come from durable reconciliation.

When Model Topology Hazard Review promotes an anchored future-use hazard into a
testable obligation, include that hazard id in the model obligation row. A green
test suite should not close the hazard unless the test or code-boundary evidence
covers the specific topology anchor and future failure mode.

## Transition Coverage Matrix

For ordinary state-transition claims, first derive a transition coverage
matrix before claiming tests cover the model. A transition cell is one finite
`Input/Event x State -> Output x State` obligation. Projecting the matrix turns
each required cell into a `ModelObligation` with obligation type
`transition_coverage`.

Use:

```python
from flowguard import (
    TransitionCoverageCell,
    TransitionCoverageMatrix,
    transition_coverage_to_model_obligations,
    transition_coverage_to_required_leaf_cell_ids,
)
```

Small matrices can feed `ModelTestAlignmentPlan.obligations` directly. Large,
slow, layered, browser-heavy, or release-only matrices should also project
required cell ids into TestMesh through
`transition_coverage_to_required_leaf_cell_ids(...)`. The generated matrix
does not prove anything by itself; it only creates stable targets that current
test evidence must cover.

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
It also does not prove that every critical state writer in a target project is
mediated by a FlowGuard-backed runtime gateway. Use Runtime Gateway Adoption
for that claim.

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
- `model_miss_origin=True` and `requires_same_class_test_evidence=True` when
  the obligation is repairing a post-runtime miss;
- required closure evidence roles, normally `observed_regression` and
  `same_class_generalized` for in-scope model-miss repairs.

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

When real code path confidence matters, add runtime path rows as well:
`RuntimeNodeContract`, `RuntimeNodeObservation`, or recorder-produced
`RuntimePathRun` entries. Each observation should name the compared
`model_id`, `model_path`, `node_id`, and model obligation so the model-test
review can block broad confidence when the code never reached the modeled
node, reached it out of order, or only printed an anonymous/internal progress
log.

List obligation-family rows when several obligations are being claimed as the
same family:

- family id, member ids, required mechanisms, and allowed provenance sources;
- whether the family requires external evidence;
- optional exempt members and the reason they are not part of the current
  family claim;
- family evidence id, member id, mechanism, result status, freshness,
  provenance, evidence scope, and optional proof artifact.

List test evidence with `TestEvidence`:

- evidence id, test name, path, and command;
- result status and freshness;
- test kind;
- evidence role: primary boundary evidence, primary edge-path evidence,
  supporting contract evidence, integration smoke evidence, or leaf matrix-cell
  evidence. Use transition-cell evidence when a row proves a projected
  transition coverage cell;
- evidence target id when a row supports a child obligation, code contract,
  leaf matrix cell, or transition coverage cell;
- covered model obligation ids;
- covered code contract ids;
- assertion scope, especially whether the test proves the external contract or
  only an internal path.
- closure evidence role for model-miss repairs:
  `observed_regression` or `same_class_generalized`;
- optional source-audit notes when real tests were inspected: asserted symbols,
  assertion forms, status/freshness source, and manual-review reasons.
- optional `proof_artifact` references. When the plan sets
  `require_proof_artifacts=True`, a declared passing/current test row must also
  carry a proof artifact with a result path, artifact fingerprint, matching
  covered obligations, and external-contract scope when code contracts are
  being proved.
- optional `result_reused=True` plus `reuse_ticket=TestResultReuseTicket(...)`
  when the row reuses a previous test result instead of a fresh run. Reused test
  evidence must carry both a current reuse ticket and a current proof artifact;
  otherwise Model-Test Alignment reports the reuse/proof gap before the row can
  support model obligation or code contract coverage.

## Findings

The review keeps these gaps visible:

- model obligations with no current passing test evidence;
- missing required test kinds;
- stale, skipped, failed, timeout, not-run, running, or error evidence;
- reused test evidence with a missing/stale reuse ticket, changed command/test
  source/tested artifact/dependency/environment boundary, mismatched result
  fingerprint, stale coverage scope, or missing/stale proof artifact;
- orphan tests, unknown obligation references, and duplicate same-kind test
  evidence owners;
- duplicate current primary `edge_path` evidence for the same obligation, which
  means the obligation is too coarse and should split or reattach evidence to
  leaf matrix cells;
- repaired model-miss obligations that only have observed-regression evidence
  and lack same-class generalized test evidence;
- same-class closure evidence that is stale, overclaimed, internal-path-only,
  or attached to the wrong model obligation;
- supporting or leaf matrix-cell evidence without a target id;
- transition-cell evidence without a target id, or with a target id that does
  not match the projected transition obligation;
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
- family members or required mechanisms that have no current passing evidence;
- family evidence whose provenance cannot prove the required mechanism;
- family evidence that is stale, non-passing, internal-only when external
  evidence is required, or attached to an unknown member/mechanism.

## Boundary

This helper is not TestMesh and not StructureMesh. Use TestMesh when the
validation flow itself needs parent/child suite ownership. Use StructureMesh
when a large script, module, command, or API surface is being split. Model-Test
Alignment stays focused on declared obligations, optional code external
contracts, transition coverage matrices, family parity matrices, and the tests
that prove them. Layered boundary proof may consume the aligned boundary
evidence for leaf matrices, but it owns the parent coverage, child disjointness,
and child reattachment decision.

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

When alignment exposes a missing model obligation, stale proof, duplicate
primary edge path, missing code-boundary observation, or code-boundary mismatch,
also feed that signal to `review_model_maturation_loop(...)`. The fix may be a
model upgrade, a child split, a new boundary observation, or a scoped claim;
adding more tests alone is not always the right repair.

If same-class model-miss coverage needs broad parameterization, property tests,
seeded fuzz, background shards, release-only runs, or parent/child ownership,
route that validation structure to TestMesh. Model-Test Alignment should
consume the resulting current evidence ids; it should not become the test
hierarchy.

Alignment only checks declared obligations and declared test evidence. If a
plan may have omitted a repeated failure class, a project adapter may have lost
raw status or freshness, or a narrow report is being promoted to broad
completion confidence, run the plan-intake and typed claim-chain helpers before
the alignment result is used as final evidence.
