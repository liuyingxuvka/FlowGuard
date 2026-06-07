"""Template text for FlowGuard model-angle deliberation route."""

MODEL_ANGLE_DELIBERATION_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Record open-ended model-angle deliberation before trusting one model boundary.
Guards against: Agents only following a fixed lens list and missing that a new model angle is needed.
Use before editing: Existing modeled systems, broad confidence claims, prompt/skill/process changes, or any case where the current model may be too narrow.
Run: python .flowguard/model_angle_deliberation/run_checks.py
"""

from flowguard import (
    MODEL_ANGLE_ACTION_ADD_CHILD_MODEL,
    MODEL_ANGLE_ACTION_EXTEND_EXISTING,
    MODEL_ANGLE_ACTION_REUSE_EXISTING,
    ModelAngleDeliberation,
)


def correct_deliberations():
    return (
        ModelAngleDeliberation(
            "angle:route-choice",
            "Route choice and owner model",
            trigger_observation="The task touches existing FlowGuard guidance and AI routing behavior.",
            current_model_sees="Existing model preflight finds owned routes and duplicate-boundary risk.",
            current_model_misses="It does not force the agent to ask whether a different model angle is missing.",
            failure_if_ignored="The agent may reuse a narrow model and claim full confidence while a new angle is unmodeled.",
            candidate_action=MODEL_ANGLE_ACTION_EXTEND_EXISTING,
            existing_model_ids=("existing_model_preflight",),
            proposed_model_boundary="Open-ended candidate angle rows consumed by preflight and final confidence routes.",
            owner_route_hint="model_maturation_loop",
            evidence_needed=("model_angle_review_report", "preflight_integration_test"),
            resolved=True,
        ),
        ModelAngleDeliberation(
            "angle:mesh-handoff",
            "Parent or child model split",
            trigger_observation="A candidate angle may need a separate child model rather than another checklist row.",
            current_model_sees="ModelMesh owns parent/child partition and reattachment evidence.",
            current_model_misses="A route prompt alone does not decide when to hand off to ModelMesh.",
            failure_if_ignored="Large model surfaces can keep growing instead of splitting into owned child models.",
            candidate_action=MODEL_ANGLE_ACTION_ADD_CHILD_MODEL,
            existing_model_ids=("model_mesh_maintenance",),
            proposed_model_boundary="Use model-angle rows to name split pressure before ModelMesh performs the split.",
            owner_route_hint="model_mesh_maintenance",
            evidence_needed=("mesh_handoff_decision",),
            resolved=True,
        ),
        ModelAngleDeliberation(
            "angle:reuse-ok",
            "Known route is enough",
            trigger_observation="Some tasks only need the existing route and should not spawn extra model work.",
            current_model_sees="The known owner model already covers the behavior and evidence gate.",
            current_model_misses="No meaningful missing angle was found after deliberation.",
            failure_if_ignored="Over-modeling would create process drag without improving confidence.",
            candidate_action=MODEL_ANGLE_ACTION_REUSE_EXISTING,
            existing_model_ids=("development_process_flow",),
            resolved=True,
        ),
    )


def broken_deliberations():
    return (
        ModelAngleDeliberation(
            "angle:unresolved",
            "Maybe data lifecycle",
            current_model_sees="The current model handles route choice.",
            current_model_misses="Field migration and lifecycle may be behavior-bearing.",
            failure_if_ignored="A field can be changed without an owning lifecycle model.",
            candidate_action=MODEL_ANGLE_ACTION_EXTEND_EXISTING,
            existing_model_ids=("existing_model_preflight",),
            proposed_model_boundary="Add a field lifecycle owner decision.",
            resolved=False,
        ),
        ModelAngleDeliberation(
            "angle:bad-scope",
            "Scoped without reason",
            current_model_sees="A candidate angle exists.",
            current_model_misses="The reason for skipping it is not documented.",
            failure_if_ignored="The final claim hides a deliberate gap.",
            candidate_action="scope_out_with_reason",
            resolved=True,
        ),
    )
'''


MODEL_ANGLE_DELIBERATION_RUN_CHECKS_TEMPLATE = '''"""Run the model-angle deliberation template checks."""

from model import broken_deliberations, correct_deliberations
from flowguard import review_model_angle_deliberations


def main() -> int:
    reports = (
        review_model_angle_deliberations(
            "correct-model-angle-review",
            correct_deliberations(),
            require_review=True,
            broad_claim=True,
        ),
        review_model_angle_deliberations(
            "broken-model-angle-review",
            broken_deliberations(),
            require_review=True,
            broad_claim=True,
        ),
    )
    for report in reports:
        print(report.format_text())
        print()
    correct, broken = reports
    if not correct.ok or correct.confidence != "full":
        return 1
    if broken.ok or not broken.unresolved_angle_ids:
        return 1
    if "unresolved_required_model_angle" not in {finding.code for finding in broken.findings}:
        return 1
    print("flowguard model-angle deliberation template checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


MODEL_ANGLE_DELIBERATION_NOTES_TEMPLATE = """# FlowGuard Model-Angle Deliberation

Use this route before trusting a single model boundary. The agent should list
free-form candidate angles in plain language:

- What does the current model already see?
- What might it miss?
- What can fail if that missing angle is ignored?
- Should the work reuse a model, extend it, add a child model, create a new
  model, scope the angle out, defer it, or ask for human review?
- Which owner route must produce the real evidence?

Known routes are hints, not the whole imagination space. A row can name an
unusual angle such as pricing semantics, lifecycle, installation sync,
human-approval policy, release evidence, or project topology as long as it also
names the consequence and owner route.
"""
