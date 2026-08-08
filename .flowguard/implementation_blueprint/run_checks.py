"""Run native checks for the implementation-blueprint FlowGuard model."""

from __future__ import annotations

from pathlib import Path
import subprocess
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
    "manifest_qualification_complete",
    "behavior_readiness_complete",
    "target_system_blueprint_complete",
    "projection_verified",
    "done_accepted",
)


def _bad_case_label(action: model.BlueprintAction) -> str:
    return f"{action.scenario_id}_blocked"


def _bad_case_id(action: model.BlueprintAction) -> str:
    return action.scenario_id


def _expected_finding_codes(action: model.BlueprintAction) -> tuple[str, ...]:
    return model.SCENARIOS[action.scenario_id].expected_finding_codes


def run_good_path() -> bool:
    results = tuple(
        run_exact_workflow_case(
            f"bounded blueprint path qualified: {action.scenario_id}",
            workflow=model.build_workflow(),
            initial_state=model.initial_state(),
            external_input_sequence=(action,) * model.MAX_SEQUENCE_LENGTH,
            invariants=model.INVARIANTS,
            final_state_predicate=lambda state, scenario_id=action.scenario_id: (
                state.done_claim == "accepted"
                and state.static_manifest_status == "complete"
                and state.behavior_status == "complete"
                and state.readiness_status == "ready"
                and state.delegated_assertion_status
                == (
                    "current"
                    if scenario_id == "delegated_direct_terminal"
                    else "not_applicable"
                )
                and state.claim_boundary == model.MODEL_CLAIM_BOUNDARY
            ),
        )
        for action in model.GOOD_ACTIONS
    )
    return all(results)


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
        external_inputs=model.GOOD_ACTIONS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=GOOD_LABELS,
        protected_error_class="implementation_blueprint_incomplete",
    )


def run_native_pytest_contract() -> bool:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *model.NATIVE_PYTEST_SELECTORS,
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=ROOT,
        check=False,
    )
    return completed.returncode == 0


def main() -> int:
    good_ok = run_good_path()
    reasons_ok = run_bad_case_reason_review()
    formal_report = run_formal_bad_case_suite()
    obligation_bindings_ok = model.native_test_obligation_bindings_are_executed()
    pytest_ok = run_native_pytest_contract()
    if (
        good_ok
        and reasons_ok
        and formal_report.ok
        and obligation_bindings_ok
        and pytest_ok
    ):
        print(
            "implementation_blueprint checks passed; "
            f"handled_bad_cases={len(model.BAD_ACTIONS)}; "
            f"good_cases={len(model.GOOD_ACTIONS)}; "
            f"native_selectors={len(model.NATIVE_PYTEST_SELECTORS)}; "
            "static_manifest_status=complete"
        )
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
