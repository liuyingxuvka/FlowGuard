# Model-Test Alignment Protocol

Use Model-Test Alignment when a FlowGuard model and ordinary tests both exist
and the question is whether they cover the same obligations.

This protocol is independent from TestMesh, StructureMesh, and ModelMesh.
It does not split tests, split code, or read mesh reports. It compares explicit
model obligations with plain test evidence.

## Trigger

Create or update a model-test alignment review when:

- a FlowGuard model adds or changes scenarios, invariants, hazards, state
  transitions, or input/output contracts;
- tests are added or changed for model-backed behavior;
- a report claims that model coverage and test coverage agree;
- a model pass and test pass need to be reconciled before release or broad
  completion;
- reviewers suspect orphan tests, duplicated test claims, stale evidence, or
  happy-path-only coverage of risky model obligations.

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

List `TestEvidence` rows:

- evidence id;
- test name, path, and command;
- result status: passed, failed, timeout, skipped, not-run, running, or error;
- freshness and stale reasons;
- test kind;
- covered model obligation ids;
- whether the test overclaims full model confidence.

## Required Findings

The review must keep these findings visible:

- `missing_test_evidence`: a required model obligation has no current passing
  test evidence;
- `missing_required_test_kind`: a required path kind is absent;
- `orphan_test_evidence`: a test is not bound to a model obligation;
- `unknown_obligation_reference`: a test names an obligation the model does not
  declare;
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
evidence. Do not invoke TestMesh, StructureMesh, ModelMesh, or split tests.
List each model obligation and bind current test evidence to it.

Model obligations:
- id:
- type:
- required:
- required test kinds:
- description:

Test evidence:
- id:
- test name/path/command:
- status:
- current or stale:
- test kind:
- covered obligation ids:
- overclaiming:

Flag missing model-obligation coverage, orphan tests, duplicate same-kind test
claims, happy-path-only coverage for risky obligations, stale or non-passing
evidence, and overclaimed model confidence.
```

## Completion Standard

A model-test alignment review can support a coverage claim only when:

- every required model obligation has current passing test evidence;
- every required test kind is covered;
- orphan and unknown-obligation tests are absent or explicitly accepted as
  warnings for the current scope;
- duplicate same-kind claims are absent or explicitly allowed by the model
  obligation;
- stale, skipped, failed, timeout, not-run, running, and error evidence remain
  visible as gaps;
- the report does not claim production conformance unless a separate
  conformance replay or equivalent production-facing check supports that claim.
