"""Closure models for ordinary UI content admission.

FlowGuard Risk Purpose Header
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: bind the UI visibility admission obligation to its implementation,
current child-model results, focused tests, the finite contract matrix,
TestMesh ownership, and final risk gates.
"""

from __future__ import annotations

import hashlib
import os
import xml.etree.ElementTree as ET
from pathlib import Path

from flowguard import (
    CODE_CONTRACT_ROLE_OWNER,
    EVIDENCE_CONFORMANCE_GREEN,
    RISK_GATE_CONTRACT_COVERAGE_SHARD,
    RISK_GATE_TEST_SPLIT,
    RISK_GATE_UI_FUNCTIONAL_CHAIN,
    RISK_GATE_UI_HUMAN_OPERABILITY,
    RISK_GATE_UI_IMPLEMENTATION,
    RISK_GATE_UI_REAL_SURFACE,
    RISK_PROOF_STATUS_PASSED,
    TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
    TEST_KIND_FAILURE_PATH,
    TEST_KIND_HAPPY_PATH,
    TEST_LAYER_CONTRACT_COMBINATION_SHARD,
    CodeContract,
    ModelObligation,
    ModelTestAlignmentPlan,
    ProofArtifactRef,
    RiskEvidenceGate,
    RiskEvidenceLedgerPlan,
    RiskEvidenceProof,
    RiskEvidenceRow,
    TestEvidence,
    TestMeshPlan,
    TestPartitionItem,
    TestSuiteEvidence,
    TestTargetSplitDerivation,
)
from flowguard.contract_exhaustion import (
    CONTRACT_ORACLE_NEEDS_HUMAN_REVIEW,
    CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
    CONTRACT_ROUTE_RISK_EVIDENCE_LEDGER,
    CONTRACT_ROUTE_TEST_MESH,
    ContractAxis,
    ContractCoverageUniverse,
    ContractExhaustionPlan,
    ContractInteractionGroup,
    contract_exhaustion_to_test_mesh_shard_ids,
    review_contract_exhaustion,
)


ROOT = Path(__file__).resolve().parents[2]
_RUN_OUTPUT_DIR = os.environ.get("FLOWGUARD_OUTPUT_DIR", "")
EVIDENCE_ROOT = (
    Path(_RUN_OUTPUT_DIR) / "evidence"
    if _RUN_OUTPUT_DIR
    else ROOT / ".flowguard" / "evidence" / "harden-ui-content-visibility"
)
CHILD_EVIDENCE_ROOT = EVIDENCE_ROOT / "children"
CORE_JUNIT = EVIDENCE_ROOT / "focused-ui-core.junit.xml"
TEMPLATE_JUNIT = EVIDENCE_ROOT / "ui-templates.junit.xml"
MATRIX_JUNIT = EVIDENCE_ROOT / "contract-matrix.junit.xml"
UI_MODEL_RESULT = CHILD_EVIDENCE_ROOT / "ui-flow-structure" / "result.json"
REAL_SURFACE_RESULT = CHILD_EVIDENCE_ROOT / "real-surface" / "result.json"
BEHAVIOR_LEDGER_RESULT = CHILD_EVIDENCE_ROOT / "behavior-ledger" / "result.json"
FIELD_LIFECYCLE_RESULT = CHILD_EVIDENCE_ROOT / "field-lifecycle" / "result.json"

OBLIGATION_ID = "commitment:ordinary-ui-content-admission"
CODE_CONTRACT_ID = "contract:review-ui-content-visibility"
CONTRACT_SHARD_ID = "contract_shard:ui_flow_structure_skill:content-admission"
CONTRACT_COVERAGE_RECEIPT_ID = "contract_coverage:ui_flow_structure_skill"
TEST_EVIDENCE_IDS = (
    "test:ui-content-admission:happy",
    "test:ui-content-admission:failure",
)


def _artifact_path(path: Path) -> str:
    """Return a portable evidence path for repository-local or isolated runs."""

    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()

CORE_PYTEST_ARGS = (
    "-m",
    "pytest",
    "tests/test_ui_structure.py",
    "tests/test_api_surface.py",
    "tests/test_behavior_commitment_ledger.py",
    "tests/test_field_lifecycle.py",
    "-q",
    f"--junitxml={_artifact_path(CORE_JUNIT)}",
)
TEMPLATE_PYTEST_ARGS = (
    "-m",
    "pytest",
    "tests/test_public_templates.py",
    "-q",
    "-k",
    "ui_flow_structure",
    f"--junitxml={_artifact_path(TEMPLATE_JUNIT)}",
)
MATRIX_PYTEST_ARGS = (
    "-m",
    "pytest",
    "tests/test_ui_structure.py",
    "-q",
    "-k",
    (
        "visibility_contract_exhaustion_declares_finite_matrix_and_shard "
        "or content_visibility_matrix_executes_all_80_combinations"
    ),
    f"--junitxml={_artifact_path(MATRIX_JUNIT)}",
)


def _command_text(args: tuple[str, ...]) -> str:
    return "python " + " ".join(args)


def _proof(
    artifact_id: str,
    path: Path,
    *covered_obligation_ids: str,
    command: str,
    producer_route: str = "flowguard-model-test-alignment",
) -> ProofArtifactRef:
    """Create a current proof reference from a result artifact produced this run."""

    relative = _artifact_path(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return ProofArtifactRef(
        artifact_id,
        producer_route=producer_route,
        command=command,
        result_path=relative,
        result_status="passed",
        exit_code=0,
        artifact_fingerprints={relative: f"sha256:{digest}"},
        covered_obligation_ids=tuple(covered_obligation_ids),
        assertion_scope=TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
    )


def _junit_test_count(path: Path) -> int:
    root = ET.parse(path).getroot()
    if "tests" in root.attrib:
        return int(root.attrib["tests"])
    return sum(int(suite.attrib.get("tests", "0")) for suite in root.findall(".//testsuite"))


def contract_exhaustion_plan() -> ContractExhaustionPlan:
    axis_ids = ("visibility_class", "mapping_target", "ui_state", "user_need_ref")
    axes = (
        ContractAxis(
            "visibility_class",
            model_id="ui_flow_structure_skill",
            values=("user_visible", "user_on_demand", "internal", "unknown"),
        ),
        ContractAxis(
            "mapping_target",
            model_id="ui_flow_structure_skill",
            values=("none", "display", "visible_surface", "text", "observed"),
        ),
        ContractAxis(
            "ui_state",
            model_id="ui_flow_structure_skill",
            values=("closed", "revealed"),
        ),
        ContractAxis(
            "user_need_ref",
            model_id="ui_flow_structure_skill",
            values=("absent", "present"),
        ),
    )
    return ContractExhaustionPlan(
        "ui-content-visibility-matrix",
        model_id="ui_flow_structure_skill",
        axes=axes,
        interaction_groups=(
            ContractInteractionGroup(
                "content-admission",
                model_id="ui_flow_structure_skill",
                axis_ids=axis_ids,
                required_routes=(
                    CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                    CONTRACT_ROUTE_TEST_MESH,
                    CONTRACT_ROUTE_RISK_EVIDENCE_LEDGER,
                ),
                oracle_status=CONTRACT_ORACLE_NEEDS_HUMAN_REVIEW,
                description="Each tuple is resolved by the executable 80-case reviewer oracle.",
            ),
        ),
        require_model_coverage_receipt=True,
        coverage_universe=ContractCoverageUniverse(
            "ui-content-admission-universe",
            claim_scope="finite-matrix",
            source_refs=(
                "openspec:ui-content-visibility-classification",
                "openspec:ui-content-visibility-enforcement",
            ),
            required_axis_ids=axis_ids,
            required_interaction_group_ids=("content-admission",),
            required_coverage_receipt_ids=(CONTRACT_COVERAGE_RECEIPT_ID,),
        ),
        require_coverage_universe=True,
    )


def contract_exhaustion_report():
    return review_contract_exhaustion(contract_exhaustion_plan())


def model_test_alignment_plan() -> ModelTestAlignmentPlan:
    core_command = _command_text(CORE_PYTEST_ARGS)
    obligation = ModelObligation(
        OBLIGATION_ID,
        description=(
            "Every state-exposing UI candidate is classified as default-visible, "
            "on-demand, or internal before any ordinary UI mapping is accepted."
        ),
        required_test_kinds=(TEST_KIND_HAPPY_PATH, TEST_KIND_FAILURE_PATH),
        risk_level="high",
        external_inputs=("candidate content", "visibility class", "mapping target", "interaction state", "typed user need"),
        external_outputs=("admitted display", "blocked mapping", "on-demand disclosure"),
        error_paths=("unclassified content", "internal mapping", "closed-state leak", "inaccessible disclosure"),
    )
    contract = CodeContract(
        CODE_CONTRACT_ID,
        path="flowguard/ui_structure.py",
        symbol="review_ui_content_visibility",
        role=CODE_CONTRACT_ROLE_OWNER,
        implements_obligations=(OBLIGATION_ID,),
        external_inputs=obligation.external_inputs,
        external_outputs=obligation.external_outputs,
        error_paths=obligation.error_paths,
    )
    return ModelTestAlignmentPlan(
        "ui-content-visibility-admission",
        obligations=(obligation,),
        code_contracts=(contract,),
        test_evidence=(
            TestEvidence(
                TEST_EVIDENCE_IDS[0],
                test_name="UI content admission positive and task-control cases",
                path="tests/test_ui_structure.py",
                command=core_command,
                result_status="passed",
                test_kind=TEST_KIND_HAPPY_PATH,
                covered_obligations=(OBLIGATION_ID,),
                covered_code_contracts=(CODE_CONTRACT_ID,),
                assertion_scope=TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
                proof_artifact=_proof(
                    "artifact:ui-content-admission:happy",
                    CORE_JUNIT,
                    OBLIGATION_ID,
                    command=core_command,
                ),
            ),
            TestEvidence(
                TEST_EVIDENCE_IDS[1],
                test_name="UI content admission semantic false-pass regressions",
                path="tests/test_ui_structure.py",
                command=core_command,
                result_status="passed",
                test_kind=TEST_KIND_FAILURE_PATH,
                covered_obligations=(OBLIGATION_ID,),
                covered_code_contracts=(CODE_CONTRACT_ID,),
                assertion_scope=TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
                proof_artifact=_proof(
                    "artifact:ui-content-admission:failure",
                    CORE_JUNIT,
                    OBLIGATION_ID,
                    command=core_command,
                ),
            ),
        ),
        require_proof_artifacts=True,
    )


def test_mesh_plan() -> TestMeshPlan:
    core_command = _command_text(CORE_PYTEST_ARGS)
    template_command = _command_text(TEMPLATE_PYTEST_ARGS)
    matrix_command = _command_text(MATRIX_PYTEST_ARGS)
    items = (
        TestPartitionItem("ui-content-core", owner_suite_id="ui-content-core"),
        TestPartitionItem("ui-content-templates", owner_suite_id="ui-content-templates"),
        TestPartitionItem(
            CONTRACT_SHARD_ID,
            item_type="contract_coverage_shard",
            owner_suite_id="ui-content-contract-matrix",
        ),
    )
    suites = (
        TestSuiteEvidence(
            "ui-content-core",
            command=core_command,
            result_status="passed",
            evidence_tier=EVIDENCE_CONFORMANCE_GREEN,
            test_count=_junit_test_count(CORE_JUNIT),
            selected_count=_junit_test_count(CORE_JUNIT),
            exit_code=0,
            result_path=_artifact_path(CORE_JUNIT),
            proof_artifact=_proof("artifact:testmesh:ui-content-core", CORE_JUNIT, command=core_command),
        ),
        TestSuiteEvidence(
            "ui-content-templates",
            command=template_command,
            result_status="passed",
            evidence_tier=EVIDENCE_CONFORMANCE_GREEN,
            test_count=_junit_test_count(TEMPLATE_JUNIT),
            selected_count=_junit_test_count(TEMPLATE_JUNIT),
            exit_code=0,
            result_path=_artifact_path(TEMPLATE_JUNIT),
            proof_artifact=_proof("artifact:testmesh:ui-content-templates", TEMPLATE_JUNIT, command=template_command),
        ),
        TestSuiteEvidence(
            "ui-content-contract-matrix",
            command=matrix_command,
            layer=TEST_LAYER_CONTRACT_COMBINATION_SHARD,
            result_status="passed",
            evidence_tier=EVIDENCE_CONFORMANCE_GREEN,
            test_count=_junit_test_count(MATRIX_JUNIT),
            selected_count=_junit_test_count(MATRIX_JUNIT),
            exit_code=0,
            result_path=_artifact_path(MATRIX_JUNIT),
            owned_coverage_shard_ids=(CONTRACT_SHARD_ID,),
            proof_artifact=_proof(
                "artifact:testmesh:ui-content-contract-matrix",
                MATRIX_JUNIT,
                CONTRACT_SHARD_ID,
                command=matrix_command,
                producer_route="flowguard-contract-exhaustion-mesh",
            ),
        ),
    )
    return TestMeshPlan(
        "harden-ui-content-visibility",
        partition_items=items,
        child_suites=suites,
        target_split_derivation=TestTargetSplitDerivation(
            "ui-content-visibility-admission",
            target_suite_ids=tuple(item.suite_id for item in suites),
            covered_partition_item_ids=tuple(item.item_id for item in items),
            source_model_path=".flowguard/ui_flow_structure_skill/model.py",
            rationale="Separate core contract, public template, and finite matrix evidence.",
        ),
        required_coverage_shard_ids=(CONTRACT_SHARD_ID,),
        required_evidence_tier=EVIDENCE_CONFORMANCE_GREEN,
        require_proof_artifacts=True,
        decision_scope="high_risk",
        release_deferred_allowed=False,
    )


def risk_evidence_ledger_plan() -> RiskEvidenceLedgerPlan:
    proof_specs = (
        ("evidence:ui-content-core", CORE_JUNIT, _command_text(CORE_PYTEST_ARGS), "flowguard-model-test-alignment", "Core admission and semantic false-pass regressions passed."),
        ("evidence:ui-content-templates", TEMPLATE_JUNIT, _command_text(TEMPLATE_PYTEST_ARGS), "flowguard-ui-flow-structure", "Public templates preserve the content-admission boundary."),
        ("evidence:ui-content-matrix", MATRIX_JUNIT, _command_text(MATRIX_PYTEST_ARGS), "flowguard-contract-exhaustion-mesh", "All 80 declared matrix combinations executed against the real reviewer."),
        ("evidence:ui-content-owner-model", UI_MODEL_RESULT, "python .flowguard/ui_flow_structure_skill/run_checks.py", "flowguard-ui-flow-structure", "Owner rollout model and known-bad variants passed."),
        ("evidence:ui-content-real-surface", REAL_SURFACE_RESULT, "python .flowguard/harden_ui_real_surface_validation/run_checks.py", "flowguard-ui-flow-structure", "Allowed-versus-observed real-surface model passed."),
        ("evidence:ui-content-behavior-ledger", BEHAVIOR_LEDGER_RESULT, "python .flowguard/behavior_commitment_ledger/run_checks.py", "flowguard-behavior-commitment-ledger", "Behavior commitment ledger passed with canonical bindings."),
        ("evidence:ui-content-field-handoff", FIELD_LIFECYCLE_RESULT, "python .flowguard/default_replacement_field_lifecycle/run_checks.py", "flowguard-field-lifecycle-mesh", "Ordinary-UI reader field handoff model and concrete contract passed."),
    )
    proofs = tuple(
        RiskEvidenceProof(
            evidence_id,
            result_status=RISK_PROOF_STATUS_PASSED,
            producer_route=producer_route,
            command=command,
            summary=summary,
            proof_artifact=_proof(
                f"artifact:risk:{evidence_id.removeprefix('evidence:')}",
                path,
                OBLIGATION_ID,
                command=command,
                producer_route=producer_route,
            ),
        )
        for evidence_id, path, command, producer_route, summary in proof_specs
    )
    return RiskEvidenceLedgerPlan(
        "ledger:harden-ui-content-visibility",
        rows=(
            RiskEvidenceRow(
                "risk:internal-or-unclassified-content-leaks-to-ordinary-ui",
                model_obligation_id=OBLIGATION_ID,
                code_contract_id=CODE_CONTRACT_ID,
                proof_evidence_ids=tuple(item.evidence_id for item in proofs),
                gates=(
                    RiskEvidenceGate(RISK_GATE_UI_IMPLEMENTATION, "ui:content-admission-implementation"),
                    RiskEvidenceGate(RISK_GATE_UI_REAL_SURFACE, "ui:allowed-vs-observed-content"),
                    RiskEvidenceGate(RISK_GATE_UI_FUNCTIONAL_CHAIN, "ui:on-demand-reveal-return"),
                    RiskEvidenceGate(RISK_GATE_UI_HUMAN_OPERABILITY, "ui:keyboard-focus-dismiss"),
                    RiskEvidenceGate(RISK_GATE_CONTRACT_COVERAGE_SHARD, CONTRACT_SHARD_ID),
                    RiskEvidenceGate(RISK_GATE_TEST_SPLIT, "testmesh:harden-ui-content-visibility"),
                ),
            ),
        ),
        proof_evidence=proofs,
        require_proof_artifacts=True,
        allow_scoped_confidence=False,
    )


def canonical_contract_chain_ok() -> bool:
    report = contract_exhaustion_report()
    return bool(
        report.ok
        and len(report.generated_cases) == 80
        and contract_exhaustion_to_test_mesh_shard_ids(report) == (CONTRACT_SHARD_ID,)
        and tuple(receipt.receipt_id for receipt in report.coverage_receipts)
        == (CONTRACT_COVERAGE_RECEIPT_ID,)
    )


__all__ = [
    "BEHAVIOR_LEDGER_RESULT",
    "CHILD_EVIDENCE_ROOT",
    "CODE_CONTRACT_ID",
    "CONTRACT_COVERAGE_RECEIPT_ID",
    "CONTRACT_SHARD_ID",
    "CORE_JUNIT",
    "CORE_PYTEST_ARGS",
    "FIELD_LIFECYCLE_RESULT",
    "MATRIX_JUNIT",
    "MATRIX_PYTEST_ARGS",
    "OBLIGATION_ID",
    "REAL_SURFACE_RESULT",
    "TEMPLATE_JUNIT",
    "TEMPLATE_PYTEST_ARGS",
    "TEST_EVIDENCE_IDS",
    "UI_MODEL_RESULT",
    "canonical_contract_chain_ok",
    "contract_exhaustion_plan",
    "contract_exhaustion_report",
    "model_test_alignment_plan",
    "risk_evidence_ledger_plan",
    "test_mesh_plan",
]
