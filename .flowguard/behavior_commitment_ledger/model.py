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


LEDGER_PATH = Path(__file__).with_name("ledger.json")
PROJECT_ROOT = Path(__file__).resolve().parents[2]


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
