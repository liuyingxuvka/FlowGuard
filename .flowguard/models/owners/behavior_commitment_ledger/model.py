"""Thin adapter for the canonical FlowGuard behavior commitment ledger."""

from __future__ import annotations

from pathlib import Path

from flowguard import (
    BehaviorCommitmentLedger,
    BehaviorSourceInventoryAuditReport,
    audit_behavior_commitment_source_inventory,
    load_behavior_commitment_ledger,
)
from flowguard.skill_contract_model import build_skill_contract_model_export


PROJECT_ROOT = Path(__file__).resolve().parents[4]
LEDGER_PATH = PROJECT_ROOT / ".flowguard" / "behavior" / "inventory" / "ledger.json"


def build_flowguard_behavior_commitment_ledger() -> BehaviorCommitmentLedger:
    """Load the single machine-readable authority without embedded inventory."""

    return load_behavior_commitment_ledger(LEDGER_PATH)


def audit_flowguard_behavior_commitment_source_inventory() -> BehaviorSourceInventoryAuditReport:
    """Bind the stored self-ledger to the current project source identity."""

    return audit_behavior_commitment_source_inventory(
        build_flowguard_behavior_commitment_ledger(),
        PROJECT_ROOT,
    )


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"


def export_contract_model():
    return build_skill_contract_model_export(
        skill_id="flowguard-behavior-commitment-ledger",
        route_id="behavior_commitment_ledger",
        owner_id="behavior_commitment_ledger",
        parent_model_id="flowguard.model_first_function_flow",
        business_intent="Register and recall exact same-plane external behavior commitments through the existing ledger owner.",
        claim_boundary="This projection binds the existing ledger route; runtime behavior, sibling evidence, release, and future AI compliance remain separately gated.",
    )


__all__ = [
    "LEDGER_PATH",
    "PROJECT_ROOT",
    "audit_flowguard_behavior_commitment_source_inventory",
    "build_flowguard_behavior_commitment_ledger",
    "export_contract_model",
]


def export_path_quality_source(model_instance_fingerprint: str):
    """Export the complete declared model scope without executing its checks."""
    from pathlib import Path
    from flowguard.model_path_quality import compile_declared_path_quality_source
    from flowguard.source_identity import functional_source_fingerprint

    return compile_declared_path_quality_source(
        model_id='behavior_commitment_ledger', model_instance_fingerprint=model_instance_fingerprint,
        graph_scope='native_check_contract',
        source_refs=({"path": '.flowguard/models/owners/behavior_commitment_ledger/model.py',
                      "source_fingerprint": functional_source_fingerprint(Path(__file__).resolve().parents[4], '.flowguard/models/owners/behavior_commitment_ledger/model.py')},),
        contract_export=export_contract_model(),
    )
