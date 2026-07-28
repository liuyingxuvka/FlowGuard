"""Run FlowGuard checks for AI entry surface reduction."""

from __future__ import annotations

import model


HAPPY_PATH = (
    "prepare_openspec",
    "add_api_layers",
    "add_compact_templates",
    "update_guidance_and_inventory",
    "run_validations",
    "sync_install_shadow_git",
    "claim_done",
)


def run_block(block, actions: tuple[str, ...]):
    state = model.initial_state()
    rows = []
    for action in actions:
        (result,) = tuple(block.apply(model.EntryAction(action), state))
        rows.append((action, result.label, result.output.status, result.new_state))
        state = result.new_state
    return state, tuple(rows)


def run_case(name: str, block, *, expect_done: str) -> bool:
    state, rows = run_block(block, HAPPY_PATH)
    ok = state.done_claim == expect_done
    print(f"{name}: {'OK' if ok else 'FAILED'}")
    for action, label, status, _state in rows:
        print(f"  - {action}: {label} ({status})")
    print(f"  final_done_claim={state.done_claim}")
    print()
    return ok


def main() -> int:
    checks = (
        run_case("correct_ai_entry_reduction", model.CorrectAIEntryReduction(), expect_done="accepted"),
        run_case("broken_default_uses_full_api", model.BrokenDefaultUsesFullApi(), expect_done="rejected"),
        run_case(
            "broken_compact_drops_safety_evidence",
            model.BrokenCompactDropsSafetyEvidence(),
            expect_done="rejected",
        ),
        run_case("broken_full_path_missing", model.BrokenFullPathMissing(), expect_done="rejected"),
    )
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
