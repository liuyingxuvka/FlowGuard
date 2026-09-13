"""Run FlowGuard checks for AI entry surface reduction."""

from __future__ import annotations

from pathlib import Path
import sys

_FLOWGUARD_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_FLOWGUARD_MODEL_ROOT = _FLOWGUARD_PROJECT_ROOT / ".flowguard" / "models" / "owners" / "ai_entry_surface_reduction"
for _flowguard_path in (_FLOWGUARD_PROJECT_ROOT, _FLOWGUARD_MODEL_ROOT):
    if str(_flowguard_path) not in sys.path:
        sys.path.insert(0, str(_flowguard_path))

from pathlib import Path
import sys


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


def run_case(name: str, block, *, expect_done: str) -> dict[str, object]:
    state, rows = run_block(block, HAPPY_PATH)
    ok = state.done_claim == expect_done
    print(f"{name}: {'OK' if ok else 'FAILED'}")
    for action, label, status, _state in rows:
        print(f"  - {action}: {label} ({status})")
    print(f"  final_done_claim={state.done_claim}")
    print()
    # Keep the wrapper oracle (``ok``) separate from the model observation.
    # A broken block that is correctly rejected is a passing check whose
    # observed model status is still a violation; the native adapter consumes
    # both fields without guessing from display text.
    return {
        "name": name,
        "ok": ok,
        "observed_status": "ok" if state.done_claim == "accepted" else "violation",
        "observed_finding_codes": [
            label
            for _action, label, _status, _state in rows
            if label and label not in {"done_accepted", "local_surfaces_synced"}
        ],
        "final_done_claim": state.done_claim,
    }


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
    return 0 if all(check["ok"] for check in checks) else 1

from flowguard.native_case_runner import native_main
if __name__ == "__main__":
    raise SystemExit(native_main("model:ai_entry_surface_reduction", main))
