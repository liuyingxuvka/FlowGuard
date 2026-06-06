"""Reusable project template content for model-first flowguard adoption."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .project_adoption import build_flowguard_agents_block, current_project_manifest_text

from .template_text.code_structure_recommendation import (
    CODE_STRUCTURE_RECOMMENDATION_MODEL_TEMPLATE,
    CODE_STRUCTURE_RECOMMENDATION_RUN_CHECKS_TEMPLATE,
    CODE_STRUCTURE_RECOMMENDATION_NOTES_TEMPLATE,
)
from .template_text.core import (
    MODEL_TEMPLATE,
    RUN_CHECKS_TEMPLATE,
    ADOPTION_LOG_TEMPLATE,
    MODEL_NOTES_TEMPLATE,
)
from .template_text.development_process_flow import (
    DEVELOPMENT_PROCESS_FLOW_MODEL_TEMPLATE,
    DEVELOPMENT_PROCESS_FLOW_RUN_CHECKS_TEMPLATE,
    DEVELOPMENT_PROCESS_FLOW_NOTES_TEMPLATE,
)
from .template_text.existing_model_preflight import (
    EXISTING_MODEL_PREFLIGHT_MODEL_TEMPLATE,
    EXISTING_MODEL_PREFLIGHT_RUN_CHECKS_TEMPLATE,
    EXISTING_MODEL_PREFLIGHT_NOTES_TEMPLATE,
)
from .template_text.field_lifecycle import (
    FIELD_LIFECYCLE_MODEL_TEMPLATE,
    FIELD_LIFECYCLE_RUN_CHECKS_TEMPLATE,
    FIELD_LIFECYCLE_NOTES_TEMPLATE,
)
from .template_text.flowguard_closure_contract import (
    FLOWGUARD_CLOSURE_CONTRACT_MODEL_TEMPLATE,
    FLOWGUARD_CLOSURE_CONTRACT_RUN_CHECKS_TEMPLATE,
    FLOWGUARD_CLOSURE_CONTRACT_NOTES_TEMPLATE,
)
from .template_text.layered_boundary_proof import (
    LAYERED_BOUNDARY_PROOF_MODEL_TEMPLATE,
    LAYERED_BOUNDARY_PROOF_RUN_CHECKS_TEMPLATE,
    LAYERED_BOUNDARY_PROOF_NOTES_TEMPLATE,
)
from .template_text.maintenance_workflow import (
    MAINTENANCE_WORKFLOW_MODEL_TEMPLATE,
    MAINTENANCE_WORKFLOW_RUN_CHECKS_TEMPLATE,
    MAINTENANCE_WORKFLOW_NOTES_TEMPLATE,
)
from .template_text.maintenance_scan import (
    MAINTENANCE_SCAN_RUN_TEMPLATE,
    MAINTENANCE_SCAN_NOTES_TEMPLATE,
)
from .template_text.model_miss_review import (
    MODEL_MISS_REVIEW_MODEL_TEMPLATE,
    MODEL_MISS_REVIEW_RUN_CHECKS_TEMPLATE,
    MODEL_MISS_REVIEW_NOTES_TEMPLATE,
)
from .template_text.model_similarity_consolidation import (
    MODEL_SIMILARITY_CONSOLIDATION_MODEL_TEMPLATE,
    MODEL_SIMILARITY_CONSOLIDATION_RUN_CHECKS_TEMPLATE,
    MODEL_SIMILARITY_CONSOLIDATION_NOTES_TEMPLATE,
)
from .template_text.model_test_alignment import (
    MODEL_TEST_ALIGNMENT_MODEL_TEMPLATE,
    MODEL_TEST_ALIGNMENT_RUN_CHECKS_TEMPLATE,
    MODEL_TEST_ALIGNMENT_NOTES_TEMPLATE,
)
from .template_text.plan_detailing import (
    PLAN_DETAILING_MODEL_TEMPLATE,
    PLAN_DETAILING_RUN_CHECKS_TEMPLATE,
    PLAN_DETAILING_NOTES_TEMPLATE,
)
from .template_text.risk_evidence_ledger import (
    RISK_EVIDENCE_LEDGER_MODEL_TEMPLATE,
    RISK_EVIDENCE_LEDGER_RUN_CHECKS_TEMPLATE,
    RISK_EVIDENCE_LEDGER_NOTES_TEMPLATE,
)
from .template_text.risk_intent_check_plan import (
    RISK_INTENT_CHECK_PLAN_MODEL_TEMPLATE,
    RISK_INTENT_CHECK_PLAN_RUN_CHECKS_TEMPLATE,
    RISK_INTENT_CHECK_PLAN_NOTES_TEMPLATE,
)
from .template_text.runtime_path_evidence import (
    RUNTIME_PATH_EVIDENCE_MODEL_TEMPLATE,
    RUNTIME_PATH_EVIDENCE_RUN_CHECKS_TEMPLATE,
    RUNTIME_PATH_EVIDENCE_NOTES_TEMPLATE,
)
from .template_text.structure_mesh import (
    STRUCTURE_MESH_MODEL_TEMPLATE,
    STRUCTURE_MESH_RUN_CHECKS_TEMPLATE,
    STRUCTURE_MESH_NOTES_TEMPLATE,
)
from .template_text.test_mesh import (
    TEST_MESH_MODEL_TEMPLATE,
    TEST_MESH_RUN_CHECKS_TEMPLATE,
    TEST_MESH_NOTES_TEMPLATE,
)
from .template_text.topology_hazard import (
    TOPOLOGY_HAZARD_MODEL_TEMPLATE,
    TOPOLOGY_HAZARD_RUN_CHECKS_TEMPLATE,
    TOPOLOGY_HAZARD_NOTES_TEMPLATE,
)
from .template_text.ui_flow_structure import (
    UI_FLOW_STRUCTURE_MODEL_TEMPLATE,
    UI_FLOW_STRUCTURE_RUN_CHECKS_TEMPLATE,
    UI_FLOW_STRUCTURE_NOTES_TEMPLATE,
)
from .template_text.workflow_step_contracts import (
    WORKFLOW_STEP_CONTRACTS_MODEL_TEMPLATE,
    WORKFLOW_STEP_CONTRACTS_RUN_CHECKS_TEMPLATE,
    WORKFLOW_STEP_CONTRACTS_NOTES_TEMPLATE,
)


@dataclass(frozen=True)
class TemplateFile:
    path: str
    content: str


def project_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile("model.py", MODEL_TEMPLATE),
        TemplateFile("run_checks.py", RUN_CHECKS_TEMPLATE),
    )


def adoption_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile("docs/flowguard_adoption_log.md", ADOPTION_LOG_TEMPLATE),
        TemplateFile("docs/flowguard_model_notes.md", MODEL_NOTES_TEMPLATE),
    )


def project_adoption_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile("AGENTS.md", build_flowguard_agents_block() + "\n"),
        TemplateFile(".flowguard/project.toml", current_project_manifest_text()),
        TemplateFile("docs/flowguard_adoption_log.md", ADOPTION_LOG_TEMPLATE),
        TemplateFile("docs/flowguard_model_notes.md", MODEL_NOTES_TEMPLATE),
    )


def risk_intent_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/risk_intent_check_plan/model.py", RISK_INTENT_CHECK_PLAN_MODEL_TEMPLATE),
        TemplateFile(".flowguard/risk_intent_check_plan/run_checks.py", RISK_INTENT_CHECK_PLAN_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/flowguard_risk_intent_check_plan.md", RISK_INTENT_CHECK_PLAN_NOTES_TEMPLATE),
    )


def plan_detailing_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/plan_detailing/model.py", PLAN_DETAILING_MODEL_TEMPLATE),
        TemplateFile(".flowguard/plan_detailing/run_checks.py", PLAN_DETAILING_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/flowguard_plan_detailing.md", PLAN_DETAILING_NOTES_TEMPLATE),
    )


def model_miss_review_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/model_miss_review/model.py", MODEL_MISS_REVIEW_MODEL_TEMPLATE),
        TemplateFile(".flowguard/model_miss_review/run_checks.py", MODEL_MISS_REVIEW_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/flowguard_model_miss_review.md", MODEL_MISS_REVIEW_NOTES_TEMPLATE),
    )


def maintenance_workflow_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/maintenance_workflow/model.py", MAINTENANCE_WORKFLOW_MODEL_TEMPLATE),
        TemplateFile(".flowguard/maintenance_workflow/run_checks.py", MAINTENANCE_WORKFLOW_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/flowguard_maintenance_workflow.md", MAINTENANCE_WORKFLOW_NOTES_TEMPLATE),
    )


def maintenance_scan_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/maintenance_scan/run_scan.py", MAINTENANCE_SCAN_RUN_TEMPLATE),
        TemplateFile("docs/flowguard_maintenance_scan.md", MAINTENANCE_SCAN_NOTES_TEMPLATE),
    )


def runtime_path_evidence_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/runtime_path_evidence/model.py", RUNTIME_PATH_EVIDENCE_MODEL_TEMPLATE),
        TemplateFile(".flowguard/runtime_path_evidence/run_checks.py", RUNTIME_PATH_EVIDENCE_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/runtime_path_evidence.md", RUNTIME_PATH_EVIDENCE_NOTES_TEMPLATE),
    )


def model_test_alignment_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/model_test_alignment/model.py", MODEL_TEST_ALIGNMENT_MODEL_TEMPLATE),
        TemplateFile(".flowguard/model_test_alignment/run_checks.py", MODEL_TEST_ALIGNMENT_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/model_test_alignment.md", MODEL_TEST_ALIGNMENT_NOTES_TEMPLATE),
    )


def development_process_flow_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/development_process_flow/model.py", DEVELOPMENT_PROCESS_FLOW_MODEL_TEMPLATE),
        TemplateFile(".flowguard/development_process_flow/run_checks.py", DEVELOPMENT_PROCESS_FLOW_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/flowguard_development_process_flow.md", DEVELOPMENT_PROCESS_FLOW_NOTES_TEMPLATE),
    )


def workflow_step_contracts_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/workflow_step_contracts/model.py", WORKFLOW_STEP_CONTRACTS_MODEL_TEMPLATE),
        TemplateFile(
            ".flowguard/workflow_step_contracts/run_checks.py",
            WORKFLOW_STEP_CONTRACTS_RUN_CHECKS_TEMPLATE,
        ),
        TemplateFile("docs/flowguard_workflow_step_contracts.md", WORKFLOW_STEP_CONTRACTS_NOTES_TEMPLATE),
    )


def code_structure_recommendation_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(
            ".flowguard/code_structure_recommendation/model.py",
            CODE_STRUCTURE_RECOMMENDATION_MODEL_TEMPLATE,
        ),
        TemplateFile(
            ".flowguard/code_structure_recommendation/run_checks.py",
            CODE_STRUCTURE_RECOMMENDATION_RUN_CHECKS_TEMPLATE,
        ),
        TemplateFile(
            "docs/flowguard_code_structure_recommendation.md",
            CODE_STRUCTURE_RECOMMENDATION_NOTES_TEMPLATE,
        ),
    )


def existing_model_preflight_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/existing_model_preflight/model.py", EXISTING_MODEL_PREFLIGHT_MODEL_TEMPLATE),
        TemplateFile(".flowguard/existing_model_preflight/run_checks.py", EXISTING_MODEL_PREFLIGHT_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/flowguard_existing_model_preflight.md", EXISTING_MODEL_PREFLIGHT_NOTES_TEMPLATE),
    )


def field_lifecycle_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/field_lifecycle/model.py", FIELD_LIFECYCLE_MODEL_TEMPLATE),
        TemplateFile(".flowguard/field_lifecycle/run_checks.py", FIELD_LIFECYCLE_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/flowguard_field_lifecycle_mesh.md", FIELD_LIFECYCLE_NOTES_TEMPLATE),
    )


def model_similarity_consolidation_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(
            ".flowguard/model_similarity_consolidation/model.py",
            MODEL_SIMILARITY_CONSOLIDATION_MODEL_TEMPLATE,
        ),
        TemplateFile(
            ".flowguard/model_similarity_consolidation/run_checks.py",
            MODEL_SIMILARITY_CONSOLIDATION_RUN_CHECKS_TEMPLATE,
        ),
        TemplateFile(
            "docs/flowguard_model_similarity_consolidation.md",
            MODEL_SIMILARITY_CONSOLIDATION_NOTES_TEMPLATE,
        ),
    )


def risk_evidence_ledger_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/risk_evidence_ledger/model.py", RISK_EVIDENCE_LEDGER_MODEL_TEMPLATE),
        TemplateFile(".flowguard/risk_evidence_ledger/run_checks.py", RISK_EVIDENCE_LEDGER_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/flowguard_risk_evidence_ledger.md", RISK_EVIDENCE_LEDGER_NOTES_TEMPLATE),
    )


def layered_boundary_proof_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/layered_boundary_proof/model.py", LAYERED_BOUNDARY_PROOF_MODEL_TEMPLATE),
        TemplateFile(".flowguard/layered_boundary_proof/run_checks.py", LAYERED_BOUNDARY_PROOF_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/flowguard_layered_boundary_proof.md", LAYERED_BOUNDARY_PROOF_NOTES_TEMPLATE),
    )


def closure_contract_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/closure_contract/model.py", FLOWGUARD_CLOSURE_CONTRACT_MODEL_TEMPLATE),
        TemplateFile(".flowguard/closure_contract/run_checks.py", FLOWGUARD_CLOSURE_CONTRACT_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/flowguard_closure_contract_review.md", FLOWGUARD_CLOSURE_CONTRACT_NOTES_TEMPLATE),
    )


def ui_flow_structure_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/ui_flow_structure/model.py", UI_FLOW_STRUCTURE_MODEL_TEMPLATE),
        TemplateFile(".flowguard/ui_flow_structure/run_checks.py", UI_FLOW_STRUCTURE_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/flowguard_ui_flow_structure.md", UI_FLOW_STRUCTURE_NOTES_TEMPLATE),
    )


def test_mesh_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/test_mesh/model.py", TEST_MESH_MODEL_TEMPLATE),
        TemplateFile(".flowguard/test_mesh/run_checks.py", TEST_MESH_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/flowguard_test_mesh.md", TEST_MESH_NOTES_TEMPLATE),
    )


def structure_mesh_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/structure_mesh/model.py", STRUCTURE_MESH_MODEL_TEMPLATE),
        TemplateFile(".flowguard/structure_mesh/run_checks.py", STRUCTURE_MESH_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/flowguard_structure_mesh.md", STRUCTURE_MESH_NOTES_TEMPLATE),
    )


def topology_hazard_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/model_topology_hazard_review/model.py", TOPOLOGY_HAZARD_MODEL_TEMPLATE),
        TemplateFile(".flowguard/model_topology_hazard_review/run_checks.py", TOPOLOGY_HAZARD_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/flowguard_model_topology_hazard_review.md", TOPOLOGY_HAZARD_NOTES_TEMPLATE),
    )


def write_template_files(
    root: str | Path,
    files: tuple[TemplateFile, ...],
    *,
    overwrite: bool = False,
) -> tuple[Path, ...]:
    target_root = Path(root)
    written: list[Path] = []
    for file in files:
        target = target_root / file.path
        if target.exists() and not overwrite:
            raise FileExistsError(f"template target already exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(file.content, encoding="utf-8")
        written.append(target)
    return tuple(written)


__all__ = [
    "ADOPTION_LOG_TEMPLATE",
    "CODE_STRUCTURE_RECOMMENDATION_MODEL_TEMPLATE",
    "CODE_STRUCTURE_RECOMMENDATION_NOTES_TEMPLATE",
    "CODE_STRUCTURE_RECOMMENDATION_RUN_CHECKS_TEMPLATE",
    "DEVELOPMENT_PROCESS_FLOW_MODEL_TEMPLATE",
    "DEVELOPMENT_PROCESS_FLOW_NOTES_TEMPLATE",
    "DEVELOPMENT_PROCESS_FLOW_RUN_CHECKS_TEMPLATE",
    "EXISTING_MODEL_PREFLIGHT_MODEL_TEMPLATE",
    "EXISTING_MODEL_PREFLIGHT_NOTES_TEMPLATE",
    "EXISTING_MODEL_PREFLIGHT_RUN_CHECKS_TEMPLATE",
    "FIELD_LIFECYCLE_MODEL_TEMPLATE",
    "FIELD_LIFECYCLE_NOTES_TEMPLATE",
    "FIELD_LIFECYCLE_RUN_CHECKS_TEMPLATE",
    "FLOWGUARD_CLOSURE_CONTRACT_MODEL_TEMPLATE",
    "FLOWGUARD_CLOSURE_CONTRACT_NOTES_TEMPLATE",
    "FLOWGUARD_CLOSURE_CONTRACT_RUN_CHECKS_TEMPLATE",
    "LAYERED_BOUNDARY_PROOF_MODEL_TEMPLATE",
    "LAYERED_BOUNDARY_PROOF_NOTES_TEMPLATE",
    "LAYERED_BOUNDARY_PROOF_RUN_CHECKS_TEMPLATE",
    "MAINTENANCE_WORKFLOW_MODEL_TEMPLATE",
    "MAINTENANCE_WORKFLOW_NOTES_TEMPLATE",
    "MAINTENANCE_WORKFLOW_RUN_CHECKS_TEMPLATE",
    "MAINTENANCE_SCAN_NOTES_TEMPLATE",
    "MAINTENANCE_SCAN_RUN_TEMPLATE",
    "MODEL_MISS_REVIEW_MODEL_TEMPLATE",
    "MODEL_MISS_REVIEW_NOTES_TEMPLATE",
    "MODEL_MISS_REVIEW_RUN_CHECKS_TEMPLATE",
    "MODEL_TEST_ALIGNMENT_MODEL_TEMPLATE",
    "MODEL_TEST_ALIGNMENT_NOTES_TEMPLATE",
    "MODEL_TEST_ALIGNMENT_RUN_CHECKS_TEMPLATE",
    "MODEL_NOTES_TEMPLATE",
    "PLAN_DETAILING_MODEL_TEMPLATE",
    "PLAN_DETAILING_NOTES_TEMPLATE",
    "PLAN_DETAILING_RUN_CHECKS_TEMPLATE",
    "RISK_INTENT_CHECK_PLAN_MODEL_TEMPLATE",
    "RISK_INTENT_CHECK_PLAN_NOTES_TEMPLATE",
    "RISK_INTENT_CHECK_PLAN_RUN_CHECKS_TEMPLATE",
    "RISK_EVIDENCE_LEDGER_MODEL_TEMPLATE",
    "RISK_EVIDENCE_LEDGER_NOTES_TEMPLATE",
    "RISK_EVIDENCE_LEDGER_RUN_CHECKS_TEMPLATE",
    "RUNTIME_PATH_EVIDENCE_MODEL_TEMPLATE",
    "RUNTIME_PATH_EVIDENCE_NOTES_TEMPLATE",
    "RUNTIME_PATH_EVIDENCE_RUN_CHECKS_TEMPLATE",
    "STRUCTURE_MESH_MODEL_TEMPLATE",
    "STRUCTURE_MESH_NOTES_TEMPLATE",
    "STRUCTURE_MESH_RUN_CHECKS_TEMPLATE",
    "TEST_MESH_MODEL_TEMPLATE",
    "TEST_MESH_NOTES_TEMPLATE",
    "TEST_MESH_RUN_CHECKS_TEMPLATE",
    "TOPOLOGY_HAZARD_MODEL_TEMPLATE",
    "TOPOLOGY_HAZARD_NOTES_TEMPLATE",
    "TOPOLOGY_HAZARD_RUN_CHECKS_TEMPLATE",
    "TemplateFile",
    "WORKFLOW_STEP_CONTRACTS_MODEL_TEMPLATE",
    "WORKFLOW_STEP_CONTRACTS_NOTES_TEMPLATE",
    "WORKFLOW_STEP_CONTRACTS_RUN_CHECKS_TEMPLATE",
    "adoption_template_files",
    "closure_contract_template_files",
    "code_structure_recommendation_template_files",
    "development_process_flow_template_files",
    "existing_model_preflight_template_files",
    "field_lifecycle_template_files",
    "layered_boundary_proof_template_files",
    "maintenance_workflow_template_files",
    "maintenance_scan_template_files",
    "model_miss_review_template_files",
    "model_similarity_consolidation_template_files",
    "model_test_alignment_template_files",
    "plan_detailing_template_files",
    "project_template_files",
    "project_adoption_template_files",
    "risk_evidence_ledger_template_files",
    "risk_intent_template_files",
    "runtime_path_evidence_template_files",
    "structure_mesh_template_files",
    "test_mesh_template_files",
    "topology_hazard_template_files",
    "ui_flow_structure_template_files",
    "workflow_step_contracts_template_files",
    "write_template_files",
]
