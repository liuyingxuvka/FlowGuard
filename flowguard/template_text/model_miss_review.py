"""Template text for FlowGuard model miss review route."""

from __future__ import annotations

MODEL_MISS_REVIEW_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Models the review loop required when a FlowGuard pass is followed by a test,
runtime, replay, or manual-validation failure.

Guards against:
- finalizing after a runtime issue without classifying the model miss;
- validating a fix before representing the observed issue in the model;
- validating a point fix before representing a same-class generalized bad case;
- validating only the observed bug without same-class test evidence;
- treating a recurring same-class miss as another ordinary point fix;
- using the known bug as the whole model target instead of holdout evidence;
- treating a later green runtime check as enough to close a known miss.

Use before editing:
bug-fix, model-miss, runtime-validation, replay, or completion-gate logic after
FlowGuard already passed.

Run:
python .flowguard/model_miss_review/run_checks.py

Replace the event names and obligations with the bug class under review.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.review import review_scenario, review_scenarios
from flowguard.scenario import Scenario, ScenarioExpectation


@dataclass(frozen=True)
class State:
    flowguard_passed: bool = False
    runtime_issue_observed: bool = False
    model_miss_classified: bool = False
    issue_represented_in_model: bool = False
    generalized_bad_case_in_scope: bool = True
    generalized_bad_case_represented_in_model: bool = False
    known_bug_used_as_holdout: bool = False
    observed_regression_test_added: bool = False
    same_class_test_evidence_added: bool = False
    model_test_alignment_rerun: bool = False
    recurring_family_detected: bool = False
    defect_family_gate_promoted: bool = False
    defect_family_gate_reviewed: bool = False
    fix_validated_after_refinement: bool = False
    completed: bool = False


@dataclass(frozen=True)
class Event:
    name: str


FLOWGUARD_PASS = Event("flowguard_pass")
RUNTIME_FAIL = Event("runtime_fail")
CLASSIFY_MISS = Event("classify_miss")
REPRESENT_ISSUE = Event("represent_issue")
REPRESENT_GENERALIZED_BAD_CASE = Event("represent_generalized_bad_case")
RECORD_KNOWN_BUG_HOLDOUT = Event("record_known_bug_holdout")
ADD_OBSERVED_REGRESSION_TEST = Event("add_observed_regression_test")
ADD_SAME_CLASS_TEST_EVIDENCE = Event("add_same_class_test_evidence")
RERUN_MODEL_TEST_ALIGNMENT = Event("rerun_model_test_alignment")
MARK_RECURRING_FAMILY = Event("mark_recurring_family")
PROMOTE_DEFECT_FAMILY_GATE = Event("promote_defect_family_gate")
REVIEW_DEFECT_FAMILY_GATE = Event("review_defect_family_gate")
VALIDATE_FIX = Event("validate_fix")
FINALIZE = Event("finalize")


class ApplyReviewStep:
    name = "ApplyReviewStep"
    reads = (
        "flowguard_passed",
        "runtime_issue_observed",
        "model_miss_classified",
        "issue_represented_in_model",
        "generalized_bad_case_in_scope",
        "generalized_bad_case_represented_in_model",
        "known_bug_used_as_holdout",
        "observed_regression_test_added",
        "same_class_test_evidence_added",
        "model_test_alignment_rerun",
        "recurring_family_detected",
        "defect_family_gate_promoted",
        "defect_family_gate_reviewed",
        "fix_validated_after_refinement",
    )
    writes = (
        "flowguard_passed",
        "runtime_issue_observed",
        "model_miss_classified",
        "issue_represented_in_model",
        "generalized_bad_case_represented_in_model",
        "known_bug_used_as_holdout",
        "observed_regression_test_added",
        "same_class_test_evidence_added",
        "model_test_alignment_rerun",
        "recurring_family_detected",
        "defect_family_gate_promoted",
        "defect_family_gate_reviewed",
        "fix_validated_after_refinement",
        "completed",
    )
    accepted_input_type = Event
    input_description = "review event"
    output_description = "updated model-miss review state"
    idempotency = "Repeated review events keep one obligation state."

    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "flowguard_pass":
            yield FunctionResult("flowguard_passed", replace(state, flowguard_passed=True), label="flowguard_passed")
            return
        if input_obj.name == "runtime_fail":
            if not state.flowguard_passed:
                yield FunctionResult("runtime_fail_before_model_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "runtime_issue_observed",
                replace(state, runtime_issue_observed=True, completed=False),
                label="runtime_issue_observed",
            )
            return
        if input_obj.name == "classify_miss":
            if not state.runtime_issue_observed:
                yield FunctionResult("classification_not_needed", state, label="blocked")
                return
            yield FunctionResult(
                "model_miss_classified",
                replace(state, model_miss_classified=True),
                label="model_miss_classified",
            )
            return
        if input_obj.name == "represent_issue":
            if not state.model_miss_classified:
                yield FunctionResult("representation_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "issue_represented_in_model",
                replace(state, issue_represented_in_model=True),
                label="issue_represented_in_model",
            )
            return
        if input_obj.name == "represent_generalized_bad_case":
            if not state.issue_represented_in_model:
                yield FunctionResult("generalized_bad_case_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "generalized_bad_case_represented_in_model",
                replace(state, generalized_bad_case_represented_in_model=True),
                label="generalized_bad_case_represented_in_model",
            )
            return
        if input_obj.name == "record_known_bug_holdout":
            if not state.generalized_bad_case_represented_in_model:
                yield FunctionResult("holdout_role_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "known_bug_used_as_holdout",
                replace(state, known_bug_used_as_holdout=True),
                label="known_bug_used_as_holdout",
            )
            return
        if input_obj.name == "add_observed_regression_test":
            if not state.known_bug_used_as_holdout:
                yield FunctionResult("observed_regression_test_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "observed_regression_test_added",
                replace(state, observed_regression_test_added=True),
                label="observed_regression_test_added",
            )
            return
        if input_obj.name == "add_same_class_test_evidence":
            if not state.observed_regression_test_added:
                yield FunctionResult("same_class_test_evidence_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "same_class_test_evidence_added",
                replace(state, same_class_test_evidence_added=True),
                label="same_class_test_evidence_added",
            )
            return
        if input_obj.name == "rerun_model_test_alignment":
            if not state.same_class_test_evidence_added:
                yield FunctionResult("model_test_alignment_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "model_test_alignment_rerun",
                replace(state, model_test_alignment_rerun=True),
                label="model_test_alignment_rerun",
            )
            return
        if input_obj.name == "mark_recurring_family":
            if not state.model_miss_classified:
                yield FunctionResult("recurring_family_mark_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "recurring_family_detected",
                replace(state, recurring_family_detected=True),
                label="recurring_family_detected",
            )
            return
        if input_obj.name == "promote_defect_family_gate":
            if not state.recurring_family_detected:
                yield FunctionResult("defect_family_gate_not_required", state, label="blocked")
                return
            if state.generalized_bad_case_in_scope and not state.model_test_alignment_rerun:
                yield FunctionResult("defect_family_gate_promotion_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "defect_family_gate_promoted",
                replace(state, defect_family_gate_promoted=True),
                label="defect_family_gate_promoted",
            )
            return
        if input_obj.name == "review_defect_family_gate":
            if not state.defect_family_gate_promoted:
                yield FunctionResult("defect_family_gate_review_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "defect_family_gate_reviewed",
                replace(state, defect_family_gate_reviewed=True),
                label="defect_family_gate_reviewed",
            )
            return
        if input_obj.name == "validate_fix":
            if not state.issue_represented_in_model:
                yield FunctionResult("fix_validation_blocked", state, label="blocked")
                return
            if state.generalized_bad_case_in_scope and not state.generalized_bad_case_represented_in_model:
                yield FunctionResult("point_fix_only_validation_blocked", state, label="blocked")
                return
            if state.generalized_bad_case_in_scope and not state.known_bug_used_as_holdout:
                yield FunctionResult("holdout_role_validation_blocked", state, label="blocked")
                return
            if state.generalized_bad_case_in_scope and not state.observed_regression_test_added:
                yield FunctionResult("observed_regression_test_validation_blocked", state, label="blocked")
                return
            if state.generalized_bad_case_in_scope and not state.same_class_test_evidence_added:
                yield FunctionResult("same_class_test_evidence_validation_blocked", state, label="blocked")
                return
            if state.generalized_bad_case_in_scope and not state.model_test_alignment_rerun:
                yield FunctionResult("model_test_alignment_validation_blocked", state, label="blocked")
                return
            if state.recurring_family_detected and not (
                state.defect_family_gate_promoted and state.defect_family_gate_reviewed
            ):
                yield FunctionResult("defect_family_gate_validation_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "fix_validated_after_refinement",
                replace(state, fix_validated_after_refinement=True),
                label="fix_validated_after_refinement",
            )
            return
        if input_obj.name == "finalize":
            if state.runtime_issue_observed and not state.fix_validated_after_refinement:
                yield FunctionResult("finalize_blocked_open_model_miss", state, label="finalize_blocked")
                return
            if state.recurring_family_detected and not state.defect_family_gate_reviewed:
                yield FunctionResult("finalize_blocked_open_defect_family_gate", state, label="finalize_blocked")
                return
            yield FunctionResult("completed", replace(state, completed=True), label="completed")
            return
        yield FunctionResult("unknown_event", state, label="blocked")


class BrokenFinalizeIgnoresModelMiss(ApplyReviewStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "finalize":
            yield FunctionResult(
                "completed_without_review",
                replace(state, completed=True),
                label="broken_completed_without_review",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenValidateFixWithoutRepresentation(ApplyReviewStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "validate_fix":
            yield FunctionResult(
                "fix_validated_without_model_representation",
                replace(state, fix_validated_after_refinement=True),
                label="broken_fix_validated_without_model_representation",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenPointFixOnlyValidation(ApplyReviewStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "validate_fix" and state.issue_represented_in_model:
            yield FunctionResult(
                "point_fix_validated_without_generalized_bad_case",
                replace(state, fix_validated_after_refinement=True),
                label="broken_point_fix_only_validation",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenValidateWithoutHoldoutRole(ApplyReviewStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if (
            input_obj.name == "validate_fix"
            and state.issue_represented_in_model
            and state.generalized_bad_case_represented_in_model
        ):
            yield FunctionResult(
                "validated_without_known_bug_holdout_role",
                replace(state, fix_validated_after_refinement=True),
                label="broken_validate_without_holdout_role",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenValidateWithoutSameClassTestEvidence(ApplyReviewStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if (
            input_obj.name == "validate_fix"
            and state.issue_represented_in_model
            and state.generalized_bad_case_represented_in_model
            and state.known_bug_used_as_holdout
        ):
            yield FunctionResult(
                "validated_without_same_class_test_evidence",
                replace(state, fix_validated_after_refinement=True),
                label="broken_validate_without_same_class_test_evidence",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenValidateRecurringWithoutDefectFamilyGate(ApplyReviewStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "validate_fix" and state.recurring_family_detected:
            yield FunctionResult(
                "recurring_family_validated_without_defect_family_gate",
                replace(state, fix_validated_after_refinement=True),
                label="broken_validate_recurring_without_defect_family_gate",
            )
            return
        yield from super().apply(input_obj, state)


def invariants() -> tuple[Invariant, ...]:
    def completion_requires_review(state: State, _trace) -> InvariantResult:
        if state.completed and state.runtime_issue_observed:
            if not (
                state.model_miss_classified
                and state.issue_represented_in_model
                and (
                    not state.generalized_bad_case_in_scope
                    or state.generalized_bad_case_represented_in_model
                )
                and (not state.generalized_bad_case_in_scope or state.known_bug_used_as_holdout)
                and (
                    not state.generalized_bad_case_in_scope
                    or (
                        state.observed_regression_test_added
                        and state.same_class_test_evidence_added
                        and state.model_test_alignment_rerun
                    )
                )
                and (
                    not state.recurring_family_detected
                    or (
                        state.defect_family_gate_promoted
                        and state.defect_family_gate_reviewed
                    )
                )
                and state.fix_validated_after_refinement
            ):
                return InvariantResult.fail(
                    "completed runtime issue without classification, observed issue model representation, same-class generalized bad case representation, known-bug holdout role, same-class test evidence, Model-Test Alignment rerun, recurring defect-family gate when needed, and refined validation"
                )
        return InvariantResult.pass_()

    def fix_validation_requires_model_representation(state: State, _trace) -> InvariantResult:
        if state.fix_validated_after_refinement and not state.issue_represented_in_model:
            return InvariantResult.fail("fix validated before the issue was represented in the model")
        return InvariantResult.pass_()

    def fix_validation_requires_generalized_bad_case(state: State, _trace) -> InvariantResult:
        if (
            state.fix_validated_after_refinement
            and state.generalized_bad_case_in_scope
            and not state.generalized_bad_case_represented_in_model
        ):
            return InvariantResult.fail("fix validated as point-fix-only without a same-class generalized bad case")
        return InvariantResult.pass_()

    def fix_validation_requires_known_bug_holdout_role(state: State, _trace) -> InvariantResult:
        if (
            state.fix_validated_after_refinement
            and state.generalized_bad_case_in_scope
            and not state.known_bug_used_as_holdout
        ):
            return InvariantResult.fail("fix validated before recording the known bug as holdout validation evidence")
        return InvariantResult.pass_()

    def fix_validation_requires_same_class_test_evidence(state: State, _trace) -> InvariantResult:
        if not (state.fix_validated_after_refinement and state.generalized_bad_case_in_scope):
            return InvariantResult.pass_()
        if not state.observed_regression_test_added:
            return InvariantResult.fail("fix validated before adding observed-regression test evidence")
        if not state.same_class_test_evidence_added:
            return InvariantResult.fail("fix validated before adding same-class generalized test evidence")
        if not state.model_test_alignment_rerun:
            return InvariantResult.fail("fix validated before rerunning Model-Test Alignment")
        return InvariantResult.pass_()

    def recurring_family_requires_defect_family_gate(state: State, _trace) -> InvariantResult:
        if not (state.fix_validated_after_refinement and state.recurring_family_detected):
            return InvariantResult.pass_()
        if not state.defect_family_gate_promoted:
            return InvariantResult.fail("recurring same-class miss validated before promoting a defect-family gate")
        if not state.defect_family_gate_reviewed:
            return InvariantResult.fail("recurring same-class miss validated before reviewing defect-family gate evidence")
        return InvariantResult.pass_()

    return (
        Invariant("completion_requires_review", "Runtime issues must be reviewed before completion.", completion_requires_review),
        Invariant(
            "fix_validation_requires_model_representation",
            "Fix validation requires executable model representation or an explicit boundary.",
            fix_validation_requires_model_representation,
        ),
        Invariant(
            "fix_validation_requires_generalized_bad_case",
            "Fix validation requires a same-class generalized bad case when that class is in scope.",
            fix_validation_requires_generalized_bad_case,
        ),
        Invariant(
            "fix_validation_requires_known_bug_holdout_role",
            "Fix validation records the known bug as holdout validation evidence, not the whole model target.",
            fix_validation_requires_known_bug_holdout_role,
        ),
        Invariant(
            "fix_validation_requires_same_class_test_evidence",
            "Fix validation requires observed regression and same-class test evidence aligned to the repaired model.",
            fix_validation_requires_same_class_test_evidence,
        ),
        Invariant(
            "recurring_family_requires_defect_family_gate",
            "Recurring same-class misses require a reviewed defect-family gate before validation.",
            recurring_family_requires_defect_family_gate,
        ),
    )


def workflow(block=None) -> Workflow:
    return Workflow((block or ApplyReviewStep(),), name="model_miss_review_template")


def scenario(name, description, events, expected, block=None) -> Scenario:
    return Scenario(
        name=name,
        description=description,
        initial_state=State(),
        external_input_sequence=events,
        expected=expected,
        workflow=workflow(block),
        invariants=invariants(),
    )


def run_checks():
    correct = review_scenario(
        scenario(
            "correct_model_miss_review",
            "Runtime issue is classified, observed issue and generalized bad case are represented, then the fix is validated and finalized.",
            (
                FLOWGUARD_PASS,
                RUNTIME_FAIL,
                CLASSIFY_MISS,
                REPRESENT_ISSUE,
                REPRESENT_GENERALIZED_BAD_CASE,
                RECORD_KNOWN_BUG_HOLDOUT,
                ADD_OBSERVED_REGRESSION_TEST,
                ADD_SAME_CLASS_TEST_EVIDENCE,
                RERUN_MODEL_TEST_ALIGNMENT,
                MARK_RECURRING_FAMILY,
                PROMOTE_DEFECT_FAMILY_GATE,
                REVIEW_DEFECT_FAMILY_GATE,
                VALIDATE_FIX,
                FINALIZE,
            ),
            ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("completed",),
                summary="model-miss obligation is closed before completion",
            ),
        )
    )
    broken = review_scenarios(
        (
            scenario(
                "finalize_without_review",
                "Broken workflow finalizes after runtime issue without review.",
                (FLOWGUARD_PASS, RUNTIME_FAIL, FINALIZE),
                ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("completion_requires_review",),
                ),
                block=BrokenFinalizeIgnoresModelMiss(),
            ),
            scenario(
                "validate_fix_without_representation",
                "Broken workflow validates the fix before representing the issue.",
                (FLOWGUARD_PASS, RUNTIME_FAIL, CLASSIFY_MISS, VALIDATE_FIX, FINALIZE),
                ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("fix_validation_requires_model_representation",),
                ),
                block=BrokenValidateFixWithoutRepresentation(),
            ),
            scenario(
                "point_fix_only_without_generalized_bad_case",
                "Broken workflow validates only the observed issue and misses a same-class generalized bad case.",
                (FLOWGUARD_PASS, RUNTIME_FAIL, CLASSIFY_MISS, REPRESENT_ISSUE, VALIDATE_FIX, FINALIZE),
                ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("fix_validation_requires_generalized_bad_case",),
                ),
                block=BrokenPointFixOnlyValidation(),
            ),
            scenario(
                "validate_without_known_bug_holdout_role",
                "Broken workflow models the class but forgets to record the known bug as holdout validation evidence.",
                (
                    FLOWGUARD_PASS,
                    RUNTIME_FAIL,
                    CLASSIFY_MISS,
                    REPRESENT_ISSUE,
                    REPRESENT_GENERALIZED_BAD_CASE,
                    VALIDATE_FIX,
                    FINALIZE,
                ),
                ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("fix_validation_requires_known_bug_holdout_role",),
                ),
                block=BrokenValidateWithoutHoldoutRole(),
            ),
            scenario(
                "validate_without_same_class_test_evidence",
                "Broken workflow models the class but only validates the observed bug.",
                (
                    FLOWGUARD_PASS,
                    RUNTIME_FAIL,
                    CLASSIFY_MISS,
                    REPRESENT_ISSUE,
                    REPRESENT_GENERALIZED_BAD_CASE,
                    RECORD_KNOWN_BUG_HOLDOUT,
                    ADD_OBSERVED_REGRESSION_TEST,
                    VALIDATE_FIX,
                    FINALIZE,
                ),
                ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("fix_validation_requires_same_class_test_evidence",),
                ),
                block=BrokenValidateWithoutSameClassTestEvidence(),
            ),
            scenario(
                "validate_recurring_without_defect_family_gate",
                "Broken workflow treats a recurring same-class miss as another ordinary point fix.",
                (
                    FLOWGUARD_PASS,
                    RUNTIME_FAIL,
                    CLASSIFY_MISS,
                    REPRESENT_ISSUE,
                    REPRESENT_GENERALIZED_BAD_CASE,
                    RECORD_KNOWN_BUG_HOLDOUT,
                    ADD_OBSERVED_REGRESSION_TEST,
                    ADD_SAME_CLASS_TEST_EVIDENCE,
                    RERUN_MODEL_TEST_ALIGNMENT,
                    MARK_RECURRING_FAMILY,
                    VALIDATE_FIX,
                    FINALIZE,
                ),
                ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("recurring_family_requires_defect_family_gate",),
                ),
                block=BrokenValidateRecurringWithoutDefectFamilyGate(),
            ),
        )
    )
    return correct, broken
'''

MODEL_MISS_REVIEW_RUN_CHECKS_TEMPLATE = '''"""Run the post-runtime model-miss review template."""

from model import run_checks


def main() -> int:
    correct, broken = run_checks()
    print(f"{correct.scenario_name}: {correct.status.upper()}")
    for item in correct.evidence:
        print(f"  - {item}")
    print()
    print(broken.format_text(max_counterexamples=2))
    return 0 if correct.ok and broken.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

MODEL_MISS_REVIEW_NOTES_TEMPLATE = """# FlowGuard Model-Miss Review Notes

Use this scaffold when real validation finds an issue after a FlowGuard pass.

## Review Questions

- Why did the earlier model miss this bug class?
- Was the boundary too narrow, the state too coarse, an input branch missing, an
  invariant weak, a replay skipped, or the issue outside the modeled scope?
- How is the issue now represented: scenario, invariant, replay adapter,
  representative trace, or explicit out-of-scope boundary?
- What same-class generalized bad case prevents a point-fix-only repair, and is
  that class represented or explicitly out of scope?
- How is the known bug used as validation or holdout evidence instead of the
  whole model target?
- Which observed-regression test and same-class generalized test evidence now
  prove the repaired obligation?
- Which Model-Test Alignment rows prove the new model obligations, owner code
  contracts, and same-class tests cover the same behavior?
- Has this same-class family appeared before, or is it high risk enough to
  require a defect-family gate rather than another ordinary bug fix?
- Which defect-family gate records the family id, authority boundary, observed
  failure, same-class generalized case, historical holdout, and current proof?
- Which refined model checks, runtime checks, and same-class tests must pass
  before completion?
- If the repair changed a child model under a parent ModelMesh, which parent
  reattachment gate consumed the new child evidence id?
- If same-class validation is large, slow, layered, background, or release-only,
  which TestMesh parent/child suite owns it and where is final result evidence?

Do not let a later green runtime check, one observed-bug regression test, or a
second local point fix close a known model miss by itself. Full closure needs
same-class test evidence, and recurring families need a defect-family gate or
an explicit scoped-confidence boundary.
Child-local green is not enough when parent mesh confidence depends on the
child's input/output/state/side-effect handoff.
"""

__all__ = [
    'MODEL_MISS_REVIEW_MODEL_TEMPLATE',
    'MODEL_MISS_REVIEW_RUN_CHECKS_TEMPLATE',
    'MODEL_MISS_REVIEW_NOTES_TEMPLATE',
]
