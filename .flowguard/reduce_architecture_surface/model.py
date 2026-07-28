"""FlowGuard model for the public facade architecture reduction."""

from __future__ import annotations

from flowguard.architecture_reduction import (
    CANDIDATE_REMOVE_DUPLICATE_VALIDATION,
    CANDIDATE_DISPOSITION_COMPLETED,
    PROOF_SAFE_BY_PUBLIC_FACADE,
    ROUTE_DEVELOPMENT_PROCESS_FLOW,
    ROUTE_EXISTING_MODEL_PREFLIGHT,
    ROUTE_STRUCTURE_MESH,
    TARGET_ACTION_REMOVE,
    ArchitectureReductionCandidate,
    ArchitectureReductionPlan,
    ArchitectureReductionTrigger,
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
    PROCESS_SCOPE_ROUTINE,
    FreshnessRule,
    ProcessAction,
    ProcessArtifact,
    ProcessEvidence,
    ValidationRequirement,
    DevelopmentProcessPlan,
    review_development_process_flow,
)
from flowguard.code_structure import CodeStructureRecommendation, TargetModuleRecommendation
from flowguard.hierarchy import EVIDENCE_ABSTRACT_GREEN
from flowguard.structuremesh import (
    STRUCTURE_SCOPE_ROUTINE,
    ModuleStructureEvidence,
    PublicEntrypointEvidence,
    StructureMeshPlan,
    StructurePartitionItem,
    review_structure_mesh,
)
from flowguard.testmesh import (
    TEST_LAYER_CHILD,
    TEST_SCOPE_ROUTINE,
    TEST_STATUS_PASSED,
    TestMeshPlan,
    TestPartitionItem,
    TestSuiteEvidence,
    TestTargetSplitDerivation,
    review_test_mesh,
)


SNAPSHOT_BEFORE = ".flowguard/run_artifacts/facade-export-before-reduction-20260527.json"


def target_code_structure() -> CodeStructureRecommendation:
    return CodeStructureRecommendation(
        recommendation_id="public-facade-export-derivation",
        source_model_id="openspec:flowguard-structure-simplification/Public Facade Compatibility",
        source_model_path="openspec/changes/reduce-flowguard-architecture-surface/specs/flowguard-structure-simplification/spec.md",
        parent_module_id="flowguard.__init__",
        facade_module_id="flowguard.__init__",
        target_modules=(
            TargetModuleRecommendation(
                module_id="flowguard.__init__",
                path="flowguard/__init__.py",
                layer="facade",
                owns_function_blocks=("derive_public_exports", "preserve_public_facade"),
                owns_state=("public export set",),
                public_entrypoints=("flowguard.__all__", "from flowguard import *", "flowguard.API_SURFACE"),
                validation_boundaries=("tests/test_api_surface.py", SNAPSHOT_BEFORE),
                rationale="Keep the public facade module while collapsing duplicate export declaration ownership.",
            ),
        ),
        function_block_map=(
            ("derive_public_exports", "flowguard.__init__"),
            ("preserve_public_facade", "flowguard.__init__"),
        ),
        state_owner_map=(("public export set", "flowguard.__init__"),),
        public_entrypoint_map=(
            ("flowguard.__all__", "flowguard.__init__"),
            ("from flowguard import *", "flowguard.__init__"),
            ("flowguard.API_SURFACE", "flowguard.__init__"),
        ),
        validation_boundaries=("tests/test_api_surface.py", "tests/test_public_templates.py", SNAPSHOT_BEFORE),
        rationale="The target structure keeps one facade owner and removes the duplicate manual __all__ declaration.",
    )


def architecture_reduction_plan() -> ArchitectureReductionPlan:
    return ArchitectureReductionPlan(
        reduction_id="reduce-flowguard-architecture-surface/public-facade",
        observable_contract=ObservableArchitectureContract(
            source_model_id="openspec:flowguard-structure-simplification/Public Facade Compatibility",
            source_code_boundary_id="flowguard.__init__:API_SURFACE->__all__",
            public_entrypoints=(
                "import flowguard",
                "from flowguard import *",
                "flowguard.__all__",
                "flowguard.API_SURFACE",
            ),
            observable_outputs=(
                "same flowguard.__all__ public name set",
                "same API_SURFACE group names",
                "same package attributes for exported names",
            ),
            observable_state=("package facade import state",),
            observable_side_effects=("none; template writes and CLI commands remain out of scope for this code node",),
            validation_boundaries=(
                SNAPSHOT_BEFORE,
                "tests/test_api_surface.py",
                "tests/test_public_templates.py",
                "python -m flowguard --help",
                "shadow workspace import check",
            ),
            rationale=(
                "The current code declares API_SURFACE groups and then repeats nearly all names in a second "
                "manual __all__ list. The target removes the duplicate declaration while keeping the public "
                "facade as the compatibility boundary."
            ),
        ),
        companion_route_triggers=(
            ArchitectureReductionTrigger(
                route_id=ROUTE_EXISTING_MODEL_PREFLIGHT,
                trigger_reason="Existing OpenSpec spec owns public facade compatibility.",
                complexity_signal="duplicate public export declaration",
                recommended_timing="before production edit",
                required=True,
            ),
            ArchitectureReductionTrigger(
                route_id=ROUTE_DEVELOPMENT_PROCESS_FLOW,
                trigger_reason="The work changes a public compatibility facade and needs fresh validation evidence.",
                complexity_signal="public API claim depends on test and install freshness",
                recommended_timing="before done claim",
                required=True,
            ),
        ),
        candidates=(
            ArchitectureReductionCandidate(
                candidate_id="derive-__all__-from-api-surface",
                candidate_type=CANDIDATE_REMOVE_DUPLICATE_VALIDATION,
                code_node_id="flowguard.__init__.__all__",
                source_model_element="Public Facade Compatibility",
                target_action=TARGET_ACTION_REMOVE,
                proof_status=PROOF_SAFE_BY_PUBLIC_FACADE,
                required_next_route=ROUTE_STRUCTURE_MESH,
                rationale=(
                    "Remove the second full manual export declaration and derive it from API_SURFACE plus "
                    "a small explicit supplement. The public facade and public name set stay observable."
                ),
                affected_public_entrypoints=("flowguard.__all__", "from flowguard import *"),
                evidence_refs=(SNAPSHOT_BEFORE, "tests/test_api_surface.py", ".flowguard/behavior_commitment_ledger/ledger.json"),
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
                lifecycle_disposition=CANDIDATE_DISPOSITION_COMPLETED,
                completion_evidence_refs=(
                    ".flowguard/run_artifacts/facade-export-after-reduction-20260527.json",
                    ".flowguard/run_artifacts/reduce-architecture-surface-post-code.txt",
                    ".flowguard/run_artifacts/api-template-post-code-targeted.txt",
                ),
                metadata={"before_all_count": 716, "before_api_surface_count": 688, "before_supplement_count": 28},
            ),
        ),
        target_structure=target_code_structure(),
        rationale="Shrink duplicated public API declaration without removing public behavior.",
    )


def structure_mesh_plan() -> StructureMeshPlan:
    return StructureMeshPlan(
        parent_module_id="flowguard.__init__",
        decision_scope=STRUCTURE_SCOPE_ROUTINE,
        partition_items=(
            StructurePartitionItem(
                item_id="API_SURFACE",
                item_type="public-api-groups",
                owner_module_id="flowguard.__init__",
                public_surface=True,
                old_path="flowguard/__init__.py",
                new_path="flowguard/__init__.py",
                description="Canonical grouped public API declaration.",
            ),
            StructurePartitionItem(
                item_id="manual-__all__-bulk-list",
                item_type="duplicate-export-declaration",
                owner_module_id="flowguard.__init__",
                public_surface=True,
                old_path="flowguard/__init__.py",
                new_path="flowguard/__init__.py",
                description="Duplicate hand-maintained public export list to be collapsed.",
            ),
            StructurePartitionItem(
                item_id="PUBLIC_API_SUPPLEMENT",
                item_type="public-api-supplement",
                owner_module_id="flowguard.__init__",
                public_surface=True,
                old_path="flowguard/__init__.py",
                new_path="flowguard/__init__.py",
                description="Small explicit export set for compatibility names outside API_SURFACE groups.",
            ),
        ),
        child_modules=(
            ModuleStructureEvidence(
                module_id="flowguard.__init__",
                path="flowguard/__init__.py",
                layer="facade",
                owns_functions=("API_SURFACE", "PUBLIC_API_SUPPLEMENT", "__all__"),
                behavior_contracts=("same exported name set", "same package attributes"),
                dependencies=("flowguard module imports",),
                facade_retained=True,
                behavior_parity_current=True,
                behavior_parity_tier=EVIDENCE_ABSTRACT_GREEN,
            ),
        ),
        public_entrypoints=(
            PublicEntrypointEvidence(
                entrypoint_id="flowguard.__all__",
                entrypoint_type="package-facade",
                old_path="flowguard/__init__.py",
                new_path="flowguard/__init__.py",
                compatibility_preserved=True,
                facade_available=True,
                parity_evidence_current=True,
                parity_evidence_tier=EVIDENCE_ABSTRACT_GREEN,
                evidence_path=SNAPSHOT_BEFORE,
            ),
            PublicEntrypointEvidence(
                entrypoint_id="from flowguard import *",
                entrypoint_type="package-import",
                old_path="flowguard/__init__.py",
                new_path="flowguard/__init__.py",
                compatibility_preserved=True,
                facade_available=True,
                parity_evidence_current=True,
                parity_evidence_tier=EVIDENCE_ABSTRACT_GREEN,
                evidence_path="tests/test_api_surface.py",
            ),
        ),
        target_structure=target_code_structure(),
    )


def development_process_plan() -> DevelopmentProcessPlan:
    return DevelopmentProcessPlan(
        process_id="reduce-flowguard-architecture-surface/pre-code",
        decision_scope=PROCESS_SCOPE_ROUTINE,
        artifacts=(
            ProcessArtifact("openspec-change", PROCESS_ARTIFACT_REQUIREMENT, "proposal-design-spec-tasks", "openspec/changes/reduce-flowguard-architecture-surface"),
            ProcessArtifact("flowguard-reduction-model", PROCESS_ARTIFACT_MODEL, "pre-code", ".flowguard/reduce_architecture_surface/model.py"),
            ProcessArtifact("export-snapshot-before", PROCESS_ARTIFACT_TEST, "before", SNAPSHOT_BEFORE),
            ProcessArtifact("public-facade-code", PROCESS_ARTIFACT_CODE, "pre-edit", "flowguard/__init__.py"),
            ProcessArtifact("api-tests", PROCESS_ARTIFACT_TEST, "pre-edit", "tests/test_api_surface.py"),
            ProcessArtifact("design-contract", PROCESS_ARTIFACT_DESIGN, "current", "openspec/changes/reduce-flowguard-architecture-surface/design.md"),
        ),
        actions=(
            ProcessAction(
                "create-openspec-change",
                action_type="requirements",
                writes_artifacts=("openspec-change", "design-contract"),
                description="Define the narrow public facade contraction scope.",
            ),
            ProcessAction(
                "capture-before-export-snapshot",
                action_type="validation",
                reads_artifacts=("public-facade-code",),
                writes_artifacts=("export-snapshot-before",),
                produced_evidence_ids=("evidence:export-snapshot-before",),
                order_after=("create-openspec-change",),
                description="Capture the pre-change public export set.",
            ),
            ProcessAction(
                "run-pre-code-flowguard-model",
                action_type="validation",
                reads_artifacts=("openspec-change", "flowguard-reduction-model", "export-snapshot-before"),
                produced_evidence_ids=("evidence:pre-code-flowguard-model",),
                required_evidence_ids=("evidence:export-snapshot-before",),
                order_after=("capture-before-export-snapshot",),
                description="Review reduction, structure mesh, process, and test mesh before editing.",
            ),
        ),
        evidence=(
            ProcessEvidence(
                "evidence:export-snapshot-before",
                evidence_kind="snapshot",
                status=PROCESS_EVIDENCE_PASSED,
                covers_artifacts=("public-facade-code", "export-snapshot-before"),
                covered_versions={"public-facade-code": "pre-edit", "export-snapshot-before": "before"},
                validation_requirement_ids=("require-before-snapshot",),
                produced_by_action_id="capture-before-export-snapshot",
                command="capture flowguard.__all__ and API_SURFACE before code edit",
                result_path=SNAPSHOT_BEFORE,
            ),
            ProcessEvidence(
                "evidence:pre-code-flowguard-model",
                evidence_kind="model-review",
                status=PROCESS_EVIDENCE_PASSED,
                covers_artifacts=("openspec-change", "flowguard-reduction-model", "export-snapshot-before"),
                covered_versions={
                    "openspec-change": "proposal-design-spec-tasks",
                    "flowguard-reduction-model": "pre-code",
                    "export-snapshot-before": "before",
                },
                validation_requirement_ids=("require-pre-code-model-review",),
                produced_by_action_id="run-pre-code-flowguard-model",
                command="python .flowguard/reduce_architecture_surface/run_checks.py",
                result_path=".flowguard/run_artifacts/reduce-architecture-surface-pre-code.txt",
            ),
        ),
        validation_requirements=(
            ValidationRequirement(
                "require-before-snapshot",
                required_artifact_ids=("public-facade-code",),
                required_evidence_kinds=("snapshot",),
                evidence_ids=("evidence:export-snapshot-before",),
                command="capture public export snapshot",
            ),
            ValidationRequirement(
                "require-pre-code-model-review",
                required_artifact_ids=("openspec-change", "flowguard-reduction-model"),
                required_evidence_kinds=("model-review",),
                evidence_ids=("evidence:pre-code-flowguard-model",),
                command="python .flowguard/reduce_architecture_surface/run_checks.py",
            ),
        ),
        freshness_rules=(
            FreshnessRule(
                "facade-code-stales-public-api-evidence",
                upstream_artifact_id="public-facade-code",
                invalidates_evidence_kinds=("api-test", "snapshot", "install-check", "shadow-check"),
                description="After editing flowguard.__init__, rerun public API, install, and shadow checks.",
            ),
        ),
    )


def test_mesh_plan() -> TestMeshPlan:
    return TestMeshPlan(
        parent_suite_id="reduce-flowguard-architecture-surface-validation",
        decision_scope=TEST_SCOPE_ROUTINE,
        partition_items=(
            TestPartitionItem(
                "export-snapshot-before",
                item_type="snapshot",
                owner_suite_id="public-export-snapshot",
                touched_paths=("flowguard/__init__.py",),
                description="Before-change public export set.",
            ),
            TestPartitionItem(
                "api-surface-targeted",
                item_type="targeted-test",
                owner_suite_id="api-surface-tests",
                touched_paths=("flowguard/__init__.py", "tests/test_api_surface.py"),
                description="Targeted facade parity tests required after edit.",
            ),
        ),
        child_suites=(
            TestSuiteEvidence(
                "public-export-snapshot",
                command="capture flowguard.__all__ and API_SURFACE before edit",
                layer=TEST_LAYER_CHILD,
                result_status=TEST_STATUS_PASSED,
                evidence_tier=EVIDENCE_ABSTRACT_GREEN,
                result_path=SNAPSHOT_BEFORE,
                owns_state=("public export set",),
            ),
            TestSuiteEvidence(
                "pre-code-flowguard-model",
                command="python .flowguard/reduce_architecture_surface/run_checks.py",
                layer=TEST_LAYER_CHILD,
                result_status=TEST_STATUS_PASSED,
                evidence_tier=EVIDENCE_ABSTRACT_GREEN,
                result_path=".flowguard/run_artifacts/reduce-architecture-surface-pre-code.txt",
                owns_state=("candidate proof status",),
            ),
            TestSuiteEvidence(
                "api-surface-tests",
                command="python -m unittest tests.test_api_surface tests.test_public_templates -v",
                layer=TEST_LAYER_CHILD,
                result_status=TEST_STATUS_PASSED,
                evidence_tier=EVIDENCE_ABSTRACT_GREEN,
                test_count=25,
                selected_count=25,
                result_path=".flowguard/run_artifacts/api-template-pre-code-targeted.txt",
                owns_state=("public export set",),
            ),
        ),
        target_split_derivation=TestTargetSplitDerivation(
            source_model_id="openspec:flowguard-structure-simplification/Public Facade Compatibility",
            target_suite_ids=("public-export-snapshot", "pre-code-flowguard-model", "api-surface-tests"),
            covered_partition_item_ids=("export-snapshot-before", "api-surface-targeted"),
            state_owner_fields=("public export set", "candidate proof status"),
            source_model_path=".flowguard/reduce_architecture_surface/model.py",
            rationale="Split facade validation into snapshot parity, model proof, and targeted API/template compatibility checks.",
        ),
        allowed_shared_state=("public export set",),
    )


def run_checks():
    return (
        review_architecture_reduction(architecture_reduction_plan()),
        review_structure_mesh(structure_mesh_plan()),
        review_development_process_flow(development_process_plan()),
        review_test_mesh(test_mesh_plan()),
    )
