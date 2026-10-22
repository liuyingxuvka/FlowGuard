# Model-Test Alignment
Reuse the current owner model and tests. Create a persistent scaffold only for a new
reusable boundary; apply the regression examples relevant to this change.
Use this to cross-check three lists row by row: what the model says must happen
(obligations), which code function owns each obligation (code contracts), and which tests
prove it (test evidence). It catches gaps between them. Examples: the model says "reject a
duplicate order" but no function claims it; the function claims it but no `failure_path`
test exists; a test is green but only asserts on an internal helper; the function writes
`orders` but the contract does not declare that write; two functions both claim to own the
same rule; a test covers an obligation id that no longer exists.
## Use when
- You add or change an obligation and must name the one function that owns it and the tests that prove it.
- A field, input, output, state write, side effect or error path changed, and you must check code and tests still match.
- You claim "every rule in the model is implemented and tested" for a component.
- A facade or adapter forwards to the real owner and must not succeed on its own.
## Do not use when
- You need to know whether the model itself is right (reachable bad states, invariants). Run the component's model (`python -m flowguard map models <MODEL_ID>`).
- You need every input x state case of one rule. Use contract-exhaustion.
- The test suite is large, slow or layered and must be split or partitioned. Use test-mesh.
- A field is added, renamed or removed across many places. Use field-lifecycle first; feed its rows here.
## Inputs

- `python -m flowguard read --component ID`: `entrypoints` (each `path/to/file.py:Symbol`),
  `state`, `side_effects`, `tests`, `models`.
- `python -m flowguard map check`: every entrypoint anchor must exist (no `anchor_broken`)
  and every `tests` pattern must match a file (no `test_missing`). Build code contracts only from anchors that pass.
- The model's rules: one obligation per rule you want proved, with its inputs, outputs,
  state reads/writes, side effects and error paths, and the test kinds it needs
  (for example `happy_path`, `failure_path`).
- The test functions in the component's `tests` files, and their real results from a run you do now.

## Steps

1. For a new reusable review, `python -m flowguard template model-test-alignment --write .`
   writes `.flowguard/models/model_test_alignment.py`, one feature-kit contract model.
   Set PARENT to the reviewed model's actual MODEL_ID and REVIEWED to its file;
   add a top-level import of that parent file. Replace all code and test anchors.
2. `alignment_plan_from_model(REVIEWED, root=ROOT)` reads literal TESTED_BY and IMPLEMENTED_BY:
   one obligation per rule, one contract per code anchor, one evidence row per unique test anchor.
   Shared tests retain every bound obligation. Its default passing statuses are design assumptions.
   The generated conformance uses `run_bound_tests` once, checks its complete ModelResult,
   and rebuilds the plan with actual statuses: missing results are not_run; a passing test that
   touched none of the model's implementation anchors is unbound. Each actual parameter case
   must independently pass and touch at least one anchor. Failed tests cannot be promoted.
   Native `ModelObligation`, `CodeContract`, `TestEvidence` and source-audit APIs remain available
   for deeper input/output/state/effect contracts; literal bindings do not infer assertion strength.
3. A facade: `CodeContract(..., role=CODE_CONTRACT_ROLE_FACADE, delegates_to_code_contract_id="orders.place",
   delegation_only=True, delegation_evidence_id=..., delegation_evidence_current=True)`.
4. Optional families (one rule over many members, e.g. every export format): `ObligationFamily`,
   `ObligationFamilyEvidence`, passed as `obligation_families` / `family_evidence`.
5. Run the contract with `python -m flowguard map models model_test_alignment`; the intended
   design must pass and each generated bad variant must fail a real design property.
6. Existing user-written runners remain supported and must be listed in their owner's models.
   Templates create no runner; contract models are discovered automatically. Then use `change`.

## What blocks

| Code | Meaning |
|---|---|
| `missing_code_contract` | An obligation has no owning code contract. |
| `duplicate_code_contract_owner` | Two contracts claim to own the same obligation. |
| `code_contract_missing_behavior` | The contract does not declare an input, output, state write, side effect or error path the obligation needs. |
| `missing_required_test_kind` | A required test kind (e.g. `failure_path`) has no passing, current test. |
| `test_evidence_not_passing` | A bound test is `failed`, `skipped`, `not_run`, etc. |
| `test_checks_internal_path_only` | The test asserts on internals, not the external contract. |
| `missing_code_contract_test_evidence` | An owner contract has no passing external test. |
| `orphan_test_evidence` | A test covers no obligation (also `unknown_obligation_reference`). |
| `missing_same_class_test_evidence` | The obligation needs a same-class test and none exists. |
| `facade_independent_business_authority` | A facade can succeed without delegating to its owner. |
| `source_audit_blocked` | The AST audit failed: e.g. `source_contract_missing_symbol`, `source_contract_missing_state_write`, `source_test_missing_code_contract_call`, `source_test_missing_external_assertion`, `source_contract_parse_error`. |

Green decision: `model_test_alignment_green`.

## Risk-specific regression examples

- No `failure_path` test for the duplicate-order rule (`missing_required_test_kind`).
- The contract drops `state_writes=("orders",)` (`code_contract_missing_behavior`).
- The test exists but the run failed or was not run (`test_evidence_not_passing`).
- A second contract also lists the obligation (`duplicate_code_contract_owner`).

## Done when

- [ ] Every code contract comes from a map entrypoint that `python -m flowguard map check` accepts.
- [ ] The selected direct native review or existing-owner check passes; relevant broken cases are blocked.
- [ ] You ran the tests `python -m flowguard change` lists; skipped or not-run tests are reported as such.
- [ ] Tests are mapped; any new/changed persistent runner is registered with one current `map models` result.
- [ ] `python -m flowguard change` is clean. Your report lists what ran, what was skipped, and which obligations had no test.

## Limits

- Declared rows are not execution evidence; the generated conformance obtains statuses from real bound tests.
  `require_source_audit=True` makes the review read the code and the tests (AST audit).
- The AST audit checks simple imports/aliases and direct call-result assertions. Unknown receivers,
  constants-only assertions and complex dataflow cannot close an execution claim. State writes are
  still approximate: a local assignment can resemble a write; review the business meaning yourself.
- A simple map anchor rename needs the existing model/tests, not a new alignment runner.
- It is not conformance replay. A contract model's `conformance()` (run by `map models`) replays model
  traces on the real code; this review checks bindings. Add conformance when order,
  state, side effects or another externally visible contract requires replay.
- Literal TESTED_BY keys supply obligations, not every explorer rule. An unlisted rule remains outside this review.
