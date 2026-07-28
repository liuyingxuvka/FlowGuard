"""FlowGuard model for direct field schema simplification.

FlowGuard Risk Purpose Header
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: review the breaking field-schema cleanup before implementation.
Modeled block shape: Input x State -> Set(Output x State).
Run: python .flowguard/simplify_field_schema/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.architecture_reduction import (
    CANDIDATE_REMOVE_BRANCH,
    PROOF_SAFE_BY_EQUIVALENCE,
    ROUTE_DEVELOPMENT_PROCESS_FLOW,
    TARGET_ACTION_REMOVE,
    ArchitectureReductionCandidate,
    ArchitectureReductionPlan,
    ObservableArchitectureContract,
    review_architecture_reduction,
)
from flowguard.development_process_flow import (
    PROCESS_ARTIFACT_CODE,
    PROCESS_ARTIFACT_DESIGN,
    PROCESS_ARTIFACT_MODEL,
    PROCESS_ARTIFACT_REQUIREMENT,
    PROCESS_ARTIFACT_TEST,
    PROCESS_EVIDENCE_PASSED,
    DevelopmentProcessPlan,
    ProcessAction,
    ProcessArtifact,
    ProcessEvidence,
    ValidationRequirement,
    review_development_process_flow,
)


@dataclass(frozen=True)
class FieldSchemaAction:
    action_type: str


@dataclass(frozen=True)
class FieldSchemaOutput:
    status: str


@dataclass(frozen=True)
class FieldSchemaState:
    openspec_valid: bool = False
    model_current: bool = False
    risk_gate_columns_removed: bool = False
    process_metrics_removed: bool = False
    plan_intake_duplicates_removed: bool = False
    duplicate_helpers_merged: bool = False
    legacy_fallbacks_removed: bool = False
    focused_tests_passed: bool = False
    broad_regression_passed: bool = False
    install_synced: bool = False
    shadow_sync_checked: bool = False
    git_boundary_checked: bool = False
    done_claim: str = "none"

    def ready_for_done(self) -> bool:
        return (
            self.openspec_valid
            and self.model_current
            and self.risk_gate_columns_removed
            and self.process_metrics_removed
            and self.plan_intake_duplicates_removed
            and self.duplicate_helpers_merged
            and self.legacy_fallbacks_removed
            and self.focused_tests_passed
            and self.broad_regression_passed
            and self.install_synced
            and self.shadow_sync_checked
            and self.git_boundary_checked
        )


class CorrectFieldSchemaCleanup:
    name = "CorrectFieldSchemaCleanup"
    reads = (
        "openspec_valid",
        "model_current",
        "risk_gate_columns_removed",
        "process_metrics_removed",
        "plan_intake_duplicates_removed",
        "duplicate_helpers_merged",
        "legacy_fallbacks_removed",
        "focused_tests_passed",
        "broad_regression_passed",
        "install_synced",
        "shadow_sync_checked",
        "git_boundary_checked",
        "done_claim",
    )
    writes = reads
    accepted_input_type = FieldSchemaAction
    input_description = "field-schema cleanup lifecycle action"
    output_description = "field-schema cleanup state or claim decision"
    idempotency = "Done claims require spec, model, deletion batches, tests, install sync, shadow sync, and git-boundary evidence."

    def apply(self, input_obj: FieldSchemaAction, state: FieldSchemaState) -> Iterable[FunctionResult]:
        action = input_obj.action_type
        if action == "validate_spec_and_model":
            yield FunctionResult(
                FieldSchemaOutput("spec_and_model_valid"),
                replace(state, openspec_valid=True, model_current=True),
                label="spec_and_model_valid",
            )
        elif action == "remove_field_surfaces":
            yield FunctionResult(
                FieldSchemaOutput("field_surfaces_removed"),
                replace(
                    state,
                    risk_gate_columns_removed=True,
                    process_metrics_removed=True,
                    plan_intake_duplicates_removed=True,
                    duplicate_helpers_merged=True,
                    legacy_fallbacks_removed=True,
                ),
                label="field_surfaces_removed",
            )
        elif action == "run_focused_tests":
            yield FunctionResult(
                FieldSchemaOutput("focused_tests_passed"),
                replace(state, focused_tests_passed=True),
                label="focused_tests_passed",
            )
        elif action == "run_broad_regression":
            yield FunctionResult(
                FieldSchemaOutput("broad_regression_passed"),
                replace(state, broad_regression_passed=True),
                label="broad_regression_passed",
            )
        elif action == "sync_and_check_boundaries":
            yield FunctionResult(
                FieldSchemaOutput("sync_boundaries_checked"),
                replace(state, install_synced=True, shadow_sync_checked=True, git_boundary_checked=True),
                label="sync_boundaries_checked",
            )
        elif action == "claim_done":
            claim = "accepted" if state.ready_for_done() else "rejected"
            yield FunctionResult(
                FieldSchemaOutput(f"done_{claim}"),
                replace(state, done_claim=claim),
                label=f"done_{claim}",
            )


class BrokenKeepsFallbackSurface(CorrectFieldSchemaCleanup):
    name = "BrokenKeepsFallbackSurface"
    idempotency = "Broken variant claims done while leaving legacy fallback fields in normal schemas."

    def apply(self, input_obj: FieldSchemaAction, state: FieldSchemaState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "remove_field_surfaces":
            yield FunctionResult(
                FieldSchemaOutput("field_surfaces_partly_removed"),
                replace(
                    state,
                    risk_gate_columns_removed=True,
                    process_metrics_removed=True,
                    plan_intake_duplicates_removed=True,
                    duplicate_helpers_merged=True,
                    legacy_fallbacks_removed=False,
                ),
                label="field_surfaces_partly_removed",
            )
            return
        if input_obj.action_type == "claim_done":
            claim = "accepted" if state.focused_tests_passed and state.install_synced else "rejected"
            yield FunctionResult(
                FieldSchemaOutput(f"done_{claim}"),
                replace(state, done_claim=claim),
                label=f"done_{claim}",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenSkipsBroadRegression(CorrectFieldSchemaCleanup):
    name = "BrokenSkipsBroadRegression"
    idempotency = "Broken variant treats focused route tests as enough for a breaking schema change."

    def apply(self, input_obj: FieldSchemaAction, state: FieldSchemaState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "claim_done":
            claim = (
                "accepted"
                if state.openspec_valid
                and state.model_current
                and state.risk_gate_columns_removed
                and state.process_metrics_removed
                and state.plan_intake_duplicates_removed
                and state.focused_tests_passed
                and state.install_synced
                else "rejected"
            )
            yield FunctionResult(
                FieldSchemaOutput(f"done_{claim}"),
                replace(state, done_claim=claim),
                label=f"done_{claim}",
            )
            return
        yield from super().apply(input_obj, state)


def initial_state() -> FieldSchemaState:
    return FieldSchemaState()


def terminal_predicate(current_output, state, trace) -> bool:
    del state, trace
    return isinstance(current_output, FieldSchemaOutput) and current_output.status.startswith("done_")


def no_done_without_complete_cleanup(state: FieldSchemaState, trace) -> InvariantResult:
    del trace
    if state.done_claim == "accepted" and not state.ready_for_done():
        return InvariantResult.fail(
            "done accepted before spec/model, deletion batches, focused tests, broad regression, install sync, shadow sync, and git-boundary evidence"
        )
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "no_done_without_complete_cleanup",
        "Breaking field schema cleanup cannot claim done until all deletion batches and validation/sync gates are complete.",
        no_done_without_complete_cleanup,
    ),
)

EXTERNAL_INPUTS = (
    FieldSchemaAction("validate_spec_and_model"),
    FieldSchemaAction("remove_field_surfaces"),
    FieldSchemaAction("run_focused_tests"),
    FieldSchemaAction("run_broad_regression"),
    FieldSchemaAction("sync_and_check_boundaries"),
    FieldSchemaAction("claim_done"),
)

MAX_SEQUENCE_LENGTH = 6


def build_correct_workflow() -> Workflow:
    return Workflow([CorrectFieldSchemaCleanup()])


def build_broken_fallback_workflow() -> Workflow:
    return Workflow([BrokenKeepsFallbackSurface()])


def build_broken_regression_workflow() -> Workflow:
    return Workflow([BrokenSkipsBroadRegression()])


def architecture_reduction_report():
    plan = ArchitectureReductionPlan(
        "direct-field-schema-contraction",
        observable_contract=ObservableArchitectureContract(
            source_model_id="simplify-field-schema",
            source_code_boundary_id="flowguard dataclass constructors and route reviewers",
            public_entrypoints=(
                "RiskEvidenceRow",
                "ProcessEvidence",
                "EvidenceAdapterMapping",
                "PlanIntakeCompletenessPlan",
                "UIResidualBlindspot",
            ),
            observable_outputs=(
                "route review findings",
                "public template examples",
                "to_dict JSON shapes",
            ),
            observable_state=(".flowguard model artifacts", "OpenSpec change artifacts"),
            observable_side_effects=("editable install sync", "shadow workspace sync"),
            validation_boundaries=(
                "tests/test_risk_evidence_ledger.py",
                "tests/test_development_process_flow.py",
                "tests/test_plan_intake_claims.py",
                "tests/test_ui_structure.py",
                "tests/test_public_templates.py",
                "tests/test_api_surface.py",
            ),
            rationale="The cleanup removes duplicate/derived fields while preserving route-visible review results.",
        ),
        candidates=(
            ArchitectureReductionCandidate(
                "risk-row-gate-clusters",
                candidate_type=CANDIDATE_REMOVE_BRANCH,
                code_node_id="RiskEvidenceRow route-specific gate fields",
                source_model_element="risk_evidence_ledger.RiskEvidenceRow",
                target_action=TARGET_ACTION_REMOVE,
                proof_status=PROOF_SAFE_BY_EQUIVALENCE,
                required_next_route=ROUTE_DEVELOPMENT_PROCESS_FLOW,
                rationale="All gate clusters share id/current/confidence/scoped-reason semantics and can be represented by one typed gate list.",
            ),
            ArchitectureReductionCandidate(
                "process-evidence-autosplit-fields",
                candidate_type=CANDIDATE_REMOVE_BRANCH,
                code_node_id="ProcessEvidence large-run metric and auto-split fields",
                source_model_element="development_process_flow.ProcessEvidence",
                target_action=TARGET_ACTION_REMOVE,
                proof_status=PROOF_SAFE_BY_EQUIVALENCE,
                required_next_route=ROUTE_DEVELOPMENT_PROCESS_FLOW,
                rationale="AutoSplit owns split analysis; process evidence owns process proof freshness.",
            ),
            ArchitectureReductionCandidate(
                "plan-intake-duplicate-evidence-shapes",
                candidate_type=CANDIDATE_REMOVE_BRANCH,
                code_node_id="PlanIntake singular/plural and strict adapter fixture fields",
                source_model_element="plan_intake.EvidenceAdapterMapping",
                target_action=TARGET_ACTION_REMOVE,
                proof_status=PROOF_SAFE_BY_EQUIVALENCE,
                required_next_route=ROUTE_DEVELOPMENT_PROCESS_FLOW,
                rationale="One mapping row should point to one mapped evidence id; fixture rejection belongs to tests.",
            ),
        ),
    )
    return review_architecture_reduction(plan)


def development_process_report():
    plan = DevelopmentProcessPlan(
        "simplify-field-schema-process",
        artifacts=(
            ProcessArtifact("openspec.simplify-field-schema", PROCESS_ARTIFACT_REQUIREMENT, "1"),
            ProcessArtifact("model.simplify-field-schema", PROCESS_ARTIFACT_MODEL, "1"),
            ProcessArtifact("code.field-schema", PROCESS_ARTIFACT_CODE, "1"),
            ProcessArtifact("tests.field-schema", PROCESS_ARTIFACT_TEST, "1"),
            ProcessArtifact("design.field-schema", PROCESS_ARTIFACT_DESIGN, "1"),
        ),
        actions=(
            ProcessAction("validate-openspec", produced_evidence_ids=("evidence:openspec",)),
            ProcessAction(
                "run-model",
                order_after=("validate-openspec",),
                produced_evidence_ids=("evidence:model",),
            ),
            ProcessAction(
                "edit-code-tests-docs",
                order_after=("run-model",),
                writes_artifacts=("code.field-schema", "tests.field-schema"),
            ),
            ProcessAction(
                "run-focused-tests",
                order_after=("edit-code-tests-docs",),
                produced_evidence_ids=("evidence:focused-tests",),
            ),
            ProcessAction(
                "run-broad-regression",
                order_after=("run-focused-tests",),
                produced_evidence_ids=("evidence:broad-regression",),
            ),
            ProcessAction(
                "sync-install-shadow",
                order_after=("run-broad-regression",),
                produced_evidence_ids=("evidence:sync",),
            ),
        ),
        evidence=(
            ProcessEvidence(
                "evidence:openspec",
                status=PROCESS_EVIDENCE_PASSED,
                produced_by_action_id="validate-openspec",
                covers_artifacts=("openspec.simplify-field-schema",),
                covered_versions={"openspec.simplify-field-schema": "1"},
            ),
            ProcessEvidence(
                "evidence:model",
                status=PROCESS_EVIDENCE_PASSED,
                produced_by_action_id="run-model",
                covers_artifacts=("model.simplify-field-schema",),
                covered_versions={"model.simplify-field-schema": "1"},
            ),
            ProcessEvidence(
                "evidence:focused-tests",
                status=PROCESS_EVIDENCE_PASSED,
                produced_by_action_id="run-focused-tests",
                covers_artifacts=("code.field-schema", "tests.field-schema"),
                covered_versions={"code.field-schema": "1", "tests.field-schema": "1"},
            ),
            ProcessEvidence(
                "evidence:broad-regression",
                status=PROCESS_EVIDENCE_PASSED,
                produced_by_action_id="run-broad-regression",
                covers_artifacts=("code.field-schema", "tests.field-schema"),
                covered_versions={"code.field-schema": "1", "tests.field-schema": "1"},
            ),
            ProcessEvidence(
                "evidence:sync",
                status=PROCESS_EVIDENCE_PASSED,
                produced_by_action_id="sync-install-shadow",
                covers_artifacts=("code.field-schema",),
                covered_versions={"code.field-schema": "1"},
            ),
        ),
        validation_requirements=(
            ValidationRequirement(
                "field-schema-focused-tests",
                required_artifact_ids=("code.field-schema", "tests.field-schema"),
                required_evidence_kinds=("test",),
                evidence_ids=("evidence:focused-tests",),
            ),
            ValidationRequirement(
                "field-schema-broad-regression",
                required_artifact_ids=("code.field-schema", "tests.field-schema"),
                required_evidence_kinds=("test",),
                evidence_ids=("evidence:broad-regression",),
            ),
        ),
    )
    return review_development_process_flow(plan)
