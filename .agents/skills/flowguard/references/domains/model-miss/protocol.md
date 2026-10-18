# Model-Miss Review

Reuse the current owner model and tests. Create a persistent scaffold only for a new
reusable boundary; apply the regression examples relevant to this change.

Use this after a model was green but a test, runtime run, log or manual check
still failed. The bug class is the "green model, broken product" escape: the
model had no input for the case (a timeout, an empty list, a second click), its
invariant was too weak to notice the bad state, or the model and the code
disagree. Make the owning model reject the escaped case, keep the intended design
passing, and protect the observed behavior with a real regression; add siblings only when required below.

## Use when

- A model listed in `map.json` passed, then a test or runtime check failed on the same behavior.
- A bug report shows a case the model should have covered (missing input, state, branch).
- A UI promised a function the model marked as present, and a user could not use it.
- The same kind of miss happened before and you want the whole class closed.

## Do not use when

- No model covered this behavior yet. Write one first (plain modeling, `references/model_recipes.md`), then come back if it escapes again.
- The failure is a plain coding error and the model already rejects that behavior. Fix the code and keep the test.
- The miss is about which tests to run or test/model drift. Use model-test.
- The miss is a field rename or retired config key. Use field-lifecycle.

## Inputs

- The failing test node id or the runtime evidence (log line, trace, screenshot).
- `python -m flowguard map impact <code file under the failure>`: owner, models, tests (a test file maps to no component).
- `python -m flowguard read --find WORDS` if you do not know the file, then
  `python -m flowguard read --component ID`: `entrypoints`, `state`, `side_effects`, `tests`, `models`.
- The owning model file (listed in the component's `models`) and the code at its entrypoints.

## Steps

1. Reproduce the failure, keep the evidence, write down the previous green claim.
2. From the `map impact` output pick the one component that owns the behavior and its model.
   No model covers it: say so (coverage gap).
3. Classify the miss. For a non-UI miss use one cause from `FALSE_NEGATIVE_CAUSES`:
   `model_input_missing`, `invariant_too_weak`, `oracle_gap`, `adapter_mapping_loss`,
   `stale_evidence`, `claim_scope_overpromotion`. For a UI miss use `UI_MODEL_MISS_TYPES`:
   `evidence_overclaimed`, `boundary_missing`, `state_too_coarse`, `input_branch_missing`,
   `code_boundary_mismatch`, `affordance_mismatch`, `action_grammar_conflict`,
   `dialog_return_missing`, `keyboard_focus_missing`, `region_semantics_conflict`,
   `human_walkthrough_failed`. `invariant_too_weak`
   is not in `UI_MODEL_MISS_TYPES`; `review_ui_model_misses` rejects it with
   `ui_model_miss_unknown_type`. Put a weak-invariant miss in a `FalseNegativeCase`.
4. Write `would_have_failed_if`: the model change that would have caught it (new input, finer state, stronger invariant).
5. Update the owning model's existing obligation/known-bad case to reject the miss; for a contract
   model, use `broken_variants()`. Add necessary independent siblings for recurring/high-risk misses,
   native-required UI scope, or an observed independent same-class path; ordinary misses need no extra sibling.
   Keep `build_explorer()` passing; reuse existing cases instead of mechanically creating another model.
6. Rerun `python -m flowguard map models <id>` (runner id = its directory name). Exit 0: intended
   design passes, every broken variant fails. Then run `python -m flowguard change`.
7. Keep one real behavior regression for the observed failure, updating an existing test if it can
   assert the same promise. Add sibling coverage only under step 5's conditions; list files in the owner's `tests`.
8. Record the backpropagation and review it:

```python
from flowguard import FalseNegativeCase, FalseNegativeBackpropagationPlan, review_false_negative_backpropagation
case = FalseNegativeCase(
    case_id="miss:login-timeout", previous_claim_id="models:login green",
    observed_failure_id="tests/test_login.py::test_timeout", cause="model_input_missing",
    would_have_failed_if=("model has a Timeout input on Submit",),
    new_model_obligation_id="login:no_timeout_branch",
    generalized_case_id="login:slow_network_retry",
    closure_evidence_ids=("tests/test_login.py::test_timeout",))
report = review_false_negative_backpropagation(
    FalseNegativeBackpropagationPlan("login-timeout", (case,), recurring_or_high_risk=True))
assert report.ok, [f.code for f in report.findings]
```

   For UI misses build `UIModelMissRecord` rows (`miss_type`, `previous_claim_id`,
   `previous_green_reason`, `observed_failure`, `observed_failure_evidence_ref`, affected and
   `same_class_*` ids, `required_test_ids`, `root_cause_backpropagation`, `code_owner`,
   `rationale`) and run `review_ui_model_misses(UIModelMissReviewPlan(plan_id, (record,)))`.
9. Optional: `diagnose_false_negative_backpropagation(report, conflict_atoms=, conflict_oracle=,
   positive_atoms=, positive_oracle=, repair_candidate=)` finds a deletion-minimal conflict over
   `DiagnosticAtom`s and blocks a `RepairCandidate` whose `rejects_original_miss` is False.
10. Optional native scaffold: `python -m flowguard template model-miss-review --write .`.
    It illustrates one non-UI repair and a point-fix failure with the real reviewer.
    The explicit `model-miss-review-full` preserves deeper holdout/legacy/mesh teaching
    examples. Use the UI native reviewer for UI-specific misses; do not chain full routes.

## What blocks

| Code | Meaning |
|---|---|
| `missing_previous_passing_claim` | No record of which green claim missed the failure. |
| `missing_observed_failure` | No failing test id or runtime evidence. |
| `missing_false_negative_cause` | The miss was not classified. |
| `missing_would_have_failed_if` | No model change that would have caught it. |
| `missing_new_model_obligation` | Nothing new in the model captures the miss. |
| `missing_false_negative_closure_evidence` | No test or run shows the repair. |
| `missing_generalized_false_negative_case` | Recurring or high-risk miss without a same-class case. |
| `missing_adapter_gap_for_adapter_cause` | `adapter_mapping_loss` without the adapter gap id. |
| `ui_model_miss_unknown_type` | `miss_type` not in `UI_MODEL_MISS_TYPES`. |
| `ui_model_miss_missing_same_class_scope` | UI miss with no same-class capability/control/field ids. |
| `ui_model_miss_missing_backpropagation` | UI miss with no root-cause backpropagation text. |
| `repair_does_not_reject_original_miss` | Diagnosis: `RepairCandidate.rejects_original_miss` is False. |

## Risk-specific regression examples

- The escaped case itself: the old model with the missing input or weak invariant, as a broken
  variant that must now fail (for example, Submit with no Timeout branch reaches `logged_in`).
- When step 5 requires it, an independent same-class sibling: another input or path
  (slow network retry, second submit while pending).
- A point fix: only the regression test is recorded, with no `new_model_obligation_id`,
  `new_plan_item_ids` or `repair_evidence_ids`. The review must block with `missing_new_model_obligation`.
- A UI miss filed as `invariant_too_weak`: `review_ui_model_misses` must return
  `ui_model_miss_unknown_type`.

## Done when

- [ ] `python -m flowguard map models <id>` exits 0: intended design passes, every broken variant fails.
- [ ] The owner's model rejects the escaped case; required independent siblings from step 5 are covered.
- [ ] The observed-failure regression and any required siblings pass and are in the owner's `tests`.
- [ ] `review_false_negative_backpropagation` (or `review_ui_model_misses`) has no blocker.
- [ ] `python -m flowguard change` is clean; you report what ran, what was skipped, and why.

## Limits

- The review checks the records you fill in. It does not detect a miss by itself and does not
  replay the failure against the model; only the model run and the real tests do that.
- `review_false_negative_backpropagation` does not check `cause` against `FALSE_NEGATIVE_CAUSES`;
  any non-empty string passes. Any `repair_evidence_ids` entry also clears `missing_new_model_obligation`,
  so check the model variant yourself. The UI list (11) and the non-UI list (6) differ.
- A green model run proves only the declared states and inputs. Keep real tests next to it.
