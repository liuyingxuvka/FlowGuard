"""FlowGuard model for OpenSpec archive cleanup after v0.27.0.

FlowGuard Risk Purpose Header
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: review the cleanup path that turns a large active OpenSpec backlog
into archived release evidence without changing package behavior.
Guards against: treating stale task checkboxes as unfinished code work,
archiving without strict validation, claiming background regressions from
progress-only logs, overwriting peer-agent work during shadow sync, and
recording release confidence without install/shadow evidence.
Use before editing: run this model before changing OpenSpec task state or
archiving changes, then rerun after archive, validation, install sync, and
shadow verification.
Run: python .flowguard/openspec_archive_cleanup/run_checks.py

Function blocks:
- InspectReleasedBacklog: Input x State -> Set(Output x State)
- NormalizeTaskState: Input x State -> Set(Output x State)
- ArchiveAndValidate: Input x State -> Set(Output x State)
- SyncAndRecord: Input x State -> Set(Output x State)
"""

from __future__ import annotations

from dataclasses import dataclass

from flowguard import (
    EVIDENCE_ABSTRACT_GREEN,
    PROCESS_ARTIFACT_DOC,
    PROCESS_ARTIFACT_MODEL,
    PROCESS_ARTIFACT_RELEASE,
    PROCESS_ARTIFACT_REQUIREMENT,
    PROCESS_ARTIFACT_TEST,
    PROCESS_EVIDENCE_PASSED,
    PROCESS_SCOPE_RELEASE,
    TEST_LAYER_PARENT,
    DevelopmentProcessPlan,
    ProcessAction,
    ProcessArtifact,
    ProcessEvidence,
    ProofArtifactRef,
    FreshnessRule,
    TestMeshPlan,
    TestPartitionItem,
    TestSuiteEvidence,
    TestTargetSplitDerivation,
    ValidationRequirement,
    review_development_process_flow,
    review_test_mesh,
)


@dataclass(frozen=True)
class ArchiveCleanupReview:
    process_ok: bool
    validation_mesh_ok: bool

    @property
    def ok(self) -> bool:
        return self.process_ok and self.validation_mesh_ok


def _proof(artifact_id: str, command: str, result_path: str, obligations: tuple[str, ...]) -> ProofArtifactRef:
    return ProofArtifactRef(
        artifact_id=artifact_id,
        producer_route="openspec_archive_cleanup",
        command=command,
        result_path=result_path,
        result_status=PROCESS_EVIDENCE_PASSED,
        exit_code=0,
        artifact_fingerprints={result_path: "sha256:recorded-at-runtime"},
        covered_obligation_ids=obligations,
    )


def development_process_report():
    plan = DevelopmentProcessPlan(
        "openspec-archive-cleanup-lifecycle",
        artifacts=(
            ProcessArtifact(
                "openspec.active_queue",
                PROCESS_ARTIFACT_REQUIREMENT,
                "v0.27.0-pre-archive",
                path="openspec/changes",
                owner="OpenSpec",
            ),
            ProcessArtifact(
                "openspec.archive_tree",
                PROCESS_ARTIFACT_REQUIREMENT,
                "v0.27.0-archive",
                path="openspec/changes/archive",
                owner="OpenSpec",
                upstream_artifact_ids=("openspec.active_queue",),
            ),
            ProcessArtifact(
                "flowguard.archive_cleanup_model",
                PROCESS_ARTIFACT_MODEL,
                "1",
                path=".flowguard/openspec_archive_cleanup/model.py",
                owner="FlowGuard",
            ),
            ProcessArtifact(
                "validation.full_regression",
                PROCESS_ARTIFACT_TEST,
                "v0.27.0",
                path=".flowguard/run_artifacts",
                owner="TestMesh",
            ),
            ProcessArtifact(
                "install.editable",
                PROCESS_ARTIFACT_RELEASE,
                "0.27.0",
                owner="DevelopmentProcessFlow",
            ),
            ProcessArtifact(
                "workspace.shadow",
                PROCESS_ARTIFACT_RELEASE,
                "0.27.0",
                path="C:/Users/liu_y/Documents/FlowGuard_20260427",
                owner="DevelopmentProcessFlow",
            ),
            ProcessArtifact(
                "adoption.kb",
                PROCESS_ARTIFACT_DOC,
                "v0.27.0-archive-cleanup",
                owner="RiskEvidenceLedger",
            ),
        ),
        actions=(
            ProcessAction(
                "inspect-release-and-queue",
                action_type="work",
                reads_artifacts=("openspec.active_queue", "install.editable", "workspace.shadow"),
            ),
            ProcessAction(
                "normalize-stale-release-tasks",
                action_type="work",
                reads_artifacts=("openspec.active_queue",),
                writes_artifacts=("openspec.active_queue",),
                order_after=("inspect-release-and-queue",),
            ),
            ProcessAction(
                "write-flowguard-cleanup-model",
                action_type="work",
                writes_artifacts=("flowguard.archive_cleanup_model",),
                order_after=("inspect-release-and-queue",),
            ),
            ProcessAction(
                "archive-completed-changes",
                action_type="archive",
                reads_artifacts=("openspec.active_queue", "flowguard.archive_cleanup_model"),
                writes_artifacts=("openspec.archive_tree",),
                order_after=("normalize-stale-release-tasks", "write-flowguard-cleanup-model"),
                decision_scope=PROCESS_SCOPE_RELEASE,
            ),
            ProcessAction(
                "run-openspec-strict-validation",
                action_type="work",
                reads_artifacts=("openspec.archive_tree",),
                produced_evidence_ids=("openspec-archive-validate-pass",),
                order_after=("archive-completed-changes",),
            ),
            ProcessAction(
                "run-background-regressions",
                action_type="work",
                reads_artifacts=("openspec.archive_tree", "flowguard.archive_cleanup_model"),
                produced_evidence_ids=("background-regression-final", "flowguard-model-regression-final"),
                order_after=("run-openspec-strict-validation",),
            ),
            ProcessAction(
                "sync-install-and-shadow",
                action_type="work",
                writes_artifacts=("install.editable", "workspace.shadow"),
                produced_evidence_ids=("install-shadow-current",),
                order_after=("run-background-regressions",),
            ),
            ProcessAction(
                "record-adoption-and-kb",
                action_type="work",
                writes_artifacts=("adoption.kb",),
                produced_evidence_ids=("adoption-kb-current",),
                order_after=("sync-install-and-shadow",),
            ),
            ProcessAction(
                "inspect-final-release-state",
                action_type="work",
                reads_artifacts=("openspec.archive_tree", "install.editable", "workspace.shadow"),
                produced_evidence_ids=("release-state-current",),
                order_after=("record-adoption-and-kb",),
            ),
            ProcessAction(
                "claim-archive-cleanup-done",
                action_type="claim_archive",
                required_evidence_ids=(
                    "release-state-current",
                    "openspec-archive-validate-pass",
                    "background-regression-final",
                    "flowguard-model-regression-final",
                    "install-shadow-current",
                    "adoption-kb-current",
                ),
                order_after=("inspect-final-release-state",),
                decision_scope=PROCESS_SCOPE_RELEASE,
            ),
        ),
        evidence=(
            ProcessEvidence(
                "release-state-current",
                evidence_kind="release_state",
                status=PROCESS_EVIDENCE_PASSED,
                covers_artifacts=("openspec.active_queue", "install.editable", "workspace.shadow"),
                covered_versions={
                    "openspec.active_queue": "v0.27.0-pre-archive",
                    "install.editable": "0.27.0",
                    "workspace.shadow": "0.27.0",
                },
                validation_requirement_ids=("release-state-current",),
                command="git status; gh release view v0.27.0; import flowguard from source and shadow",
                result_path=".flowguard/run_artifacts/archive-preflight.txt",
                produced_by_action_id="inspect-final-release-state",
                proof_artifact=_proof(
                    "proof:release-state-current",
                    "preflight release/source/shadow checks",
                    ".flowguard/run_artifacts/archive-preflight.txt",
                    ("release-state-current",),
                ),
            ),
            ProcessEvidence(
                "openspec-archive-validate-pass",
                evidence_kind="openspec",
                status=PROCESS_EVIDENCE_PASSED,
                covers_artifacts=("openspec.active_queue", "openspec.archive_tree"),
                covered_versions={
                    "openspec.active_queue": "v0.27.0-pre-archive",
                    "openspec.archive_tree": "v0.27.0-archive",
                },
                validation_requirement_ids=("openspec-archive-current",),
                command="openspec validate --all --strict --json",
                result_path=".flowguard/run_artifacts/openspec-archive-validate.json",
                produced_by_action_id="run-openspec-strict-validation",
                proof_artifact=_proof(
                    "proof:openspec-archive",
                    "openspec validate --all --strict --json",
                    ".flowguard/run_artifacts/openspec-archive-validate.json",
                    ("openspec-archive-current",),
                ),
            ),
            ProcessEvidence(
                "background-regression-final",
                evidence_kind="regression",
                status=PROCESS_EVIDENCE_PASSED,
                covers_artifacts=("validation.full_regression", "openspec.archive_tree"),
                covered_versions={
                    "validation.full_regression": "v0.27.0",
                    "openspec.archive_tree": "v0.27.0-archive",
                },
                validation_requirement_ids=("background-regression-final",),
                command="python -m unittest discover -s tests -v",
                result_path=".flowguard/run_artifacts/full-unittest-archive-cleanup.out.txt",
                produced_by_action_id="run-background-regressions",
                proof_artifact=_proof(
                    "proof:full-regression",
                    "python -m unittest discover -s tests -v",
                    ".flowguard/run_artifacts/full-unittest-archive-cleanup.out.txt",
                    ("background-regression-final",),
                ),
                background=True,
                has_exit_artifact=True,
                has_result_artifact=True,
            ),
            ProcessEvidence(
                "flowguard-model-regression-final",
                evidence_kind="flowguard_model",
                status=PROCESS_EVIDENCE_PASSED,
                covers_artifacts=("flowguard.archive_cleanup_model", "openspec.archive_tree"),
                covered_versions={
                    "flowguard.archive_cleanup_model": "1",
                    "openspec.archive_tree": "v0.27.0-archive",
                },
                validation_requirement_ids=("flowguard-model-regression-current",),
                command="all .flowguard run_checks.py scripts",
                result_path=".flowguard/run_artifacts/model-regression-archive-cleanup.out.txt",
                produced_by_action_id="run-background-regressions",
                proof_artifact=_proof(
                    "proof:model-regression",
                    "all .flowguard run_checks.py scripts",
                    ".flowguard/run_artifacts/model-regression-archive-cleanup.out.txt",
                    ("flowguard-model-regression-current",),
                ),
                background=True,
                has_exit_artifact=True,
                has_result_artifact=True,
            ),
            ProcessEvidence(
                "install-shadow-current",
                evidence_kind="install_sync",
                status=PROCESS_EVIDENCE_PASSED,
                covers_artifacts=("install.editable", "workspace.shadow"),
                covered_versions={"install.editable": "0.27.0", "workspace.shadow": "0.27.0"},
                validation_requirement_ids=("install-shadow-current",),
                command="pip editable install and source/shadow import checks",
                result_path=".flowguard/run_artifacts/install-shadow-archive-cleanup.txt",
                produced_by_action_id="sync-install-and-shadow",
                proof_artifact=_proof(
                    "proof:install-shadow",
                    "pip editable install and source/shadow import checks",
                    ".flowguard/run_artifacts/install-shadow-archive-cleanup.txt",
                    ("install-shadow-current",),
                ),
            ),
            ProcessEvidence(
                "adoption-kb-current",
                evidence_kind="adoption",
                status=PROCESS_EVIDENCE_PASSED,
                covers_artifacts=("adoption.kb",),
                covered_versions={"adoption.kb": "v0.27.0-archive-cleanup"},
                validation_requirement_ids=("adoption-kb-current",),
                command="flowguard adoption-finish and KB feedback",
                result_path="docs/flowguard_adoption_log.md",
                produced_by_action_id="record-adoption-and-kb",
                proof_artifact=_proof(
                    "proof:adoption-kb",
                    "flowguard adoption-finish and KB feedback",
                    "docs/flowguard_adoption_log.md",
                    ("adoption-kb-current",),
                ),
            ),
        ),
        validation_requirements=(
            ValidationRequirement(
                "release-state-current",
                required_artifact_ids=("openspec.active_queue", "install.editable", "workspace.shadow"),
                required_evidence_kinds=("release_state",),
                evidence_ids=("release-state-current",),
            ),
            ValidationRequirement(
                "openspec-archive-current",
                required_artifact_ids=("openspec.active_queue", "openspec.archive_tree"),
                required_evidence_kinds=("openspec",),
                evidence_ids=("openspec-archive-validate-pass",),
            ),
            ValidationRequirement(
                "background-regression-final",
                required_artifact_ids=("validation.full_regression",),
                required_evidence_kinds=("regression",),
                evidence_ids=("background-regression-final",),
            ),
            ValidationRequirement(
                "flowguard-model-regression-current",
                required_artifact_ids=("flowguard.archive_cleanup_model",),
                required_evidence_kinds=("flowguard_model",),
                evidence_ids=("flowguard-model-regression-final",),
            ),
            ValidationRequirement(
                "install-shadow-current",
                required_artifact_ids=("install.editable", "workspace.shadow"),
                required_evidence_kinds=("install_sync",),
                evidence_ids=("install-shadow-current",),
            ),
            ValidationRequirement(
                "adoption-kb-current",
                required_artifact_ids=("adoption.kb",),
                required_evidence_kinds=("adoption",),
                evidence_ids=("adoption-kb-current",),
            ),
        ),
        freshness_rules=(
            FreshnessRule(
                "active-queue-invalidates-archive-tree",
                upstream_artifact_id="openspec.active_queue",
                invalidates_artifact_ids=("openspec.archive_tree",),
                invalidates_evidence_kinds=("openspec", "regression", "flowguard_model"),
                description=(
                    "If active OpenSpec changes are edited after archive, the archive tree "
                    "and archive validation evidence must be regenerated."
                ),
            ),
        ),
        decision_scope=PROCESS_SCOPE_RELEASE,
        require_proof_artifacts=True,
    )
    return review_development_process_flow(plan)


def validation_mesh_report():
    plan = TestMeshPlan(
        parent_suite_id="openspec-archive-cleanup-validation",
        partition_items=(
            TestPartitionItem("openspec-strict", owner_suite_id="openspec-strict"),
            TestPartitionItem("flowguard-models", owner_suite_id="flowguard-models"),
            TestPartitionItem("full-regression", owner_suite_id="full-regression"),
            TestPartitionItem("install-shadow", owner_suite_id="install-shadow"),
            TestPartitionItem("adoption-kb", owner_suite_id="adoption-kb"),
        ),
        child_suites=(
            TestSuiteEvidence(
                "openspec-strict",
                result_status="passed",
                evidence_tier=EVIDENCE_ABSTRACT_GREEN,
                test_count=1,
                selected_count=1,
                result_path=".flowguard/run_artifacts/openspec-archive-validate.json",
            ),
            TestSuiteEvidence(
                "flowguard-models",
                command="all .flowguard run_checks.py scripts",
                result_status="passed",
                evidence_tier=EVIDENCE_ABSTRACT_GREEN,
                test_count=1,
                selected_count=1,
                exit_code=0,
                result_path=".flowguard/run_artifacts/model-regression-archive-cleanup-20260527-190230.out.txt",
                background=True,
                has_exit_artifact=True,
                has_result_artifact=True,
                proof_artifact=_proof(
                    "proof:archive-cleanup-flowguard-models",
                    "all .flowguard run_checks.py scripts",
                    ".flowguard/run_artifacts/model-regression-archive-cleanup-20260527-190230.out.txt",
                    ("flowguard-models",),
                ),
                inventory_revision="openspec-archive-cleanup-v0.27.0",
                owned_inventory_item_ids=("flowguard-models",),
                run_id="run:archive-cleanup:model-regression:20260527-190230",
                terminal_status="passed",
                result_fingerprint="sha256:A4797D6E33F86CD6F09107F608D843F616825AE0E60D4B263E2C288385559ADD",
                covered_obligation_ids=("flowguard-models",),
                artifact_version="archive-cleanup-20260527-190230",
                verifier_version="flowguard-0.27.0",
            ),
            TestSuiteEvidence(
                "full-regression",
                command="python -m unittest discover -s tests -v",
                layer=TEST_LAYER_PARENT,
                result_status="passed",
                evidence_tier=EVIDENCE_ABSTRACT_GREEN,
                test_count=515,
                selected_count=515,
                exit_code=0,
                result_path=".flowguard/run_artifacts/full-unittest-archive-cleanup-20260527-190230.err.txt",
                background=True,
                has_exit_artifact=True,
                has_result_artifact=True,
                proof_artifact=_proof(
                    "proof:archive-cleanup-full-regression",
                    "python -m unittest discover -s tests -v",
                    ".flowguard/run_artifacts/full-unittest-archive-cleanup-20260527-190230.err.txt",
                    ("full-regression",),
                ),
                inventory_revision="openspec-archive-cleanup-v0.27.0",
                owned_inventory_item_ids=("full-regression",),
                run_id="run:archive-cleanup:full-unittest:20260527-190230",
                terminal_status="passed",
                result_fingerprint="sha256:64DF196BA8F9D67B9790ED4113F7E1592C8101B1D1351CEAFC19FE5DB2EBAA51",
                covered_obligation_ids=("full-regression",),
                artifact_version="archive-cleanup-20260527-190230",
                verifier_version="python-unittest-3.12",
            ),
            TestSuiteEvidence(
                "install-shadow",
                result_status="passed",
                evidence_tier=EVIDENCE_ABSTRACT_GREEN,
                test_count=3,
                selected_count=3,
                result_path=".flowguard/run_artifacts/install-shadow-archive-cleanup.txt",
            ),
            TestSuiteEvidence(
                "adoption-kb",
                result_status="passed",
                evidence_tier=EVIDENCE_ABSTRACT_GREEN,
                test_count=2,
                selected_count=2,
            ),
        ),
        target_split_derivation=TestTargetSplitDerivation(
            "openspec-archive-cleanup-validation",
            target_suite_ids=(
                "openspec-strict",
                "flowguard-models",
                "full-regression",
                "install-shadow",
                "adoption-kb",
            ),
            covered_partition_item_ids=(
                "openspec-strict",
                "flowguard-models",
                "full-regression",
                "install-shadow",
                "adoption-kb",
            ),
            rationale=(
                "The archive cleanup validation separates spec validity, model "
                "regression, full tests, install/shadow sync, and adoption/Kb evidence."
            ),
        ),
        decision_scope=PROCESS_SCOPE_RELEASE,
        release_deferred_allowed=False,
    )
    return review_test_mesh(plan)


def run_review() -> tuple[ArchiveCleanupReview, tuple[object, ...]]:
    reports = (development_process_report(), validation_mesh_report())
    review = ArchiveCleanupReview(*(report.ok for report in reports))
    return review, reports


__all__ = [
    "ArchiveCleanupReview",
    "development_process_report",
    "run_review",
    "validation_mesh_report",
]
