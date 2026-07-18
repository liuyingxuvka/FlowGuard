"""Small FlowGuard-to-SkillGuard V2 contract projection helper.

The exported graph describes an existing skill route. It is deliberately not
an executor: FlowGuard still owns route behavior and SkillGuard binds current
checks and receipts to the projected steps.
"""

from __future__ import annotations

from typing import Any

from . import SCHEMA_VERSION


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
SKILLGUARD_MODEL_EXPORT_SCHEMA = "skillguard.flowguard_model_export.v2"


def build_skill_contract_model_export(
    *,
    skill_id: str,
    route_id: str,
    owner_id: str,
    parent_model_id: str,
    business_intent: str,
    claim_boundary: str,
) -> dict[str, Any]:
    """Project one existing FlowGuard-owned skill route into the V2 schema."""

    model_id = f"flowguard.{route_id}.skill_contract.v2"
    function_id = f"function:{route_id}"
    route_ref = f"route:{route_id}"
    step_prefix = f"step:{skill_id}"
    obligation_prefix = f"obligation:{skill_id}"
    intake = f"{step_prefix}:intake"
    execute = f"{step_prefix}:execute"
    verify = f"{step_prefix}:verify"
    success = f"{step_prefix}:success"
    blocked = f"{step_prefix}:blocked"
    return {
        "schema_version": SKILLGUARD_MODEL_EXPORT_SCHEMA,
        "flowguard_schema_version": SCHEMA_VERSION,
        "model_id": model_id,
        "parent_model_id": parent_model_id,
        "claim_boundary": claim_boundary,
        "functions": [
            {
                "function_id": function_id,
                "business_intent": business_intent,
                "owner_id": owner_id,
                "route_ids": [route_ref],
            }
        ],
        "routes": [
            {
                "route_id": route_ref,
                "function_id": function_id,
                "owner_id": owner_id,
                "step_ids": [intake, execute, verify, success, blocked],
                "success_terminal_step_id": success,
                "blocked_terminal_step_id": blocked,
                "handoffs": [],
            }
        ],
        "steps": [
            {
                "step_id": intake,
                "route_id": route_ref,
                "owner_id": owner_id,
                "action_kind": "inventory",
                "terminal_kind": "",
                "prerequisite_step_ids": [],
            },
            {
                "step_id": execute,
                "route_id": route_ref,
                "owner_id": owner_id,
                "action_kind": "native",
                "terminal_kind": "",
                "prerequisite_step_ids": [intake],
            },
            {
                "step_id": verify,
                "route_id": route_ref,
                "owner_id": owner_id,
                "action_kind": "verifier",
                "terminal_kind": "",
                "prerequisite_step_ids": [execute],
            },
            {
                "step_id": success,
                "route_id": route_ref,
                "owner_id": owner_id,
                "action_kind": "terminal",
                "terminal_kind": "success",
                "prerequisite_step_ids": [verify],
            },
            {
                "step_id": blocked,
                "route_id": route_ref,
                "owner_id": owner_id,
                "action_kind": "terminal",
                "terminal_kind": "blocked",
                "prerequisite_step_ids": [],
            },
        ],
        "invariant_ids": [
            "invariant:plane-boundary",
            "invariant:native-authority",
            "invariant:evidence-closure",
        ],
        "obligations": [
            {
                "obligation_id": f"{obligation_prefix}:plane-boundary",
                "invariant_id": "invariant:plane-boundary",
                "owner_step_ids": [intake],
                "required": True,
            },
            {
                "obligation_id": f"{obligation_prefix}:native-authority",
                "invariant_id": "invariant:native-authority",
                "owner_step_ids": [execute],
                "required": True,
            },
            {
                "obligation_id": f"{obligation_prefix}:evidence-closure",
                "invariant_id": "invariant:evidence-closure",
                "owner_step_ids": [verify],
                "required": True,
            },
        ],
    }


__all__ = [
    "FLOWGUARD_MODEL_MARKER",
    "SKILLGUARD_MODEL_EXPORT_SCHEMA",
    "build_skill_contract_model_export",
]
