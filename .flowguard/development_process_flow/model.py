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
    spec_session_state: str = "closed"
    spec_begin_fingerprint: str = "sha256:current-inputs"
    spec_post_fingerprint: str = "sha256:current-inputs"
    spec_terminal_receipts: bool = True
    spec_provider_verified: bool = True


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
    spec_session_state: str = ""
    spec_begin_fingerprint: str = ""
    spec_post_fingerprint: str = ""
    spec_terminal_receipts: bool = False
    spec_provider_verified: bool = False

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
            and self.spec_session_state == "closed"
            and bool(self.spec_begin_fingerprint)
            and self.spec_begin_fingerprint == self.spec_post_fingerprint
            and self.spec_terminal_receipts
            and self.spec_provider_verified
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
                    spec_session_state=input_obj.spec_session_state,
                    spec_begin_fingerprint=input_obj.spec_begin_fingerprint,
                    spec_post_fingerprint=input_obj.spec_post_fingerprint,
                    spec_terminal_receipts=input_obj.spec_terminal_receipts,
                    spec_provider_verified=input_obj.spec_provider_verified,
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
    LifecycleAction("run_validation", spec_post_fingerprint=""),
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
    return exported


__all__ = [
    "EXTERNAL_INPUTS",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "LifecycleAction",
    "LifecycleOutput",
    "LifecycleState",
    "build_broken_workflow",
    "build_broken_plane_workflow",
    "build_correct_workflow",
    "export_contract_model",
    "initial_state",
    "terminal_predicate",
]
