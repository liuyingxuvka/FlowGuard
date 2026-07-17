"""Run the existing-model preflight FlowGuard checks."""

from __future__ import annotations

from flowguard.formal_runner import FormalWorkflowCase, run_exact_workflow_case, run_formal_workflow_suite

import model


REQUIRED_LABELS = (
    "light_existing_model_grounding",
    "full_existing_model_preflight",
    "blocked_duplicate_risk",
    "preflight_skipped_with_reason",
    "blocked_surface_inventory_incomplete",
)


def main() -> int:
    exact_inputs = tuple(
        input_obj
        for input_obj in model.EXTERNAL_INPUTS
        if input_obj.task_id not in {
            "unhandled-duplicate",
            "omitted-same-intent-surface",
            "wrong-plane-promotion",
            "stale-provider-context",
        }
    )
    exact_ok = run_exact_workflow_case(
        "correct_existing_model_preflight",
        workflow=model.build_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=exact_inputs,
        invariants=model.INVARIANTS,
        final_state_predicate=lambda state: not state.blocked
        and len(state.route_selected) == len(exact_inputs),
    )
    report = run_formal_workflow_suite(
        "existing_model_preflight",
        (
            FormalWorkflowCase(
                "broken_bypasses_existing_model_search",
                model.build_workflow(search_block=model.BrokenBypassSearch()),
                False,
            ),
            FormalWorkflowCase(
                "broken_uses_light_grounding_for_full_work",
                model.build_workflow(search_block=model.BrokenLightForFull()),
                False,
            ),
            FormalWorkflowCase(
                "broken_ignores_same_intent_surface_inventory",
                model.build_workflow(search_block=model.BrokenIgnoresSurfaceInventory()),
                False,
            ),
            FormalWorkflowCase(
                "broken_promotes_related_plane_context",
                model.build_workflow(search_block=model.BrokenPromotesRelatedPlane()),
                False,
            ),
            FormalWorkflowCase(
                "stale_provider_context_blocks",
                model.build_workflow(search_block=model.BrokenIgnoresSurfaceInventory()),
                False,
                required_labels=("broken_grounded_from_caller_selected_surface_subset",),
                external_inputs=(
                    next(item for item in model.EXTERNAL_INPUTS if item.task_id == "stale-provider-context"),
                ),
                max_sequence_length=3,
            ),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=REQUIRED_LABELS,
        protected_error_class="existing_model_preflight_bypassed",
    )
    return 0 if exact_ok and report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
