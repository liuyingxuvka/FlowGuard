"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Models the review loop required for a non-trivial bug repair, or when a
FlowGuard pass is followed by a test, runtime, replay, or manual-validation
failure.

Guards against:
- finalizing after a runtime issue without classifying the model miss;
- classifying a miss without first looking up the affected behavior plane;
- attaching a miss to a different plane's commitment or creating a duplicate
  gap when a same-plane commitment already exists;
- validating a fix before backpropagating the root cause into the prior
  plan/model/test gap;
- validating a fix before representing the observed issue in the model;
- validating a point fix before representing a same-class generalized bad case;
- validating only the observed bug without same-class test evidence;
- validating a known-bad or counterexample repair without target-aware
  owner-code replay evidence;
- validating without binding the repaired obligation to the owner code
  contract;
- leaving old, fallback, compatibility, or alternate paths reachable without a
  disposition;
- treating a recurring same-class miss as another ordinary point fix;
- using the known bug as the whole model target instead of holdout evidence;
- treating a later green runtime check as enough to close a known miss.

Use before editing:
non-trivial bug-fix, model-miss, runtime-validation, replay, or completion-gate
logic.

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
    affected_behavior_plane: str = ""
    affected_commitment_id: str = ""
    primary_owner_model_id: str = ""
    same_plane_lookup_performed: bool = False
    coverage_gap_registered: bool = False
    root_cause_backpropagated: bool = False
    issue_represented_in_model: bool = False
    generalized_bad_case_in_scope: bool = True
    generalized_bad_case_represented_in_model: bool = False
    known_bug_used_as_holdout: bool = False
    observed_regression_test_added: bool = False
    target_aware_replay_evidence_added: bool = False
    same_class_test_evidence_added: bool = False
    owner_code_contract_bound: bool = False
    model_test_alignment_rerun: bool = False
    legacy_path_disposition_in_scope: bool = True
    legacy_path_disposition_recorded: bool = False
    recurring_family_detected: bool = False
    defect_family_gate_promoted: bool = False
    defect_family_gate_reviewed: bool = False
    fix_validated_after_refinement: bool = False
    completed: bool = False


@dataclass(frozen=True)
class Event:
    name: str
    affected_behavior_plane: str = ""
    affected_commitment_id: str = ""
    primary_owner_model_id: str = ""
    same_plane_lookup_performed: bool = False
    coverage_gap_registered: bool = False


FLOWGUARD_PASS = Event("flowguard_pass")
RUNTIME_FAIL = Event("runtime_fail")
CLASSIFY_MISS = Event(
    "classify_miss",
    affected_behavior_plane="agent_operation",
    affected_commitment_id="commitment:flowguard-agent-guidance-route",
    primary_owner_model_id=".flowguard/minimum_valuable_model_entry/model.py",
    same_plane_lookup_performed=True,
)
BACKPROPAGATE_ROOT_CAUSE = Event("backpropagate_root_cause")
REPRESENT_ISSUE = Event("represent_issue")
REPRESENT_GENERALIZED_BAD_CASE = Event("represent_generalized_bad_case")
RECORD_KNOWN_BUG_HOLDOUT = Event("record_known_bug_holdout")
ADD_OBSERVED_REGRESSION_TEST = Event("add_observed_regression_test")
ADD_TARGET_AWARE_REPLAY_EVIDENCE = Event("add_target_aware_replay_evidence")
ADD_SAME_CLASS_TEST_EVIDENCE = Event("add_same_class_test_evidence")
BIND_OWNER_CODE_CONTRACT = Event("bind_owner_code_contract")
RERUN_MODEL_TEST_ALIGNMENT = Event("rerun_model_test_alignment")
RECORD_LEGACY_PATH_DISPOSITION = Event("record_legacy_path_disposition")
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
        "affected_behavior_plane",
        "affected_commitment_id",
        "primary_owner_model_id",
        "same_plane_lookup_performed",
        "coverage_gap_registered",
        "root_cause_backpropagated",
        "issue_represented_in_model",
        "generalized_bad_case_in_scope",
        "generalized_bad_case_represented_in_model",
        "known_bug_used_as_holdout",
        "observed_regression_test_added",
        "target_aware_replay_evidence_added",
        "same_class_test_evidence_added",
        "owner_code_contract_bound",
        "model_test_alignment_rerun",
        "legacy_path_disposition_in_scope",
        "legacy_path_disposition_recorded",
        "recurring_family_detected",
        "defect_family_gate_promoted",
        "defect_family_gate_reviewed",
        "fix_validated_after_refinement",
    )
    writes = (
        "flowguard_passed",
        "runtime_issue_observed",
        "model_miss_classified",
        "affected_behavior_plane",
        "affected_commitment_id",
        "primary_owner_model_id",
        "same_plane_lookup_performed",
        "coverage_gap_registered",
        "root_cause_backpropagated",
        "issue_represented_in_model",
        "generalized_bad_case_represented_in_model",
        "known_bug_used_as_holdout",
        "observed_regression_test_added",
        "target_aware_replay_evidence_added",
        "same_class_test_evidence_added",
        "owner_code_contract_bound",
        "model_test_alignment_rerun",
        "legacy_path_disposition_recorded",
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
            if input_obj.affected_behavior_plane not in {
                "product_runtime",
                "agent_operation",
                "development_process",
            }:
                yield FunctionResult("classification_missing_behavior_plane", state, label="blocked")
                return
            if not input_obj.same_plane_lookup_performed:
                yield FunctionResult("classification_missing_same_plane_lookup", state, label="blocked")
                return
            has_existing_owner = bool(
                input_obj.affected_commitment_id and input_obj.primary_owner_model_id
            )
            if not has_existing_owner and not input_obj.coverage_gap_registered:
                yield FunctionResult("classification_missing_owner_or_gap", state, label="blocked")
                return
            if has_existing_owner and input_obj.coverage_gap_registered:
                yield FunctionResult("classification_duplicate_gap", state, label="blocked")
                return
            yield FunctionResult(
                "model_miss_classified",
                replace(
                    state,
                    model_miss_classified=True,
                    affected_behavior_plane=input_obj.affected_behavior_plane,
                    affected_commitment_id=input_obj.affected_commitment_id,
                    primary_owner_model_id=input_obj.primary_owner_model_id,
                    same_plane_lookup_performed=True,
                    coverage_gap_registered=input_obj.coverage_gap_registered,
                ),
                label="model_miss_classified",
            )
            return
        if input_obj.name == "backpropagate_root_cause":
            if not state.model_miss_classified:
                yield FunctionResult("root_cause_backpropagation_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "root_cause_backpropagated",
                replace(state, root_cause_backpropagated=True),
                label="root_cause_backpropagated",
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
        if input_obj.name == "add_target_aware_replay_evidence":
            if not state.observed_regression_test_added:
                yield FunctionResult("target_aware_replay_evidence_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "target_aware_replay_evidence_added",
                replace(state, target_aware_replay_evidence_added=True),
                label="target_aware_replay_evidence_added",
            )
            return
        if input_obj.name == "add_same_class_test_evidence":
            if not state.target_aware_replay_evidence_added:
                yield FunctionResult("same_class_test_evidence_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "same_class_test_evidence_added",
                replace(state, same_class_test_evidence_added=True),
                label="same_class_test_evidence_added",
            )
            return
        if input_obj.name == "bind_owner_code_contract":
            if not state.same_class_test_evidence_added:
                yield FunctionResult("owner_code_contract_binding_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "owner_code_contract_bound",
                replace(state, owner_code_contract_bound=True),
                label="owner_code_contract_bound",
            )
            return
        if input_obj.name == "rerun_model_test_alignment":
            if not state.same_class_test_evidence_added:
                yield FunctionResult("model_test_alignment_blocked", state, label="blocked")
                return
            if not state.owner_code_contract_bound:
                yield FunctionResult("model_test_alignment_missing_owner_contract", state, label="blocked")
                return
            yield FunctionResult(
                "model_test_alignment_rerun",
                replace(state, model_test_alignment_rerun=True),
                label="model_test_alignment_rerun",
            )
            return
        if input_obj.name == "record_legacy_path_disposition":
            if not state.model_test_alignment_rerun:
                yield FunctionResult("legacy_path_disposition_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "legacy_path_disposition_recorded",
                replace(state, legacy_path_disposition_recorded=True),
                label="legacy_path_disposition_recorded",
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
            if not (
                state.same_plane_lookup_performed
                and state.affected_behavior_plane
                and (
                    (
                        state.affected_commitment_id
                        and state.primary_owner_model_id
                        and not state.coverage_gap_registered
                    )
                    or (
                        not state.affected_commitment_id
                        and not state.primary_owner_model_id
                        and state.coverage_gap_registered
                    )
                )
            ):
                yield FunctionResult("same_plane_backfeed_validation_blocked", state, label="blocked")
                return
            if not state.root_cause_backpropagated:
                yield FunctionResult("root_cause_backpropagation_validation_blocked", state, label="blocked")
                return
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
            if state.generalized_bad_case_in_scope and not state.target_aware_replay_evidence_added:
                yield FunctionResult("target_aware_replay_evidence_validation_blocked", state, label="blocked")
                return
            if state.generalized_bad_case_in_scope and not state.same_class_test_evidence_added:
                yield FunctionResult("same_class_test_evidence_validation_blocked", state, label="blocked")
                return
            if state.generalized_bad_case_in_scope and not state.owner_code_contract_bound:
                yield FunctionResult("owner_code_contract_validation_blocked", state, label="blocked")
                return
            if state.generalized_bad_case_in_scope and not state.model_test_alignment_rerun:
                yield FunctionResult("model_test_alignment_validation_blocked", state, label="blocked")
                return
            if state.legacy_path_disposition_in_scope and not state.legacy_path_disposition_recorded:
                yield FunctionResult("legacy_path_disposition_validation_blocked", state, label="blocked")
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


class BrokenClassifyWithoutSamePlaneLookup(ApplyReviewStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "classify_miss":
            yield FunctionResult(
                "classified_without_same_plane_lookup",
                replace(state, model_miss_classified=True),
                label="broken_classified_without_same_plane_lookup",
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


class BrokenValidateWithoutRootCauseBackpropagation(ApplyReviewStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "validate_fix" and state.issue_represented_in_model:
            yield FunctionResult(
                "validated_without_root_cause_backpropagation",
                replace(state, fix_validated_after_refinement=True),
                label="broken_validate_without_root_cause_backpropagation",
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


class BrokenValidateWithoutTargetAwareReplayEvidence(ApplyReviewStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "validate_fix" and state.observed_regression_test_added:
            yield FunctionResult(
                "validated_without_target_aware_replay_evidence",
                replace(
                    state,
                    same_class_test_evidence_added=True,
                    owner_code_contract_bound=True,
                    model_test_alignment_rerun=True,
                    legacy_path_disposition_recorded=True,
                    fix_validated_after_refinement=True,
                ),
                label="broken_validate_without_target_aware_replay_evidence",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenValidateWithoutOwnerCodeContract(ApplyReviewStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "validate_fix" and state.same_class_test_evidence_added:
            yield FunctionResult(
                "validated_without_owner_code_contract",
                replace(
                    state,
                    model_test_alignment_rerun=True,
                    legacy_path_disposition_recorded=True,
                    fix_validated_after_refinement=True,
                ),
                label="broken_validate_without_owner_code_contract",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenValidateWithoutLegacyPathDisposition(ApplyReviewStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "validate_fix" and state.model_test_alignment_rerun:
            yield FunctionResult(
                "validated_without_legacy_path_disposition",
                replace(state, fix_validated_after_refinement=True),
                label="broken_validate_without_legacy_path_disposition",
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
    def classification_requires_same_plane_backfeed(state: State, _trace) -> InvariantResult:
        if not state.model_miss_classified:
            return InvariantResult.pass_()
        if not state.same_plane_lookup_performed:
            return InvariantResult.fail("model miss classified before same-plane commitment lookup")
        if state.affected_behavior_plane not in {
            "product_runtime",
            "agent_operation",
            "development_process",
        }:
            return InvariantResult.fail("model miss classification has no valid affected behavior plane")
        has_existing_owner = bool(
            state.affected_commitment_id and state.primary_owner_model_id
        )
        if not has_existing_owner and not state.coverage_gap_registered:
            return InvariantResult.fail("model miss classification has neither a same-plane owner nor a registered gap")
        if has_existing_owner and state.coverage_gap_registered:
            return InvariantResult.fail("model miss classification duplicates a gap for an existing same-plane owner")
        return InvariantResult.pass_()

    def completion_requires_review(state: State, _trace) -> InvariantResult:
        if state.completed and state.runtime_issue_observed:
            if not (
                state.model_miss_classified
                and state.same_plane_lookup_performed
                and state.affected_behavior_plane
                and (
                    (
                        state.affected_commitment_id
                        and state.primary_owner_model_id
                        and not state.coverage_gap_registered
                    )
                    or (
                        not state.affected_commitment_id
                        and not state.primary_owner_model_id
                        and state.coverage_gap_registered
                    )
                )
                and state.root_cause_backpropagated
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
                        and state.target_aware_replay_evidence_added
                        and state.same_class_test_evidence_added
                        and state.owner_code_contract_bound
                        and state.model_test_alignment_rerun
                    )
                )
                and (
                    not state.legacy_path_disposition_in_scope
                    or state.legacy_path_disposition_recorded
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
                    "completed runtime issue without classification, root-cause backpropagation, observed issue model representation, same-class generalized bad case representation, known-bug holdout role, owner code contract, target-aware replay evidence, same-class test evidence, legacy path disposition, Model-Test Alignment rerun, recurring defect-family gate when needed, and refined validation"
                )
        return InvariantResult.pass_()

    def fix_validation_requires_root_cause_backpropagation(state: State, _trace) -> InvariantResult:
        if state.fix_validated_after_refinement and not state.root_cause_backpropagated:
            return InvariantResult.fail("fix validated before root cause was backpropagated into the prior plan/model/test gap")
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

    def fix_validation_requires_target_aware_replay_evidence(state: State, _trace) -> InvariantResult:
        if (
            state.fix_validated_after_refinement
            and state.generalized_bad_case_in_scope
            and not state.target_aware_replay_evidence_added
        ):
            return InvariantResult.fail("fix validated before adding target-aware counterexample/known-bad replay evidence")
        return InvariantResult.pass_()

    def fix_validation_requires_owner_code_contract(state: State, _trace) -> InvariantResult:
        if (
            state.fix_validated_after_refinement
            and state.generalized_bad_case_in_scope
            and not state.owner_code_contract_bound
        ):
            return InvariantResult.fail("fix validated before binding the repaired obligation to the owner code contract")
        return InvariantResult.pass_()

    def fix_validation_requires_legacy_path_disposition(state: State, _trace) -> InvariantResult:
        if (
            state.fix_validated_after_refinement
            and state.legacy_path_disposition_in_scope
            and not state.legacy_path_disposition_recorded
        ):
            return InvariantResult.fail("fix validated before recording legacy, fallback, or compatibility path disposition")
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
        Invariant(
            "classification_requires_same_plane_backfeed",
            "Model-miss classification first reuses a same-plane commitment or registers a real same-plane gap.",
            classification_requires_same_plane_backfeed,
        ),
        Invariant("completion_requires_review", "Runtime issues must be reviewed before completion.", completion_requires_review),
        Invariant(
            "fix_validation_requires_root_cause_backpropagation",
            "Fix validation requires root-cause backpropagation into the plan/model/test gap.",
            fix_validation_requires_root_cause_backpropagation,
        ),
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
            "fix_validation_requires_target_aware_replay_evidence",
            "Fix validation requires target-aware counterexample or known-bad replay evidence.",
            fix_validation_requires_target_aware_replay_evidence,
        ),
        Invariant(
            "fix_validation_requires_owner_code_contract",
            "Fix validation requires the owner code contract for the repaired obligation.",
            fix_validation_requires_owner_code_contract,
        ),
        Invariant(
            "fix_validation_requires_legacy_path_disposition",
            "Fix validation requires reachable old/fallback path disposition.",
            fix_validation_requires_legacy_path_disposition,
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
                BACKPROPAGATE_ROOT_CAUSE,
                REPRESENT_ISSUE,
                REPRESENT_GENERALIZED_BAD_CASE,
                RECORD_KNOWN_BUG_HOLDOUT,
                ADD_OBSERVED_REGRESSION_TEST,
                ADD_TARGET_AWARE_REPLAY_EVIDENCE,
                ADD_SAME_CLASS_TEST_EVIDENCE,
                BIND_OWNER_CODE_CONTRACT,
                RERUN_MODEL_TEST_ALIGNMENT,
                RECORD_LEGACY_PATH_DISPOSITION,
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
                "classify_without_same_plane_lookup",
                "Broken workflow labels a miss but does not look up the affected plane's existing commitment.",
                (FLOWGUARD_PASS, RUNTIME_FAIL, CLASSIFY_MISS),
                ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("classification_requires_same_plane_backfeed",),
                ),
                block=BrokenClassifyWithoutSamePlaneLookup(),
            ),
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
                (FLOWGUARD_PASS, RUNTIME_FAIL, CLASSIFY_MISS, BACKPROPAGATE_ROOT_CAUSE, VALIDATE_FIX, FINALIZE),
                ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("fix_validation_requires_model_representation",),
                ),
                block=BrokenValidateFixWithoutRepresentation(),
            ),
            scenario(
                "validate_without_root_cause_backpropagation",
                "Broken workflow validates the fix before backpropagating the root cause.",
                (FLOWGUARD_PASS, RUNTIME_FAIL, CLASSIFY_MISS, REPRESENT_ISSUE, VALIDATE_FIX, FINALIZE),
                ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("fix_validation_requires_root_cause_backpropagation",),
                ),
                block=BrokenValidateWithoutRootCauseBackpropagation(),
            ),
            scenario(
                "point_fix_only_without_generalized_bad_case",
                "Broken workflow validates only the observed issue and misses a same-class generalized bad case.",
                (FLOWGUARD_PASS, RUNTIME_FAIL, CLASSIFY_MISS, BACKPROPAGATE_ROOT_CAUSE, REPRESENT_ISSUE, VALIDATE_FIX, FINALIZE),
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
                    BACKPROPAGATE_ROOT_CAUSE,
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
                "validate_without_target_aware_replay_evidence",
                "Broken workflow has a known-bad proof but does not replay that target through owner code.",
                (
                    FLOWGUARD_PASS,
                    RUNTIME_FAIL,
                    CLASSIFY_MISS,
                    BACKPROPAGATE_ROOT_CAUSE,
                    REPRESENT_ISSUE,
                    REPRESENT_GENERALIZED_BAD_CASE,
                    RECORD_KNOWN_BUG_HOLDOUT,
                    ADD_OBSERVED_REGRESSION_TEST,
                    VALIDATE_FIX,
                    FINALIZE,
                ),
                ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("fix_validation_requires_target_aware_replay_evidence",),
                ),
                block=BrokenValidateWithoutTargetAwareReplayEvidence(),
            ),
            scenario(
                "validate_without_same_class_test_evidence",
                "Broken workflow models the class but only validates the observed bug.",
                (
                    FLOWGUARD_PASS,
                    RUNTIME_FAIL,
                    CLASSIFY_MISS,
                    BACKPROPAGATE_ROOT_CAUSE,
                    REPRESENT_ISSUE,
                    REPRESENT_GENERALIZED_BAD_CASE,
                    RECORD_KNOWN_BUG_HOLDOUT,
                    ADD_OBSERVED_REGRESSION_TEST,
                    ADD_TARGET_AWARE_REPLAY_EVIDENCE,
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
                "validate_without_owner_code_contract",
                "Broken workflow has model and tests but no owner code contract binding.",
                (
                    FLOWGUARD_PASS,
                    RUNTIME_FAIL,
                    CLASSIFY_MISS,
                    BACKPROPAGATE_ROOT_CAUSE,
                    REPRESENT_ISSUE,
                    REPRESENT_GENERALIZED_BAD_CASE,
                    RECORD_KNOWN_BUG_HOLDOUT,
                    ADD_OBSERVED_REGRESSION_TEST,
                    ADD_TARGET_AWARE_REPLAY_EVIDENCE,
                    ADD_SAME_CLASS_TEST_EVIDENCE,
                    VALIDATE_FIX,
                    FINALIZE,
                ),
                ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("fix_validation_requires_owner_code_contract",),
                ),
                block=BrokenValidateWithoutOwnerCodeContract(),
            ),
            scenario(
                "validate_without_legacy_path_disposition",
                "Broken workflow leaves the old or fallback path reachable without disposition.",
                (
                    FLOWGUARD_PASS,
                    RUNTIME_FAIL,
                    CLASSIFY_MISS,
                    BACKPROPAGATE_ROOT_CAUSE,
                    REPRESENT_ISSUE,
                    REPRESENT_GENERALIZED_BAD_CASE,
                    RECORD_KNOWN_BUG_HOLDOUT,
                    ADD_OBSERVED_REGRESSION_TEST,
                    ADD_TARGET_AWARE_REPLAY_EVIDENCE,
                    ADD_SAME_CLASS_TEST_EVIDENCE,
                    BIND_OWNER_CODE_CONTRACT,
                    RERUN_MODEL_TEST_ALIGNMENT,
                    VALIDATE_FIX,
                    FINALIZE,
                ),
                ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("fix_validation_requires_legacy_path_disposition",),
                ),
                block=BrokenValidateWithoutLegacyPathDisposition(),
            ),
            scenario(
                "validate_recurring_without_defect_family_gate",
                "Broken workflow treats a recurring same-class miss as another ordinary point fix.",
                (
                    FLOWGUARD_PASS,
                    RUNTIME_FAIL,
                    CLASSIFY_MISS,
                    BACKPROPAGATE_ROOT_CAUSE,
                    REPRESENT_ISSUE,
                    REPRESENT_GENERALIZED_BAD_CASE,
                    RECORD_KNOWN_BUG_HOLDOUT,
                    ADD_OBSERVED_REGRESSION_TEST,
                    ADD_TARGET_AWARE_REPLAY_EVIDENCE,
                    ADD_SAME_CLASS_TEST_EVIDENCE,
                    BIND_OWNER_CODE_CONTRACT,
                    RERUN_MODEL_TEST_ALIGNMENT,
                    RECORD_LEGACY_PATH_DISPOSITION,
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


from flowguard.skill_contract_model import build_skill_contract_model_export

FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"


def export_contract_model():
    return build_skill_contract_model_export(
        skill_id="flowguard-model-miss-review",
        route_id="model_miss_review",
        owner_id="model_miss_review",
        parent_model_id="flowguard.model_first_function_flow",
        business_intent="Backfeed observed failures to an existing same-plane commitment or register a real coverage gap.",
        claim_boundary="This projection binds miss classification and backfeed; a proposed fix remains unproven until owner code, tests, replay, and disposition evidence are current.",
    )
