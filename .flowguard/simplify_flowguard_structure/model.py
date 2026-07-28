"""FlowGuard model for the FlowGuard structure simplification pass.

FlowGuard Risk Purpose Header
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: review a narrow self-refactor of FlowGuard before and after
implementation. It guards against deleting public facade exports, treating
CLI command wrapper consolidation as safe without StructureMesh/parity
evidence, deleting peer-created artifacts during shadow sync, and claiming
background regression success from progress alone.
Guards against: public API drift, CLI template behavior drift, stale install
sync, hidden duplicate-artifact cleanup, and overclaiming validation evidence.
Use before editing: run this model before touching `flowguard/__main__.py` and
rerun after focused tests, install sync, and shadow verification.
Run: python .flowguard/simplify_flowguard_structure/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass

from flowguard import (
    CANDIDATE_KEEP_PUBLIC_FACADE,
    CANDIDATE_DISPOSITION_COMPLETED,
    CANDIDATE_DISPOSITION_HISTORICAL,
    CANDIDATE_MERGE_HANDLERS,
    CANDIDATE_REMOVE_BRANCH,
    EVIDENCE_ABSTRACT_GREEN,
    ExistingModelPreflight,
    ExistingOwnershipSnapshot,
    ModelContextHit,
    ModuleStructureEvidence,
    ObservableArchitectureContract,
    PROCESS_ARTIFACT_CODE,
    PROCESS_ARTIFACT_MODEL,
    PROCESS_ARTIFACT_REQUIREMENT,
    PROCESS_ARTIFACT_TEST,
    PROCESS_EVIDENCE_PASSED,
    PublicEntrypointEvidence,
    REUSE_DECISION_REUSE_EXISTING,
    ROUTE_CODE_STRUCTURE_RECOMMENDATION,
    ROUTE_DEVELOPMENT_PROCESS_FLOW,
    ROUTE_MANUAL_REVIEW,
    ROUTE_STRUCTURE_MESH,
    STRUCTURE_SCOPE_ROUTINE,
    TARGET_ACTION_KEEP_FACADE,
    TARGET_ACTION_MERGE,
    TARGET_ACTION_REMOVE,
    TEST_LAYER_CODE_BOUNDARY_CONFORMANCE,
    ArchitectureReductionCandidate,
    ArchitectureReductionPlan,
    ArchitectureReductionTrigger,
    CodeStructureRecommendation,
    DevelopmentProcessPlan,
    ProcessAction,
    ProcessArtifact,
    ProcessEvidence,
    StructureMeshPlan,
    StructurePartitionItem,
    TargetModuleRecommendation,
    TestMeshPlan,
    TestPartitionItem,
    TestSuiteEvidence,
    TestTargetSplitDerivation,
    ValidationRequirement,
    review_architecture_reduction,
    review_development_process_flow,
    review_existing_model_preflight,
    review_structure_mesh,
    review_test_mesh,
)


TEMPLATE_COMMANDS = (
    "project-template",
    "risk-intent-template",
    "model-miss-template",
    "model-test-alignment-template",
    "code-structure-recommendation-template",
    "ui-flow-structure-template",
    "development-process-flow-template",
    "existing-model-preflight-template",
    "risk-evidence-ledger-template",
    "layered-boundary-proof-template",
    "test-mesh-template",
    "structure-mesh-template",
    "maintenance-template",
)


@dataclass(frozen=True)
class SimplificationReview:
    existing_model_ok: bool
    architecture_ok: bool
    structure_ok: bool
    process_ok: bool
    test_mesh_ok: bool

    @property
    def ok(self) -> bool:
        return all(
            (
                self.existing_model_ok,
                self.architecture_ok,
                self.structure_ok,
                self.process_ok,
                self.test_mesh_ok,
            )
        )


def observable_contract() -> ObservableArchitectureContract:
    return ObservableArchitectureContract(
        source_model_id="simplify-flowguard-structure",
        source_code_boundary_id="flowguard package CLI and public facade",
        public_entrypoints=(
            "from flowguard import ... API_SURFACE names",
            "python -m flowguard *-template commands",
        ),
        observable_outputs=(
            "template JSON stdout envelopes",
            "flowguard_template_write JSON envelopes",
            "API_SURFACE and __all__ package attributes",
        ),
        observable_state=(
            ".flowguard/adoption_log.jsonl for adoption commands",
            "docs/flowguard_adoption_log.md for adoption commands",
        ),
        observable_side_effects=("template file writes when --output is supplied",),
        validation_boundaries=(
            "tests.test_public_templates",
            "tests.test_maintenance_template",
            "tests.test_api_surface",
            ".flowguard/simplify_flowguard_structure/run_checks.py",
        ),
        rationale=(
            "The simplification may reduce internal command-wrapper repetition, "
            "but public imports, command names, outputs, and file-writing "
            "side effects define the behavior contract."
        ),
    )


def existing_model_preflight_report():
    preflight = ExistingModelPreflight(
        "simplify-flowguard-structure-preflight",
        "Simplify FlowGuard CLI/template wrapper structure while preserving public behavior.",
        mode="full",
        model_search_performed=True,
        search_paths=(
            ".flowguard/architecture_reduction/model.py",
            ".flowguard/existing_model_preflight/model.py",
            ".flowguard/structure_refactor_mesh/model.py",
            "docs/structure_mesh.md",
        ),
        relevant_models=(
            ModelContextHit(
                model_id="architecture_reduction",
                model_path=".flowguard/architecture_reduction/model.py",
                evidence_id="architecture_reduction:current",
                evidence_tier="abstract_green",
                responsibilities=(
                    "classify contraction candidates",
                    "keep proof status and next route visible",
                ),
                function_blocks=("EvaluateArchitectureReductionPlan",),
                state_owned=("ArchitectureReductionPolicy",),
                public_entrypoints=("review_architecture_reduction",),
                validation_evidence=("python .flowguard/architecture_reduction/run_checks.py",),
            ),
            ModelContextHit(
                model_id="structure_refactor_mesh",
                model_path=".flowguard/structure_refactor_mesh/model.py",
                evidence_id="structure_refactor_mesh:current",
                evidence_tier="abstract_green",
                responsibilities=(
                    "preserve public entrypoints",
                    "review target module ownership and parity evidence",
                ),
                function_blocks=("EvaluateStructureMeshPlan",),
                state_owned=("StructureMeshPolicy",),
                public_entrypoints=("review_structure_mesh",),
                validation_evidence=("python -m unittest tests.test_structure_mesh",),
            ),
        ),
        ownership_snapshot=ExistingOwnershipSnapshot(
            function_block_owners=(
                ("EvaluateArchitectureReductionPlan", "architecture_reduction"),
                ("EvaluateStructureMeshPlan", "structure_refactor_mesh"),
            ),
            state_owners=(
                ("ArchitectureReductionPolicy", "architecture_reduction"),
                ("StructureMeshPolicy", "structure_refactor_mesh"),
            ),
            public_entrypoint_owners=(
                ("review_architecture_reduction", "architecture_reduction"),
                ("review_structure_mesh", "structure_refactor_mesh"),
            ),
        ),
        reuse_decision=REUSE_DECISION_REUSE_EXISTING,
        downstream_routes=("architecture_reduction", "structure_mesh_maintenance", "development_process_flow"),
        rationale="Existing FlowGuard routes own this self-refactor; no new behavior boundary is needed.",
    )
    return review_existing_model_preflight(preflight)


def target_structure() -> CodeStructureRecommendation:
    return CodeStructureRecommendation(
        "flowguard-cli-template-target-structure",
        source_model_id="simplify-flowguard-structure",
        source_model_path=".flowguard/simplify_flowguard_structure/model.py",
        parent_module_id="flowguard",
        target_modules=(
            TargetModuleRecommendation(
                "cli_template_registry",
                path="flowguard/__main__.py",
                owns_function_blocks=("RegisterTemplateCommands", "DispatchTemplateCommand"),
                public_entrypoints=TEMPLATE_COMMANDS,
                validation_boundaries=(
                    "tests.test_public_templates.PublicTemplateTests.test_template_cli_prints_and_writes_new_templates",
                    "tests.test_maintenance_template.MaintenanceWorkflowTemplateTests.test_cli_prints_and_writes_template",
                ),
                rationale="The registry owns repeated template-command parser wiring and dispatch.",
            ),
            TargetModuleRecommendation(
                "public_facade",
                path="flowguard/__init__.py",
                owns_function_blocks=("ExposeApiSurface",),
                public_entrypoints=("from flowguard import ... API_SURFACE names",),
                validation_boundaries=("tests.test_api_surface",),
                rationale="The broad facade remains intact while internals simplify behind it.",
            ),
            TargetModuleRecommendation(
                "shadow_artifact_sync",
                path=".flowguard",
                owns_function_blocks=("RemoveDuplicateShadowModelCopy",),
                validation_boundaries=("manual bounded sync check",),
                rationale="Shadow-only duplicate artifacts are local cleanup, not package behavior.",
            ),
        ),
        function_block_map=(
            ("RegisterTemplateCommands", "cli_template_registry"),
            ("DispatchTemplateCommand", "cli_template_registry"),
            ("ExposeApiSurface", "public_facade"),
            ("RemoveDuplicateShadowModelCopy", "shadow_artifact_sync"),
        ),
        public_entrypoint_map=tuple((command, "cli_template_registry") for command in TEMPLATE_COMMANDS)
        + (("from flowguard import ... API_SURFACE names", "public_facade"),),
        facade_module_id="public_facade",
        validation_boundaries=(
            "tests.test_public_templates",
            "tests.test_maintenance_template",
            "tests.test_api_surface",
        ),
        rationale="The model separates CLI template registration from the public import facade and local sync cleanup.",
        hierarchical_model_used=True,
    )


def architecture_reduction_report():
    plan = ArchitectureReductionPlan(
        "flowguard-cli-template-architecture-reduction",
        observable_contract=observable_contract(),
        candidates=(
            ArchitectureReductionCandidate(
                candidate_id="merge-template-command-wrapper-functions",
                candidate_type=CANDIDATE_MERGE_HANDLERS,
                code_node_id="flowguard.__main__ template command wrappers",
                source_model_element="RegisterTemplateCommands",
                target_action=TARGET_ACTION_MERGE,
                proof_status="safe_by_public_facade",
                required_next_route=ROUTE_STRUCTURE_MESH,
                rationale="Command names and public behavior stay behind the same CLI facade while repeated wrappers merge.",
                affected_public_entrypoints=TEMPLATE_COMMANDS,
                affected_side_effects=("template file writes when --output is supplied",),
                evidence_refs=(
                    "tests.test_public_templates",
                    "tests.test_maintenance_template",
                    "tests.test_api_surface",
                    ".flowguard/behavior_commitment_ledger/ledger.json",
                ),
                business_intent_id="intent:flowguard-template-cli-dispatch",
                behavior_commitment_id="commitment:flowguard-template-cli-dispatch",
                primary_path_id="path:flowguard-template-cli:registry-dispatch",
                inventory_revision="2026-07-12-plane-partition-and-facade-authority",
                owner_code_contract_id="contract:flowguard-template-cli-dispatch",
                delegates_to_code_contract_id="contract:flowguard-template-cli-dispatch",
                delegates_to_primary_path_id="path:flowguard-template-cli:registry-dispatch",
                delegation_evidence_id="proof:flowguard-template-cli-dispatch-current",
                delegation_evidence_current=True,
                delegation_only=True,
                independent_business_authority=False,
                lifecycle_disposition=CANDIDATE_DISPOSITION_COMPLETED,
                completion_evidence_refs=(
                    "flowguard/__main__.py:FILE_TEMPLATE_COMMANDS",
                    ".flowguard/run_artifacts/full-unittest-20260527-165800.out.txt",
                    "docs/flowguard_adoption_log.md#simplify-flowguard-structure-final-sync",
                ),
            ),
            ArchitectureReductionCandidate(
                candidate_id="keep-flowguard-public-import-facade",
                candidate_type=CANDIDATE_KEEP_PUBLIC_FACADE,
                code_node_id="flowguard.__init__",
                source_model_element="ExposeApiSurface",
                target_action=TARGET_ACTION_KEEP_FACADE,
                proof_status="safe_by_public_facade",
                required_next_route=ROUTE_STRUCTURE_MESH,
                rationale="The public import facade remains the stable compatibility boundary.",
                affected_public_entrypoints=("from flowguard import ... API_SURFACE names",),
                evidence_refs=("tests.test_api_surface", ".flowguard/behavior_commitment_ledger/ledger.json"),
                business_intent_id="intent:flowguard-public-api-surface",
                behavior_commitment_id="commitment:flowguard-public-api-surface",
                primary_path_id="path:flowguard-public-api:api-surface-facade",
                inventory_revision="2026-07-12-plane-partition-and-facade-authority",
                owner_code_contract_id="contract:flowguard-public-api-surface",
                delegates_to_code_contract_id="contract:flowguard-public-api-surface",
                delegates_to_primary_path_id="path:flowguard-public-api:api-surface-facade",
                delegation_evidence_id="proof:flowguard-public-api-surface-current",
                delegation_evidence_current=True,
                delegation_only=True,
                independent_business_authority=False,
                lifecycle_disposition=CANDIDATE_DISPOSITION_HISTORICAL,
                completion_evidence_refs=(
                    "tests/test_api_surface.py",
                    "flowguard/__init__.py:API_SURFACE",
                ),
            ),
            ArchitectureReductionCandidate(
                candidate_id="remove-shadow-only-duplicate-flowguard-artifact",
                candidate_type=CANDIDATE_REMOVE_BRANCH,
                code_node_id=".flowguard/*/* duplicate shadow artifact",
                source_model_element="RemoveDuplicateShadowModelCopy",
                target_action=TARGET_ACTION_REMOVE,
                proof_status="safe_by_equivalence",
                required_next_route=ROUTE_MANUAL_REVIEW,
                rationale="Duplicate nested shadow artifacts are local workspace sync cleanup and have no package behavior.",
                evidence_refs=("bounded shadow sync check",),
                lifecycle_disposition=CANDIDATE_DISPOSITION_COMPLETED,
                completion_evidence_refs=(
                    "docs/flowguard_adoption_log.md#simplify-flowguard-structure-final-sync",
                    "bounded shadow sync check",
                ),
            ),
        ),
        companion_route_triggers=(
            ArchitectureReductionTrigger(
                route_id=ROUTE_DEVELOPMENT_PROCESS_FLOW,
                trigger_reason="Staged self-refactor with validation and install/shadow sync freshness requirements.",
                complexity_signal="repeated template command wrappers and shadow duplicate model artifact",
                recommended_timing="before implementation and before done claim",
                required=True,
            ),
            ArchitectureReductionTrigger(
                route_id=ROUTE_CODE_STRUCTURE_RECOMMENDATION,
                trigger_reason="Target ownership must keep CLI registry, public facade, and shadow cleanup separate.",
                complexity_signal="public entrypoint plus local sync cleanup in one task",
                recommended_timing="before StructureMesh evidence",
                required=True,
            ),
        ),
        target_structure=target_structure(),
        rationale="This pass contracts repeated CLI template wrapper code while keeping public behavior stable.",
    )
    return review_architecture_reduction(plan)


def structure_mesh_report():
    plan = StructureMeshPlan(
        parent_module_id="flowguard",
        target_structure=target_structure(),
        partition_items=(
            StructurePartitionItem(
                "template_commands",
                item_type="public_cli",
                owner_module_id="cli_template_registry",
                public_surface=True,
                old_path="flowguard/__main__.py",
                new_path="flowguard/__main__.py",
            ),
            StructurePartitionItem(
                "api_surface",
                item_type="public_import_facade",
                owner_module_id="public_facade",
                public_surface=True,
                old_path="flowguard/__init__.py",
                new_path="flowguard/__init__.py",
            ),
            StructurePartitionItem(
                "shadow_duplicate_artifact",
                item_type="local_artifact",
                owner_module_id="shadow_artifact_sync",
                old_path=".flowguard/*/* duplicate shadow artifact",
                new_path="",
            ),
        ),
        child_modules=(
            ModuleStructureEvidence(
                "cli_template_registry",
                path="flowguard/__main__.py",
                layer="child",
                extracted_from="flowguard/__main__.py",
                owns_functions=("RegisterTemplateCommands", "DispatchTemplateCommand"),
                behavior_contracts=("template command stdout/write parity",),
                behavior_parity_tier=EVIDENCE_ABSTRACT_GREEN,
            ),
            ModuleStructureEvidence(
                "public_facade",
                path="flowguard/__init__.py",
                layer="facade",
                owns_functions=("ExposeApiSurface",),
                behavior_contracts=("API_SURFACE/__all__ compatibility",),
                facade_retained=True,
                behavior_parity_tier=EVIDENCE_ABSTRACT_GREEN,
            ),
            ModuleStructureEvidence(
                "shadow_artifact_sync",
                path=".flowguard",
                layer="child",
                owns_functions=("RemoveDuplicateShadowModelCopy",),
                behavior_contracts=("bounded sync cleanup only",),
                behavior_parity_tier=EVIDENCE_ABSTRACT_GREEN,
            ),
        ),
        public_entrypoints=(
            PublicEntrypointEvidence(
                "python -m flowguard *-template",
                entrypoint_type="cli",
                old_path="flowguard/__main__.py",
                new_path="flowguard/__main__.py",
                evidence_path="tests/test_public_templates.py; tests/test_maintenance_template.py",
            ),
            PublicEntrypointEvidence(
                "from flowguard import API_SURFACE names",
                entrypoint_type="import",
                old_path="flowguard/__init__.py",
                new_path="flowguard/__init__.py",
                evidence_path="tests/test_api_surface.py",
            ),
        ),
        required_evidence_tier=EVIDENCE_ABSTRACT_GREEN,
        decision_scope=STRUCTURE_SCOPE_ROUTINE,
    )
    return review_structure_mesh(plan)


def development_process_report():
    plan = DevelopmentProcessPlan(
        "simplify-flowguard-structure-lifecycle",
        artifacts=(
            ProcessArtifact("openspec.simplify-flowguard-structure", PROCESS_ARTIFACT_REQUIREMENT, "1"),
            ProcessArtifact("model.simplify-flowguard-structure", PROCESS_ARTIFACT_MODEL, "1"),
            ProcessArtifact("code.flowguard.__main__", PROCESS_ARTIFACT_CODE, "2"),
            ProcessArtifact("tests.template-cli", PROCESS_ARTIFACT_TEST, "2"),
            ProcessArtifact("install.editable", "install", "1"),
            ProcessArtifact("workspace.shadow", "workspace", "1"),
        ),
        actions=(
            ProcessAction("write-openspec-and-model", writes_artifacts=("openspec.simplify-flowguard-structure", "model.simplify-flowguard-structure")),
            ProcessAction("edit-cli-registry", writes_artifacts=("code.flowguard.__main__", "tests.template-cli")),
            ProcessAction("run-focused-validation", produced_evidence_ids=("focused-tests-pass",)),
            ProcessAction("run-background-regression", produced_evidence_ids=("broad-regression-pass",)),
            ProcessAction("sync-install-and-shadow", writes_artifacts=("install.editable", "workspace.shadow"), produced_evidence_ids=("install-shadow-pass",)),
            ProcessAction(
                "claim-done",
                action_type="claim_done",
                required_validation_ids=("focused-current", "regression-final", "install-shadow-current"),
            ),
        ),
        evidence=(
            ProcessEvidence(
                "focused-tests-pass",
                evidence_kind="unit",
                status=PROCESS_EVIDENCE_PASSED,
                covers_artifacts=("code.flowguard.__main__", "tests.template-cli", "model.simplify-flowguard-structure"),
                covered_versions={
                    "code.flowguard.__main__": "2",
                    "tests.template-cli": "2",
                    "model.simplify-flowguard-structure": "1",
                },
                validation_requirement_ids=("focused-current",),
                produced_by_action_id="run-focused-validation",
            ),
            ProcessEvidence(
                "broad-regression-pass",
                evidence_kind="regression",
                status=PROCESS_EVIDENCE_PASSED,
                covers_artifacts=("code.flowguard.__main__", "tests.template-cli"),
                covered_versions={"code.flowguard.__main__": "2", "tests.template-cli": "2"},
                validation_requirement_ids=("regression-final",),
                produced_by_action_id="run-background-regression",
            ),
            ProcessEvidence(
                "install-shadow-pass",
                evidence_kind="install_sync",
                status=PROCESS_EVIDENCE_PASSED,
                covers_artifacts=("install.editable", "workspace.shadow"),
                covered_versions={"install.editable": "1", "workspace.shadow": "1"},
                validation_requirement_ids=("install-shadow-current",),
                produced_by_action_id="sync-install-and-shadow",
            ),
        ),
        validation_requirements=(
            ValidationRequirement(
                "focused-current",
                required_artifact_ids=("code.flowguard.__main__", "tests.template-cli"),
                required_evidence_kinds=("unit",),
                evidence_ids=("focused-tests-pass",),
                v_model_pair=True,
            ),
            ValidationRequirement(
                "regression-final",
                required_artifact_ids=("code.flowguard.__main__", "tests.template-cli"),
                required_evidence_kinds=("regression",),
                evidence_ids=("broad-regression-pass",),
            ),
            ValidationRequirement(
                "install-shadow-current",
                required_artifact_ids=("install.editable", "workspace.shadow"),
                required_evidence_kinds=("install_sync",),
                evidence_ids=("install-shadow-pass",),
            ),
        ),
    )
    return review_development_process_flow(plan)


def test_mesh_report():
    plan = TestMeshPlan(
        parent_suite_id="simplify-flowguard-structure-validation",
        partition_items=(
            TestPartitionItem("flowguard-model", owner_suite_id="flowguard-model"),
            TestPartitionItem("template-cli-parity", owner_suite_id="template-cli-parity"),
            TestPartitionItem("api-surface", owner_suite_id="api-surface"),
            TestPartitionItem("install-shadow-sync", owner_suite_id="install-shadow-sync"),
        ),
        child_suites=(
            TestSuiteEvidence(
                "flowguard-model",
                result_status="passed",
                evidence_tier=EVIDENCE_ABSTRACT_GREEN,
                test_count=1,
                selected_count=1,
            ),
            TestSuiteEvidence(
                "template-cli-parity",
                layer=TEST_LAYER_CODE_BOUNDARY_CONFORMANCE,
                result_status="passed",
                evidence_tier=EVIDENCE_ABSTRACT_GREEN,
                test_count=2,
                selected_count=2,
            ),
            TestSuiteEvidence(
                "api-surface",
                result_status="passed",
                evidence_tier=EVIDENCE_ABSTRACT_GREEN,
                test_count=1,
                selected_count=1,
            ),
            TestSuiteEvidence(
                "install-shadow-sync",
                result_status="passed",
                evidence_tier=EVIDENCE_ABSTRACT_GREEN,
                test_count=2,
                selected_count=2,
                background=False,
                has_exit_artifact=True,
                has_result_artifact=True,
            ),
        ),
        target_split_derivation=TestTargetSplitDerivation(
            "simplify-flowguard-structure-validation",
            target_suite_ids=(
                "flowguard-model",
                "template-cli-parity",
                "api-surface",
                "install-shadow-sync",
            ),
            covered_partition_item_ids=(
                "flowguard-model",
                "template-cli-parity",
                "api-surface",
                "install-shadow-sync",
            ),
            rationale="The validation mesh separates model checks, CLI parity, API facade, and install/shadow sync evidence.",
        ),
    )
    return review_test_mesh(plan)


def run_review() -> tuple[SimplificationReview, tuple[object, ...]]:
    reports = (
        existing_model_preflight_report(),
        architecture_reduction_report(),
        structure_mesh_report(),
        development_process_report(),
        test_mesh_report(),
    )
    review = SimplificationReview(*(report.ok for report in reports))
    return review, reports


__all__ = [
    "SimplificationReview",
    "TEMPLATE_COMMANDS",
    "architecture_reduction_report",
    "development_process_report",
    "existing_model_preflight_report",
    "observable_contract",
    "run_review",
    "structure_mesh_report",
    "target_structure",
    "test_mesh_report",
]
