"""Template text for the specification work-package bridge."""

SPEC_WORK_PACKAGE_MODEL_TEMPLATE = r'''"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Model provider-owned tasks as one development-process work package with
bidirectional obligation/check mappings.

Guards against:
- copying OpenSpec or Spec Kit task authority into FlowGuard;
- unmapped tasks or obligations;
- treating provider checkboxes as terminal evidence.

Use before editing:
specification-provider adapters, verification contracts, or archive gates.

Run:
python .flowguard/spec_provider_work_packages/run_checks.py

Function blocks use Input x State -> Set(Output x State).
"""

from flowguard import (
    SpecCheckDefinition,
    SpecObligation,
    SpecProviderRef,
    SpecTask,
    SpecTaskObligationBinding,
    SpecWorkPackage,
    review_spec_work_package,
)


def build_package():
    return SpecWorkPackage(
        provider=SpecProviderRef("openspec", "openspec"),
        work_package_id="replace-with-change-id",
        change_id="replace-with-change-id",
        tasks=(SpecTask("1.1", "Replace with provider task", completed=False),),
        obligations=(SpecObligation("req.example", check_ids=("check.example",)),),
        checks=(
            SpecCheckDefinition(
                "check.example",
                ("python", "-m", "pytest", "-q"),
                obligation_ids=("req.example",),
                validation_obligation_ids=("validation:example",),
            ),
        ),
        bindings=(
            SpecTaskObligationBinding(
                "binding:1.1",
                task_ids=("1.1",),
                obligation_ids=("req.example",),
                check_ids=("check.example",),
            ),
        ),
    )


def run_model_checks():
    review = review_spec_work_package(build_package())
    return {
        "artifact_type": "flowguard_spec_work_package_template_review",
        "ok": review.ok,
        "status": review.status,
        "findings": list(review.finding_codes),
        "claim_boundary": "Mapping proof only; provider verification and terminal receipts remain separate.",
    }
'''


SPEC_WORK_PACKAGE_RUN_CHECKS_TEMPLATE = r'''"""Run the specification work-package starter model."""

import json

from model import run_model_checks


def main():
    report = run_model_checks()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


__all__ = (
    "SPEC_WORK_PACKAGE_MODEL_TEMPLATE",
    "SPEC_WORK_PACKAGE_RUN_CHECKS_TEMPLATE",
)
