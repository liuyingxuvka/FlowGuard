# Model-Test Alignment Protocol

Use Model-Test Alignment when a FlowGuard model and ordinary tests both exist
and the question is whether they cover the same obligations. When the reviewed
behavior also has an externally visible code surface, include optional code
external contracts between the model obligations and the test evidence.

This protocol is independent from TestMesh, StructureMesh, and ModelMesh.
It does not split tests, split code, split models, or read mesh reports. It
compares explicit model obligations, optional code external contracts, and
plain test evidence.

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
- reviewers suspect orphan tests, orphan code contracts, duplicated test
  claims, duplicated code contract owners, stale evidence, internal-path-only
  tests, or happy-path-only coverage of risky model obligations.

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
- externally visible inputs and outputs when the obligation owns an external
  behavior contract;
- state reads, state writes, side effects, and error paths that the external
  contract must preserve;
- whether the external code contract must be exact, meaning extra externally
  visible behavior is also a gap.

List optional `CodeContract` rows when an externally visible code surface is in
scope. Do not invent or refactor code solely to fill this section.

- code contract id;
- path, symbol, and surface type such as function, class, API, CLI, facade, or
  persisted output;
- role such as `owner`, `helper`, `adapter`, `facade`, or `read_only`;
- implemented model obligation ids;
- externally visible inputs and outputs;
- state reads, state writes, side effects, and error paths;
- whether the contract is required.

List `TestEvidence` rows:

- evidence id;
- test name, path, and command;
- result status: passed, failed, timeout, skipped, not-run, running, or error;
- freshness and stale reasons;
- test kind;
- covered model obligation ids;
- covered code contract ids when code contracts are in scope;
- assertion scope: `external_contract`, `internal_path`, `mixed`, or
  `unknown`;
- whether the test overclaims full model confidence.

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
- `missing_code_contract_test_evidence`: a required owner code contract has no
  current passing external-contract test evidence;
- `missing_required_test_kind`: a required path kind is absent;
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
- `stale_test_evidence`: stale evidence is being reused;
- `test_evidence_not_passing`: skipped, failed, timeout, not-run, running, or
  error evidence is not coverage;
- `test_overclaims_model_confidence`: a test report claims broader model
  confidence than its bindings prove.

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

Flag missing model-obligation coverage, missing or mismatched code external
contracts, missing external-contract test evidence, orphan tests, orphan code
contracts, unknown references, duplicate same-kind test claims, duplicate code
contract owners, internal-path-only tests, model-code-test binding mismatches,
happy-path-only coverage for risky obligations, stale or non-passing evidence,
and overclaimed model confidence.
```

## Completion Standard

A model-test alignment review can support a coverage claim only when:

- every required model obligation has current passing test evidence;
- every required test kind is covered;
- when code contracts are in scope, every required model obligation has an
  owner code contract unless the obligation explicitly allows the omission for
  the current review;
- owner code contracts preserve required external inputs, outputs, state reads,
  state writes, side effects, and error paths;
- exact external contracts do not expose extra behavior without being reported;
- every required owner code contract has current passing test evidence with an
  `external_contract` or `mixed` assertion scope;
- orphan and unknown-obligation tests are absent or explicitly accepted as
  warnings for the current scope;
- orphan code contracts and unknown code-contract references are absent or
  explicitly accepted as warnings for the current scope;
- duplicate same-kind claims are absent or explicitly allowed by the model
  obligation;
- duplicate code contract owners are absent or explicitly allowed by the model
  obligation;
- tests that bind model obligations and code contracts refer to overlapping
  behavior;
- stale, skipped, failed, timeout, not-run, running, and error evidence remain
  visible as gaps;
- the report does not claim production conformance unless a separate
  conformance replay or equivalent production-facing check supports that claim.
