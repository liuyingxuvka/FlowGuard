"""Template text for FlowGuard model miss review route."""

from __future__ import annotations

MODEL_MISS_REVIEW_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header.

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
- closing a recurring same-class miss without contributing exact affected
  relation and case identities to ContractExhaustion and ModelMaturation;
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
    affected_blueprint_gap_id: str = ""
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
    affected_canonical_relation_ids: tuple[str, ...] = ()
    affected_contract_case_ids: tuple[str, ...] = ()
    contract_exhaustion_contribution_emitted: bool = False
    model_maturation_contribution_emitted: bool = False
    fix_validated_after_refinement: bool = False
    completed: bool = False


@dataclass(frozen=True)
class Event:
    name: str
    affected_behavior_plane: str = ""
    affected_commitment_id: str = ""
    primary_owner_model_id: str = ""
    affected_blueprint_gap_id: str = ""
    affected_canonical_relation_ids: tuple[str, ...] = ()
    affected_contract_case_ids: tuple[str, ...] = ()
    same_plane_lookup_performed: bool = False
    coverage_gap_registered: bool = False


FLOWGUARD_PASS = Event("flowguard_pass")
RUNTIME_FAIL = Event("runtime_fail")
CLASSIFY_MISS = Event(
    "classify_miss",
    affected_behavior_plane="agent_operation",
    affected_commitment_id="commitment:flowguard-agent-guidance-route",
    primary_owner_model_id=".flowguard/minimum_valuable_model_entry/model.py",
    affected_blueprint_gap_id="blueprint-gap:model-miss-review:guidance-route",
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
EMIT_CONTRACT_EXHAUSTION_CONTRIBUTION = Event(
    "emit_contract_exhaustion_contribution",
    affected_canonical_relation_ids=("relation:shared-owner:model-miss-review",),
    affected_contract_case_ids=(
        "case:observed:model-miss-review",
        "case:same-class:model-miss-review",
    ),
)
EMIT_MODEL_MATURATION_CONTRIBUTION = Event("emit_model_maturation_contribution")
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
        "affected_blueprint_gap_id",
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
        "affected_canonical_relation_ids",
        "affected_contract_case_ids",
        "contract_exhaustion_contribution_emitted",
        "model_maturation_contribution_emitted",
        "fix_validated_after_refinement",
    )
    writes = (
        "flowguard_passed",
        "runtime_issue_observed",
        "model_miss_classified",
        "affected_behavior_plane",
        "affected_commitment_id",
        "primary_owner_model_id",
        "affected_blueprint_gap_id",
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
        "affected_canonical_relation_ids",
        "affected_contract_case_ids",
        "contract_exhaustion_contribution_emitted",
        "model_maturation_contribution_emitted",
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
            if not input_obj.affected_blueprint_gap_id:
                yield FunctionResult("classification_missing_blueprint_gap", state, label="blocked")
                return
            yield FunctionResult(
                "model_miss_classified",
                replace(
                    state,
                    model_miss_classified=True,
                    affected_behavior_plane=input_obj.affected_behavior_plane,
                    affected_commitment_id=input_obj.affected_commitment_id,
                    primary_owner_model_id=input_obj.primary_owner_model_id,
                    affected_blueprint_gap_id=input_obj.affected_blueprint_gap_id,
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
        if input_obj.name == "emit_contract_exhaustion_contribution":
            if not state.recurring_family_detected:
                yield FunctionResult("contract_exhaustion_contribution_not_required", state, label="blocked")
                return
            if state.generalized_bad_case_in_scope and not state.model_test_alignment_rerun:
                yield FunctionResult("contract_exhaustion_contribution_blocked", state, label="blocked")
                return
            if not state.affected_blueprint_gap_id:
                yield FunctionResult("contract_exhaustion_missing_blueprint_gap", state, label="blocked")
                return
            if not input_obj.affected_canonical_relation_ids:
                yield FunctionResult("contract_exhaustion_missing_canonical_relations", state, label="blocked")
                return
            if not input_obj.affected_contract_case_ids:
                yield FunctionResult("contract_exhaustion_missing_case_identities", state, label="blocked")
                return
            yield FunctionResult(
                "contract_exhaustion_contribution_emitted",
                replace(
                    state,
                    affected_canonical_relation_ids=input_obj.affected_canonical_relation_ids,
                    affected_contract_case_ids=input_obj.affected_contract_case_ids,
                    contract_exhaustion_contribution_emitted=True,
                ),
                label="contract_exhaustion_contribution_emitted",
            )
            return
        if input_obj.name == "emit_model_maturation_contribution":
            if not state.contract_exhaustion_contribution_emitted:
                yield FunctionResult("model_maturation_contribution_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "model_maturation_contribution_emitted",
                replace(state, model_maturation_contribution_emitted=True),
                label="model_maturation_contribution_emitted",
            )
            return
        if input_obj.name == "validate_fix":
            if not (
                state.same_plane_lookup_performed
                and state.affected_behavior_plane
                and state.affected_blueprint_gap_id
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
                state.contract_exhaustion_contribution_emitted
                and state.model_maturation_contribution_emitted
            ):
                yield FunctionResult("canonical_contribution_validation_blocked", state, label="blocked")
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
            if state.recurring_family_detected and not state.model_maturation_contribution_emitted:
                yield FunctionResult("finalize_blocked_open_model_maturation", state, label="finalize_blocked")
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


class BrokenValidateRecurringWithoutCanonicalContributions(ApplyReviewStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "validate_fix" and state.recurring_family_detected:
            yield FunctionResult(
                "recurring_family_validated_without_canonical_contributions",
                replace(state, fix_validated_after_refinement=True),
                label="broken_validate_recurring_without_canonical_contributions",
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
        if not state.affected_blueprint_gap_id:
            return InvariantResult.fail("model miss classification has no exact affected blueprint gap")
        return InvariantResult.pass_()

    def completion_requires_review(state: State, _trace) -> InvariantResult:
        if state.completed and state.runtime_issue_observed:
            if not (
                state.model_miss_classified
                and state.same_plane_lookup_performed
                and state.affected_behavior_plane
                and state.affected_blueprint_gap_id
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
                        state.affected_canonical_relation_ids
                        and state.affected_contract_case_ids
                        and state.contract_exhaustion_contribution_emitted
                        and state.model_maturation_contribution_emitted
                    )
                )
                and state.fix_validated_after_refinement
            ):
                return InvariantResult.fail(
                    "completed runtime issue without exact commitment/blueprint-gap classification, root-cause backpropagation, observed issue model representation, same-class generalized bad case representation, known-bug holdout role, owner code contract, target-aware replay evidence, same-class test evidence, legacy path disposition, Model-Test Alignment rerun, canonical ContractExhaustion and ModelMaturation contributions when needed, and refined validation"
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

    def recurring_family_requires_canonical_contributions(state: State, _trace) -> InvariantResult:
        if not (state.fix_validated_after_refinement and state.recurring_family_detected):
            return InvariantResult.pass_()
        if not state.affected_canonical_relation_ids:
            return InvariantResult.fail("recurring same-class miss has no affected canonical relation identities")
        if not state.affected_contract_case_ids:
            return InvariantResult.fail("recurring same-class miss has no affected ContractExhaustion case identities")
        if not state.contract_exhaustion_contribution_emitted:
            return InvariantResult.fail("recurring same-class miss validated before emitting a ContractExhaustion contribution")
        if not state.model_maturation_contribution_emitted:
            return InvariantResult.fail("recurring same-class miss validated before emitting a ModelMaturation contribution")
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
            "recurring_family_requires_canonical_contributions",
            "Recurring same-class misses contribute exact canonical relations/cases to ContractExhaustion and ModelMaturation before validation.",
            recurring_family_requires_canonical_contributions,
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
                EMIT_CONTRACT_EXHAUSTION_CONTRIBUTION,
                EMIT_MODEL_MATURATION_CONTRIBUTION,
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
                "validate_recurring_without_canonical_contributions",
                "Broken workflow closes a recurring same-class miss without contributing its exact relations and cases to the canonical owners.",
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
                    expected_violation_names=("recurring_family_requires_canonical_contributions",),
                ),
                block=BrokenValidateRecurringWithoutCanonicalContributions(),
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
    )'''

MODEL_MISS_REVIEW_RUN_CHECKS_TEMPLATE = '''"""Run the bug-repair/model-miss review template."""

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

Use this scaffold for non-trivial bug repairs and when real validation finds an
issue after a FlowGuard pass.

## Review Questions

- Why did the earlier model miss this bug class?
- Was there a previous green or broad-confidence claim? If yes, what was the
  previous claim id, observed failure, supported root cause, and
  `would_have_failed_if` condition?
- Which new plan, model, code-contract, or test item would have caught this
  bug class before the fix?
- Was the boundary too narrow, the state too coarse, an input branch missing, an
  invariant weak, a replay skipped, or the issue outside the modeled scope?
- Was a behavior-bearing field omitted, under-modeled, scoped out incorrectly,
  or left without FieldLifecycleMesh projection?
- How is the issue now represented: scenario, invariant, replay adapter,
  representative trace, or explicit out-of-scope boundary?
- What same-class family seed or finite boundary prevents a point-fix-only repair,
  and which ContractExhaustionMesh case ids represent it or explicitly scope it out?
- If this is a combination miss, which affected model ids, root-cause dimension
  ids, interaction group ids, generated combination case ids, and coverage
  receipt ids represent the wider bug class, and does the coverage universe now
  include those ids?
- How is the known bug used as validation or holdout evidence instead of the
  whole model target?
- Which observed-regression test and ContractExhaustionMesh case test evidence
  now prove the repaired obligation, and which ObservedProblemBackfeed row maps
  the real miss back to generated and same-class cases?
- If the miss produced a concrete counterexample or known-bad proof, which
  stable target id is replayed by current external owner-code
  `counterexample_regression` or `known_bad_replay` evidence?
- Which `root_cause_field_ids`, `same_class_field_ids`, and `old_field_ids`
  describe the field-level miss, and does FieldLifecycleMesh close their
  projection or disposition gaps?
- Which owner code contract implements the repaired behavior, and which
  Model-Test Alignment rows prove the model obligation, owner code contract,
  observed-regression test, and same-class test cover the same behavior?
- Are old, fallback, compatibility, or alternate paths still reachable? If yes,
  are they deleted, blocked, delegated to the repaired contract,
  same-contract repaired, or explicitly out of scope with a reason? Include old
  fields and aliases in the same disposition review.
- Has this same-class failure appeared before, and which exact affected
  commitment and blueprint-gap id receive the backfeed?
- Which canonical relation ids and ContractExhaustion case ids receive the
  bounded contribution, and which ModelMaturation contribution records the
  resulting increase in model depth?
- Which refined model checks, runtime checks, and contract-exhaustion cases must
  pass before completion?
- If the repair changed a child model under a parent ModelMesh, which parent
  reattachment gate consumed the new child evidence id, and which mesh closure
  transitions were rerun when child outputs or retry/rejection handoffs changed?
- If contract-exhaustion validation is large, slow, layered, background, or release-only,
  which TestMesh parent/child suite owns it and where is final result evidence?
- Which DevelopmentProcessFlow and Risk Evidence Ledger rows consume the final
  model/code/test/legacy-path evidence, and which later edits would stale them?

Do not let a later green runtime check, one observed-bug regression test, or a
second local point fix close a known model miss by itself. Full closure needs
root-cause backpropagation when there was a prior claim, FieldLifecycleMesh
projection for behavior-bearing fields, owner code contract binding,
ContractExhaustionMesh case evidence, old-path/old-field disposition for reachable old paths or
fields. Recurring or same-class closure additionally needs exact canonical
relation/case identities emitted to ContractExhaustion and a corresponding
ModelMaturation contribution.
Child-local green is not enough when parent mesh confidence depends on the
child's input/output/state/side-effect handoff.
"""

MODEL_MISS_REVIEW_FULL_MODEL_TEMPLATE = MODEL_MISS_REVIEW_MODEL_TEMPLATE
MODEL_MISS_REVIEW_FULL_RUN_CHECKS_TEMPLATE = MODEL_MISS_REVIEW_RUN_CHECKS_TEMPLATE
MODEL_MISS_REVIEW_FULL_NOTES_TEMPLATE = MODEL_MISS_REVIEW_NOTES_TEMPLATE

MODEL_MISS_REVIEW_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header.

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: compact model-miss repair review for one observed runtime/test miss.
Guards against: validating a point fix without root-cause model repair,
same-class test evidence, owner code contract binding, replay/negative
evidence, or UI promised-capability classification after a green claim.
Use before editing: non-trivial bug repairs after runtime, tests, replay, or
manual validation reveals a FlowGuard model miss.
Run: python .flowguard/model_miss_review/run_checks.py
Modeled block shape: Input x State -> Set(Output x State).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MissRepairPlan:
    plan_id: str
    runtime_issue_observed: bool
    model_miss_classified: bool
    root_cause_backpropagated: bool
    issue_represented_in_model: bool
    same_class_test_evidence_added: bool
    owner_code_contract_bound: bool
    replay_or_negative_check_added: bool
    fix_validated_after_refinement: bool
    completed: bool = False
    ui_capability_miss_observed: bool = False
    missing_promised_ui_capability_classified: bool = True
    same_class_ui_capability_scope_bound: bool = True
    behavior_lookup_performed: bool = False
    affected_behavior_plane: str = ""
    existing_commitment_reused_or_gap_registered: bool = False
    primary_owner_model_bound: bool = False
    error_signature_evidence_bound: bool = False
    typed_related_context_preserved: bool = True
    affected_blueprint_gap_id: str = ""
    affected_canonical_relation_ids: tuple[str, ...] = ()
    affected_contract_case_ids: tuple[str, ...] = ()
    contract_exhaustion_contribution_emitted: bool = False
    model_maturation_contribution_emitted: bool = False


@dataclass(frozen=True)
class MissRepairReport:
    scenario_name: str
    ok: bool
    findings: tuple[str, ...]


def review_compact_model_miss(plan: MissRepairPlan) -> MissRepairReport:
    findings: list[str] = []
    if not plan.runtime_issue_observed:
        findings.append("missing_runtime_issue_observed")
    if not plan.model_miss_classified:
        findings.append("missing_model_miss_classification")
    if not plan.root_cause_backpropagated:
        findings.append("missing_root_cause_backpropagation")
    if not plan.issue_represented_in_model:
        findings.append("missing_model_representation")
    if not plan.same_class_test_evidence_added:
        findings.append("missing_same_class_test_evidence")
    if not plan.owner_code_contract_bound:
        findings.append("missing_owner_code_contract")
    if not plan.replay_or_negative_check_added:
        findings.append("missing_replay_or_negative_check")
    if not plan.behavior_lookup_performed:
        findings.append("missing_same_plane_behavior_lookup")
    if plan.affected_behavior_plane not in {
        "product_runtime",
        "agent_operation",
        "development_process",
    }:
        findings.append("missing_or_invalid_affected_behavior_plane")
    if not plan.existing_commitment_reused_or_gap_registered:
        findings.append("existing_commitment_not_reused_and_gap_not_registered")
    if not plan.primary_owner_model_bound:
        findings.append("missing_primary_owner_model_binding")
    if not plan.error_signature_evidence_bound:
        findings.append("missing_error_signature_evidence_binding")
    if not plan.typed_related_context_preserved:
        findings.append("cross_plane_context_promoted_to_primary")
    if not plan.affected_blueprint_gap_id:
        findings.append("missing_affected_blueprint_gap")
    if not (plan.affected_canonical_relation_ids and plan.affected_contract_case_ids and plan.contract_exhaustion_contribution_emitted):
        findings.append("missing_contract_exhaustion_contribution")
    if not plan.model_maturation_contribution_emitted:
        findings.append("missing_model_maturation_contribution")
    if plan.ui_capability_miss_observed:
        if not plan.missing_promised_ui_capability_classified:
            findings.append("ui_promised_capability_miss_not_classified")
        if not plan.same_class_ui_capability_scope_bound:
            findings.append("missing_same_class_ui_capability_scope")
    if plan.fix_validated_after_refinement and findings:
        findings.append("fix_validation_requires_root_cause_backpropagation")
    if plan.completed and (findings or not plan.fix_validated_after_refinement):
        findings.append("completion_requires_refined_validation")
    return MissRepairReport(plan.plan_id, not findings and plan.completed, tuple(findings))


def correct_plan() -> MissRepairPlan:
    return MissRepairPlan(
        plan_id="correct_model_miss_review",
        runtime_issue_observed=True,
        model_miss_classified=True,
        root_cause_backpropagated=True,
        issue_represented_in_model=True,
        same_class_test_evidence_added=True,
        owner_code_contract_bound=True,
        replay_or_negative_check_added=True,
        fix_validated_after_refinement=True,
        completed=True,
        behavior_lookup_performed=True,
        affected_behavior_plane="agent_operation", existing_commitment_reused_or_gap_registered=True,
        primary_owner_model_bound=True, error_signature_evidence_bound=True,
        affected_blueprint_gap_id="blueprint-gap:model-miss-review:guidance-route",
        affected_canonical_relation_ids=("relation:shared-owner:model-miss-review",),
        affected_contract_case_ids=("case:observed:model-miss-review", "case:same-class:model-miss-review"),
        contract_exhaustion_contribution_emitted=True, model_maturation_contribution_emitted=True,
    )


def broken_plans() -> tuple[MissRepairPlan, ...]:
    return (
        MissRepairPlan("validate_without_root_cause_backpropagation", True, True, False, True, True, True, True, True, True),
        MissRepairPlan("point_fix_only_without_same_class_test", True, True, True, True, False, True, True, True, True),
        MissRepairPlan("validate_without_owner_code_contract", True, True, True, True, True, False, True, True, True),
        MissRepairPlan("validate_without_replay_or_negative_check", True, True, True, True, True, True, False, True, True),
        MissRepairPlan(
            "ui_promised_capability_missing_after_green_claim",
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            ui_capability_miss_observed=True,
            missing_promised_ui_capability_classified=False,
            same_class_ui_capability_scope_bound=False,
        ),
        MissRepairPlan("validate_without_behavior_lookup", True, True, True, True, True, True, True, True, True, affected_behavior_plane="agent_operation", existing_commitment_reused_or_gap_registered=True, primary_owner_model_bound=True, error_signature_evidence_bound=True),
        MissRepairPlan("cross_plane_context_used_as_primary", True, True, True, True, True, True, True, True, True, behavior_lookup_performed=True, affected_behavior_plane="agent_operation", existing_commitment_reused_or_gap_registered=True, primary_owner_model_bound=True, error_signature_evidence_bound=True, typed_related_context_preserved=False),
    )


def run_checks():
    correct = review_compact_model_miss(correct_plan())
    broken = tuple(review_compact_model_miss(plan) for plan in broken_plans())
    return correct, broken
'''

MODEL_MISS_REVIEW_RUN_CHECKS_TEMPLATE = '''"""Run the compact bug-repair/model-miss review template."""

from model import run_checks


def main() -> int:
    correct, broken = run_checks()
    print(f"{correct.scenario_name}: {'PASS' if correct.ok else 'FAIL'}")
    print("required gates: root_cause_backpropagated, affected_blueprint_gap_id, same_class_test_evidence_added, owner_code_contract_bound")
    print("behavior binding: same-plane lookup, existing-commitment reuse or registered gap, owner model, error evidence")
    print("required test/replay: replay_or_negative_check_added, target-aware known-bad/counterexample replay when present")
    print("canonical growth: contract_exhaustion_contribution_emitted, model_maturation_contribution_emitted")
    print(f"expected violations observed: {sum(not report.ok for report in broken)}")
    for report in broken:
        print(f"- {report.scenario_name}: {', '.join(report.findings)}")
    return 0 if correct.ok and all(not report.ok for report in broken) else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

MODEL_MISS_REVIEW_NOTES_TEMPLATE = """# FlowGuard Model-Miss Review Notes

This is the compact default scaffold for ordinary bug repair after runtime,
test, replay, or manual validation exposes a miss that earlier modeling did not
catch.

Default closure needs:

- observed runtime or validation issue;
- model-miss classification;
- root-cause backpropagation into the model;
- same-class test evidence, not only the observed regression;
- target-aware counterexample or known-bad replay evidence when a concrete
  trace/proof is in scope;
- owner code contract binding through Model-Test Alignment;
- replay or negative check evidence;
- validation after the refined model/checks.
- a lightweight behavior-ledger lookup that classifies the failed promise as
  `product_runtime`, `agent_operation`, or `development_process` before
  canonical relation lookup;
- reuse of an existing same-plane commitment and its primary owner model; only
  register a coverage gap when no matching promise exists;
- one exact affected blueprint-gap id for the missing or under-modeled
  behavior;
- exact affected canonical relation and ContractExhaustion case ids, followed
  by one ModelMaturation contribution;
- bounded error signatures tied to observed evidence, with cross-plane
  commitments retained only as typed related context rather than execution
  instructions;
- for UI misses where a promised function is absent, classify it as
  `boundary_missing` or `evidence_overclaimed`, record the affected capability
  ids, bind the finite same-class capability/control/field scope, and add current
  implementation or test evidence before closure.

Escalate to `model-miss-full-template` when the repair needs generalized bad
case modeling, known-bug holdout evidence, target-aware counterexample replay,
legacy path or old-field disposition, recurring canonical ContractExhaustion
and ModelMaturation contributions, parent/child ModelMesh reattachment and
closure, TestMesh ownership, or Risk
Evidence Ledger closure.

If old runtime paths or fields are still reachable, the full route should record
`legacy_path_disposition_recorded` evidence before broad completion.
"""

__all__ = [
    'MODEL_MISS_REVIEW_MODEL_TEMPLATE',
    'MODEL_MISS_REVIEW_RUN_CHECKS_TEMPLATE',
    'MODEL_MISS_REVIEW_NOTES_TEMPLATE',
    'MODEL_MISS_REVIEW_FULL_MODEL_TEMPLATE',
    'MODEL_MISS_REVIEW_FULL_RUN_CHECKS_TEMPLATE',
    'MODEL_MISS_REVIEW_FULL_NOTES_TEMPLATE',
]
