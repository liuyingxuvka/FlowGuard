"""Run FlowGuard checks for the automatic state closure gate."""

from __future__ import annotations

from flowguard import (
    STATE_CLOSURE_DIMENSION_EXTERNAL_INPUT,
    STATE_CLOSURE_HANDLING_ACCEPT_AS_NORMAL,
    STATE_CLOSURE_HANDLING_REJECT,
    STATE_CLOSURE_POLICY_OPEN,
    StateClosureDimension,
    StateClosurePlan,
    review_state_closure,
)
from flowguard.formal_runner import FormalWorkflowCase, run_formal_workflow_suite
import model


REQUIRED_LABELS = (
    "unknown_observed",
    "unknown_case_generated",
    "safe_handling_declared",
    "full_claim_accepted",
    "scoped_or_blocked_claim",
)


def run_workflow_suite() -> bool:
    cases = [FormalWorkflowCase("correct_state_closure_gate", model.build_correct_workflow(), True)]
    cases.extend(FormalWorkflowCase(broken.name, broken, False) for broken in model.build_broken_workflows())
    report = run_formal_workflow_suite(
        "state_closure_gate",
        tuple(cases),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=REQUIRED_LABELS,
        protected_error_class="unknown_state_not_safely_closed",
    )
    return report.ok


def helper_case(name: str, plan: StateClosurePlan, *, expect_ok: bool) -> bool:
    report = review_state_closure(plan)
    ok = report.ok is expect_ok
    print(f"{name}: {'OK' if ok else 'VIOLATION'}")
    print(report.format_text())
    print()
    return ok


def run_helper_cases() -> bool:
    return all(
        (
            helper_case(
                "safe_unknown_rejects_before_side_effect",
                StateClosurePlan(
                    "safe",
                    dimensions=(
                        StateClosureDimension(
                            "external_input",
                            STATE_CLOSURE_DIMENSION_EXTERNAL_INPUT,
                            policy=STATE_CLOSURE_POLICY_OPEN,
                            known_values=("known",),
                            representative_unknowns=("other",),
                            handling=STATE_CLOSURE_HANDLING_REJECT,
                        ),
                    ),
                ),
                expect_ok=True,
            ),
            helper_case(
                "unsafe_unknown_accepts_as_normal",
                StateClosurePlan(
                    "unsafe",
                    dimensions=(
                        StateClosureDimension(
                            "external_input",
                            STATE_CLOSURE_DIMENSION_EXTERNAL_INPUT,
                            policy=STATE_CLOSURE_POLICY_OPEN,
                            known_values=("known",),
                            representative_unknowns=("other",),
                            handling=STATE_CLOSURE_HANDLING_ACCEPT_AS_NORMAL,
                        ),
                    ),
                ),
                expect_ok=False,
            ),
        )
    )


def main() -> int:
    workflow_checks = run_workflow_suite()
    helper_checks = run_helper_cases()
    return 0 if workflow_checks and helper_checks else 1


if __name__ == "__main__":
    raise SystemExit(main())
