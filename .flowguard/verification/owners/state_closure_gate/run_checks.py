"""Run FlowGuard checks for the automatic state closure gate."""

from __future__ import annotations

from pathlib import Path
import os
import sys

_FLOWGUARD_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_FLOWGUARD_MODEL_ROOT = _FLOWGUARD_PROJECT_ROOT / ".flowguard" / "models" / "owners" / "state_closure_gate"
for _flowguard_path in (_FLOWGUARD_PROJECT_ROOT, _FLOWGUARD_MODEL_ROOT):
    if str(_flowguard_path) not in sys.path:
        sys.path.insert(0, str(_flowguard_path))

from flowguard import (
    STATE_CLOSURE_DIMENSION_EXTERNAL_INPUT,
    STATE_CLOSURE_HANDLING_ACCEPT_AS_NORMAL,
    STATE_CLOSURE_HANDLING_REJECT,
    STATE_CLOSURE_POLICY_OPEN,
    StateClosureDimension,
    StateClosurePlan,
    review_state_closure,
    run_exact_sequence,
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
    exact = run_exact_sequence(
        workflow=model.build_correct_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=tuple(
            input_obj
            for input_obj in model.EXTERNAL_INPUTS
            if input_obj.action_type != "observe_side_effect_before_resolution"
        ),
        invariants=model.INVARIANTS,
    )
    exact_ok = (
        exact.model_report.ok
        and len(exact.final_states) == 1
        and exact.final_states[0].final_claim == "full"
    )
    print(
        "correct_state_closure_gate: "
        + ("observed=OK expected=OK match=yes exact=yes" if exact_ok else "observed=VIOLATION expected=OK match=no")
    )
    # Each broken workflow has a smallest witness.  Keep the proof bounded to
    # that witness instead of enumerating the full five-input product: the
    # missing-generation case is caught by its absent required label, while
    # the two unsafe cases violate an invariant on their first input.
    broken_workflows = model.build_broken_workflows()
    cases = (
        FormalWorkflowCase(
            broken_workflows[0].name,
            broken_workflows[0],
            False,
            required_labels=("unknown_case_generated",),
            max_sequence_length=2,
        ),
        FormalWorkflowCase(
            broken_workflows[1].name,
            broken_workflows[1],
            False,
            max_sequence_length=1,
        ),
        FormalWorkflowCase(
            broken_workflows[2].name,
            broken_workflows[2],
            False,
            max_sequence_length=1,
        ),
    )
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
    return exact_ok and report.ok


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

from flowguard.native_case_runner import native_main
if __name__ == "__main__":
    # Native evidence is temporary work output.  Isolate this invocation so
    # native_main does not scan the entire historical evidence tree on every
    # direct owner check.
    os.environ.setdefault(
        "FLOWGUARD_OUTPUT_DIR",
        str(
            _FLOWGUARD_PROJECT_ROOT
            / "work"
            / "flowguard"
            / "native-owner-tests"
            / f"state-closure-gate-{os.getpid()}"
        ),
    )
    raise SystemExit(native_main("model:state_closure_gate", main))
