# Model-Test Alignment

Model-Test Alignment compares a FlowGuard model's explicit obligations with
owner code contracts and ordinary test evidence. It is still
a direct alignment helper: it does not split tests, refactor source code, or
read TestMesh, StructureMesh, or ModelMesh reports.

Use it before claiming that model coverage, code behavior, and test coverage
describe the same behavioral surface.

For real Python code claims, make the source-audit decision part of the same
plan instead of leaving it as a side note. Add
`ModelTestAlignmentPlan.source_audit_reports` and set
`require_source_audit=True` when the claim depends on declared `path` and
`symbol` rows matching actual source and tests. Missing, red, or unrelated
source-audit reports block the final alignment decision.

Each report also emits `ModelCodeTestBindingRow` closure summaries. A row names
the model obligation, owner code contract ids, code paths and symbols, test
evidence ids, boundary/runtime/payload ids, source-audit decision, and open gap
codes. Treat that row as the final claim boundary for an AI-written code
change: if the row says the source audit or runtime evidence is missing, the
final claim stays scoped.

For post-runtime model-miss repairs and non-trivial bug fixes, use Model-Test
Alignment after Model-Miss Review updates the model. The repaired in-scope
obligation should mark that it originated from a model miss and require closure
evidence roles: one current observed-regression test and one current
ContractExhaustionMesh same-class case test. It also needs the owner `CodeContract` for the real public,
CLI, API, facade, adapter, or persisted-output surface that implements the
repair. A green exact regression test is necessary, but it is not enough for
full closure.

When the model miss came from a concrete counterexample trace or known-bad
proof, add a target-aware closure requirement. Use
`ClosureEvidenceTarget` with `counterexample_regression` or
`known_bad_replay`, and make the matching `TestEvidence` cite the same
`evidence_target_id`, owner code contract, and external assertion scope.

If the same-class miss recurs or is high risk, Model-Test Alignment still only
proves the obligation/test rows. The recurring family itself is handled by
`review_defect_family_gates(...)` and then consumed by the Risk Evidence Ledger.
The sibling bad-case ids should come from ContractExhaustionMesh, normally via
`family_bad_case_seed_to_contract_cases(...)` and
`contract_exhaustion_to_model_obligations(...)`.

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
    contract_exhaustion_to_model_obligations,
    transition_coverage_to_contract_cases,
    TransitionCoverageCell,
    TransitionCoverageMatrix,
    model_mesh_closure_to_contract_cases,
    model_mesh_closure_to_transition_coverage,
    transition_coverage_to_code_contracts,
    transition_coverage_to_model_obligations,
    transition_coverage_to_required_leaf_cell_ids,
)
```

Small matrices can feed `ModelTestAlignmentPlan.obligations` directly. Large,
slow, layered, browser-heavy, or release-only matrices should also project
required cell ids into TestMesh through
`transition_coverage_to_required_leaf_cell_ids(...)`. The generated matrix
does not prove anything by itself; it only creates stable targets that current
test evidence must cover. When a cell names `code_contract_id`, also project
the matrix into `CodeContract` rows with
`transition_coverage_to_code_contracts(...)` and bind transition-cell test
evidence to the same contract.

When ModelMesh owns the parent/child handoff, project the
`MeshClosureModel` with `model_mesh_closure_to_transition_coverage(...)` before
claiming tests cover that mesh route. Retry or rejection closure transitions
that declare repeated input tokens require happy-path, failure-path,
negative-path, and replay evidence through the generated transition cells.
For canonical same-class, no-delta, stale-child, or unconsumed-child coverage,
also project the closure model through `model_mesh_closure_to_contract_cases(...)`
and feed the resulting cases through ContractExhaustionMesh.

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

## Artifact Payload Validation

When a model-backed feature loads, saves, imports, exports, generates, or
consumes a file-like payload or AI work package, add payload validation rows
before trusting the user-facing claim. Use `ArtifactPayloadContract`,
`ArtifactPayloadCase`, `ArtifactPayloadEvidence`, and
`review_artifact_payload_validation()`, or include `payload_contracts` and
`payload_evidence` in `ModelTestAlignmentPlan`.

Each payload contract should name the model obligation, owner code contract,
payload surface, payload kind, and a small synthetic pack of accepted and
rejected cases. The synthetic cases are test inputs for the real payload
surface; they are not standalone payload-only paths. Evidence should
record the case id, method, current status, external assertion scope, observed
status/output/error path/state writes/side effects, round-trip result when
required, and an `evidence_ref` or `proof_artifact` that points to the real
surface run. Manual checks must still be structured case evidence; prose-only
manual review is scoped or blocked.

When payload cases are used to claim finite bad-case coverage, project the
contract through `artifact_payload_cases_to_contract_cases(...)` and then
`review_contract_exhaustion(...)`. Model-Test Alignment consumes the resulting
model obligations and evidence rows; it does not treat ad hoc payload examples
as canonical exhaustive coverage.

## Conservative Source Audit

When real Python source and tests are available, add a conservative source
audit before relying on hand-authored `CodeContract` and `TestEvidence` rows.
The audit reads Python ASTs and asks whether observable code structure and
observable test assertions support the declared external contracts.

Use `audit_python_code_contracts(...)` to produce
`PythonCodeContractEvidence`, `audit_python_test_assertions(...)` to produce
`PythonTestAssertionEvidence`, and `review_python_contract_source_audit(...)`
to report source-level findings before trusting the declared rows.

When this audit is required for a real-code alignment claim, pass the resulting
`ContractSourceAuditReport` into `ModelTestAlignmentPlan.source_audit_reports`
and set `require_source_audit=True`. A green audit must cover the plan's
required code contract ids and real test evidence ids; an unrelated green audit
is not enough.

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
- required closure targets with `ClosureEvidenceTarget` when a specific
  counterexample id, known-bad proof id, or replay case id must become a real
  code regression test.

List code external contracts with `CodeContract` for every required model
obligation that is part of the confidence claim. These rows may be
hand-authored, generated from transition coverage or conservative source audit,
or hand-authored and then checked against source audit evidence:

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

List artifact payload rows when the behavior has file/work-package surfaces:

- payload contract id, model obligation id, owner code contract id, payload
  surface, and payload kind;
- required case ids, expected accepted/rejected status, expected output, error
  path, state writes, side effects, and round-trip requirement;
- current evidence id, method, assertion scope, observed status/output/error,
  observed state writes and side effects, evidence reference or proof artifact
  for the real surface run, and stale reason.

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

For field-bearing changes, supply FieldLifecycleMesh reports or projections to
`ModelTestAlignmentPlan`. Behavior-bearing fields become model obligations and
owner code contracts through `FieldProjection`; they still need current test
evidence. Old or replacement fields must have closing field lifecycle
disposition evidence before the alignment can support full confidence.
When a FieldLifecycleMesh plan claims full, runtime, release, production, or
closure confidence, behavior field projections should also carry minimal route
refs in `FieldProjection.evidence_refs`: `gate:` for the boundary or runtime
gate, `test:` for negative or failure-path proof, and `replay:` for replay
evidence. Those refs make the field route auditable, but Model-Test Alignment
still owns current passing test evidence and binding to the owner code
contract.

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
  and lack ContractExhaustionMesh case test evidence;
- ContractExhaustionMesh closure evidence that is stale, overclaimed, internal-path-only,
  or attached to the wrong model obligation;
- bug-repair closure evidence whose model obligation, owner code contract, and
  observed/contract-exhaustion case tests do not all bind the same repaired behavior;
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
- tests that bind a code contract that does not implement the same model
  obligation;
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
Alignment stays focused on declared obligations, owner code external
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
