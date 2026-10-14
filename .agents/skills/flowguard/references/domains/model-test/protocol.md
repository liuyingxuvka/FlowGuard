# Model-Test Alignment
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
- Tests should record which modeled steps the real code hit, in order (runtime path evidence).

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

1. `python -m flowguard template model-test-alignment --write .` writes
   `.flowguard/models/owners/model_test_alignment/model.py`,
   `.flowguard/verification/owners/model_test_alignment/run_checks.py` and
   `docs/model_test_alignment.md`. Rename `model_test_alignment` to your component id.
   The template's plan is a small local stand-in; replace it with the real API below.
   `model-test-alignment-full` is a runnable teaching example; its sample statuses are not project execution evidence.
2. In `model.py`, build the rows with the real API:
   ```python
   from flowguard import (ModelObligation, CodeContract, TestEvidence, ModelTestAlignmentPlan,
       review_model_test_alignment, audit_python_code_contracts, audit_python_test_assertions,
       review_python_contract_source_audit)
   ob = ModelObligation("reject_duplicate_order", required_test_kinds=("happy_path", "failure_path"),
       external_inputs=("order",), external_outputs=("result",), state_writes=("orders",))
   cc = CodeContract("orders.place", path="shop/orders.py", symbol="place_order",   # = map entrypoint
       implements_obligations=("reject_duplicate_order",), external_inputs=("order",),
       external_outputs=("result",), state_writes=("orders",))
   t = TestEvidence("t_dup", test_name="test_duplicate_rejected", path="tests/test_orders.py",
       result_status=status_from_pytest["tests/test_orders.py::test_duplicate_rejected"],
       test_kind="failure_path", covered_obligations=("reject_duplicate_order",),
       covered_code_contracts=("orders.place",))
   src = {p: open(p).read() for p in ("shop/orders.py", "tests/test_orders.py")}
   audit = review_python_contract_source_audit((cc,), (t, ...),
       audit_python_code_contracts((cc,), src), audit_python_test_assertions((t, ...), (cc,), src))
   report = review_model_test_alignment(ModelTestAlignmentPlan("orders", obligations=(ob,),
       code_contracts=(cc,), test_evidence=(t, ...), source_audit_reports=(audit,),
       require_source_audit=True, require_executed_evidence=True))
   # report.ok, report.decision, report.findings[i].code, report.binding_rows
   ```
3. Run pytest once outside the runner with `FLOWGUARD_PYTEST_NODEIDS=.flowguard/cache/pytest-run.json`,
   `-p flowguard.pytest_nodeid_recorder --junitxml=.flowguard/cache/pytest.xml` in a git project.
   A separate `bind_run.py` audits sources and calls `bind_pytest_execution(plan,
   evidence_nodeids={evidence_id: exact_nodeid}, nodeid_manifest=..., project_root=root)`.
   The recorder supplies actual statuses and input freshness; no hand-written digests/statuses.
   Missing, skipped, failed or stale results remain blocked. Keep evidence outside model/run_checks.
4. A facade: `CodeContract(..., role=CODE_CONTRACT_ROLE_FACADE, delegates_to_code_contract_id="orders.place",
   delegation_only=True, delegation_evidence_id=..., delegation_evidence_current=True)`.
5. Optional runtime path: in a test, `rec = RuntimePathRecorder("run-1")`, call `rec.record(node_id, ...)`
   at each modeled step, and pass `runtime_node_contracts` (`RuntimeNodeContract`), `runtime_node_observations=rec.observations`
   and `require_runtime_path_evidence=True` in the plan. Every node contract and every `record(...)` call
   must carry the same `business_intent_id`, `behavior_commitment_id` and `primary_path_id`, or it blocks.
   Template: `runtime-path-evidence`.
6. Optional families (one rule over many members, e.g. every export format): `ObligationFamily`,
   `ObligationFamilyEvidence`, passed as `obligation_families` / `family_evidence`.
7. In `run_checks.py`, return 0 only when the good plan is `ok` and every broken variant is not.
   Run `python .flowguard/verification/owners/<id>/run_checks.py`.
8. Add that `run_checks.py` path to the component's `models` in `.flowguard/map.json`, then run
   `python -m flowguard map models <MODEL_ID>` and `python -m flowguard change`.

## What blocks

| Code | Meaning |
|---|---|
| `missing_code_contract` | An obligation has no owning code contract. |
| `duplicate_code_contract_owner` | Two contracts claim to own the same obligation. |
| `code_contract_missing_behavior` | The contract does not declare an input, output, state write, side effect or error path the obligation needs. |
| `missing_required_test_kind` | A required test kind (e.g. `failure_path`) has no passing, current test. |
| `test_evidence_not_passing` | A bound test is `failed`, `skipped`, `not_run`, etc. |
| `stale_test_evidence` | The test result is marked not current. |
| `test_checks_internal_path_only` | The test asserts on internals, not the external contract. |
| `missing_code_contract_test_evidence` | An owner contract has no passing external test. |
| `orphan_test_evidence` | A test covers no obligation (also `unknown_obligation_reference`). |
| `missing_same_class_test_evidence` | The obligation needs a same-class test and none exists. |
| `facade_independent_business_authority` | A facade can succeed without delegating to its owner. |
| `source_audit_blocked` | The AST audit failed: e.g. `source_contract_missing_symbol`, `source_contract_missing_state_write`, `source_test_missing_code_contract_call`, `source_test_missing_external_assertion`, `source_contract_parse_error`. |

`executed_evidence_required` appears when `require_executed_evidence=True` and a test was not run.
Green decision: `model_test_alignment_green`. Runtime path: `runtime_path_order_mismatch`, `runtime_node_missing_observation`.

## Known-bad cases to include

- No `failure_path` test for the duplicate-order rule (`missing_required_test_kind`).
- The contract drops `state_writes=("orders",)` (`code_contract_missing_behavior`).
- The test exists but the run failed or was not run (`test_evidence_not_passing`).
- A second contract also lists the obligation (`duplicate_code_contract_owner`).

## Done when

- [ ] Every code contract comes from a map entrypoint that `python -m flowguard map check` accepts.
- [ ] `run_checks.py` exits 0: the good plan is green and every broken variant is blocked.
- [ ] Test statuses come from a pytest run in this session; skipped or not-run tests are reported as such.
- [ ] The tests are in the component's `tests`; the runner is in its `models`; `map models <MODEL_ID>` passes.
- [ ] `python -m flowguard change` is clean. Your report lists what ran, what was skipped, and which obligations had no test.

## Limits

- Declared rows are not execution evidence. Feed exact pytest node statuses through the result
  connector with recorder-owned current input scope; require source audit and executed evidence for implementation claims.
- The AST audit checks simple imports/aliases and direct call-result assertions. Unknown receivers,
  constants-only assertions and complex dataflow cannot close an execution claim. State writes are
  still approximate: a local assignment can resemble a write; review the business meaning yourself.
- It is not conformance replay. A contract model's `conformance()` (run by `map models`) replays model
  traces on the real code; this review only checks that obligations, code and tests are bound. Use both.
- Obligations are not derived from your model's explorer; you write them by hand, so a rule you forget is not checked.
