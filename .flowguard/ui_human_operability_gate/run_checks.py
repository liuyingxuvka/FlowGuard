"""Run FlowGuard checks for UI human-operability hardening."""

from __future__ import annotations

import json
from pathlib import Path

import model


def run_block(block, actions: tuple[str, ...]):
    state = model.initial_state()
    rows = []
    for action in actions:
        (result,) = tuple(block.apply(model.UIHumanAction(action), state))
        rows.append({"action": action, "label": result.label, "status": result.output.status})
        state = result.new_state
    return state, tuple(rows)


def run_case(name: str, block, *, expect_done: str, expect_invariant: bool = True) -> dict[str, object]:
    state, rows = run_block(block, model.HAPPY_PATH)
    invariant = model.no_human_operable_done_without_evidence(state, ()).passed
    ok = state.done_claim == expect_done and invariant is expect_invariant
    return {
        "case": name,
        "ok": ok,
        "expected_done": expect_done,
        "actual_done": state.done_claim,
        "expected_invariant": expect_invariant,
        "invariant_ok": invariant,
        "rows": list(rows),
    }


def main() -> int:
    cases = (
        run_case("correct_ui_human_operability", model.CorrectUIHumanOperabilityHardening(), expect_done="accepted"),
        run_case("broken_missing_task_coverage", model.BrokenMissingTaskCoverage(), expect_done="rejected"),
        run_case("broken_orphan_primary_control", model.BrokenOrphanPrimaryControl(), expect_done="rejected"),
        run_case("broken_duplicate_primary_action", model.BrokenDuplicatePrimaryAction(), expect_done="rejected"),
        run_case("broken_dialog_return", model.BrokenDialogReturn(), expect_done="rejected"),
        run_case("broken_keyboard_focus", model.BrokenKeyboardFocus(), expect_done="rejected"),
        run_case("broken_confused_walkthrough", model.BrokenConfusedWalkthrough(), expect_done="rejected"),
        run_case(
            "broken_overbroad_human_done",
            model.BrokenOverbroadHumanDone(),
            expect_done="accepted",
            expect_invariant=False,
        ),
    )
    ok = all(bool(case["ok"]) for case in cases)
    payload = {"ok": ok, "cases": cases}
    Path(__file__).with_name("result.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("=== flowguard UI human-operability hardening self-model ===")
    print("status:", "OK" if ok else "FAILED")
    for case in cases:
        print(
            f"- {case['case']}: {'OK' if case['ok'] else 'FAILED'} "
            f"(done={case['actual_done']}, invariant={case['invariant_ok']})"
        )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
