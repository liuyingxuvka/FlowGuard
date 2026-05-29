"""FlowGuard model for legacy compatibility cleanup.

FlowGuard Risk Purpose Header
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: review removal of compatibility-only fields, aliases, wrappers, and
skill guidance while preserving safety classifiers and installed-skill parity.
Modeled block shape: Input x State -> Set(Output x State).
Run: python .flowguard/legacy_compatibility_cleanup/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.architecture_reduction import (
    CANDIDATE_REMOVE_BRANCH,
    COMPATIBILITY_ACTION_KEEP,
    COMPATIBILITY_ACTION_PRUNE,
    COMPATIBILITY_SURFACE_CURRENT_CONTRACT,
    COMPATIBILITY_SURFACE_NEGATIVE_LEGACY_TEST,
    COMPATIBILITY_SURFACE_PRUNE_CANDIDATE,
    PROOF_SAFE_BY_EQUIVALENCE,
    ROUTE_DEVELOPMENT_PROCESS_FLOW,
    TARGET_ACTION_REMOVE,
    ArchitectureReductionCandidate,
    ArchitectureReductionPlan,
    CompatibilitySurfaceClassification,
    ObservableArchitectureContract,
    review_architecture_reduction,
)
from flowguard.development_process_flow import (
    PROCESS_ARTIFACT_CODE,
    PROCESS_ARTIFACT_DOC,
    PROCESS_ARTIFACT_MODEL,
    PROCESS_ARTIFACT_RELEASE,
    PROCESS_ARTIFACT_REQUIREMENT,
    PROCESS_ARTIFACT_TEST,
    PROCESS_EVIDENCE_PASSED,
    PROCESS_SCOPE_ROUTINE,
    DevelopmentProcessPlan,
    FreshnessRule,
    ProcessAction,
    ProcessArtifact,
    ProcessEvidence,
    ValidationRequirement,
    review_development_process_flow,
)


@dataclass(frozen=True)
class CleanupAction:
    action_type: str


@dataclass(frozen=True)
class CleanupOutput:
    status: str


@dataclass(frozen=True)
class CleanupState:
    audit_complete: bool = False
    removable_legacy_selected: bool = False
    current_contracts_preserved: bool = False
    safety_classifiers_preserved: bool = False
    route_first_replacement_done: bool = False
    focused_validation_passed: bool = False
    editable_install_synced: bool = False
    installed_skill_parity: bool = False
    shadow_workspace_synced: bool = False
    git_evidence_ready: bool = False
    done_claim: str = "none"

    def ready_for_done(self) -> bool:
        return (
            self.audit_complete
            and self.removable_legacy_selected
            and self.current_contracts_preserved
            and self.safety_classifiers_preserved
            and self.route_first_replacement_done
            and self.focused_validation_passed
            and self.editable_install_synced
            and self.installed_skill_parity
            and self.shadow_workspace_synced
            and self.git_evidence_ready
        )


class CorrectLegacyCompatibilityCleanup:
    name = "CorrectLegacyCompatibilityCleanup"
    reads = (
        "audit_complete",
        "removable_legacy_selected",
        "current_contracts_preserved",
        "safety_classifiers_preserved",
        "route_first_replacement_done",
        "focused_validation_passed",
        "editable_install_synced",
        "installed_skill_parity",
        "shadow_workspace_synced",
        "git_evidence_ready",
        "done_claim",
    )
    writes = reads
    accepted_input_type = CleanupAction
    input_description = "legacy compatibility cleanup lifecycle action"
    output_description = "cleanup state or claim decision"
    idempotency = (
        "Done claims require audit, safe removal selection, safety preservation, "
        "route-first replacement, validation, install, installed-skill, shadow, and git evidence."
    )

    def apply(self, input_obj: CleanupAction, state: CleanupState) -> Iterable[FunctionResult]:
        action = input_obj.action_type
        if action == "audit_and_classify":
            yield FunctionResult(
                CleanupOutput("audit_classified"),
                replace(
                    state,
                    audit_complete=True,
                    removable_legacy_selected=True,
                    current_contracts_preserved=True,
                    safety_classifiers_preserved=True,
                ),
                label="audit_classified",
            )
        elif action == "replace_legacy_surface":
            yield FunctionResult(
                CleanupOutput("route_first_replacement_done"),
                replace(state, route_first_replacement_done=True),
                label="route_first_replacement_done",
            )
        elif action == "run_validations":
            yield FunctionResult(
                CleanupOutput("focused_validation_passed"),
                replace(state, focused_validation_passed=True),
                label="focused_validation_passed",
            )
        elif action == "sync_local_surfaces":
            yield FunctionResult(
                CleanupOutput("local_surfaces_synced"),
                replace(
                    state,
                    editable_install_synced=True,
                    installed_skill_parity=True,
                    shadow_workspace_synced=True,
                    git_evidence_ready=True,
                ),
                label="local_surfaces_synced",
            )
        elif action == "claim_done":
            claim = "accepted" if state.ready_for_done() else "rejected"
            yield FunctionResult(
                CleanupOutput(f"done_{claim}"),
                replace(state, done_claim=claim),
                label=f"done_{claim}",
            )


class BrokenDeletesSafetyClassifier(CorrectLegacyCompatibilityCleanup):
    name = "BrokenDeletesSafetyClassifier"
    idempotency = "Broken variant accepts deletion without preserving compatibility safety classifiers."

    def apply(self, input_obj: CleanupAction, state: CleanupState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "audit_and_classify":
            yield FunctionResult(
                CleanupOutput("audit_classified_without_safety"),
                replace(
                    state,
                    audit_complete=True,
                    removable_legacy_selected=True,
                    current_contracts_preserved=True,
                    safety_classifiers_preserved=False,
                ),
                label="audit_classified_without_safety",
            )
            return
        if input_obj.action_type == "claim_done":
            claim = "accepted" if state.audit_complete and state.route_first_replacement_done else "rejected"
            yield FunctionResult(
                CleanupOutput(f"done_{claim}"),
                replace(state, done_claim=claim),
                label=f"done_{claim}",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenSkipsInstalledSkillParity(CorrectLegacyCompatibilityCleanup):
    name = "BrokenSkipsInstalledSkillParity"
    idempotency = "Broken variant treats package version and shadow sync as installed Codex skill parity."

    def apply(self, input_obj: CleanupAction, state: CleanupState) -> Iterable[FunctionResult]:
        if input_obj.action_type == "sync_local_surfaces":
            yield FunctionResult(
                CleanupOutput("partial_local_surfaces_synced"),
                replace(
                    state,
                    editable_install_synced=True,
                    installed_skill_parity=False,
                    shadow_workspace_synced=True,
                    git_evidence_ready=True,
                ),
                label="partial_local_surfaces_synced",
            )
            return
        if input_obj.action_type == "claim_done":
            claim = (
                "accepted"
                if state.audit_complete
                and state.route_first_replacement_done
                and state.focused_validation_passed
                and state.editable_install_synced
                and state.shadow_workspace_synced
                else "rejected"
            )
            yield FunctionResult(
                CleanupOutput(f"done_{claim}"),
                replace(state, done_claim=claim),
                label=f"done_{claim}",
            )
            return
        yield from super().apply(input_obj, state)


def terminal_predicate(current_output, state, trace) -> bool:
    del state, trace
    return isinstance(current_output, CleanupOutput) and current_output.status.startswith("done_")


def no_done_without_safe_cleanup(state: CleanupState, trace) -> InvariantResult:
    del trace
    if state.done_claim == "accepted" and not state.ready_for_done():
        return InvariantResult.fail(
            "done accepted before audit, safety preservation, route-first replacement, validation, install, installed-skill, shadow, and git evidence"
        )
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "no_done_without_safe_cleanup",
        "Legacy compatibility cleanup completion requires safe classification, validation, installed-skill parity, shadow sync, and git evidence.",
        no_done_without_safe_cleanup,
    ),
)

EXTERNAL_INPUTS = (
    CleanupAction("audit_and_classify"),
    CleanupAction("replace_legacy_surface"),
    CleanupAction("run_validations"),
    CleanupAction("sync_local_surfaces"),
    CleanupAction("claim_done"),
)

MAX_SEQUENCE_LENGTH = 5


def initial_state() -> CleanupState:
    return CleanupState()


def build_correct_workflow() -> Workflow:
    return Workflow((CorrectLegacyCompatibilityCleanup(),), name="legacy_compatibility_cleanup_correct")


def build_broken_safety_workflow() -> Workflow:
    return Workflow((BrokenDeletesSafetyClassifier(),), name="legacy_compatibility_cleanup_broken_safety")


def build_broken_installed_skill_workflow() -> Workflow:
    return Workflow((BrokenSkipsInstalledSkillParity(),), name="legacy_compatibility_cleanup_broken_skill_sync")


def architecture_reduction_report():
    cleanup_candidate_id = "remove-stale-repeated-similarity-fields"
    plan = ArchitectureReductionPlan(
        "clean-legacy-compatibility-fields/architecture",
        observable_contract=ObservableArchitectureContract(
            source_model_id="openspec:clean-legacy-compatibility-fields",
            source_code_boundary_id="FlowGuard compatibility and skill guidance surface",
            public_entrypoints=(
                "flowguard.SimilarityHandoff",
                "flowguard.FLOWGUARD_ROUTE_API",
                ".agents/skills/model-first-function-flow/SKILL.md",
            ),
            observable_outputs=(
                "agents use SimilarityHandoff for similarity provenance",
                "agents keep compatibility-surface safety classifiers",
                "installed Codex skills match repository-managed route guidance",
            ),
            observable_state=("public API exports", "installed skill text", "shadow workspace source"),
            observable_side_effects=("editable install refresh", "installed skill sync", "local git commit/tag"),
            validation_boundaries=(
                "tests/test_api_surface.py",
                "tests/test_model_similarity_integrations.py",
                "tests/test_architecture_reduction.py",
                "tests/test_skill_docs.py",
            ),
            rationale="Compatibility cleanup changes AI and API surfaces while preserving current public behavior and deletion guards.",
        ),
        candidates=(
            ArchitectureReductionCandidate(
                candidate_id=cleanup_candidate_id,
                candidate_type=CANDIDATE_REMOVE_BRANCH,
                code_node_id="FunctionResult.state alias, plan_intake public aliases, old repeated similarity fields, and stale skill handoff wording",
                source_model_element="SimilarityHandoff owns downstream similarity provenance",
                target_action=TARGET_ACTION_REMOVE,
                proof_status=PROOF_SAFE_BY_EQUIVALENCE,
                required_next_route=ROUTE_DEVELOPMENT_PROCESS_FLOW,
                rationale="Old compatibility-only aliases, fields, and stale prompt lines duplicate the current core names or route-first handoff.",
                evidence_refs=(
                    "tests/test_api_surface.py::test_similarity_handoff_replaces_repeated_downstream_fields",
                    "tests/test_model_similarity_integrations.py",
                ),
            ),
        ),
        compatibility_surfaces=(
            CompatibilitySurfaceClassification(
                surface_id="obsolete-compatibility-only-aliases-and-fields",
                classification=COMPATIBILITY_SURFACE_PRUNE_CANDIDATE,
                recommended_action=COMPATIBILITY_ACTION_PRUNE,
                rationale="Current names and SimilarityHandoff cover the intended API and route handoff surface.",
                code_node_ids=(
                    "flowguard.core.FunctionResult.state",
                    "flowguard.plan_intake legacy public aliases",
                    "ExistingModelPreflight",
                    "CodeStructureRecommendation",
                    "ModelTestAlignmentPlan",
                ),
                candidate_ids=(cleanup_candidate_id,),
                evidence_refs=("tests/test_api_surface.py",),
            ),
            CompatibilitySurfaceClassification(
                surface_id="compatibility-surface-classifier",
                classification=COMPATIBILITY_SURFACE_CURRENT_CONTRACT,
                recommended_action=COMPATIBILITY_ACTION_KEEP,
                rationale="The classifier protects public facades, current contracts, and unknown surfaces from accidental deletion.",
                code_node_ids=("flowguard.architecture_reduction.CompatibilitySurfaceClassification",),
                evidence_refs=("tests/test_architecture_reduction.py",),
            ),
            CompatibilitySurfaceClassification(
                surface_id="negative-legacy-test-classifier",
                classification=COMPATIBILITY_SURFACE_NEGATIVE_LEGACY_TEST,
                recommended_action=COMPATIBILITY_ACTION_KEEP,
                rationale="Negative legacy tests remain safety evidence unless replacement rejection evidence exists.",
                code_node_ids=("tests/test_architecture_reduction.py",),
                evidence_refs=("tests/test_architecture_reduction.py",),
            ),
        ),
        rationale="Remove obsolete parallel compatibility paths only when the current route handoff and safety classifiers remain proven.",
    )
    return review_architecture_reduction(plan)


def development_process_report():
    plan = DevelopmentProcessPlan(
        "clean-legacy-compatibility-fields/lifecycle",
        decision_scope=PROCESS_SCOPE_ROUTINE,
        artifacts=(
            ProcessArtifact("openspec.compat-cleanup", PROCESS_ARTIFACT_REQUIREMENT, "1"),
            ProcessArtifact("model.compat-cleanup", PROCESS_ARTIFACT_MODEL, "1"),
            ProcessArtifact("code.compat-cleanup", PROCESS_ARTIFACT_CODE, "1"),
            ProcessArtifact("tests.compat-cleanup", PROCESS_ARTIFACT_TEST, "1"),
            ProcessArtifact("docs.skills", PROCESS_ARTIFACT_DOC, "1"),
            ProcessArtifact("editable-install", PROCESS_ARTIFACT_RELEASE, "1"),
            ProcessArtifact("installed-codex-skills", PROCESS_ARTIFACT_RELEASE, "1"),
            ProcessArtifact("shadow-workspace", PROCESS_ARTIFACT_RELEASE, "1"),
            ProcessArtifact("local-git-evidence", PROCESS_ARTIFACT_RELEASE, "1"),
        ),
        actions=(
            ProcessAction(
                "create-openspec-and-model",
                writes_artifacts=("openspec.compat-cleanup", "model.compat-cleanup"),
            ),
            ProcessAction(
                "apply-compatibility-cleanup",
                reads_artifacts=("openspec.compat-cleanup", "model.compat-cleanup"),
                writes_artifacts=("code.compat-cleanup", "tests.compat-cleanup", "docs.skills"),
            ),
            ProcessAction(
                "run-focused-validation",
                reads_artifacts=("model.compat-cleanup", "code.compat-cleanup", "tests.compat-cleanup", "docs.skills"),
                produced_evidence_ids=("evidence:focused-validation",),
            ),
            ProcessAction(
                "sync-local-surfaces",
                reads_artifacts=("code.compat-cleanup", "docs.skills"),
                writes_artifacts=("editable-install", "installed-codex-skills", "shadow-workspace", "local-git-evidence"),
                produced_evidence_ids=("evidence:local-sync",),
            ),
        ),
        evidence=(
            ProcessEvidence(
                "evidence:focused-validation",
                evidence_kind="compat-cleanup-focused-tests",
                status=PROCESS_EVIDENCE_PASSED,
                covers_artifacts=("model.compat-cleanup", "code.compat-cleanup", "tests.compat-cleanup", "docs.skills"),
                covered_versions={
                    "model.compat-cleanup": "1",
                    "code.compat-cleanup": "1",
                    "tests.compat-cleanup": "1",
                    "docs.skills": "1",
                },
                validation_requirement_ids=("require-focused-validation",),
                produced_by_action_id="run-focused-validation",
                command="python .flowguard/legacy_compatibility_cleanup/run_checks.py; focused unittest commands",
            ),
            ProcessEvidence(
                "evidence:local-sync",
                evidence_kind="install-skill-shadow-git-sync",
                status=PROCESS_EVIDENCE_PASSED,
                covers_artifacts=("editable-install", "installed-codex-skills", "shadow-workspace", "local-git-evidence"),
                covered_versions={
                    "editable-install": "1",
                    "installed-codex-skills": "1",
                    "shadow-workspace": "1",
                    "local-git-evidence": "1",
                },
                validation_requirement_ids=("require-local-sync",),
                produced_by_action_id="sync-local-surfaces",
                command="editable install, installed skill content parity, shadow import check, git commit/tag check",
            ),
        ),
        validation_requirements=(
            ValidationRequirement(
                "require-focused-validation",
                required_artifact_ids=("model.compat-cleanup", "code.compat-cleanup", "tests.compat-cleanup", "docs.skills"),
                required_evidence_kinds=("compat-cleanup-focused-tests",),
                evidence_ids=("evidence:focused-validation",),
            ),
            ValidationRequirement(
                "require-local-sync",
                required_artifact_ids=("editable-install", "installed-codex-skills", "shadow-workspace", "local-git-evidence"),
                required_evidence_kinds=("install-skill-shadow-git-sync",),
                evidence_ids=("evidence:local-sync",),
            ),
        ),
        freshness_rules=(
            FreshnessRule(
                "skill-doc-edits-stale-installed-skill-parity",
                upstream_artifact_id="docs.skills",
                invalidates_evidence_kinds=("install-skill-shadow-git-sync",),
                description="Skill guidance edits stale installed Codex skill parity and shadow sync evidence.",
            ),
            FreshnessRule(
                "code-or-test-edits-stale-focused-validation",
                upstream_artifact_id="code.compat-cleanup",
                invalidates_evidence_kinds=("compat-cleanup-focused-tests",),
                description="Compatibility cleanup code edits stale focused validation evidence.",
            ),
        ),
    )
    return review_development_process_flow(plan)


__all__ = [
    "EXTERNAL_INPUTS",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "CleanupAction",
    "CleanupOutput",
    "CleanupState",
    "architecture_reduction_report",
    "build_broken_installed_skill_workflow",
    "build_broken_safety_workflow",
    "build_correct_workflow",
    "development_process_report",
    "initial_state",
    "terminal_predicate",
]
