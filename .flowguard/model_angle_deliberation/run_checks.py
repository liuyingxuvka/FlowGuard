"""Run FlowGuard self-checks for model-angle deliberation."""

from model import correct_model_angle_deliberations, unresolved_model_angle_deliberations
from flowguard import review_model_angle_deliberations


def main() -> int:
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
