"""Replay adapter protocol and observations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .core import FrozenMetadata, freeze_metadata
from .export import to_json_text, to_jsonable
from .trace import TraceStep


@dataclass(frozen=True)
class ReplayObservation:
    """Projected behavior observed after replaying one trace step."""

    function_name: str
    observed_output: Any
    observed_state: Any
    label: str = ""
    reason: str = ""
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "function_name", str(self.function_name))
        object.__setattr__(self, "label", str(self.label or ""))
        object.__setattr__(self, "reason", str(self.reason or ""))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "function_name": self.function_name,
            "observed_output": to_jsonable(self.observed_output),
            "observed_state": to_jsonable(self.observed_state),
            "label": self.label,
            "reason": self.reason,
            "metadata": to_jsonable(self.metadata),
        }

    def to_json_text(self, indent: int = 2) -> str:
        return to_json_text(self.to_dict(), indent=indent)


@runtime_checkable
class ReplayAdapter(Protocol):
    """Adapter that maps abstract trace steps to real implementation calls."""

    def reset(self, initial_state: Any) -> None:
        """Prepare the real system for replaying a trace."""

    def apply_step(self, step: TraceStep) -> ReplayObservation | None:
        """Execute the production behavior corresponding to a trace step."""

    def observe_state(self) -> Any:
        """Return a projection of real state after the latest step."""

    def observe_output(self) -> Any:
        """Return a projection of the latest real output."""


def coerce_observation(value: Any, step: TraceStep, adapter: Any) -> ReplayObservation:
    """Normalize adapter output into a ReplayObservation."""

    if isinstance(value, ReplayObservation):
        return value

    if value is None:
        return ReplayObservation(
            function_name=step.function_name,
            observed_output=adapter.observe_output(),
            observed_state=adapter.observe_state(),
            label=getattr(adapter, "observe_label", lambda: "")(),
            reason=getattr(adapter, "observe_reason", lambda: "")(),
        )

    if hasattr(value, "observed_output") and hasattr(value, "observed_state"):
        return ReplayObservation(
            function_name=getattr(value, "function_name", step.function_name),
            observed_output=getattr(value, "observed_output"),
            observed_state=getattr(value, "observed_state"),
            label=getattr(value, "label", ""),
            reason=getattr(value, "reason", ""),
            metadata=getattr(value, "metadata", None),
        )

    raise TypeError("ReplayAdapter.apply_step must return ReplayObservation or None")


__all__ = ["ReplayAdapter", "ReplayObservation", "coerce_observation"]
