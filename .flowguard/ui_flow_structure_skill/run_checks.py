"""Run the UI flow structure satellite rollout model checks."""

from __future__ import annotations

import json
import os
from pathlib import Path

from flowguard import run_exact_sequence
import model


def run_sequence(name: str, workflow, *, expect_ok: bool, sequence: tuple[model.RolloutAction, ...]) -> bool:
    run = run_exact_sequence(
        workflow=workflow,
        initial_state=model.initial_state(),
        external_input_sequence=sequence,
        invariants=model.INVARIANTS,
    )
    ok = run.model_report.ok
    print(f"{name}: {'OK' if ok else 'VIOLATION'}")
    print(run.model_report.format_text(max_examples=1))
    return ok is expect_ok


def run_rejected_release_sequence(name: str, workflow, sequence: tuple[model.RolloutAction, ...]) -> bool:
    run = run_exact_sequence(
        workflow=workflow,
        initial_state=model.initial_state(),
        external_input_sequence=sequence,
        invariants=model.INVARIANTS,
    )
    rejected = (
        run.model_report.ok
        and len(run.final_states) == 1
        and run.final_states[0].release_claim != "accepted"
    )
    print(f"{name}: {'REJECTED AS REQUIRED' if rejected else 'UNSAFE OR UNOBSERVED'}")
    print(run.model_report.format_text(max_examples=1))
    return rejected


DESIGN_SEQUENCE = (
    model.RolloutAction("create_ui_model"),
    model.RolloutAction("review_ui_model"),
    model.RolloutAction("review_content_visibility_plan"),
    model.RolloutAction("review_product_language"),
    model.RolloutAction("review_journey_coverage"),
    model.RolloutAction("derive_structure"),
    model.RolloutAction("document_skill"),
)

IMPLEMENTATION_SEQUENCE = DESIGN_SEQUENCE[:-1] + (
    model.RolloutAction("review_implementation_validation"),
    model.RolloutAction("document_skill"),
    model.RolloutAction("claim_implemented_ui"),
)


def main() -> int:
    checks = (
        run_sequence(
            "correct_ui_flow_structure_rollout",
            model.build_correct_workflow(),
            expect_ok=True,
            sequence=model.RELEASE_INPUTS,
        ),
        run_sequence(
            "broken_layout_only_without_ui_model",
            model.build_broken_layout_only_workflow(),
            expect_ok=False,
            sequence=model.RELEASE_INPUTS,
        ),
        run_sequence(
            "broken_missing_expected_product_surface",
            model.build_broken_missing_product_surface_workflow(),
            expect_ok=False,
            sequence=model.RELEASE_INPUTS,
        ),
        run_sequence(
            "broken_cross_surface_product_semantic_drift",
            model.build_broken_product_semantic_drift_workflow(),
            expect_ok=False,
            sequence=model.RELEASE_INPUTS,
        ),
        run_sequence(
            "broken_invalid_behavior_authority_exception",
            model.build_broken_invalid_product_exception_workflow(),
            expect_ok=False,
            sequence=model.RELEASE_INPUTS,
        ),
        run_sequence(
            "broken_typography_role_token_scale_weight_drift",
            model.build_broken_typography_role_drift_workflow(),
            expect_ok=False,
            sequence=model.RELEASE_INPUTS,
        ),
        run_sequence(
            "broken_same_intent_business_authority_drift",
            model.build_broken_business_authority_drift_workflow(),
            expect_ok=False,
            sequence=model.RELEASE_INPUTS,
        ),
        run_sequence(
            "broken_fourth_content_visibility_class",
            model.build_broken_fourth_visibility_class_workflow(),
            expect_ok=False,
            sequence=model.RELEASE_INPUTS,
        ),
        run_sequence(
            "broken_internal_product_content_leak",
            model.build_broken_internal_product_content_leak_workflow(),
            expect_ok=False,
            sequence=model.RELEASE_INPUTS,
        ),
        run_sequence(
            "broken_missing_content_visibility_plan",
            model.build_broken_missing_visibility_plan_workflow(),
            expect_ok=False,
            sequence=model.RELEASE_INPUTS,
        ),
        run_sequence(
            "broken_unclassified_content_accepted",
            model.build_broken_unclassified_content_workflow(),
            expect_ok=False,
            sequence=model.RELEASE_INPUTS,
        ),
        run_sequence(
            "broken_untyped_user_need_accepted",
            model.build_broken_untyped_user_need_workflow(),
            expect_ok=False,
            sequence=model.RELEASE_INPUTS,
        ),
        run_sequence(
            "broken_overbroad_control_label_exemption_accepted",
            model.build_broken_overbroad_control_label_exemption_workflow(),
            expect_ok=False,
            sequence=model.RELEASE_INPUTS,
        ),
        run_sequence(
            "broken_internal_content_mapped_to_ui",
            model.build_broken_internal_content_mapping_workflow(),
            expect_ok=False,
            sequence=model.RELEASE_INPUTS,
        ),
        run_sequence(
            "broken_on_demand_content_visible_by_default",
            model.build_broken_on_demand_default_visible_workflow(),
            expect_ok=False,
            sequence=model.RELEASE_INPUTS,
        ),
        run_sequence(
            "broken_on_demand_non_display_state_bypass",
            model.build_broken_on_demand_mapping_state_bypass_workflow(),
            expect_ok=False,
            sequence=model.RELEASE_INPUTS,
        ),
        run_sequence(
            "broken_on_demand_content_missing_reveal",
            model.build_broken_on_demand_missing_reveal_workflow(),
            expect_ok=False,
            sequence=model.RELEASE_INPUTS,
        ),
        run_sequence(
            "broken_on_demand_content_missing_return",
            model.build_broken_on_demand_no_return_workflow(),
            expect_ok=False,
            sequence=model.RELEASE_INPUTS,
        ),
        run_sequence(
            "broken_on_demand_affordance_or_feedback_gap",
            model.build_broken_on_demand_affordance_feedback_workflow(),
            expect_ok=False,
            sequence=model.RELEASE_INPUTS,
        ),
        run_rejected_release_sequence(
            "broken_no_parent_child_topology",
            model.build_broken_no_topology_workflow(),
            model.RELEASE_INPUTS,
        ),
        run_sequence(
            "broken_no_journey_coverage",
            model.build_broken_no_journey_coverage_workflow(),
            expect_ok=False,
            sequence=model.RELEASE_INPUTS,
        ),
        run_sequence(
            "broken_no_visible_branch_coverage",
            model.build_broken_no_visible_branch_coverage_workflow(),
            expect_ok=False,
            sequence=model.RELEASE_INPUTS,
        ),
        run_sequence(
            "broken_no_typography_handoff",
            model.build_broken_no_typography_handoff_workflow(),
            expect_ok=False,
            sequence=model.RELEASE_INPUTS,
        ),
        run_sequence(
            "correct_implemented_ui_validation",
            model.build_correct_workflow(),
            expect_ok=True,
            sequence=IMPLEMENTATION_SEQUENCE,
        ),
        run_sequence(
            "broken_implementation_without_feature_alignment_sequence",
            model.build_broken_implementation_without_feature_alignment_workflow(),
            expect_ok=False,
            sequence=IMPLEMENTATION_SEQUENCE,
        ),
        run_sequence(
            "broken_implementation_without_clickthrough_sequence",
            model.build_broken_implementation_without_clickthrough_workflow(),
            expect_ok=False,
            sequence=IMPLEMENTATION_SEQUENCE,
        ),
        run_sequence(
            "broken_stale_implementation_evidence_sequence",
            model.build_broken_stale_implementation_evidence_workflow(),
            expect_ok=False,
            sequence=IMPLEMENTATION_SEQUENCE,
        ),
        run_sequence(
            "broken_opaque_content_visibility_evidence_sequence",
            model.build_broken_opaque_content_visibility_evidence_workflow(),
            expect_ok=False,
            sequence=IMPLEMENTATION_SEQUENCE,
        ),
        run_sequence(
            "broken_cross_content_visibility_evidence_sequence",
            model.build_broken_cross_content_visibility_evidence_workflow(),
            expect_ok=False,
            sequence=IMPLEMENTATION_SEQUENCE,
        ),
    )
    ok = all(checks)
    payload = {
        "ok": ok,
        "check_count": len(checks),
        "passed_expectations": sum(1 for check in checks if check),
    }
    output_dir = Path(os.environ.get("FLOWGUARD_OUTPUT_DIR", Path(__file__).parent))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir.joinpath("result.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
