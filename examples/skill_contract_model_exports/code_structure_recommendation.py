"""Thin SkillGuard V2 projection for the existing code-structure route.

The domain owner remains :mod:`flowguard.code_structure`; this file only gives
the external contract compiler a package-independent model export.
"""

from flowguard.skill_contract_model import (
    FLOWGUARD_MODEL_MARKER,
    build_skill_contract_model_export,
)


def export_contract_model():
    return build_skill_contract_model_export(
        skill_id="flowguard-code-structure-recommendation",
        route_id="code_structure_recommendation",
        owner_id="code_structure_recommendation",
        parent_model_id="flowguard.model_first_function_flow",
        business_intent="Recommend model-derived module, function, state, field, side-effect, facade, adapter, and validation ownership before code edits.",
        claim_boundary="Projection only; flowguard.code_structure and its owner tests remain the recommendation authority, and StructureMesh owns later refactoring.",
    )


__all__ = ["FLOWGUARD_MODEL_MARKER", "export_contract_model"]
