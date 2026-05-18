# Model-Test Alignment

Model-Test Alignment compares a FlowGuard model's explicit obligations with
ordinary test evidence and, when supplied, code external contracts. It is still
a direct alignment helper: it does not split tests, refactor source code, or
read TestMesh, StructureMesh, or ModelMesh reports.

Use it before claiming that model coverage, code behavior, and test coverage
describe the same behavioral surface.

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
is in scope:

- code contract id, path, symbol, and surface type;
- role: owner, helper, adapter, facade, or read-only support;
- implemented model obligation ids;
- external inputs and outputs;
- state reads and writes;
- side effects and error paths.

List test evidence with `TestEvidence`:

- evidence id, test name, path, and command;
- result status and freshness;
- test kind;
- covered model obligation ids;
- covered code contract ids;
- assertion scope, especially whether the test proves the external contract or
  only an internal path.

## Findings

The review keeps these gaps visible:

- model obligations with no current passing test evidence;
- missing required test kinds;
- stale, skipped, failed, timeout, not-run, running, or error evidence;
- orphan tests, unknown obligation references, and duplicate same-kind test
  evidence owners;
- model obligations with no code external contract owner;
- code contracts that miss model-declared external behavior;
- exact code contracts that add model-forbidden external behavior;
- tests that cover a model obligation without binding the code contract they
  are meant to prove;
- tests that bind a code contract but only inspect internal implementation
  paths;
- model, code, and test bindings that do not refer to the same obligation.

## Boundary

This helper is not TestMesh and not StructureMesh. Use TestMesh when the
validation flow itself needs parent/child suite ownership. Use StructureMesh
when a large script, module, command, or API surface is being split. Model-Test
Alignment stays focused on declared obligations, optional code external
contracts, and the tests that prove them.
