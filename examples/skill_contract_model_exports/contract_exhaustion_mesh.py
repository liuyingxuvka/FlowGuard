"""Thin SkillGuard V2 projection for the existing contract-exhaustion route.

The domain owner remains :mod:`flowguard.contract_exhaustion`; this file only
gives the external contract compiler a package-independent model export.
"""

from flowguard.skill_contract_model import (
    FLOWGUARD_MODEL_MARKER,
    build_skill_contract_model_export,
)


def export_contract_model():
    return build_skill_contract_model_export(
        skill_id="flowguard-contract-exhaustion-mesh",
        route_id="contract_exhaustion_mesh",
        owner_id="contract_exhaustion_mesh",
        parent_model_id="flowguard.model_first_function_flow",
        business_intent="Generate finite canonical bad cases, combinations, oracles, shards, receipts, and typed consumer handoffs from one declared boundary.",
        claim_boundary="Projection only; flowguard.contract_exhaustion, declared coverage universes, native tests, and downstream acceptance remain authoritative.",
    )


__all__ = ["FLOWGUARD_MODEL_MARKER", "export_contract_model"]
