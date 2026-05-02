"""Print copyable Mermaid source for a small FlowGuard state graph."""

from __future__ import annotations

from dataclasses import dataclass

from flowguard import (
    GraphEdge,
    LoopCheckConfig,
    check_loops,
    loop_report_to_mermaid_text,
    mermaid_code_block,
)


@dataclass(frozen=True)
class ReviewState:
    phase: str
    retry_count: int = 0


def transition(state: ReviewState) -> tuple[GraphEdge, ...]:
    if state.phase == "new":
        return (GraphEdge(state, ReviewState("error", retry_count=0), "start"),)
    if state.phase == "error" and state.retry_count == 0:
        return (GraphEdge(state, ReviewState("retry", retry_count=1), "retry"),)
    if state.phase == "retry":
        return (GraphEdge(state, ReviewState("done", retry_count=1), "finish"),)
    return ()


def main() -> int:
    report = check_loops(
        LoopCheckConfig(
            initial_states=(ReviewState("new"),),
            transition_fn=transition,
            is_terminal=lambda state: state.phase == "done",
            is_success=lambda state: state.phase == "done",
            required_success=True,
        )
    )
    print(
        mermaid_code_block(
            loop_report_to_mermaid_text(
                report,
                title="FlowGuard retry flow",
                include_reasons=False,
            )
        )
    )
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
