"""Workflow composition and branch expansion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

from .core import block_accepts_input, block_name, invoke_block, normalize_function_results
from .report import DeadBranch, ExceptionBranch
from .trace import Trace, TraceStep


TerminalPredicate = Callable[[Any, Any, Trace], bool]


@dataclass(frozen=True)
class WorkflowPath:
    """One active or completed branch in a workflow execution."""

    current_input: Any
    state: Any
    trace: Trace


@dataclass(frozen=True)
class WorkflowRun:
    """Structured result of executing a workflow for one external input."""

    completed_paths: tuple[WorkflowPath, ...]
    dead_branches: tuple[DeadBranch, ...] = ()
    exception_branches: tuple[ExceptionBranch, ...] = ()


@dataclass(frozen=True)
class Workflow:
    """Ordered composition of function blocks."""

    blocks: tuple[Any, ...]
    name: str = "workflow"

    def __init__(self, blocks: Sequence[Any], name: str = "workflow") -> None:
        object.__setattr__(self, "blocks", tuple(blocks))
        object.__setattr__(self, "name", name)

    def execute(
        self,
        initial_state: Any,
        external_input: Any,
        trace: Trace | None = None,
        terminal_predicate: TerminalPredicate | None = None,
    ) -> WorkflowRun:
        """Execute one external input through the ordered function blocks."""

        initial_trace = trace or Trace(initial_state=initial_state, external_inputs=(external_input,))
        active = (
            WorkflowPath(
                current_input=external_input,
                state=initial_state,
                trace=initial_trace,
            ),
        )
        completed_early: list[WorkflowPath] = []
        dead_branches: list[DeadBranch] = []
        exception_branches: list[ExceptionBranch] = []

        for block in self.blocks:
            next_active: list[WorkflowPath] = []
            name = block_name(block)

            for path in active:
                if terminal_predicate is not None:
                    try:
                        if terminal_predicate(path.current_input, path.state, path.trace):
                            completed_early.append(path)
                            continue
                    except Exception as exc:
                        exception_branches.append(
                            ExceptionBranch(
                                error_type=type(exc).__name__,
                                message=str(exc),
                                trace=path.trace,
                                function_name=name,
                                function_input=path.current_input,
                                state=path.state,
                            )
                        )
                        continue

                try:
                    accepts = block_accepts_input(block, path.current_input, path.state)
                except Exception as exc:
                    exception_branches.append(
                        ExceptionBranch(
                            error_type=type(exc).__name__,
                            message=str(exc),
                            trace=path.trace,
                            function_name=name,
                            function_input=path.current_input,
                            state=path.state,
                        )
                    )
                    continue

                if not accepts:
                    dead_branches.append(
                        DeadBranch(
                            reason=f"{name} cannot consume {type(path.current_input).__name__}",
                            trace=path.trace,
                            function_name=name,
                            function_input=path.current_input,
                            state=path.state,
                        )
                    )
                    continue

                try:
                    results = normalize_function_results(invoke_block(block, path.current_input, path.state))
                except Exception as exc:
                    exception_branches.append(
                        ExceptionBranch(
                            error_type=type(exc).__name__,
                            message=str(exc),
                            trace=path.trace,
                            function_name=name,
                            function_input=path.current_input,
                            state=path.state,
                        )
                    )
                    continue

                if not results:
                    dead_branches.append(
                        DeadBranch(
                            reason=f"{name} returned zero results",
                            trace=path.trace,
                            function_name=name,
                            function_input=path.current_input,
                            state=path.state,
                        )
                    )
                    continue

                for result in results:
                    step = TraceStep(
                        external_input=external_input,
                        function_name=name,
                        function_input=path.current_input,
                        function_output=result.output,
                        old_state=path.state,
                        new_state=result.new_state,
                        label=result.label,
                        reason=result.reason,
                        metadata=result.metadata,
                    )
                    next_active.append(
                        WorkflowPath(
                            current_input=result.output,
                            state=result.new_state,
                            trace=path.trace.append(step),
                        )
                    )

            active = tuple(next_active)
            if not active:
                break

        return WorkflowRun(
            completed_paths=tuple(completed_early) + tuple(active),
            dead_branches=tuple(dead_branches),
            exception_branches=tuple(exception_branches),
        )


__all__ = ["TerminalPredicate", "Workflow", "WorkflowPath", "WorkflowRun"]
