"""Run native checks for the implementation-blueprint FlowGuard model."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flowguard.formal_runner import (
    FormalWorkflowCase,
    run_exact_workflow_case,
    run_formal_workflow_suite,
)
import model


GOOD_LABELS = (
    "inventory_complete",
    "binding_complete",
    "static_complete_empirical_not_run",
    "projection_verified",
    "done_accepted",
)


def _bad_case_label(action: model.BlueprintAction) -> str:
    if action.automatic_rebuild_requested:
        return "automatic_rebuild_attempt_blocked"
    return f"{action.scenario_id}_blocked"


def _bad_case_id(action: model.BlueprintAction) -> str:
    if action.automatic_rebuild_requested:
        return "automatic_rebuild_attempt"
    return action.scenario_id


def _expected_finding_codes(action: model.BlueprintAction) -> tuple[str, ...]:
    if action.automatic_rebuild_requested:
        return ("automatic_reconstruction_forbidden",)
    return model.SCENARIOS[action.scenario_id].expected_finding_codes


def run_good_path() -> bool:
    return run_exact_workflow_case(
        "static blueprint complete with empirical reconstruction not run",
        workflow=model.build_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=(model.GOOD_ACTION,) * model.MAX_SEQUENCE_LENGTH,
        invariants=model.INVARIANTS,
        final_state_predicate=lambda state: (
            state.done_claim == "accepted"
            and state.static_status == "complete"
            and state.empirical_status == "not_run"
            and not state.reconstruction_executed
            and state.claim_text
            == "blueprint complete; reconstruction not verified"
        ),
    )


def run_bad_case_reason_review() -> bool:
    unexpected: list[str] = []
    for action in model.BAD_ACTIONS:
        block = model.ReviewImplementationBlueprint()
        state = model.initial_state()
        reached_terminal = False
        invariant_ok = True
        for _ in range(model.MAX_SEQUENCE_LENGTH):
            results = tuple(block.apply(action, state))
            if len(results) != 1:
                invariant_ok = False
                break
            result = results[0]
            state = result.new_state
            invariant_ok = invariant_ok and all(
                invariant.check(state, None).ok for invariant in model.INVARIANTS
            )
            if model.terminal_predicate(result.output, state, None):
                reached_terminal = True
                break
        expected_codes = set(_expected_finding_codes(action))
        caught = (
            reached_terminal
            and invariant_ok
            and state.done_claim == "rejected"
            and state.empirical_status == "not_run"
            and not state.reconstruction_executed
            and expected_codes.issubset(set(state.finding_codes))
        )
        if not caught:
            unexpected.append(_bad_case_id(action))
    ok = not unexpected
    print(
        "implementation-blueprint bad-case reasons: "
        f"{'pass' if ok else 'fail'}; "
        f"cases={len(model.BAD_ACTIONS)}; "
        f"unexpected={','.join(unexpected) or 'none'}"
    )
    print()
    return ok


def run_formal_bad_case_suite():
    cases = tuple(
        FormalWorkflowCase(
            f"handled_{_bad_case_id(action)}",
            model.build_workflow(),
            True,
            required_labels=(_bad_case_label(action),),
            known_bad_labels=(_bad_case_label(action),),
            external_inputs=(action,),
            max_sequence_length=model.MAX_SEQUENCE_LENGTH,
            terminal_predicate=model.terminal_predicate,
            protected_error_class="implementation_blueprint_incomplete",
            allowed_success_statuses=("pass", "pass_with_gaps"),
        )
        for action in model.BAD_ACTIONS
    )
    return run_formal_workflow_suite(
        "implementation_blueprint",
        cases,
        initial_states=(model.initial_state(),),
        external_inputs=(model.GOOD_ACTION,),
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=GOOD_LABELS,
        protected_error_class="implementation_blueprint_incomplete",
    )


def main() -> int:
    good_ok = run_good_path()
    reasons_ok = run_bad_case_reason_review()
    formal_report = run_formal_bad_case_suite()
    if good_ok and reasons_ok and formal_report.ok:
        print(
            "implementation_blueprint checks passed; "
            f"handled_bad_cases={len(model.BAD_ACTIONS)}; "
            "static_status=complete; empirical_status=not_run; "
            "automatic_rebuild=blocked"
        )
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
