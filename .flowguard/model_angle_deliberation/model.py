"""FlowGuard self-model for open-ended model-angle deliberation.

Purpose: Keep the new route from collapsing into a fixed checklist.
"""

from flowguard import (
    MODEL_ANGLE_ACTION_ADD_CHILD_MODEL,
    MODEL_ANGLE_ACTION_EXTEND_EXISTING,
    MODEL_ANGLE_ACTION_REUSE_EXISTING,
    ModelAngleDeliberation,
)


def correct_model_angle_deliberations():
    return (
        ModelAngleDeliberation(
            "self:existing-preflight",
            "Existing preflight is necessary but not enough",
            trigger_observation="The user noticed AI stays inside narrow route or field-flow prompts.",
            current_model_sees="Existing Model Preflight finds current model owners and duplicate boundaries.",
            current_model_misses="It does not force open-ended missing-viewpoint reasoning before route trust.",
            failure_if_ignored="The agent can claim grounded reuse while a needed model angle is absent.",
            candidate_action=MODEL_ANGLE_ACTION_EXTEND_EXISTING,
            existing_model_ids=("existing_model_preflight",),
            proposed_model_boundary="Model-angle rows consumed by preflight, ledger, closure, and scan routes.",
            owner_route_hint="model_maturation_loop",
            evidence_needed=("tests:test_model_angle_deliberation", "tests:test_existing_model_preflight"),
            resolved=True,
        ),
        ModelAngleDeliberation(
            "self:model-mesh-handoff",
            "Candidate child model pressure",
            trigger_observation="Some missing viewpoints should become child models instead of more prompt text.",
            current_model_sees="ModelMesh owns parent/child split and reattachment evidence.",
            current_model_misses="A prompt-only fix can keep adding vague checklist bullets to the parent route.",
            failure_if_ignored="Large models keep growing without a clear child ownership boundary.",
            candidate_action=MODEL_ANGLE_ACTION_ADD_CHILD_MODEL,
            existing_model_ids=("model_mesh_maintenance",),
            proposed_model_boundary="Model-angle deliberation names split pressure before ModelMesh does the split.",
            owner_route_hint="model_mesh_maintenance",
            evidence_needed=("maintenance_scan:model_angle_gap",),
            resolved=True,
        ),
        ModelAngleDeliberation(
            "self:no-overfix",
            "Known route remains enough when no angle is missing",
            trigger_observation="The user rejected over-repair and narrow checklist expansion.",
            current_model_sees="Some tasks only need the selected direct route.",
            current_model_misses="Nothing material after open-ended deliberation.",
            failure_if_ignored="The system would create ceremony without improving confidence.",
            candidate_action=MODEL_ANGLE_ACTION_REUSE_EXISTING,
            existing_model_ids=("development_process_flow",),
            resolved=True,
        ),
    )


def unresolved_model_angle_deliberations():
    return (
        ModelAngleDeliberation(
            "self:open-angle",
            "Unresolved missing viewpoint",
            trigger_observation="A possible missing model angle was noticed.",
            current_model_sees="The current model sees only route ownership.",
            current_model_misses="The new angle may require field lifecycle or mesh split evidence.",
            failure_if_ignored="Broad confidence would hide an unowned model boundary.",
            candidate_action=MODEL_ANGLE_ACTION_EXTEND_EXISTING,
            existing_model_ids=("existing_model_preflight",),
            proposed_model_boundary="Name and resolve the missing viewpoint through its owner route.",
            resolved=False,
        ),
    )
