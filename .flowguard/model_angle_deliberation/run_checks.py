"""Run FlowGuard self-checks for model-angle deliberation."""

from model import correct_model_angle_deliberations, unresolved_model_angle_deliberations
from flowguard import review_model_angle_deliberations
from flowguard import Scenario, ScenarioExpectation, review_scenarios

import model


def run_owner_proof_model() -> bool:
    report = review_scenarios(
        (
            Scenario(
                "current_exact_owner_proof",
                "current exact owner proof can support broad confidence",
                model.angle_proof_initial_state(),
                model.GOOD_ANGLE_PROOF_SEQUENCE,
                ScenarioExpectation(expected_status="ok"),
                workflow=model.build_angle_proof_workflow(),
            ),
            Scenario(
                "bare_resolved_boolean",
                "a bare resolved boolean cannot replace owner proof",
                model.angle_proof_initial_state(),
                model.BROKEN_BARE_RESOLUTION_SEQUENCE,
                ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("no_broad_claim_from_bare_resolution",),
                ),
                workflow=model.build_angle_proof_workflow(broken=True),
            ),
        ),
        default_invariants=model.ANGLE_PROOF_INVARIANTS,
    )
    print(report.format_text())
    print()
    return report.ok


def main() -> int:
    owner_proof_ok = run_owner_proof_model()
    correct = review_model_angle_deliberations(
        "self-model-angle-correct",
        correct_model_angle_deliberations(),
        require_review=True,
        broad_claim=True,
    )
    unresolved = review_model_angle_deliberations(
        "self-model-angle-unresolved",
        unresolved_model_angle_deliberations(),
        require_review=True,
        broad_claim=True,
    )

    print(correct.format_text())
    print()
    print(unresolved.format_text())

    if not owner_proof_ok:
        return 1
    if not correct.ok or correct.confidence != "full":
        return 1
    if unresolved.ok:
        return 1
    if "self:open-angle" not in unresolved.unresolved_angle_ids:
        return 1
    print("model_angle_deliberation self-model checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
