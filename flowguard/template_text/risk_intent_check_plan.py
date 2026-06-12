"""Template text for FlowGuard risk intent check plan route."""

from __future__ import annotations

RISK_INTENT_CHECK_PLAN_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Models a sample item-acceptance workflow with an explicit Risk Intent before
related production changes.

Guards against:
- duplicate acceptance after retries;
- invalid item requests being accepted;
- skipped conformance gaps being hidden as full production confidence.

Use before editing:
acceptance, deduplication, idempotency, side-effect, or confidence-reporting
logic.

Run:
python .flowguard/risk_intent_check_plan/run_checks.py

Replace this sample item workflow with the current behavior under review.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import (
    FlowGuardCheckPlan,
    FunctionResult,
    Invariant,
    InvariantResult,
    MinimumModelContract,
    RiskIntent,
    RiskProfile,
    SkippedCheck,
    TemplateReuseReview,
    Workflow,
    run_model_first_checks,
)


@dataclass(frozen=True)
class ItemInput:
    item_id: str
    should_accept: bool = True


@dataclass(frozen=True)
class Accepted:
    item_id: str


@dataclass(frozen=True)
class Rejected:
    item_id: str
    reason: str


@dataclass(frozen=True)
class State:
    accepted_ids: tuple[str, ...] = ()


class AcceptItem:
    name = "AcceptItem"
    reads = ("accepted_ids",)
    writes = ("accepted_ids",)
    accepted_input_type = ItemInput
    input_description = "item request"
    output_description = "Accepted or Rejected"
    idempotency = "Repeated item_id is rejected as a duplicate."

    def apply(self, input_obj: ItemInput, state: State) -> Iterable[FunctionResult]:
        if not input_obj.should_accept:
            yield FunctionResult(Rejected(input_obj.item_id, "not_allowed"), state, label="rejected")
            return
        if input_obj.item_id in state.accepted_ids:
            yield FunctionResult(Rejected(input_obj.item_id, "duplicate"), state, label="rejected_duplicate")
            return
        yield FunctionResult(
            Accepted(input_obj.item_id),
            replace(state, accepted_ids=state.accepted_ids + (input_obj.item_id,)),
            label="accepted",
        )


def no_duplicate_accepts(state: State, _trace) -> InvariantResult:
    if len(state.accepted_ids) != len(set(state.accepted_ids)):
        return InvariantResult.fail("accepted_ids contains duplicates")
    return InvariantResult.pass_()


def risk_profile() -> RiskProfile:
    return RiskProfile(
        modeled_boundary="sample item acceptance",
        risk_classes=("deduplication", "idempotency", "side_effect"),
        risk_intent=RiskIntent(
            failure_modes=("duplicate acceptance after retry", "invalid item accepted"),
            protected_error_classes=("duplicate_side_effect", "invalid_completion"),
            protected_harms=("downstream workflow acts on the same item twice",),
            must_model_state=("accepted_ids",),
            must_model_side_effects=("acceptance_record_write",),
            completion_evidence=("accepted_id_recorded",),
            adversarial_inputs=("same item repeated", "invalid item request"),
            hard_invariants=("one acceptance per item",),
            known_bad_cases=("retry_accepts_same_item_twice",),
            used_template_ids=("side_effect_at_most_once",),
            blindspots=("real storage isolation requires a conformance replay adapter"),
        ),
        confidence_goal="model_level",
        skipped_checks=(
            SkippedCheck("conformance_replay", "no production adapter exists in this starter template"),
        ),
    )


def build_workflow() -> Workflow:
    return Workflow((AcceptItem(),), name="risk_intent_template")


def build_check_plan() -> FlowGuardCheckPlan:
    return FlowGuardCheckPlan(
        workflow=build_workflow(),
        initial_states=(State(),),
        external_inputs=(ItemInput("item-1"), ItemInput("item-1"), ItemInput("item-bad", False)),
        invariants=(
            Invariant(
                "no_duplicate_accepts",
                "accepted_ids contains each item at most once",
                no_duplicate_accepts,
                metadata={"property_classes": ("deduplication", "idempotency")},
            ),
        ),
        max_sequence_length=2,
        risk_profile=risk_profile(),
        template_reuse_review=TemplateReuseReview(
            used_template_ids=("side_effect_at_most_once",),
            searched_layers=("public", "local"),
            match_template_ids=("side_effect_at_most_once",),
        ),
        minimum_model_contract=MinimumModelContract(
            protected_error_classes=("duplicate_side_effect", "invalid_completion"),
            modeled_state=("accepted_ids",),
            modeled_side_effects=("acceptance_record_write",),
            completion_evidence=("accepted_id_recorded",),
            known_bad_cases=("retry_accepts_same_item_twice",),
        ),
    )


def run_checks():
    return run_model_first_checks(build_check_plan())
'''

RISK_INTENT_CHECK_PLAN_RUN_CHECKS_TEMPLATE = '''"""Run the Risk Intent + CheckPlan template."""

from flowguard import maintenance_scan_plan_from_summary_report, review_maintenance_scan
from model import risk_profile, run_checks


def main() -> int:
    print(f"risk_intent: {risk_profile().modeled_boundary}")
    report = run_checks()
    print(report.format_text())
    print()
    scan = review_maintenance_scan(
        maintenance_scan_plan_from_summary_report(
            report,
            plan_id="risk-intent-summary-bridge",
            claim_scope="done",
        )
    )
    print(scan.format_text())
    return 0 if report.overall_status in {"pass", "pass_with_gaps"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

RISK_INTENT_CHECK_PLAN_NOTES_TEMPLATE = """# FlowGuard Risk Intent CheckPlan Notes

Use this scaffold when the main risk should be named before modeling.

## Risk Intent

Record:

- failure modes;
- protected error classes;
- protected harms;
- state and side effects that must be visible;
- completion evidence;
- known-bad cases that should fail on broken models;
- public/local template ids used, or a no-match reason;
- adversarial inputs or retries;
- hard invariants;
- blindspots.

## Calibration

This template reports model-level confidence only. Add conformance replay or
equivalent real-code evidence before claiming production confidence.
The run script also shows how to bridge the summary report into MaintenanceScan
so route-owned gaps remain visible as scoped or required follow-up actions.
"""

__all__ = [
    'RISK_INTENT_CHECK_PLAN_MODEL_TEMPLATE',
    'RISK_INTENT_CHECK_PLAN_RUN_CHECKS_TEMPLATE',
    'RISK_INTENT_CHECK_PLAN_NOTES_TEMPLATE',
]
