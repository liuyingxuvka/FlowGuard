"""Trace objects for executable function-flow models."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Iterator

from .core import FrozenMetadata, freeze_metadata
from .export import trace_step_to_dict, trace_to_dict, to_json_text, trace_to_json_text


@dataclass(frozen=True)
class TraceStep:
    """One function-block transition inside a workflow path."""

    external_input: Any
    function_name: str
    function_input: Any
    function_output: Any
    old_state: Any
    new_state: Any
    label: str = ""
    reason: str = ""
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "function_name", str(self.function_name))
        object.__setattr__(self, "label", str(self.label or ""))
        object.__setattr__(self, "reason", str(self.reason or ""))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    @property
    def block_name(self) -> str:
        return self.function_name

    def to_dict(self) -> dict[str, Any]:
        return trace_step_to_dict(self)

    def to_json_text(self, indent: int = 2) -> str:
        return to_json_text(self.to_dict(), indent=indent)


@dataclass(frozen=True)
class Trace:
    """Immutable sequence of trace steps."""

    steps: tuple[TraceStep, ...] = ()
    initial_state: Any = None
    external_inputs: tuple[Any, ...] = ()
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "steps", tuple(self.steps))
        object.__setattr__(self, "external_inputs", tuple(self.external_inputs))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def __iter__(self) -> Iterator[TraceStep]:
        return iter(self.steps)

    def __len__(self) -> int:
        return len(self.steps)

    def append(self, step: TraceStep) -> "Trace":
        return replace(self, steps=self.steps + (step,))

    def with_external_inputs(self, external_inputs: tuple[Any, ...]) -> "Trace":
        return replace(self, external_inputs=tuple(external_inputs))

    @property
    def final_state(self) -> Any:
        if not self.steps:
            return self.initial_state
        return self.steps[-1].new_state

    @property
    def final_output(self) -> Any:
        if not self.steps:
            return None
        return self.steps[-1].function_output

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple(step.label for step in self.steps if step.label)

    def has_label(self, label: str) -> bool:
        return label in self.labels

    def format_text(self) -> str:
        lines = []
        if self.external_inputs:
            lines.append(f"external_inputs: {self.external_inputs!r}")
        if not self.steps:
            lines.append("(empty trace)")
            return "\n".join(lines)
        for index, step in enumerate(self.steps, start=1):
            label = f" [{step.label}]" if step.label else ""
            reason = f" - {step.reason}" if step.reason else ""
            lines.append(
                f"{index}. {step.function_name}{label}: "
                f"{step.function_input!r} -> {step.function_output!r}; "
                f"state {step.old_state!r} -> {step.new_state!r}{reason}"
            )
        return "\n".join(lines)

    def format(self) -> str:
        return self.format_text()

    def to_dict(self) -> dict[str, Any]:
        return trace_to_dict(self)

    def to_json_text(self, indent: int = 2) -> str:
        return trace_to_json_text(self, indent=indent)


__all__ = ["Trace", "TraceStep"]
