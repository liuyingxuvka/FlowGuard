"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Models the development_process_flow route before implementation. The model
reviews whether lifecycle claims can reuse validation evidence after later
artifact or verifier changes and keeps source, consumer projection, installed
package, installed skill, model authority, OpenSpec, Git commit, tag, and
GitHub Release as independent currentness identities.

Guards against:
- release or done claims that reuse stale validation evidence;
- validation evidence that remains current after code, requirement, or test
  verifier changes;
- background progress-only validation being treated as release evidence.
- one synchronization or publication identity being reused as proof for a
  different domain;
- a peer write being overwritten or ignored after evidence was produced.
- a tag or GitHub Release substituting for a stale source, consumer, install,
  model-authority, OpenSpec, or Git-commit identity.
- repeated full observation or semantic verification being treated as useful
  release work when one invocation-local observation plus one final identity
  freshness check is sufficient;
- per-leaf source-current rebuilds or receipt-store scans after a shared final
  observation, instead of one batch receipt reconciliation;
- an installed consumer projection being treated as author source material;
- author-shadow synchronization writing outside its exact owned paths,
  overwriting peer content, using stale source fingerprints, or leaving a
  partial activation visible after failure.

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
    validation_observation_scope: str = "invocation_local"
    validation_complete_observation_count: int = 2
    validation_semantic_verification_count: int = 1
    validation_final_identity_freshness_passed: bool = True
    validation_per_leaf_source_current_rebuild_count: int = 0
    validation_per_leaf_receipt_store_scan_count: int = 0
    validation_receipt_reconciliation_count: int = 1


@dataclass(frozen=True)
class LifecycleOutput:
    status: str


@dataclass(frozen=True)
class LifecycleState:
    requirement_version: int = 1
    code_version: int = 1
    test_version: int = 1
    source_version: int = 1
    consumer_projection_version: int = 1
    installed_package_version: int = 1
    installed_skill_version: int = 1
    model_authority_version: int = 1
    openspec_version: int = 1
    git_commit_version: int = 0
    tag_version: int = 0
    github_release_version: int = 0
    evidence_status: str = "none"
    evidence_requirement_version: int = 0
    evidence_code_version: int = 0
    evidence_test_version: int = 0
    evidence_source_version: int = 0
    evidence_consumer_projection_version: int = 0
    evidence_installed_package_version: int = 0
    evidence_installed_skill_version: int = 0
    evidence_model_authority_version: int = 0
    evidence_openspec_version: int = 0
    release_claim: str = "none"
    wrong_plane_action_accepted: bool = False
    spec_context_provider: str = ""
    spec_context_read_only: bool = False
    spec_context_artifacts_current: bool = False
    spec_receipt_bridge_present: bool = False
    validation_observation_scope: str = ""
    validation_complete_observation_count: int = 0
    validation_semantic_verification_count: int = 0
    validation_final_identity_freshness_passed: bool = False
    validation_per_leaf_source_current_rebuild_count: int = 0
    validation_per_leaf_receipt_store_scan_count: int = 0
    validation_receipt_reconciliation_count: int = 0

    def pre_release_identities_current(self) -> bool:
        return (
            self.source_version > 0
            and self.consumer_projection_version == self.source_version
            and self.installed_package_version == self.source_version
            and self.installed_skill_version == self.consumer_projection_version
            and self.model_authority_version == self.source_version
            and self.openspec_version == self.source_version
        )

    def evidence_matches_current(self) -> bool:
        return (
            self.evidence_status == "current"
            and self.evidence_requirement_version == self.requirement_version
            and self.evidence_code_version == self.code_version
            and self.evidence_test_version == self.test_version
            and self.evidence_source_version == self.source_version
            and self.evidence_consumer_projection_version
            == self.consumer_projection_version
            and self.evidence_installed_package_version
            == self.installed_package_version
            and self.evidence_installed_skill_version
            == self.installed_skill_version
            and self.evidence_model_authority_version
            == self.model_authority_version
            and self.evidence_openspec_version == self.openspec_version
            and self.pre_release_identities_current()
            and self.spec_context_provider == "openspec"
            and self.spec_context_read_only
            and self.spec_context_artifacts_current
            and not self.spec_receipt_bridge_present
            and self.validation_observation_scope == "invocation_local"
            and self.validation_complete_observation_count == 2
            and self.validation_semantic_verification_count == 1
            and self.validation_final_identity_freshness_passed
            and self.validation_per_leaf_source_current_rebuild_count == 0
            and self.validation_per_leaf_receipt_store_scan_count == 0
            and self.validation_receipt_reconciliation_count == 1
        )

    def publication_identities_current(self) -> bool:
        return (
            self.git_commit_version == self.source_version
            and self.tag_version == self.git_commit_version
            and self.github_release_version == self.tag_version
            and self.github_release_version > 0
        )

    def release_ready(self) -> bool:
        return self.evidence_matches_current() and self.publication_identities_current()


def _stale_after_pre_release_change(state: LifecycleState) -> LifecycleState:
    if state.evidence_status == "current":
        return replace(state, evidence_status="stale")
    return state


class CorrectLifecycleGate:
    name = "CorrectLifecycleGate"
    reads = (
        "requirement_version",
        "code_version",
        "test_version",
        "source_version",
        "consumer_projection_version",
        "installed_package_version",
        "installed_skill_version",
        "model_authority_version",
        "openspec_version",
        "git_commit_version",
        "tag_version",
        "github_release_version",
        "evidence_status",
        "release_claim",
        "wrong_plane_action_accepted",
        "validation_observation_scope",
        "validation_complete_observation_count",
        "validation_semantic_verification_count",
        "validation_final_identity_freshness_passed",
        "validation_per_leaf_source_current_rebuild_count",
        "validation_per_leaf_receipt_store_scan_count",
        "validation_receipt_reconciliation_count",
    )
    writes = (
        "requirement_version",
        "code_version",
        "test_version",
        "source_version",
        "consumer_projection_version",
        "installed_package_version",
        "installed_skill_version",
        "model_authority_version",
        "openspec_version",
        "git_commit_version",
        "tag_version",
        "github_release_version",
        "evidence_status",
        "release_claim",
        "wrong_plane_action_accepted",
        "validation_observation_scope",
        "validation_complete_observation_count",
        "validation_semantic_verification_count",
        "validation_final_identity_freshness_passed",
        "validation_per_leaf_source_current_rebuild_count",
        "validation_per_leaf_receipt_store_scan_count",
        "validation_receipt_reconciliation_count",
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
            new_state = replace(
                state,
                requirement_version=state.requirement_version + 1,
                source_version=state.source_version + 1,
            )
            yield FunctionResult(
                LifecycleOutput("requirement_updated"),
                _stale_after_pre_release_change(new_state),
                label="requirement_updated",
            )
            return
        if action == "update_code":
            new_state = replace(
                state,
                code_version=state.code_version + 1,
                source_version=state.source_version + 1,
            )
            yield FunctionResult(
                LifecycleOutput("code_updated"),
                _stale_after_pre_release_change(new_state),
                label="code_updated",
            )
            return
        if action == "update_tests":
            new_state = replace(
                state,
                test_version=state.test_version + 1,
                source_version=state.source_version + 1,
            )
            yield FunctionResult(
                LifecycleOutput("tests_updated"),
                _stale_after_pre_release_change(new_state),
                label="tests_updated",
            )
            return
        if action in {"update_source", "peer_write_source"}:
            new_state = replace(state, source_version=state.source_version + 1)
            yield FunctionResult(
                LifecycleOutput(
                    "peer_write_observed" if action == "peer_write_source" else "source_updated"
                ),
                _stale_after_pre_release_change(new_state),
                label=(
                    "peer_write_observed" if action == "peer_write_source" else "source_updated"
                ),
            )
            return
        if action == "project_consumer":
            new_state = replace(
                state,
                consumer_projection_version=state.source_version,
            )
            yield FunctionResult(
                LifecycleOutput("consumer_projection_current"),
                _stale_after_pre_release_change(new_state),
                label="consumer_projection_current",
            )
            return
        if action == "install_package":
            new_state = replace(
                state,
                installed_package_version=state.source_version,
            )
            yield FunctionResult(
                LifecycleOutput("package_installed"),
                _stale_after_pre_release_change(new_state),
                label="package_installed",
            )
            return
        if action == "install_skills":
            new_state = replace(
                state,
                installed_skill_version=state.consumer_projection_version,
            )
            yield FunctionResult(
                LifecycleOutput("skills_installed"),
                _stale_after_pre_release_change(new_state),
                label="skills_installed",
            )
            return
        if action == "accept_model_authority":
            new_state = replace(state, model_authority_version=state.source_version)
            yield FunctionResult(
                LifecycleOutput("model_authority_current"),
                _stale_after_pre_release_change(new_state),
                label="model_authority_current",
            )
            return
        if action == "sync_openspec":
            new_state = replace(state, openspec_version=state.source_version)
            yield FunctionResult(
                LifecycleOutput("openspec_current"),
                _stale_after_pre_release_change(new_state),
                label="openspec_current",
            )
            return
        substitution_fields = {
            "substitute_consumer_projection": "consumer_projection_version",
            "substitute_installed_package": "installed_package_version",
            "substitute_installed_skill": "installed_skill_version",
            "substitute_model_authority": "model_authority_version",
            "substitute_openspec": "openspec_version",
        }
        if action in substitution_fields:
            field = substitution_fields[action]
            new_state = replace(state, **{field: state.source_version + 1})
            yield FunctionResult(
                LifecycleOutput(action),
                _stale_after_pre_release_change(new_state),
                label=action,
            )
            return
        if action == "commit_git":
            yield FunctionResult(
                LifecycleOutput("git_committed"),
                replace(state, git_commit_version=state.source_version),
                label="git_committed",
            )
            return
        if action == "create_tag":
            yield FunctionResult(
                LifecycleOutput("tag_created"),
                replace(state, tag_version=state.git_commit_version),
                label="tag_created",
            )
            return
        if action == "publish_github_release":
            yield FunctionResult(
                LifecycleOutput("github_release_published"),
                replace(state, github_release_version=state.tag_version),
                label="github_release_published",
            )
            return
        publication_substitutions = {
            "substitute_git_commit": (
                "git_commit_version",
                state.source_version + 1,
            ),
            "substitute_tag": ("tag_version", state.git_commit_version + 1),
            "substitute_github_release": (
                "github_release_version",
                state.tag_version + 1,
            ),
        }
        if action in publication_substitutions:
            field, value = publication_substitutions[action]
            yield FunctionResult(
                LifecycleOutput(action),
                replace(state, **{field: value}),
                label=action,
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
                    evidence_source_version=state.source_version,
                    evidence_consumer_projection_version=(
                        state.consumer_projection_version
                    ),
                    evidence_installed_package_version=(
                        state.installed_package_version
                    ),
                    evidence_installed_skill_version=(
                        state.installed_skill_version
                    ),
                    evidence_model_authority_version=(
                        state.model_authority_version
                    ),
                    evidence_openspec_version=state.openspec_version,
                    spec_context_provider=input_obj.spec_context_provider,
                    spec_context_read_only=input_obj.spec_context_read_only,
                    spec_context_artifacts_current=(
                        input_obj.spec_context_artifacts_current
                    ),
                    spec_receipt_bridge_present=(
                        input_obj.spec_receipt_bridge_present
                    ),
                    validation_observation_scope=(
                        input_obj.validation_observation_scope
                    ),
                    validation_complete_observation_count=(
                        input_obj.validation_complete_observation_count
                    ),
                    validation_semantic_verification_count=(
                        input_obj.validation_semantic_verification_count
                    ),
                    validation_final_identity_freshness_passed=(
                        input_obj.validation_final_identity_freshness_passed
                    ),
                    validation_per_leaf_source_current_rebuild_count=(
                        input_obj.validation_per_leaf_source_current_rebuild_count
                    ),
                    validation_per_leaf_receipt_store_scan_count=(
                        input_obj.validation_per_leaf_receipt_store_scan_count
                    ),
                    validation_receipt_reconciliation_count=(
                        input_obj.validation_receipt_reconciliation_count
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
            claim = "accepted" if state.release_ready() else "rejected"
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
        if action == "claim_release":
            claim = "accepted" if state.evidence_status in {"current", "progress_only"} else "rejected"
            yield FunctionResult(
                LifecycleOutput(f"release_{claim}"),
                replace(state, release_claim=claim),
                label=f"release_{claim}",
            )
            return
        for result in super().apply(input_obj, state):
            if action not in {"run_validation", "background_progress", "fail_validation"}:
                yield FunctionResult(
                    result.output,
                    replace(result.new_state, evidence_status=state.evidence_status),
                    label=result.label,
                    reason=result.reason,
                    metadata=result.metadata,
                )
                continue
            yield result


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


AUTHOR_SYNC_ROLE_AUTHOR_SOURCE = "author_source"
AUTHOR_SYNC_ROLE_CONSUMER_DISTRIBUTION = "consumer_distribution"
AUTHOR_SYNC_PROJECTION_ID = "projection:author-source"
AUTHOR_SYNC_CURRENT_RAW_FINGERPRINT = "sha256:" + "a" * 64
AUTHOR_SYNC_CURRENT_SEMANTIC_FINGERPRINT = "sha256:" + "b" * 64
AUTHOR_SYNC_STALE_RAW_FINGERPRINT = "sha256:" + "c" * 64
AUTHOR_SYNC_OWNED_PATH_IDS = (
    "owned:skill-author-file",
    "owned:author-ownership-manifest",
)


@dataclass(frozen=True)
class AuthorSyncAction:
    action_type: str
    source_role: str = AUTHOR_SYNC_ROLE_AUTHOR_SOURCE
    target_role_before: str = AUTHOR_SYNC_ROLE_CONSUMER_DISTRIBUTION
    target_role_after: str = AUTHOR_SYNC_ROLE_AUTHOR_SOURCE
    projection_id: str = AUTHOR_SYNC_PROJECTION_ID
    frozen_raw_fingerprint: str = AUTHOR_SYNC_CURRENT_RAW_FINGERPRINT
    frozen_semantic_fingerprint: str = AUTHOR_SYNC_CURRENT_SEMANTIC_FINGERPRINT
    current_raw_fingerprint: str = AUTHOR_SYNC_CURRENT_RAW_FINGERPRINT
    current_semantic_fingerprint: str = AUTHOR_SYNC_CURRENT_SEMANTIC_FINGERPRINT
    target_raw_fingerprint: str = AUTHOR_SYNC_CURRENT_RAW_FINGERPRINT
    target_semantic_fingerprint: str = AUTHOR_SYNC_CURRENT_SEMANTIC_FINGERPRINT
    owned_path_ids: tuple[str, ...] = AUTHOR_SYNC_OWNED_PATH_IDS
    attempted_path_ids: tuple[str, ...] = AUTHOR_SYNC_OWNED_PATH_IDS
    modified_owned_path_ids: tuple[str, ...] = ()
    peer_paths_preserved: bool = True
    activation_succeeds: bool = True
    rollback_succeeds: bool = True
    partial_write_visible: bool = False
    manifest_written_last: bool = True


@dataclass(frozen=True)
class AuthorSyncOutput:
    status: str


@dataclass(frozen=True)
class AuthorSyncState:
    transaction_status: str = "not_started"
    claim: str = "none"
    source_role: str = ""
    target_role_before: str = ""
    target_role_after: str = ""
    projection_id: str = ""
    frozen_raw_fingerprint: str = ""
    frozen_semantic_fingerprint: str = ""
    current_raw_fingerprint: str = ""
    current_semantic_fingerprint: str = ""
    target_raw_fingerprint: str = ""
    target_semantic_fingerprint: str = ""
    owned_path_ids: tuple[str, ...] = ()
    attempted_path_ids: tuple[str, ...] = ()
    modified_owned_path_ids: tuple[str, ...] = ()
    peer_paths_preserved: bool = True
    activation_succeeded: bool = False
    rollback_status: str = "not_needed"
    target_restored: bool = True
    partial_write_visible: bool = False
    manifest_written_last: bool = False

    def source_fingerprint_is_current(self) -> bool:
        return (
            self.frozen_raw_fingerprint == self.current_raw_fingerprint
            and self.frozen_semantic_fingerprint
            == self.current_semantic_fingerprint
            and self.target_raw_fingerprint == self.frozen_raw_fingerprint
            and self.target_semantic_fingerprint
            == self.frozen_semantic_fingerprint
        )

    def writes_only_owned_paths(self) -> bool:
        return (
            set(self.attempted_path_ids).issubset(set(self.owned_path_ids))
            and not self.modified_owned_path_ids
            and self.peer_paths_preserved
        )

    def author_projection_is_current(self) -> bool:
        return (
            self.transaction_status == "activated"
            and self.source_role == AUTHOR_SYNC_ROLE_AUTHOR_SOURCE
            and self.target_role_before
            in {
                AUTHOR_SYNC_ROLE_CONSUMER_DISTRIBUTION,
                AUTHOR_SYNC_ROLE_AUTHOR_SOURCE,
            }
            and self.target_role_after == AUTHOR_SYNC_ROLE_AUTHOR_SOURCE
            and self.projection_id == AUTHOR_SYNC_PROJECTION_ID
            and self.source_fingerprint_is_current()
            and self.writes_only_owned_paths()
            and self.activation_succeeded
            and not self.partial_write_visible
            and self.manifest_written_last
        )


def _author_sync_state(
    action: AuthorSyncAction,
    *,
    transaction_status: str,
    claim: str,
    activation_succeeded: bool,
    rollback_status: str,
    target_restored: bool,
    partial_write_visible: bool,
) -> AuthorSyncState:
    return AuthorSyncState(
        transaction_status=transaction_status,
        claim=claim,
        source_role=action.source_role,
        target_role_before=action.target_role_before,
        target_role_after=action.target_role_after,
        projection_id=action.projection_id,
        frozen_raw_fingerprint=action.frozen_raw_fingerprint,
        frozen_semantic_fingerprint=action.frozen_semantic_fingerprint,
        current_raw_fingerprint=action.current_raw_fingerprint,
        current_semantic_fingerprint=action.current_semantic_fingerprint,
        target_raw_fingerprint=action.target_raw_fingerprint,
        target_semantic_fingerprint=action.target_semantic_fingerprint,
        owned_path_ids=action.owned_path_ids,
        attempted_path_ids=action.attempted_path_ids,
        modified_owned_path_ids=action.modified_owned_path_ids,
        peer_paths_preserved=action.peer_paths_preserved,
        activation_succeeded=activation_succeeded,
        rollback_status=rollback_status,
        target_restored=target_restored,
        partial_write_visible=partial_write_visible,
        manifest_written_last=action.manifest_written_last,
    )


class CorrectAuthorShadowSyncGate:
    name = "CorrectAuthorShadowSyncGate"
    reads = ("transaction_status", "claim")
    writes = (
        "transaction_status",
        "claim",
        "source_role",
        "target_role_after",
        "projection_id",
        "current_raw_fingerprint",
        "current_semantic_fingerprint",
        "attempted_path_ids",
        "activation_succeeded",
        "rollback_status",
        "target_restored",
        "partial_write_visible",
    )
    accepted_input_type = AuthorSyncAction
    input_description = "one frozen author skill shadow synchronization transaction"
    output_description = "activated, rolled-back, or rejected author projection"
    idempotency = (
        "Only exact current author source may atomically replace its frozen owned paths."
    )

    def apply(
        self,
        input_obj: AuthorSyncAction,
        _state: AuthorSyncState,
    ) -> Iterable[FunctionResult]:
        if input_obj.action_type != "sync":
            yield FunctionResult(
                AuthorSyncOutput("author_sync_rejected"),
                AuthorSyncState(transaction_status="not_started", claim="rejected"),
                label="author_sync_rejected",
            )
            return
        candidate = _author_sync_state(
            input_obj,
            transaction_status="candidate",
            claim="none",
            activation_succeeded=input_obj.activation_succeeds,
            rollback_status="not_needed",
            target_restored=False,
            partial_write_visible=input_obj.partial_write_visible,
        )
        role_current = (
            candidate.source_role == AUTHOR_SYNC_ROLE_AUTHOR_SOURCE
            and candidate.target_role_before
            in {
                AUTHOR_SYNC_ROLE_CONSUMER_DISTRIBUTION,
                AUTHOR_SYNC_ROLE_AUTHOR_SOURCE,
            }
            and candidate.target_role_after == AUTHOR_SYNC_ROLE_AUTHOR_SOURCE
            and candidate.projection_id == AUTHOR_SYNC_PROJECTION_ID
        )
        preconditions_current = (
            role_current
            and candidate.source_fingerprint_is_current()
            and candidate.writes_only_owned_paths()
        )
        if (
            preconditions_current
            and input_obj.activation_succeeds
            and not input_obj.partial_write_visible
            and input_obj.manifest_written_last
        ):
            accepted = replace(
                candidate,
                transaction_status="activated",
                claim="accepted",
                activation_succeeded=True,
            )
            yield FunctionResult(
                AuthorSyncOutput("author_sync_accepted"),
                accepted,
                label="author_sync_accepted",
            )
            return
        if preconditions_current and not input_obj.activation_succeeds:
            if input_obj.rollback_succeeds:
                rolled_back = replace(
                    candidate,
                    transaction_status="rolled_back",
                    claim="rejected",
                    activation_succeeded=False,
                    rollback_status="restored",
                    target_restored=True,
                    partial_write_visible=False,
                )
                yield FunctionResult(
                    AuthorSyncOutput("author_sync_rolled_back"),
                    rolled_back,
                    label="author_sync_rolled_back",
                )
                return
            rejected = replace(
                candidate,
                transaction_status="rollback_failed",
                claim="rejected",
                activation_succeeded=False,
                rollback_status="failed",
                target_restored=False,
            )
            yield FunctionResult(
                AuthorSyncOutput("author_sync_rejected"),
                rejected,
                label="author_sync_rejected",
            )
            return
        rejected = replace(
            candidate,
            transaction_status="not_started",
            claim="rejected",
            activation_succeeded=False,
            rollback_status="not_needed",
            target_restored=True,
            partial_write_visible=False,
        )
        yield FunctionResult(
            AuthorSyncOutput("author_sync_rejected"),
            rejected,
            label="author_sync_rejected",
        )


class BrokenAuthorShadowSyncGate(CorrectAuthorShadowSyncGate):
    name = "BrokenAuthorShadowSyncGate"
    idempotency = (
        "Broken variant treats any attempted consumer, stale, unowned, or partial transaction as author-current."
    )

    def apply(
        self,
        input_obj: AuthorSyncAction,
        _state: AuthorSyncState,
    ) -> Iterable[FunctionResult]:
        if input_obj.activation_succeeds:
            transaction_status = "activated"
            rollback_status = "not_needed"
            target_restored = False
        elif input_obj.rollback_succeeds:
            transaction_status = "rolled_back"
            rollback_status = "restored"
            target_restored = True
        else:
            transaction_status = "rollback_failed"
            rollback_status = "failed"
            target_restored = False
        yield FunctionResult(
            AuthorSyncOutput("author_sync_accepted"),
            _author_sync_state(
                input_obj,
                transaction_status=transaction_status,
                claim="accepted",
                activation_succeeded=input_obj.activation_succeeds,
                rollback_status=rollback_status,
                target_restored=target_restored,
                partial_write_visible=input_obj.partial_write_visible,
            ),
            label="author_sync_accepted",
        )


def author_sync_requires_author_source_role(
    state: AuthorSyncState,
    _trace,
) -> InvariantResult:
    if state.claim == "accepted" and (
        state.source_role != AUTHOR_SYNC_ROLE_AUTHOR_SOURCE
        or state.target_role_before
        not in {
            AUTHOR_SYNC_ROLE_CONSUMER_DISTRIBUTION,
            AUTHOR_SYNC_ROLE_AUTHOR_SOURCE,
        }
        or state.target_role_after != AUTHOR_SYNC_ROLE_AUTHOR_SOURCE
        or state.projection_id != AUTHOR_SYNC_PROJECTION_ID
    ):
        return InvariantResult.fail(
            "consumer distribution or a wrong projection identity was accepted as author source"
        )
    return InvariantResult.pass_()


def author_sync_preserves_unowned_paths(
    state: AuthorSyncState,
    _trace,
) -> InvariantResult:
    if state.claim == "accepted" and (
        not set(state.attempted_path_ids).issubset(set(state.owned_path_ids))
        or not state.peer_paths_preserved
    ):
        return InvariantResult.fail(
            "author synchronization modified an unowned or peer-owned shadow path"
        )
    return InvariantResult.pass_()


def author_sync_preserves_modified_owned_peer_content(
    state: AuthorSyncState,
    _trace,
) -> InvariantResult:
    if state.claim == "accepted" and state.modified_owned_path_ids:
        return InvariantResult.fail(
            "author synchronization overwrote a currently modified owned path without exact ownership"
        )
    return InvariantResult.pass_()


def author_sync_failure_is_atomic(
    state: AuthorSyncState,
    _trace,
) -> InvariantResult:
    if state.claim == "accepted" and (
        not state.activation_succeeded
        or state.partial_write_visible
        or not state.manifest_written_last
    ):
        return InvariantResult.fail(
            "failed or partially ordered author activation was accepted without exact rollback"
        )
    return InvariantResult.pass_()


def author_sync_requires_current_source_fingerprint(
    state: AuthorSyncState,
    _trace,
) -> InvariantResult:
    if state.claim == "accepted" and not state.source_fingerprint_is_current():
        return InvariantResult.fail(
            "author synchronization accepted stale source or mismatched target fingerprints"
        )
    return InvariantResult.pass_()


AUTHOR_SYNC_INVARIANTS = (
    Invariant(
        "author_sync_requires_author_source_role",
        "Only current author-source material may create projection:author-source.",
        author_sync_requires_author_source_role,
    ),
    Invariant(
        "author_sync_preserves_unowned_paths",
        "Author synchronization writes only the frozen owned-path set and preserves peer paths.",
        author_sync_preserves_unowned_paths,
    ),
    Invariant(
        "author_sync_preserves_modified_owned_peer_content",
        "A peer-modified owned file blocks replacement until exact ownership is current.",
        author_sync_preserves_modified_owned_peer_content,
    ),
    Invariant(
        "author_sync_failure_is_atomic",
        "Activation failure restores the previous target completely; the ownership manifest is written last.",
        author_sync_failure_is_atomic,
    ),
    Invariant(
        "author_sync_requires_current_source_fingerprint",
        "Frozen raw and semantic source fingerprints must remain current through target post-verification.",
        author_sync_requires_current_source_fingerprint,
    ),
)


GOOD_AUTHOR_SYNC_SEQUENCE = (AuthorSyncAction("sync"),)

GOOD_AUTHOR_SYNC_ROLLBACK_SEQUENCE = (
    AuthorSyncAction(
        "sync",
        activation_succeeds=False,
        rollback_succeeds=True,
        partial_write_visible=True,
    ),
)

AUTHOR_SYNC_FAILURE_CASES = (
    (
        "consumer_projection_as_author",
        "author-sync:consumer-projection-as-author",
        "author_sync_requires_author_source_role",
        (
            AuthorSyncAction(
                "sync",
                source_role=AUTHOR_SYNC_ROLE_CONSUMER_DISTRIBUTION,
            ),
        ),
    ),
    (
        "unowned_shadow_path_write",
        "author-sync:unowned-shadow-path-write",
        "author_sync_preserves_unowned_paths",
        (
            AuthorSyncAction(
                "sync",
                attempted_path_ids=(
                    *AUTHOR_SYNC_OWNED_PATH_IDS,
                    "unowned:other-ai-work",
                ),
                peer_paths_preserved=False,
            ),
        ),
    ),
    (
        "modified_owned_peer_content_overwrite",
        "author-sync:modified-owned-peer-content-overwrite",
        "author_sync_preserves_modified_owned_peer_content",
        (
            AuthorSyncAction(
                "sync",
                modified_owned_path_ids=("owned:skill-author-file",),
            ),
        ),
    ),
    (
        "partial_failure_without_rollback",
        "author-sync:partial-failure-without-rollback",
        "author_sync_failure_is_atomic",
        (
            AuthorSyncAction(
                "sync",
                activation_succeeds=False,
                rollback_succeeds=False,
                partial_write_visible=True,
            ),
        ),
    ),
    (
        "stale_source_fingerprint",
        "author-sync:stale-source-fingerprint",
        "author_sync_requires_current_source_fingerprint",
        (
            AuthorSyncAction(
                "sync",
                current_raw_fingerprint=AUTHOR_SYNC_STALE_RAW_FINGERPRINT,
            ),
        ),
    ),
)


def author_sync_initial_state() -> AuthorSyncState:
    return AuthorSyncState()


def build_author_sync_workflow(*, broken: bool = False) -> Workflow:
    gate = BrokenAuthorShadowSyncGate() if broken else CorrectAuthorShadowSyncGate()
    return Workflow((gate,), name="author_shadow_sync")


PRE_RELEASE_SYNC_SEQUENCE = (
    LifecycleAction("update_source"),
    LifecycleAction("project_consumer"),
    LifecycleAction("install_package"),
    LifecycleAction("install_skills"),
    LifecycleAction("accept_model_authority"),
    LifecycleAction("sync_openspec"),
)

PUBLICATION_SEQUENCE = (
    LifecycleAction("commit_git"),
    LifecycleAction("create_tag"),
    LifecycleAction("publish_github_release"),
)

GOOD_RELEASE_SEQUENCE = (
    *PRE_RELEASE_SYNC_SEQUENCE,
    LifecycleAction("run_validation"),
    *PUBLICATION_SEQUENCE,
    LifecycleAction("claim_release"),
)

_VALIDATED_RELEASE_PREFIX = (
    *PRE_RELEASE_SYNC_SEQUENCE,
    LifecycleAction("run_validation"),
)


def _release_sequence_with_validation(
    validation_action: LifecycleAction,
) -> tuple[LifecycleAction, ...]:
    return (
        *PRE_RELEASE_SYNC_SEQUENCE,
        validation_action,
        *PUBLICATION_SEQUENCE,
        LifecycleAction("claim_release"),
    )


STALE_OR_SUBSTITUTED_RELEASE_SEQUENCES = (
    (
        "source",
        (
            *_VALIDATED_RELEASE_PREFIX,
            LifecycleAction("update_source"),
            *PUBLICATION_SEQUENCE,
            LifecycleAction("claim_release"),
        ),
    ),
    (
        "consumer_projection",
        (
            *_VALIDATED_RELEASE_PREFIX,
            LifecycleAction("substitute_consumer_projection"),
            *PUBLICATION_SEQUENCE,
            LifecycleAction("claim_release"),
        ),
    ),
    (
        "installed_package",
        (
            *_VALIDATED_RELEASE_PREFIX,
            LifecycleAction("substitute_installed_package"),
            *PUBLICATION_SEQUENCE,
            LifecycleAction("claim_release"),
        ),
    ),
    (
        "installed_skill",
        (
            *_VALIDATED_RELEASE_PREFIX,
            LifecycleAction("substitute_installed_skill"),
            *PUBLICATION_SEQUENCE,
            LifecycleAction("claim_release"),
        ),
    ),
    (
        "model_authority",
        (
            *_VALIDATED_RELEASE_PREFIX,
            LifecycleAction("substitute_model_authority"),
            *PUBLICATION_SEQUENCE,
            LifecycleAction("claim_release"),
        ),
    ),
    (
        "openspec",
        (
            *_VALIDATED_RELEASE_PREFIX,
            LifecycleAction("substitute_openspec"),
            *PUBLICATION_SEQUENCE,
            LifecycleAction("claim_release"),
        ),
    ),
    (
        "persistent_validation_observation",
        _release_sequence_with_validation(
            LifecycleAction(
                "run_validation",
                validation_observation_scope="persistent",
            )
        ),
    ),
    (
        "repeated_semantic_validation",
        _release_sequence_with_validation(
            LifecycleAction(
                "run_validation",
                validation_semantic_verification_count=2,
            )
        ),
    ),
    (
        "missing_final_identity_freshness",
        _release_sequence_with_validation(
            LifecycleAction(
                "run_validation",
                validation_complete_observation_count=1,
                validation_final_identity_freshness_passed=False,
            )
        ),
    ),
    (
        "repeated_per_leaf_source_current_rebuild",
        _release_sequence_with_validation(
            LifecycleAction(
                "run_validation",
                validation_per_leaf_source_current_rebuild_count=4,
            )
        ),
    ),
    (
        "repeated_per_leaf_receipt_store_scan",
        _release_sequence_with_validation(
            LifecycleAction(
                "run_validation",
                validation_per_leaf_receipt_store_scan_count=4,
            )
        ),
    ),
    (
        "missing_receipt_reconciliation",
        _release_sequence_with_validation(
            LifecycleAction(
                "run_validation",
                validation_receipt_reconciliation_count=0,
            )
        ),
    ),
    (
        "git_commit",
        (
            *_VALIDATED_RELEASE_PREFIX,
            LifecycleAction("commit_git"),
            LifecycleAction("substitute_git_commit"),
            LifecycleAction("create_tag"),
            LifecycleAction("publish_github_release"),
            LifecycleAction("claim_release"),
        ),
    ),
    (
        "tag",
        (
            *_VALIDATED_RELEASE_PREFIX,
            LifecycleAction("commit_git"),
            LifecycleAction("create_tag"),
            LifecycleAction("substitute_tag"),
            LifecycleAction("publish_github_release"),
            LifecycleAction("claim_release"),
        ),
    ),
    (
        "github_release",
        (
            *_VALIDATED_RELEASE_PREFIX,
            *PUBLICATION_SEQUENCE,
            LifecycleAction("substitute_github_release"),
            LifecycleAction("claim_release"),
        ),
    ),
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
    if last_label == "release_accepted" and not state.release_ready():
        return InvariantResult.fail(
            "release accepted without exact current source, consumer, install, model, "
            "OpenSpec, Git commit, tag, GitHub Release, and validation identities"
        )
    return InvariantResult.pass_()


def no_wrong_plane_action_accepted(state: LifecycleState, _trace) -> InvariantResult:
    if state.wrong_plane_action_accepted:
        return InvariantResult.fail(
            "development process accepted an agent-operation or product-runtime action as its own work"
        )
    return InvariantResult.pass_()


def release_validation_observation_is_bounded(
    state: LifecycleState,
    trace,
) -> InvariantResult:
    last_label = trace.steps[-1].label if trace.steps else ""
    if last_label != "release_accepted":
        return InvariantResult.pass_()
    if (
        state.validation_observation_scope != "invocation_local"
        or state.validation_complete_observation_count != 2
        or state.validation_semantic_verification_count != 1
        or not state.validation_final_identity_freshness_passed
        or state.validation_per_leaf_source_current_rebuild_count != 0
        or state.validation_per_leaf_receipt_store_scan_count != 0
        or state.validation_receipt_reconciliation_count != 1
    ):
        return InvariantResult.fail(
            "release accepted without one invocation-local semantic observation "
            "and one final identity freshness check, or repeated per-leaf source/receipt discovery instead of one receipt reconciliation"
        )
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "no_release_with_stale_or_incomplete_evidence",
        "Release claims require current validation and an exact immutable publication chain "
        "across every independently owned identity domain.",
        no_release_with_stale_or_incomplete_evidence,
    ),
    Invariant(
        "development_process_owns_only_its_plane",
        "DevelopmentProcessFlow may reference other planes only as typed targets.",
        no_wrong_plane_action_accepted,
    ),
    Invariant(
        "validation_observation_bounded_currentness",
        "Release validation reuses one invocation-local semantic observation "
        "and performs exactly one final identity freshness check plus one batch "
        "receipt reconciliation, with no per-leaf source or receipt rediscovery.",
        release_validation_observation_is_bounded,
    ),
)

EXTERNAL_INPUTS = (
    LifecycleAction("run_validation"),
    LifecycleAction("update_code"),
    LifecycleAction("update_tests"),
    LifecycleAction("update_requirement"),
    LifecycleAction("update_source"),
    LifecycleAction("peer_write_source"),
    LifecycleAction("project_consumer"),
    LifecycleAction("install_package"),
    LifecycleAction("install_skills"),
    LifecycleAction("accept_model_authority"),
    LifecycleAction("sync_openspec"),
    LifecycleAction("commit_git"),
    LifecycleAction("create_tag"),
    LifecycleAction("publish_github_release"),
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


@dataclass(frozen=True)
class PathQualityLifecycleAction:
    action_type: str
    result_fingerprint: str = ""


@dataclass(frozen=True)
class PathQualityLifecycleOutput:
    status: str


@dataclass(frozen=True)
class PathQualityLifecycleState:
    owner_intent_closed: bool = False
    artifact_revision: int = 0
    implementation_performed: bool = False
    affected_validation_revision: int = -1
    light_review_revision: int = -1
    light_result_fingerprint: str = ""
    deep_review_triggered: bool = False
    deep_review_revision: int = -1
    candidate_revision: int = -1
    candidate_result_fingerprint: str = ""
    activation_revision: int = -1
    activation_result_fingerprint: str = ""

    def current_review_complete(self) -> bool:
        return (
            self.owner_intent_closed
            and self.implementation_performed
            and self.affected_validation_revision == self.artifact_revision
            and self.light_review_revision == self.artifact_revision
            and bool(self.light_result_fingerprint)
            and (
                not self.deep_review_triggered
                or self.deep_review_revision == self.artifact_revision
            )
        )

    def activation_is_current(self) -> bool:
        return (
            self.current_review_complete()
            and self.candidate_revision == self.artifact_revision
            and self.activation_revision == self.artifact_revision
            and self.candidate_result_fingerprint == self.light_result_fingerprint
            and self.activation_result_fingerprint == self.light_result_fingerprint
        )


class CorrectPathQualityLifecycleGate:
    """Order one model's quality proof without making deep review ceremonial."""

    name = "CorrectPathQualityLifecycleGate"
    reads = (
        "owner_intent_closed",
        "artifact_revision",
        "implementation_performed",
        "affected_validation_revision",
        "light_review_revision",
        "light_result_fingerprint",
        "deep_review_triggered",
        "deep_review_revision",
        "candidate_revision",
        "candidate_result_fingerprint",
        "activation_revision",
        "activation_result_fingerprint",
    )
    writes = reads
    accepted_input_type = PathQualityLifecycleAction
    input_description = "one model path-quality lifecycle action"
    output_description = "ordered path-quality lifecycle decision"
    idempotency = "A repeated current review is rejected unless the artifact changed."

    @staticmethod
    def _result(
        state: PathQualityLifecycleState,
        status: str,
        *,
        next_state: PathQualityLifecycleState | None = None,
    ) -> FunctionResult:
        return FunctionResult(
            PathQualityLifecycleOutput(status),
            next_state or state,
            label=status,
        )

    def apply(
        self,
        input_obj: PathQualityLifecycleAction,
        state: PathQualityLifecycleState,
    ) -> Iterable[FunctionResult]:
        action = input_obj.action_type
        if action == "close_owner_intent":
            if state.owner_intent_closed:
                yield self._result(state, "duplicate_owner_intent_closure_rejected")
                return
            yield self._result(
                state,
                "owner_intent_closed",
                next_state=replace(state, owner_intent_closed=True),
            )
            return
        if action == "trigger_deep_review":
            if not state.owner_intent_closed or state.deep_review_triggered:
                yield self._result(state, "deep_review_trigger_rejected")
                return
            yield self._result(
                state,
                "deep_review_triggered",
                next_state=replace(state, deep_review_triggered=True),
            )
            return
        if action == "review_light":
            if not state.owner_intent_closed or not input_obj.result_fingerprint:
                yield self._result(state, "light_review_rejected")
                return
            if (
                state.light_review_revision == state.artifact_revision
                and state.light_result_fingerprint == input_obj.result_fingerprint
            ):
                yield self._result(state, "duplicate_light_review_rejected")
                return
            yield self._result(
                state,
                "light_review_current",
                next_state=replace(
                    state,
                    light_review_revision=state.artifact_revision,
                    light_result_fingerprint=input_obj.result_fingerprint,
                    deep_review_revision=-1,
                ),
            )
            return
        if action == "review_deep":
            if (
                not state.deep_review_triggered
                or state.light_review_revision != state.artifact_revision
                or input_obj.result_fingerprint != state.light_result_fingerprint
            ):
                yield self._result(state, "deep_review_rejected")
                return
            if state.deep_review_revision == state.artifact_revision:
                yield self._result(state, "duplicate_deep_review_rejected")
                return
            yield self._result(
                state,
                "deep_review_current",
                next_state=replace(
                    state,
                    deep_review_revision=state.artifact_revision,
                ),
            )
            return
        if action == "implement":
            if (
                state.light_review_revision != state.artifact_revision
                or (
                    state.deep_review_triggered
                    and state.deep_review_revision != state.artifact_revision
                )
            ):
                yield self._result(state, "implementation_rejected")
                return
            yield self._result(
                state,
                "implementation_changed_model",
                next_state=replace(
                    state,
                    artifact_revision=state.artifact_revision + 1,
                    implementation_performed=True,
                    affected_validation_revision=-1,
                    candidate_revision=-1,
                    candidate_result_fingerprint="",
                    activation_revision=-1,
                    activation_result_fingerprint="",
                ),
            )
            return
        if action == "validate_affected":
            if not state.implementation_performed:
                yield self._result(state, "affected_validation_rejected")
                return
            yield self._result(
                state,
                "affected_validation_current",
                next_state=replace(
                    state,
                    affected_validation_revision=state.artifact_revision,
                ),
            )
            return
        if action == "build_candidate":
            if (
                not state.current_review_complete()
                or input_obj.result_fingerprint != state.light_result_fingerprint
            ):
                yield self._result(state, "candidate_rejected")
                return
            yield self._result(
                state,
                "candidate_bound_to_current_review",
                next_state=replace(
                    state,
                    candidate_revision=state.artifact_revision,
                    candidate_result_fingerprint=input_obj.result_fingerprint,
                ),
            )
            return
        if action == "activate":
            if (
                state.candidate_revision != state.artifact_revision
                or input_obj.result_fingerprint != state.light_result_fingerprint
                or state.candidate_result_fingerprint != state.light_result_fingerprint
            ):
                yield self._result(state, "activation_rejected")
                return
            yield self._result(
                state,
                "activation_bound_to_current_review",
                next_state=replace(
                    state,
                    activation_revision=state.artifact_revision,
                    activation_result_fingerprint=input_obj.result_fingerprint,
                ),
            )
            return
        yield self._result(state, "unknown_path_quality_action_rejected")


class BrokenPathQualityLifecycleGate(CorrectPathQualityLifecycleGate):
    """Known-bad comparison that lets stale evidence activate a candidate."""

    name = "BrokenPathQualityLifecycleGate"

    def apply(
        self,
        input_obj: PathQualityLifecycleAction,
        state: PathQualityLifecycleState,
    ) -> Iterable[FunctionResult]:
        if input_obj.action_type == "build_candidate":
            yield self._result(
                state,
                "candidate_bound_to_current_review",
                next_state=replace(
                    state,
                    candidate_revision=state.artifact_revision,
                    candidate_result_fingerprint=input_obj.result_fingerprint,
                ),
            )
            return
        if input_obj.action_type == "activate":
            yield self._result(
                state,
                "activation_bound_to_current_review",
                next_state=replace(
                    state,
                    activation_revision=state.artifact_revision,
                    activation_result_fingerprint=input_obj.result_fingerprint,
                ),
            )
            return
        yield from super().apply(input_obj, state)


PATH_QUALITY_BEFORE_FINGERPRINT = "sha256:" + "1" * 64
PATH_QUALITY_AFTER_FINGERPRINT = "sha256:" + "2" * 64
PATH_QUALITY_STALE_FINGERPRINT = "sha256:" + "3" * 64

GOOD_PATH_QUALITY_SEQUENCE = (
    PathQualityLifecycleAction("close_owner_intent"),
    PathQualityLifecycleAction("review_light", PATH_QUALITY_BEFORE_FINGERPRINT),
    PathQualityLifecycleAction("implement"),
    PathQualityLifecycleAction("validate_affected"),
    PathQualityLifecycleAction("review_light", PATH_QUALITY_AFTER_FINGERPRINT),
    PathQualityLifecycleAction("build_candidate", PATH_QUALITY_AFTER_FINGERPRINT),
    PathQualityLifecycleAction("activate", PATH_QUALITY_AFTER_FINGERPRINT),
)

GOOD_TRIGGERED_DEEP_PATH_QUALITY_SEQUENCE = (
    PathQualityLifecycleAction("close_owner_intent"),
    PathQualityLifecycleAction("trigger_deep_review"),
    PathQualityLifecycleAction("review_light", PATH_QUALITY_BEFORE_FINGERPRINT),
    PathQualityLifecycleAction("review_deep", PATH_QUALITY_BEFORE_FINGERPRINT),
    PathQualityLifecycleAction("implement"),
    PathQualityLifecycleAction("validate_affected"),
    PathQualityLifecycleAction("review_light", PATH_QUALITY_AFTER_FINGERPRINT),
    PathQualityLifecycleAction("review_deep", PATH_QUALITY_AFTER_FINGERPRINT),
    PathQualityLifecycleAction("build_candidate", PATH_QUALITY_AFTER_FINGERPRINT),
    PathQualityLifecycleAction("activate", PATH_QUALITY_AFTER_FINGERPRINT),
)

PATH_QUALITY_FAILURE_SEQUENCES = (
    (
        "review_before_owner_intent",
        (PathQualityLifecycleAction("review_light", PATH_QUALITY_BEFORE_FINGERPRINT),),
        "light_review_rejected",
    ),
    (
        "untriggered_deep_ceremony",
        (
            PathQualityLifecycleAction("close_owner_intent"),
            PathQualityLifecycleAction("review_light", PATH_QUALITY_BEFORE_FINGERPRINT),
            PathQualityLifecycleAction("review_deep", PATH_QUALITY_BEFORE_FINGERPRINT),
        ),
        "deep_review_rejected",
    ),
    (
        "candidate_without_post_change_refresh",
        (
            PathQualityLifecycleAction("close_owner_intent"),
            PathQualityLifecycleAction("review_light", PATH_QUALITY_BEFORE_FINGERPRINT),
            PathQualityLifecycleAction("implement"),
            PathQualityLifecycleAction("validate_affected"),
            PathQualityLifecycleAction("build_candidate", PATH_QUALITY_BEFORE_FINGERPRINT),
        ),
        "candidate_rejected",
    ),
    (
        "activation_with_stale_fingerprint",
        (
            *GOOD_PATH_QUALITY_SEQUENCE[:-1],
            PathQualityLifecycleAction("activate", PATH_QUALITY_STALE_FINGERPRINT),
        ),
        "activation_rejected",
    ),
)


def path_quality_activation_requires_current_exact_result(
    state: PathQualityLifecycleState,
    trace,
) -> InvariantResult:
    last_label = trace.steps[-1].label if trace.steps else ""
    if last_label == "activation_bound_to_current_review" and not state.activation_is_current():
        return InvariantResult.fail(
            "activation accepted without the current exact per-model path-quality result"
        )
    return InvariantResult.pass_()


PATH_QUALITY_LIFECYCLE_INVARIANTS = (
    Invariant(
        "path_quality_activation_requires_current_exact_result",
        "A candidate can activate only after owner/intent closure, affected validation, "
        "current light review, conditional deep review, and exact result binding.",
        path_quality_activation_requires_current_exact_result,
    ),
)


def path_quality_lifecycle_initial_state() -> PathQualityLifecycleState:
    return PathQualityLifecycleState()


def build_path_quality_lifecycle_workflow(*, broken: bool = False) -> Workflow:
    gate = BrokenPathQualityLifecycleGate() if broken else CorrectPathQualityLifecycleGate()
    return Workflow((gate,), name="development_process_path_quality_lifecycle")


from flowguard.skill_contract_model import build_skill_contract_model_export

FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"


def export_contract_model():
    exported = build_skill_contract_model_export(
        skill_id="flowguard-development-process-flow",
        route_id="development_process_flow",
        owner_id="development_process_flow",
        parent_model_id="flowguard.model_first_function_flow",
        business_intent="Order non-trivial development actions, keep ordinary work lightweight, conditionally select a hard-equivalent lower-rework process shape, reuse one invocation-local validation observation with one final identity freshness check and one batch receipt reconciliation, avoid per-leaf source or receipt rediscovery, keep evidence current across diagnosis, root-cause repair, peer writes, install, and closure, and atomically synchronize a current author-source skill projection into its exact owned shadow paths.",
        claim_boundary="This projection owns lifecycle order, conditional internal process optimization, bounded validation observation reuse, freshness, and author-shadow synchronization order, not product behavior, distribution inventory semantics, universal collect-all, global optimality, or future-agent compliance; a consumer projection used as author source, stale source fingerprint, unowned write, peer overwrite, partial activation, unnecessary ceremony, repeated semantic verification, per-leaf source or receipt rediscovery, missing final identity freshness or receipt reconciliation, non-equivalent candidate, progress-only evidence, or uncovered affected revalidation cannot close the route.",
    )
    for invariant_id in (
        "invariant:process-strategy-equivalence",
        "invariant:author-shadow-sync-atomic-currentness",
        "invariant:validation-observation-bounded-currentness",
    ):
        exported["invariant_ids"].append(invariant_id)
    for obligation_id, invariant_id in (
        (
            "obligation:flowguard-development-process-flow:process-strategy-equivalence",
            "invariant:process-strategy-equivalence",
        ),
        (
            "obligation:flowguard-development-process-flow:author-shadow-sync-atomic-currentness",
            "invariant:author-shadow-sync-atomic-currentness",
        ),
        (
            "obligation:flowguard-development-process-flow:validation-observation-bounded-currentness",
            "invariant:validation-observation-bounded-currentness",
        ),
    ):
        exported["obligations"].append(
            {
                "obligation_id": obligation_id,
                "invariant_id": invariant_id,
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
    "AUTHOR_SYNC_FAILURE_CASES",
    "AUTHOR_SYNC_INVARIANTS",
    "BROKEN_AUTHORIZATION_SEQUENCE",
    "EXTERNAL_INPUTS",
    "GOOD_AUTHOR_SYNC_ROLLBACK_SEQUENCE",
    "GOOD_AUTHOR_SYNC_SEQUENCE",
    "GOOD_CLOSED_ADMISSION_SEQUENCE",
    "GOOD_PATH_QUALITY_SEQUENCE",
    "GOOD_RELEASE_SEQUENCE",
    "GOOD_SCOPED_ADMISSION_SEQUENCE",
    "GOOD_TRIGGERED_DEEP_PATH_QUALITY_SEQUENCE",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "PRE_RELEASE_SYNC_SEQUENCE",
    "PUBLICATION_SEQUENCE",
    "PATH_QUALITY_FAILURE_SEQUENCES",
    "PATH_QUALITY_LIFECYCLE_INVARIANTS",
    "STALE_OR_SUBSTITUTED_RELEASE_SEQUENCES",
    "AdmissionAction",
    "AdmissionState",
    "AuthorSyncAction",
    "AuthorSyncState",
    "LifecycleAction",
    "LifecycleOutput",
    "LifecycleState",
    "PathQualityLifecycleAction",
    "PathQualityLifecycleOutput",
    "PathQualityLifecycleState",
    "admission_initial_state",
    "author_sync_initial_state",
    "build_admission_workflow",
    "build_author_sync_workflow",
    "build_broken_workflow",
    "build_broken_plane_workflow",
    "build_correct_workflow",
    "build_path_quality_lifecycle_workflow",
    "export_contract_model",
    "initial_state",
    "path_quality_lifecycle_initial_state",
    "terminal_predicate",
]
