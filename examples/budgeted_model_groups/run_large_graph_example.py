"""Run a small FlowPilot-style graph through the budgeted model-group helper."""

from __future__ import annotations

import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from flowguard import BudgetedGraphConfig, Invariant, InvariantResult, run_budgeted_graph_checks  # noqa: E402


@dataclass(frozen=True)
class ExampleState:
    phase: str
    index: int
    branch: str = "root"


def encode_state(state: ExampleState):
    return asdict(state)


def decode_state(payload):
    return ExampleState(**payload)


def state_id(state: ExampleState) -> str:
    return f"{state.phase}:{state.index}:{state.branch}"


def transition(state: ExampleState):
    if state.phase == "done":
        return ()
    if state.index >= 12:
        return (("complete", ExampleState("done", state.index, state.branch)),)
    return (
        ("keep_main_path", ExampleState("running", state.index + 1, state.branch)),
        ("try_capability_branch", ExampleState("running", state.index + 1, f"{state.branch}.cap")),
    )


def branch_depth_is_bounded(state: ExampleState, _trace):
    if state.branch.count(".") <= 12:
        return InvariantResult.pass_()
    return InvariantResult.fail("capability branch grew beyond the modeled bound")


def main() -> int:
    budget = int(os.environ.get("FLOWGUARD_EXAMPLE_BUDGET", "10000"))
    config = BudgetedGraphConfig(
        model_name="flowpilot-style-large-graph-example",
        initial_states=(ExampleState("running", 0),),
        transition_fn=transition,
        state_id=state_id,
        encode_state=encode_state,
        decode_state=decode_state,
        budget_per_shard=budget,
        max_shards_per_run=1,
        required_labels=("complete",),
        invariants=(
            Invariant(
                "branch_depth_is_bounded",
                "Example branch depth stays within the finite abstraction.",
                branch_depth_is_bounded,
            ),
        ),
        fingerprint_parts=("flowpilot-style-large-graph-example-v1",),
    )
    report = run_budgeted_graph_checks(config)
    print(report.format_text())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
