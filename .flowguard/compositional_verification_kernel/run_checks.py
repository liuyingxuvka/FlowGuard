"""Run the portable compositional verification kernel model checks."""

from __future__ import annotations

from flowguard import run_exact_sequence
from flowguard.formal_runner import FormalWorkflowCase, run_formal_workflow_suite

import model


REQUIRED_LABELS = (
    "validated",
    "semantics_checked",
    "refinement_checked",
    "composition_checked",
    "system_interactions_checked",
    "accepted",
)


EXPECTED_TERMINALS = {
    "bad-schema": ("invalid", "non_current_schema"),
    "bad-temporal": ("fail", "temporal_not_passed"),
    "bad-refinement": ("blocked", "refinement_not_passed"),
    "bad-provider": ("blocked", "assumption_provider_not_passed"),
    "bad-slice": ("blocked", "impact_slice_not_passed"),
    "bad-system": ("fail", "system_interaction_not_passed"),
    "bad-truncation": ("blocked", "exploration_incomplete"),
    "safety-fail-with-truncation": (
        "fail",
        "confirmed_safety_failure_with_truncation_residual",
    ),
    "temporal-observation-with-truncation": ("blocked", "exploration_incomplete"),
    "system-not-run": ("blocked", "system_interaction_not_passed"),
}


def status_classification_ok() -> bool:
    ok = True
    for request in model.EXTERNAL_INPUTS[1:]:
        run = run_exact_sequence(
            workflow=model.workflow(),
            initial_state=model.initial_state(),
            external_input_sequence=(request,),
            invariants=model.INVARIANTS,
        )
        terminal_trace = (
            run.traces[0]
            if run.traces
            else run.model_report.dead_branches[0].trace
            if run.model_report.dead_branches
            else None
        )
        terminal = terminal_trace.final_output if terminal_trace is not None else None
        observed = (
            (terminal.status, terminal.reason)
            if isinstance(terminal, model.VerificationRejected)
            else None
        )
        expected = EXPECTED_TERMINALS[request.request_id]
        case_ok = observed == expected
        print(
            f"status:{request.request_id}: "
            f"{'pass' if case_ok else f'failed expected={expected!r} observed={observed!r}'}"
        )
        ok = ok and case_ok
    return ok


def main() -> int:
    correct = run_exact_sequence(
        workflow=model.workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=(model.EXTERNAL_INPUTS[0],),
        invariants=model.INVARIANTS,
    )
    correct_ok = correct.model_report.ok
    print(f"correct_portable_kernel: {'exact model pass' if correct_ok else 'failed'}")
    classification_ok = status_classification_ok()
    report = run_formal_workflow_suite(
        "compositional_verification_kernel",
        (
            FormalWorkflowCase(
                "broken_schema_gate",
                model.workflow(schema_gate=model.BrokenSchemaGate()),
                False,
            ),
            FormalWorkflowCase(
                "broken_temporal_gate",
                model.workflow(semantics_gate=model.BrokenTemporalGate()),
                False,
            ),
            FormalWorkflowCase(
                "broken_refinement_gate",
                model.workflow(refinement_gate=model.BrokenRefinementGate()),
                False,
            ),
            FormalWorkflowCase(
                "broken_composition_gate",
                model.workflow(composition_gate=model.BrokenCompositionGate()),
                False,
            ),
            FormalWorkflowCase(
                "broken_impact_slice_gate",
                model.workflow(system_interaction_gate=model.BrokenImpactSliceGate()),
                False,
            ),
            FormalWorkflowCase(
                "broken_system_interaction_gate",
                model.workflow(system_interaction_gate=model.BrokenSystemInteractionGate()),
                False,
            ),
            FormalWorkflowCase(
                "broken_exploration_completeness_gate",
                model.workflow(
                    system_interaction_gate=model.BrokenExplorationCompletenessGate()
                ),
                False,
            ),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=REQUIRED_LABELS,
        protected_error_class="portable_verification_missing_gate",
    )
    return 0 if correct_ok and classification_ok and report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
