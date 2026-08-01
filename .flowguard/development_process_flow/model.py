"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Models the new development_process_flow route before implementation. The model
reviews whether lifecycle claims can reuse validation evidence after later
artifact or verifier changes, peer writes, and independent shadow/formal/
package/skill/Git synchronization boundaries.

Guards against:
- release or done claims that reuse stale validation evidence;
- validation evidence that remains current after code, requirement, or test
  verifier changes;
- background progress-only validation being treated as release evidence.
- one synchronization receipt being reused as proof for a different domain;
- a peer write being overwritten or ignored after evidence was produced.

Use before editing:
development lifecycle routing, process evidence freshness, V-style validation
pairs, template guidance, and release/readiness claim logic.

Run:
python .flowguard/development_process_flow/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.behavior_plane import (
    BCL_BEHAVIOR_PLANES,
    BCL_PLANE_DEVELOPMENT_PROCESS,
)


@dataclass(frozen=True)
class LifecycleAction:
    action_type: str
    behavior_plane: str = BCL_PLANE_DEVELOPMENT_PROCESS
    target_behavior_planes: tuple[str, ...] = ()
    target_commitment_ids: tuple[str, ...] = ()
    typed_commitment_relation_refs: tuple[str, ...] = ()
    spec_context_provider: str = "openspec"
    spec_context_read_only: bool = True
    spec_context_artifacts_current: bool = True
    spec_receipt_bridge_present: bool = False


@dataclass(frozen=True)
class LifecycleOutput:
    status: str


@dataclass(frozen=True)
class LifecycleState:
    requirement_version: int = 1
    code_version: int = 1
    test_version: int = 1
    evidence_status: str = "none"
    evidence_requirement_version: int = 0
    evidence_code_version: int = 0
    evidence_test_version: int = 0
    shadow_version: int = 1
    formal_version: int = 1
    package_version: int = 1
    skills_version: int = 1
    git_version: int = 1
    evidence_shadow_version: int = 0
    evidence_formal_version: int = 0
    evidence_package_version: int = 0
    evidence_skills_version: int = 0
    evidence_git_version: int = 0
    release_claim: str = "none"
    wrong_plane_action_accepted: bool = False
    spec_context_provider: str = ""
    spec_context_read_only: bool = False
    spec_context_artifacts_current: bool = False
    spec_receipt_bridge_present: bool = False

    def evidence_matches_current(self) -> bool:
        return (
            self.evidence_status == "current"
            and self.evidence_requirement_version == self.requirement_version
            and self.evidence_code_version == self.code_version
            and self.evidence_test_version == self.test_version
            and self.evidence_shadow_version == self.shadow_version
            and self.evidence_formal_version == self.formal_version
            and self.evidence_package_version == self.package_version
            and self.evidence_skills_version == self.skills_version
            and self.evidence_git_version == self.git_version
            and self.shadow_version == self.formal_version
            and self.formal_version == self.package_version
            and self.formal_version == self.skills_version
            and self.formal_version == self.git_version
            and self.spec_context_provider == "openspec"
            and self.spec_context_read_only
            and self.spec_context_artifacts_current
            and not self.spec_receipt_bridge_present
        )


def _stale_if_covering(state: LifecycleState, *, field: str) -> LifecycleState:
    if state.evidence_status != "current":
        return state
    covered = {
        "requirement_version": state.evidence_requirement_version,
        "code_version": state.evidence_code_version,
        "test_version": state.evidence_test_version,
        "shadow_version": state.evidence_shadow_version,
        "formal_version": state.evidence_formal_version,
        "package_version": state.evidence_package_version,
        "skills_version": state.evidence_skills_version,
        "git_version": state.evidence_git_version,
    }[field]
    current = getattr(state, field)
    if covered != current:
        return replace(state, evidence_status="stale")
    return state


class CorrectLifecycleGate:
    name = "CorrectLifecycleGate"
    reads = (
        "requirement_version",
        "code_version",
        "test_version",
        "evidence_status",
        "shadow_version",
        "formal_version",
        "package_version",
        "skills_version",
        "git_version",
        "release_claim",
        "wrong_plane_action_accepted",
    )
    writes = (
        "requirement_version",
        "code_version",
        "test_version",
        "evidence_status",
        "shadow_version",
        "formal_version",
        "package_version",
        "skills_version",
        "git_version",
        "release_claim",
        "wrong_plane_action_accepted",
    )
    accepted_input_type = LifecycleAction
    input_description = "development lifecycle action"
    output_description = "lifecycle state update or claim decision"
    idempotency = "Claims require evidence for the current artifact versions."

    def apply(self, input_obj: LifecycleAction, state: LifecycleState) -> Iterable[FunctionResult]:
        invalid_targets = tuple(
            plane for plane in input_obj.target_behavior_planes if plane not in BCL_BEHAVIOR_PLANES
        )
        cross_plane_targets = tuple(
            plane
            for plane in input_obj.target_behavior_planes
            if plane != BCL_PLANE_DEVELOPMENT_PROCESS
        )
        if input_obj.behavior_plane != BCL_PLANE_DEVELOPMENT_PROCESS or invalid_targets:
            yield FunctionResult(
                LifecycleOutput("plane_boundary_rejected"),
                state,
                label="plane_boundary_rejected",
            )
            return
        if cross_plane_targets and not (
            input_obj.target_commitment_ids and input_obj.typed_commitment_relation_refs
        ):
            yield FunctionResult(
                LifecycleOutput("cross_plane_target_unbound"),
                state,
                label="cross_plane_target_unbound",
            )
            return
        action = input_obj.action_type
        if action == "update_requirement":
            new_state = replace(state, requirement_version=state.requirement_version + 1)
            yield FunctionResult(
                LifecycleOutput("requirement_updated"),
                _stale_if_covering(new_state, field="requirement_version"),
                label="requirement_updated",
            )
            return
        if action == "update_code":
            new_state = replace(state, code_version=state.code_version + 1)
            yield FunctionResult(
                LifecycleOutput("code_updated"),
                _stale_if_covering(new_state, field="code_version"),
                label="code_updated",
            )
            return
        if action == "update_tests":
            new_state = replace(state, test_version=state.test_version + 1)
            yield FunctionResult(
                LifecycleOutput("tests_updated"),
                _stale_if_covering(new_state, field="test_version"),
                label="tests_updated",
            )
            return
        if action in {"update_shadow", "peer_write_shadow"}:
            new_state = replace(state, shadow_version=state.shadow_version + 1)
            yield FunctionResult(
                LifecycleOutput("peer_write_observed" if action == "peer_write_shadow" else "shadow_updated"),
                _stale_if_covering(new_state, field="shadow_version"),
                label="peer_write_observed" if action == "peer_write_shadow" else "shadow_updated",
            )
            return
        if action == "sync_formal":
            new_state = replace(state, formal_version=state.shadow_version)
            yield FunctionResult(
                LifecycleOutput("formal_synchronized"),
                _stale_if_covering(new_state, field="formal_version"),
                label="formal_synchronized",
            )
            return
        if action == "install_package":
            new_state = replace(state, package_version=state.formal_version)
            yield FunctionResult(
                LifecycleOutput("package_installed"),
                _stale_if_covering(new_state, field="package_version"),
                label="package_installed",
            )
            return
        if action == "install_skills":
            new_state = replace(state, skills_version=state.formal_version)
            yield FunctionResult(
                LifecycleOutput("skills_installed"),
                _stale_if_covering(new_state, field="skills_version"),
                label="skills_installed",
            )
            return
        if action == "commit_git":
            new_state = replace(state, git_version=state.formal_version)
            yield FunctionResult(
                LifecycleOutput("git_committed"),
                _stale_if_covering(new_state, field="git_version"),
                label="git_committed",
            )
            return
        if action == "run_validation":
            yield FunctionResult(
                LifecycleOutput("validation_passed"),
                replace(
                    state,
                    evidence_status="current",
                    evidence_requirement_version=state.requirement_version,
                    evidence_code_version=state.code_version,
                    evidence_test_version=state.test_version,
                    evidence_shadow_version=state.shadow_version,
                    evidence_formal_version=state.formal_version,
                    evidence_package_version=state.package_version,
                    evidence_skills_version=state.skills_version,
                    evidence_git_version=state.git_version,
                    spec_context_provider=input_obj.spec_context_provider,
                    spec_context_read_only=input_obj.spec_context_read_only,
                    spec_context_artifacts_current=(
                        input_obj.spec_context_artifacts_current
                    ),
                    spec_receipt_bridge_present=(
                        input_obj.spec_receipt_bridge_present
                    ),
                ),
                label="validation_passed",
            )
            return
        if action == "background_progress":
            yield FunctionResult(
                LifecycleOutput("validation_progress_only"),
                replace(state, evidence_status="progress_only"),
                label="validation_progress_only",
            )
            return
        if action == "fail_validation":
            yield FunctionResult(
                LifecycleOutput("validation_failed"),
                replace(state, evidence_status="failed"),
                label="validation_failed",
            )
            return
        if action == "claim_release":
            claim = "accepted" if state.evidence_matches_current() else "rejected"
            yield FunctionResult(
                LifecycleOutput(f"release_{claim}"),
                replace(state, release_claim=claim),
                label=f"release_{claim}",
            )


class BrokenNoFreshnessGate(CorrectLifecycleGate):
    name = "BrokenNoFreshnessGate"
    idempotency = "Broken variant accepts any prior pass, even after later changes."

    def apply(self, input_obj: LifecycleAction, state: LifecycleState) -> Iterable[FunctionResult]:
        action = input_obj.action_type
        if action == "update_requirement":
            yield FunctionResult(
                LifecycleOutput("requirement_updated"),
                replace(state, requirement_version=state.requirement_version + 1),
                label="requirement_updated",
            )
            return
        if action == "update_code":
            yield FunctionResult(
                LifecycleOutput("code_updated"),
                replace(state, code_version=state.code_version + 1),
                label="code_updated",
            )
            return
        if action == "update_tests":
            yield FunctionResult(
                LifecycleOutput("tests_updated"),
                replace(state, test_version=state.test_version + 1),
                label="tests_updated",
            )
            return
        if action in {"update_shadow", "peer_write_shadow"}:
            yield FunctionResult(
                LifecycleOutput("peer_write_observed" if action == "peer_write_shadow" else "shadow_updated"),
                replace(state, shadow_version=state.shadow_version + 1),
                label="peer_write_observed" if action == "peer_write_shadow" else "shadow_updated",
            )
            return
        if action == "sync_formal":
            yield FunctionResult(
                LifecycleOutput("formal_synchronized"),
                replace(state, formal_version=state.shadow_version),
                label="formal_synchronized",
            )
            return
        if action == "install_package":
            yield FunctionResult(
                LifecycleOutput("package_installed"),
                replace(state, package_version=state.formal_version),
                label="package_installed",
            )
            return
        if action == "install_skills":
            yield FunctionResult(
                LifecycleOutput("skills_installed"),
                replace(state, skills_version=state.formal_version),
                label="skills_installed",
            )
            return
        if action == "commit_git":
            yield FunctionResult(
                LifecycleOutput("git_committed"),
                replace(state, git_version=state.formal_version),
                label="git_committed",
            )
            return
        if action == "claim_release":
            claim = "accepted" if state.evidence_status in {"current", "progress_only"} else "rejected"
            yield FunctionResult(
                LifecycleOutput(f"release_{claim}"),
                replace(state, release_claim=claim),
                label=f"release_{claim}",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenNoPlaneBoundary(CorrectLifecycleGate):
    name = "BrokenNoPlaneBoundary"
    idempotency = "Broken variant accepts product or agent actions as development-process-owned work."

    def apply(self, input_obj: LifecycleAction, state: LifecycleState) -> Iterable[FunctionResult]:
        if input_obj.behavior_plane != BCL_PLANE_DEVELOPMENT_PROCESS:
            yield FunctionResult(
                LifecycleOutput("wrong_plane_action_accepted"),
                replace(state, wrong_plane_action_accepted=True),
                label="wrong_plane_action_accepted",
            )
            return
        yield from super().apply(input_obj, state)


@dataclass(frozen=True)
class AdmissionAction:
    action_type: str
    task_id: str = "task:model-first-upgrade"
    candidate_fingerprint: str = "sha256:candidate"
    coverage_fingerprint: str = "sha256:coverage"
    evidence_fingerprint: str = "sha256:evidence"
    maturation_decision: str = "closed_for_task"
    open_gap_ids: tuple[str, ...] = ()
    requested_scope_ids: tuple[str, ...] = ("scope:production-code",)
    authorization_current: bool = False
    authorization_task_id: str = ""
    authorization_candidate_fingerprint: str = ""
    authorization_coverage_fingerprint: str = ""
    authorization_evidence_fingerprint: str = ""
    authorization_allowed_scope_ids: tuple[str, ...] = ()
    authorization_accepted_gap_ids: tuple[str, ...] = ()
    read_only: bool = False


@dataclass(frozen=True)
class AdmissionOutput:
    status: str


@dataclass(frozen=True)
class AdmissionState:
    maturation_current: bool = False
    task_id: str = ""
    candidate_fingerprint: str = ""
    coverage_fingerprint: str = ""
    evidence_fingerprint: str = ""
    maturation_decision: str = "none"
    open_gap_ids: tuple[str, ...] = ()
    requested_scope_ids: tuple[str, ...] = ()
    authorization_exact: bool = False
    authorization_allowed_scope_ids: tuple[str, ...] = ()
    admission_status: str = "not_requested"

    def closed_for_task(self) -> bool:
        return (
            self.maturation_current
            and self.maturation_decision == "closed_for_task"
            and not self.open_gap_ids
        )


class CorrectImplementationAdmissionGate:
    name = "CorrectImplementationAdmissionGate"
    reads = (
        "maturation_current",
        "task_id",
        "candidate_fingerprint",
        "coverage_fingerprint",
        "evidence_fingerprint",
        "maturation_decision",
        "open_gap_ids",
        "requested_scope_ids",
        "authorization_exact",
        "authorization_allowed_scope_ids",
        "admission_status",
    )
    writes = reads
    accepted_input_type = AdmissionAction
    input_description = "task-level maturation evidence, implementation request, or scoped authorization"
    output_description = "ready, ready_scoped, blocked, or no_code_requested admission"
    idempotency = "Implementation admission is bound to the exact task, candidate, coverage, evidence, and scope."

    def apply(
        self, input_obj: AdmissionAction, state: AdmissionState
    ) -> Iterable[FunctionResult]:
        if input_obj.action_type == "consume_maturation":
            current = all(
                (
                    input_obj.task_id,
                    input_obj.candidate_fingerprint,
                    input_obj.coverage_fingerprint,
                    input_obj.evidence_fingerprint,
                )
            )
            yield FunctionResult(
                AdmissionOutput("maturation_consumed" if current else "maturation_rejected"),
                replace(
                    state,
                    maturation_current=current,
                    task_id=input_obj.task_id,
                    candidate_fingerprint=input_obj.candidate_fingerprint,
                    coverage_fingerprint=input_obj.coverage_fingerprint,
                    evidence_fingerprint=input_obj.evidence_fingerprint,
                    maturation_decision=input_obj.maturation_decision,
                    open_gap_ids=input_obj.open_gap_ids,
                ),
                label="maturation_consumed" if current else "maturation_rejected",
            )
            return
        if input_obj.action_type == "request_implementation":
            yield FunctionResult(
                AdmissionOutput("implementation_requested"),
                replace(state, requested_scope_ids=input_obj.requested_scope_ids),
                label="implementation_requested",
            )
            return
        if input_obj.action_type == "request_read_only":
            yield FunctionResult(
                AdmissionOutput("no_code_requested"),
                replace(state, admission_status="no_code_requested"),
                label="no_code_requested",
            )
            return
        if input_obj.action_type == "supply_authorization":
            exact = (
                input_obj.authorization_current
                and input_obj.authorization_task_id == state.task_id
                and input_obj.authorization_candidate_fingerprint
                == state.candidate_fingerprint
                and input_obj.authorization_coverage_fingerprint
                == state.coverage_fingerprint
                and input_obj.authorization_evidence_fingerprint
                == state.evidence_fingerprint
                and set(state.open_gap_ids).issubset(
                    set(input_obj.authorization_accepted_gap_ids)
                )
            )
            yield FunctionResult(
                AdmissionOutput("authorization_exact" if exact else "authorization_rejected"),
                replace(
                    state,
                    authorization_exact=exact,
                    authorization_allowed_scope_ids=input_obj.authorization_allowed_scope_ids,
                ),
                label="authorization_exact" if exact else "authorization_rejected",
            )
            return
        if input_obj.action_type == "decide_admission":
            requested = set(state.requested_scope_ids)
            allowed = set(state.authorization_allowed_scope_ids)
            if not requested:
                status = "no_code_requested"
            elif state.closed_for_task():
                status = "ready"
            elif state.authorization_exact and requested.issubset(allowed):
                status = "ready_scoped"
            else:
                status = "blocked"
            yield FunctionResult(
                AdmissionOutput(status),
                replace(state, admission_status=status),
                label=status,
            )


class BrokenAuthorizationAsConfidence(CorrectImplementationAdmissionGate):
    name = "BrokenAuthorizationAsConfidence"
    idempotency = "Broken variant lets any authorization erase maturation gaps and scope boundaries."

    def apply(
        self, input_obj: AdmissionAction, state: AdmissionState
    ) -> Iterable[FunctionResult]:
        if input_obj.action_type == "supply_authorization" and input_obj.authorization_current:
            yield FunctionResult(
                AdmissionOutput("authorization_exact"),
                replace(
                    state,
                    authorization_exact=True,
                    authorization_allowed_scope_ids=input_obj.authorization_allowed_scope_ids,
                ),
                label="authorization_exact",
            )
            return
        if input_obj.action_type == "decide_admission" and state.authorization_exact:
            yield FunctionResult(
                AdmissionOutput("ready"),
                replace(
                    state,
                    admission_status="ready",
                ),
                label="ready",
            )
            return
        yield from super().apply(input_obj, state)


def no_admission_without_task_sufficiency_or_exact_scope(
    state: AdmissionState, _trace
) -> InvariantResult:
    if state.admission_status == "ready" and not state.closed_for_task():
        return InvariantResult.fail(
            "unscoped implementation admitted without current closed-for-task maturation evidence"
        )
    if state.admission_status == "ready_scoped":
        if not state.authorization_exact:
            return InvariantResult.fail("scoped implementation admitted without exact authorization")
        if not set(state.requested_scope_ids).issubset(
            set(state.authorization_allowed_scope_ids)
        ):
            return InvariantResult.fail("scoped implementation exceeded authorized scope")
    return InvariantResult.pass_()


def authorization_does_not_rewrite_understanding(
    state: AdmissionState, _trace
) -> InvariantResult:
    if state.authorization_exact and state.maturation_decision == "closed_for_task" and state.open_gap_ids:
        return InvariantResult.fail(
            "implementation authorization rewrote an open model-maturation result as understood"
        )
    return InvariantResult.pass_()


ADMISSION_INVARIANTS = (
    Invariant(
        "no_admission_without_task_sufficiency_or_exact_scope",
        "Implementation needs closed task-level maturation or exact current scoped authorization.",
        no_admission_without_task_sufficiency_or_exact_scope,
    ),
    Invariant(
        "authorization_does_not_rewrite_understanding",
        "Authorization changes what may be attempted, never what the model evidence proved.",
        authorization_does_not_rewrite_understanding,
    ),
)


GOOD_CLOSED_ADMISSION_SEQUENCE = (
    AdmissionAction("consume_maturation"),
    AdmissionAction("request_implementation"),
    AdmissionAction("decide_admission"),
)

GOOD_SCOPED_ADMISSION_SEQUENCE = (
    AdmissionAction(
        "consume_maturation",
        maturation_decision="progress_stalled",
        open_gap_ids=("gap:external-contract",),
    ),
    AdmissionAction("request_implementation", requested_scope_ids=("scope:prototype",)),
    AdmissionAction(
        "supply_authorization",
        authorization_current=True,
        authorization_task_id="task:model-first-upgrade",
        authorization_candidate_fingerprint="sha256:candidate",
        authorization_coverage_fingerprint="sha256:coverage",
        authorization_evidence_fingerprint="sha256:evidence",
        authorization_allowed_scope_ids=("scope:prototype",),
        authorization_accepted_gap_ids=("gap:external-contract",),
    ),
    AdmissionAction("decide_admission"),
)

BROKEN_AUTHORIZATION_SEQUENCE = (
    AdmissionAction(
        "consume_maturation",
        maturation_decision="progress_stalled",
        open_gap_ids=("gap:external-contract",),
    ),
    AdmissionAction("request_implementation", requested_scope_ids=("scope:production-code",)),
    AdmissionAction(
        "supply_authorization",
        authorization_current=True,
        authorization_task_id="wrong-task",
        authorization_allowed_scope_ids=("scope:prototype",),
    ),
    AdmissionAction("decide_admission"),
)


def admission_initial_state() -> AdmissionState:
    return AdmissionState()


def build_admission_workflow(*, broken: bool = False) -> Workflow:
    gate = BrokenAuthorizationAsConfidence() if broken else CorrectImplementationAdmissionGate()
    return Workflow((gate,), name="implementation_admission")


def terminal_predicate(current_output, state, trace) -> bool:
    del state, trace
    return isinstance(current_output, LifecycleOutput) and current_output.status.startswith("release_")


def no_release_with_stale_or_incomplete_evidence(state: LifecycleState, trace) -> InvariantResult:
    last_label = trace.steps[-1].label if trace.steps else ""
    if last_label == "release_accepted" and not state.evidence_matches_current():
        return InvariantResult.fail(
            "release accepted without current evidence for requirement/code/test versions"
        )
    return InvariantResult.pass_()


def no_wrong_plane_action_accepted(state: LifecycleState, _trace) -> InvariantResult:
    if state.wrong_plane_action_accepted:
        return InvariantResult.fail(
            "development process accepted an agent-operation or product-runtime action as its own work"
        )
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "no_release_with_stale_or_incomplete_evidence",
        "Release claims require current validation evidence for all covered lifecycle artifacts.",
        no_release_with_stale_or_incomplete_evidence,
    ),
    Invariant(
        "development_process_owns_only_its_plane",
        "DevelopmentProcessFlow may reference other planes only as typed targets.",
        no_wrong_plane_action_accepted,
    ),
)

EXTERNAL_INPUTS = (
    LifecycleAction("run_validation"),
    LifecycleAction("update_code"),
    LifecycleAction("update_tests"),
    LifecycleAction("update_requirement"),
    LifecycleAction("update_shadow"),
    LifecycleAction("peer_write_shadow"),
    LifecycleAction("sync_formal"),
    LifecycleAction("install_package"),
    LifecycleAction("install_skills"),
    LifecycleAction("commit_git"),
    LifecycleAction("background_progress"),
    LifecycleAction("fail_validation"),
    LifecycleAction("claim_release"),
    LifecycleAction("update_code", behavior_plane="agent_operation"),
    LifecycleAction(
        "run_validation",
        target_behavior_planes=("product_runtime",),
    ),
    LifecycleAction("run_validation", spec_context_read_only=False),
)

MAX_SEQUENCE_LENGTH = 3


def initial_state() -> LifecycleState:
    return LifecycleState()


def build_correct_workflow() -> Workflow:
    return Workflow((CorrectLifecycleGate(),), name="development_process_flow_correct")


def build_broken_workflow() -> Workflow:
    return Workflow((BrokenNoFreshnessGate(),), name="development_process_flow_broken")


def build_broken_plane_workflow() -> Workflow:
    return Workflow((BrokenNoPlaneBoundary(),), name="development_process_flow_broken_plane")


from flowguard.skill_contract_model import build_skill_contract_model_export

FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"


def export_contract_model():
    exported = build_skill_contract_model_export(
        skill_id="flowguard-development-process-flow",
        route_id="development_process_flow",
        owner_id="development_process_flow",
        parent_model_id="flowguard.model_first_function_flow",
        business_intent="Order non-trivial development actions, keep ordinary work lightweight, conditionally select a hard-equivalent lower-rework process shape, and keep evidence current across diagnosis, root-cause repair, peer writes, install, and closure.",
        claim_boundary="This projection owns lifecycle order, conditional internal process optimization, and freshness, not product behavior, universal collect-all, global optimality, or future-agent compliance; unnecessary ceremony, a non-equivalent candidate, progress-only evidence, or uncovered affected revalidation cannot close the route.",
    )
    exported["invariant_ids"].append("invariant:process-strategy-equivalence")
    exported["obligations"].append(
        {
            "obligation_id": "obligation:flowguard-development-process-flow:process-strategy-equivalence",
            "invariant_id": "invariant:process-strategy-equivalence",
            "owner_step_ids": ["step:flowguard-development-process-flow:execute"],
            "required": True,
        }
    )
    for route_id, namespace, business_intent, claim_boundary in (
        (
            "plan_detailing_compiler",
            "flowguard-development-process-flow:plan-detailing",
            "Compile a rough non-trivial plan into plane-safe steps, gates, failure branches, and evidence requirements.",
            "This internal route structures a plan; it does not execute steps or absorb referenced product behavior.",
        ),
        (
            "agent_workflow_rehearsal",
            "flowguard-development-process-flow:agent-workflow",
            "Rehearse a selected AI-operation workflow while keeping product commitments as typed target context.",
            "This internal route rehearses agent-operation order and gates only; it does not own product runtime behavior.",
        ),
    ):
        internal = build_skill_contract_model_export(
            skill_id="flowguard-development-process-flow",
            route_id=route_id,
            owner_id="development_process_flow",
            parent_model_id=exported["model_id"],
            business_intent=business_intent,
            claim_boundary=claim_boundary,
        )
        default_step_prefix = "step:flowguard-development-process-flow"
        internal_step_prefix = f"step:{namespace}"
        default_obligation_prefix = "obligation:flowguard-development-process-flow"
        internal_obligation_prefix = f"obligation:{namespace}"
        for route in internal["routes"]:
            route["step_ids"] = [
                step_id.replace(default_step_prefix, internal_step_prefix, 1)
                for step_id in route["step_ids"]
            ]
            route["success_terminal_step_id"] = route["success_terminal_step_id"].replace(
                default_step_prefix, internal_step_prefix, 1
            )
            route["blocked_terminal_step_id"] = route["blocked_terminal_step_id"].replace(
                default_step_prefix, internal_step_prefix, 1
            )
        for step in internal["steps"]:
            step["step_id"] = step["step_id"].replace(
                default_step_prefix, internal_step_prefix, 1
            )
            step["prerequisite_step_ids"] = [
                step_id.replace(default_step_prefix, internal_step_prefix, 1)
                for step_id in step["prerequisite_step_ids"]
            ]
        for obligation in internal["obligations"]:
            obligation["obligation_id"] = obligation["obligation_id"].replace(
                default_obligation_prefix, internal_obligation_prefix, 1
            )
            obligation["owner_step_ids"] = [
                step_id.replace(default_step_prefix, internal_step_prefix, 1)
                for step_id in obligation["owner_step_ids"]
            ]
        exported["functions"].extend(internal["functions"])
        exported["routes"].extend(internal["routes"])
        exported["steps"].extend(internal["steps"])
        exported["obligations"].extend(internal["obligations"])
    function_ids = [str(item["function_id"]) for item in exported["functions"]]
    for function in exported["functions"]:
        function["composable_with"] = [
            function_id
            for function_id in function_ids
            if function_id != function["function_id"]
        ]
    return exported


__all__ = [
    "ADMISSION_INVARIANTS",
    "BROKEN_AUTHORIZATION_SEQUENCE",
    "EXTERNAL_INPUTS",
    "GOOD_CLOSED_ADMISSION_SEQUENCE",
    "GOOD_SCOPED_ADMISSION_SEQUENCE",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "AdmissionAction",
    "AdmissionState",
    "LifecycleAction",
    "LifecycleOutput",
    "LifecycleState",
    "admission_initial_state",
    "build_admission_workflow",
    "build_broken_workflow",
    "build_broken_plane_workflow",
    "build_correct_workflow",
    "export_contract_model",
    "initial_state",
    "terminal_predicate",
]
