# Model-Test Alignment Protocol

Use Model-Test Alignment when a FlowGuard model and ordinary tests both exist
and the question is whether they cover the same obligations. When the reviewed
behavior also has an externally visible code surface, include optional code
external contracts between the model obligations and the test evidence.

This protocol is independent from TestMesh, StructureMesh, and ModelMesh.
It does not split tests, split code, split models, or read mesh reports. It
compares explicit model obligations, optional code external contracts, and
plain test evidence.

When the result supports a final done, release, publish, or full-confidence
claim, pass the obligation ids, code contract ids, test evidence ids, statuses,
freshness, and assertion scopes into a Risk Evidence Ledger. Alignment proves
rows agree; the ledger decides whether the broader user-risk claim is full,
scoped, or blocked.

For recurring or high-risk same-class model misses, alignment evidence is an
input to the defect-family gate. Use `review_defect_family_gates(...)` before
the Risk Evidence Ledger claim; do not make Model-Test Alignment the family
promotion route.

For related obligations that share a family-level confidence claim, add
`ObligationFamily` and `ObligationFamilyEvidence` rows. The family parity check
is not the defect-family gate; it verifies that every sibling obligation has
the same required mechanism coverage from allowed provenance sources before the
family claim is treated as full confidence.

When real code observations are available for a finite code boundary, add the
code-boundary conformance layer before trusting a hand-authored code contract.
This layer checks whether real code accepted only allowed input cases, rejected
forbidden input cases, and emitted only declared outputs, state writes, side
effects, and error paths. Use `CodeBoundaryContract`,
`CodeBoundaryObservation`, and `review_code_boundary_conformance()`. It checks
the code boundary; it is not a new skill and not a replacement for full trace
replay.

When the finite code boundary belongs to a leaf model in a parent/child mesh,
upgrade the boundary observations into a leaf boundary matrix. A matrix row is
one `Input x State` cell and records allowed outputs, next states, state
writes, side effects, error paths, evidence ids, status, and freshness. A leaf
model can support parent confidence only when every finite cell is current and
passing, or when the leaf is split further or explicitly scoped.

When real-code progress is being compared to the model, add runtime path
evidence rows. Each runtime node observation must name `model_id`,
`model_path`, `node_id`, run id, status, and the model obligation or code
contract when known. Anonymous logs or helper-only progress messages are not
model-test alignment evidence.

When real Python source and tests are available, add the conservative source audit
layer before trusting hand-authored rows. This layer reads Python ASTs to
generate or check `PythonCodeContractEvidence` and
`PythonTestAssertionEvidence`, then feeds the resulting rows and confidence
boundaries into the same Model-Test Alignment review. Use
`audit_python_code_contracts()`, `audit_python_test_assertions()`, and
`review_python_contract_source_audit()` when the Python source is available.
It is an evidence collector, not a semantic proof engine.

## Trigger

Create or update a model-test alignment review when:

- a FlowGuard model adds or changes scenarios, invariants, hazards, state
  transitions, or input/output contracts;
- a public function, API, CLI, facade, adapter, persisted output, or other
  externally visible code surface is expected to implement a model-backed
  obligation;
- tests are added or changed for model-backed behavior;
- a report claims that model coverage and test coverage agree;
- a report claims that code contract coverage and test coverage agree for a
  model-backed behavior;
- a model pass and test pass need to be reconciled before release or broad
  completion;
- a post-runtime model-miss repair needs proof that tests cover both the
  observed regression and the same-class generalized bug family;
- several sibling obligations are being promoted as one family-level claim and
  need required mechanism coverage with allowed provenance;
- reviewers suspect orphan tests, orphan code contracts, duplicated test
  claims, duplicated code contract owners, stale evidence, internal-path-only
  tests, or happy-path-only coverage of risky model obligations.
- declared `CodeContract` or `TestEvidence` rows need to be checked against
  real Python source/test files before a coverage claim is trusted.
- alignment evidence suggests the model is missing an obligation, code-boundary
  observation, state branch, split child obligation, or current evidence refresh;
  feed those rows to `review_model_maturation_loop(...)`.
- declared code boundaries need runtime observation evidence showing allowed
  inputs, rejected inputs, outputs, errors, state writes, and side effects
  stayed inside the model-declared boundary.

Do not trigger this protocol merely because tests are large or slow. Use
TestMesh for parent/child test hierarchy problems. Do not trigger it merely
because source structure is being split. Use StructureMesh for code or API
partition problems.

## Input Checklist

List `ModelObligation` rows:

- obligation id;
- type such as scenario, invariant, hazard, transition, or contract;
- short description;
- whether it is required for the current decision;
- required test kinds, such as `happy_path`, `failure_path`, `edge_path`,
  `negative_path`, or `replay`;
- whether shared evidence is explicitly allowed.
- whether shared implementation is explicitly allowed;
- whether the obligation originated from a model miss;
- whether same-class model-miss closure evidence is required;
- required closure evidence roles, normally `observed_regression` and
  `same_class_generalized` for in-scope model-miss repairs;
- externally visible inputs and outputs when the obligation owns an external
  behavior contract;
- state reads, state writes, side effects, and error paths that the external
  contract must preserve;
- whether the external code contract must be exact, meaning extra externally
  visible behavior is also a gap.

List optional `ObligationFamily` rows when sibling obligations share a
family-level claim:

- family id and member obligation ids;
- required mechanisms each non-exempt member must prove;
- allowed provenance sources, such as durable reconciliation, runtime
  observation, or controller receipt;
- whether external evidence is required;
- exempt member ids and why the family claim is scoped;
- evidence ids with member id, mechanism, status, freshness, provenance, scope,
  and optional proof artifact.

List optional `CodeContract` rows when an externally visible code surface is in
scope. Do not invent or refactor code solely to fill this section. When Python
source audit is available, record whether each row is hand-authored,
AST-supported, partial, missing, ambiguous, dynamic, or manual-review-required.

- code contract id;
- path, symbol, and surface type such as function, class, API, CLI, facade, or
  persisted output;
- role such as `owner`, `helper`, `adapter`, `facade`, or `read_only`;
- implemented model obligation ids;
- externally visible inputs and outputs;
- state reads, state writes, side effects, and error paths;
- whether the contract is required.
- source-audit notes: inspected path, discovered symbol, supported fields,
  missing fields, dynamic features, and manual-review reason.

List optional `CodeBoundaryContract` and `CodeBoundaryObservation` rows when a
code surface claims a closed boundary:

- boundary id;
- bound code contract id and model obligation id;
- allowed input cases and rejected input cases;
- allowed outputs, state writes, side effects, and error paths;
- whether the boundary is exact;
- observation id, input case, accepted/rejected result, observed output, error
  path, state writes, side effects, status, freshness, and assertion scope.

List leaf boundary matrix rows when this review is proving a leaf model:

- leaf model id and matrix id;
- expected `Input x State` cell ids;
- input case and state case for each cell;
- expected and observed outputs, next states, state writes, side effects, and
  error paths;
- evidence ids, result status, freshness, and assertion scope;
- split-required or scoped-exemption status if the leaf is too large.

List `TestEvidence` rows:

- evidence id;
- test name, path, and command;
- result status: passed, failed, timeout, skipped, not-run, running, or error;
- freshness and stale reasons;
- test kind;
- evidence role: `primary`, `primary_edge_path`, `leaf_matrix_cell`,
  `supporting_contract`, or `integration_smoke`;
- evidence target id when the role is supporting evidence or a leaf matrix
  cell;
- covered model obligation ids;
- covered code contract ids when code contracts are in scope;
- assertion scope: `external_contract`, `internal_path`, `mixed`, or
  `unknown`;
- whether the test overclaims full model confidence;
- model-miss closure role when relevant: `observed_regression` or
  `same_class_generalized`.
- source-audit notes: asserted symbol, assertion forms, expected exceptions,
  output/state/call/persisted-output checks, monkeypatch/fixture usage, and
  manual-review reason.

## Conservative Source Audit Checklist

Use this checklist only when real Python source or tests are in scope:

- parse Python files with `ast` and inspect real definitions, imports,
  decorators, calls, returns, yields, raises, assignments, context managers, and
  writes that are visible without executing the program;
- inspect function signatures, return values, raises, assignments, and calls,
  then keep missing Python symbol, missing input, missing output, missing state write,
  and extra side effect findings visible;
- identify external surfaces such as public functions, classes, methods, CLIs,
  facades, adapters, and persisted outputs;
- compare AST-visible inputs, outputs, state reads, state writes, side effects,
  and error paths with declared `CodeContract` fields;
- inspect Python tests for direct calls to the external surface, assertions,
  expected exceptions, output checks, state checks, call checks, persisted-output
  checks, parametrization, pytest markers, fixtures, and monkeypatching;
- check that tests must call the declared code contract symbol and contain an
  assert or unittest assertion; keep helper/internal path and no assert findings
  visible;
- classify assertion scope as `external_contract`, `mixed`, `internal_path`, or
  `unknown`;
- treat name similarity as a candidate binding only; require explicit ids,
  reviewer maps, direct calls, or other strong evidence for high-confidence
  model/code/test bindings;
- preserve execution status and freshness: AST-visible assertions in skipped,
  stale, failed, timeout, not-run, running, or error tests are not current
  coverage;
- mark dynamic imports, reflection, generated attributes, monkeypatch-heavy
  behavior, framework lifecycle hooks, concurrency, external services, and
  runtime-value-dependent behavior as ambiguous or manual-review-required unless
  stronger evidence is supplied.

The audit must never claim perfect Python semantics. It also must not replace
conformance replay when production state, durable side effects, external
systems, trace-level behavior, or adapter projection is part of the confidence
claim.

## Required Findings

The review must keep these findings visible:

- `missing_test_evidence`: a required model obligation has no current passing
  test evidence;
- `missing_code_contract`: a required model obligation has code contracts in
  scope but no owner contract;
- `code_contract_missing_behavior`: an owner code contract omits external
  inputs, outputs, state reads, state writes, side effects, or error paths
  required by the model obligation;
- `code_contract_extra_behavior`: an exact model obligation is implemented by a
  code contract that exposes extra behavior;
- `boundary_missing_runtime_evidence`: a code boundary has no current
  external-boundary observation;
- `boundary_missing_allowed_input_evidence`: an allowed input case has no
  current accepted observation;
- `boundary_missing_rejected_input_evidence`: a rejected input case has no
  current input-gate rejection observation;
- `boundary_forbidden_input_accepted`: a forbidden input was accepted by real
  code;
- `boundary_unknown_input_accepted`: an unknown input was accepted by an exact
  boundary;
- `boundary_extra_output`, `boundary_extra_error_path`,
  `boundary_extra_state_write`, and `boundary_extra_side_effect`: real code
  emitted behavior outside the declared boundary;
- `missing_code_contract_test_evidence`: a required owner code contract has no
  current passing external-contract test evidence;
- `missing_required_test_kind`: a required path kind is absent;
- `missing_observed_regression_test_evidence`: an in-scope model-miss
  obligation lacks current observed-regression evidence;
- `missing_same_class_test_evidence`: an in-scope model-miss obligation lacks
  current same-class generalized test evidence;
- `model_miss_closure_evidence_internal_path_only`: model-miss closure evidence
  does not prove the external behavior boundary;
- `orphan_test_evidence`: a test is not bound to a model obligation;
- `orphan_code_contract`: an owner code contract is not bound to any model
  obligation;
- `unknown_obligation_reference`: a test names an obligation the model does not
  declare;
- `unknown_model_obligation_reference`: a code contract names an obligation the
  model does not declare;
- `unknown_code_contract_reference`: a test names a code contract the review
  does not declare;
- `test_not_bound_to_code_contract`: code contracts are in scope but a test only
  binds to model obligations;
- `test_checks_internal_path_only`: a test binds to a code contract but does
  not assert the external contract;
- `model_code_test_binding_mismatch`: a test's model-obligation binding and
  code-contract binding do not overlap;
- `duplicate_code_contract_owner`: multiple owner code contracts claim the same
  obligation without explicit shared implementation intent;
- `duplicate_test_evidence_owner`: multiple tests claim the same obligation and
  kind without explicit shared intent;
- `obligation_too_coarse_for_primary_evidence`: multiple current primary
  `edge_path` rows claim the same obligation, so the obligation needs child
  split or leaf matrix-cell reattachment;
- `leaf_matrix_cell_target_missing`: a leaf matrix-cell evidence row does not
  name the cell it proves;
- `supporting_evidence_target_missing`: supporting evidence is not attached to
  a child obligation, code contract, boundary, or leaf cell;
- `stale_test_evidence`: stale evidence is being reused;
- `test_evidence_not_passing`: skipped, failed, timeout, not-run, running, or
  error evidence is not coverage;
- `test_overclaims_model_confidence`: a test report claims broader model
  confidence than its bindings prove.
- `source_audit_partial_contract`: AST-visible code supports only part of a
  declared code contract;
- `source_audit_dynamic_or_ambiguous`: source or test behavior depends on
  dynamic features the conservative audit cannot prove;
- `source_audit_manual_review_required`: complex behavior needs human review
  before the evidence can support an external-contract claim.

## Prompt Template

```text
Build a FlowGuard Model-Test Alignment review for this repository.

Treat the FlowGuard model as the obligation source and ordinary tests as
evidence. If an externally visible code surface is in scope, include optional
code external contracts as plain alignment rows between the model obligations
and tests. Do not invoke TestMesh, StructureMesh, ModelMesh, split tests, split
code, split models, or read mesh reports.
List each model obligation, optional code contract, and current test evidence.

Model obligations:
- id:
- type:
- required:
- required test kinds:
- shared evidence allowed:
- shared implementation allowed:
- external inputs/outputs:
- state reads/writes:
- side effects:
- error paths:
- exact external contract:
- description:

Code external contracts (optional; include only when in scope):
- id:
- path/symbol/surface type:
- role:
- implements obligation ids:
- required:
- external inputs/outputs:
- state reads/writes:
- side effects:
- error paths:

Code boundary conformance (optional; include when a code surface must be closed):
- boundary id:
- code contract id:
- model obligation id:
- allowed input cases:
- rejected input cases:
- allowed outputs/state writes/side effects/error paths:
- exact boundary:
- observations:

Test evidence:
- id:
- test name/path/command:
- status:
- current or stale:
- test kind:
- covered obligation ids:
- covered code contract ids:
- assertion scope:
- overclaiming:
- model-miss closure role:
- source-audit notes:

If real Python source or tests are available, first perform a conservative AST
audit of code contracts and test assertions. Use it to generate or check the
CodeContract and TestEvidence rows, but do not treat it as a perfect semantic
proof or a conformance replay substitute.

For post-runtime model-miss repairs, mark observed-regression and same-class
generalized evidence separately. Do not let the observed regression substitute
for same-class closure evidence.

Flag missing model-obligation coverage, missing or mismatched code external
contracts, boundary observations that accept forbidden inputs or emit
undeclared behavior, missing external-contract test evidence, orphan tests,
orphan code contracts, unknown references, duplicate same-kind test claims,
duplicate code contract owners, internal-path-only tests, model-code-test
binding mismatches, happy-path-only coverage for risky obligations, stale or
non-passing evidence, partial source-audit support, dynamic or ambiguous
source-audit findings, manual-review-required findings, and overclaimed model
confidence.
```

## Completion Standard

A model-test alignment review can support a coverage claim only when:

- every required model obligation has current passing test evidence;
- every in-scope repaired model-miss obligation has current observed-regression
  and same-class generalized test evidence;
- every required test kind is covered;
- when code contracts are in scope, every required model obligation has an
  owner code contract unless the obligation explicitly allows the omission for
  the current review;
- owner code contracts preserve required external inputs, outputs, state reads,
  state writes, side effects, and error paths;
- exact external contracts do not expose extra behavior without being reported;
- exact code boundaries have current observations for allowed and rejected
  input cases, and observed outputs, errors, state writes, and side effects do
  not exceed the boundary;
- every required owner code contract has current passing test evidence with an
  `external_contract` or `mixed` assertion scope;
- orphan and unknown-obligation tests are absent or explicitly accepted as
  warnings for the current scope;
- orphan code contracts and unknown code-contract references are absent or
  explicitly accepted as warnings for the current scope;
- duplicate same-kind claims are absent or explicitly allowed by the model
  obligation;
- duplicate primary `edge_path` claims are absent; if several real code
  boundaries need primary proof, the model obligation is split or the evidence
  is reattached to leaf matrix cells;
- missing obligations, stale rows, boundary mismatches, or duplicate primary
  edge paths have been fed to `review_model_maturation_loop(...)` before broad
  confidence is claimed;
- supporting and leaf matrix-cell evidence rows name their target ids;
- duplicate code contract owners are absent or explicitly allowed by the model
  obligation;
- tests that bind model obligations and code contracts refer to overlapping
  behavior;
- stale, skipped, failed, timeout, not-run, running, and error evidence remain
  visible as gaps;
- conservative source-audit findings are not overclaimed as semantic proof;
- partial, dynamic, ambiguous, or manual-review-required audit results remain
  visible as confidence boundaries;
- the report does not claim production conformance unless a separate
  conformance replay or equivalent production-facing check supports that claim.
- the report supplies enough evidence ids and assertion scopes for
  `review_risk_evidence_ledger(...)` when a final confidence claim is being
  made.
