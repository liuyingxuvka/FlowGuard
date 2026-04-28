"""Function contract composition and refinement checks."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from .core import FrozenMetadata, freeze_metadata
from .export import to_jsonable, trace_step_to_dict
from .trace import Trace, TraceStep


ContractPredicate = Callable[[TraceStep], bool | str | None]
ProjectionFn = Callable[[Any], Any]


@dataclass(frozen=True)
class FunctionContract:
    """Optional explicit contract around a FunctionBlock."""

    function_name: str
    accepted_input_type: type | tuple[type, ...] | None = None
    output_type: type | tuple[type, ...] | None = None
    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()
    forbidden_writes: tuple[str, ...] = ()
    preconditions: tuple[ContractPredicate, ...] = ()
    postconditions: tuple[ContractPredicate, ...] = ()
    idempotency_rule: str = ""
    traceability_rule: str = ""
    failure_modes: tuple[str, ...] = ()
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "function_name", str(self.function_name))
        object.__setattr__(self, "reads", tuple(str(item) for item in self.reads))
        object.__setattr__(self, "writes", tuple(str(item) for item in self.writes))
        object.__setattr__(
            self,
            "forbidden_writes",
            tuple(str(item) for item in self.forbidden_writes),
        )
        object.__setattr__(self, "preconditions", tuple(self.preconditions))
        object.__setattr__(self, "postconditions", tuple(self.postconditions))
        object.__setattr__(self, "idempotency_rule", str(self.idempotency_rule))
        object.__setattr__(self, "traceability_rule", str(self.traceability_rule))
        object.__setattr__(self, "failure_modes", tuple(str(item) for item in self.failure_modes))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))


@dataclass(frozen=True)
class ContractViolation:
    """One contract or refinement violation."""

    name: str
    message: str
    function_name: str = ""
    step_index: int | None = None
    step: TraceStep | None = None
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", str(self.name))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "function_name", str(self.function_name))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "message": self.message,
            "function_name": self.function_name,
            "step_index": self.step_index,
            "step": trace_step_to_dict(self.step) if self.step is not None else None,
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class ContractCheckReport:
    """Structured contract-check report."""

    ok: bool
    violations: tuple[ContractViolation, ...] = ()
    checked_steps: int = 0
    summary: str = ""

    def violation_names(self) -> tuple[str, ...]:
        return tuple(violation.name for violation in self.violations)

    def format_text(self, max_examples: int = 5) -> str:
        lines = [
            f"status: {'OK' if self.ok else 'VIOLATION'}",
            f"checked_steps: {self.checked_steps}",
            f"violations: {len(self.violations)}",
        ]
        if self.summary:
            lines.append(f"summary: {self.summary}")
        for violation in self.violations[:max_examples]:
            lines.extend(
                [
                    "",
                    f"violation: {violation.name}",
                    f"function: {violation.function_name}",
                    f"step: {violation.step_index}",
                    f"message: {violation.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "violations": [violation.to_dict() for violation in self.violations],
            "checked_steps": self.checked_steps,
            "summary": self.summary,
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def _type_name(type_obj: Any) -> str:
    if isinstance(type_obj, tuple):
        return "|".join(_type_name(item) for item in type_obj)
    return getattr(type_obj, "__name__", repr(type_obj))


def _changed_fields(old_state: Any, new_state: Any) -> tuple[str, ...]:
    if old_state == new_state:
        return ()
    if hasattr(old_state, "__dataclass_fields__") and hasattr(new_state, "__dataclass_fields__"):
        names = tuple(old_state.__dataclass_fields__.keys())
        return tuple(
            name
            for name in names
            if getattr(old_state, name, None) != getattr(new_state, name, None)
        )
    if isinstance(old_state, Mapping) and isinstance(new_state, Mapping):
        keys = set(old_state) | set(new_state)
        return tuple(sorted(str(key) for key in keys if old_state.get(key) != new_state.get(key)))
    return ("state",)


def _predicate_violation(
    predicate: ContractPredicate,
    step: TraceStep,
    *,
    name: str,
    function_name: str,
    step_index: int,
) -> ContractViolation | None:
    try:
        result = predicate(step)
    except Exception as exc:
        return ContractViolation(
            name=name,
            message=f"contract predicate raised {type(exc).__name__}: {exc}",
            function_name=function_name,
            step_index=step_index,
            step=step,
        )
    if result is True or result is None:
        return None
    message = result if isinstance(result, str) else f"contract predicate failed: {name}"
    return ContractViolation(
        name=name,
        message=message,
        function_name=function_name,
        step_index=step_index,
        step=step,
    )


def check_trace_contracts(
    trace: Trace,
    contracts: Sequence[FunctionContract],
) -> ContractCheckReport:
    """Check function contracts against every step in a trace."""

    by_name = {contract.function_name: contract for contract in contracts}
    violations: list[ContractViolation] = []
    checked = 0
    for index, step in enumerate(trace.steps, start=1):
        contract = by_name.get(step.function_name)
        if contract is None:
            continue
        checked += 1

        if contract.accepted_input_type is not None and not isinstance(step.function_input, contract.accepted_input_type):
            violations.append(
                ContractViolation(
                    name="precondition_input_type",
                    message=(
                        f"input must be {_type_name(contract.accepted_input_type)}, "
                        f"got {type(step.function_input).__name__}"
                    ),
                    function_name=step.function_name,
                    step_index=index,
                    step=step,
                )
            )

        if contract.output_type is not None and not isinstance(step.function_output, contract.output_type):
            violations.append(
                ContractViolation(
                    name="postcondition_output_type",
                    message=(
                        f"output must be {_type_name(contract.output_type)}, "
                        f"got {type(step.function_output).__name__}"
                    ),
                    function_name=step.function_name,
                    step_index=index,
                    step=step,
                )
            )

        changed = set(_changed_fields(step.old_state, step.new_state))
        forbidden_changed = tuple(sorted(changed & set(contract.forbidden_writes)))
        if forbidden_changed:
            violations.append(
                ContractViolation(
                    name="forbidden_write",
                    message=f"function changed forbidden state fields: {forbidden_changed!r}",
                    function_name=step.function_name,
                    step_index=index,
                    step=step,
                    metadata={"fields": forbidden_changed},
                )
            )

        undeclared = tuple(sorted(changed - set(contract.writes)))
        if contract.writes and undeclared:
            violations.append(
                ContractViolation(
                    name="undeclared_write",
                    message=f"function changed state fields outside declared writes: {undeclared!r}",
                    function_name=step.function_name,
                    step_index=index,
                    step=step,
                    metadata={"fields": undeclared},
                )
            )

        for precondition in contract.preconditions:
            violation = _predicate_violation(
                precondition,
                step,
                name="precondition",
                function_name=step.function_name,
                step_index=index,
            )
            if violation is not None:
                violations.append(violation)

        for postcondition in contract.postconditions:
            violation = _predicate_violation(
                postcondition,
                step,
                name="postcondition",
                function_name=step.function_name,
                step_index=index,
            )
            if violation is not None:
                violations.append(violation)

    return ContractCheckReport(
        ok=not violations,
        violations=tuple(violations),
        checked_steps=checked,
        summary=f"checked {checked} trace step(s) against {len(tuple(contracts))} contract(s)",
    )


def check_refinement_projection(
    *,
    expected_abstract_state: Any,
    real_state: Any,
    projection: ProjectionFn,
    function_name: str = "",
) -> ContractCheckReport:
    """Check one simple refinement step through a RealState -> AbstractState projection."""

    try:
        projected = projection(real_state)
    except Exception as exc:
        violation = ContractViolation(
            name="projection_exception",
            message=f"projection raised {type(exc).__name__}: {exc}",
            function_name=function_name,
        )
        return ContractCheckReport(ok=False, violations=(violation,), checked_steps=1)

    if projected != expected_abstract_state:
        violation = ContractViolation(
            name="refinement_projection_mismatch",
            message=f"projected real state {projected!r} does not match expected {expected_abstract_state!r}",
            function_name=function_name,
        )
        return ContractCheckReport(ok=False, violations=(violation,), checked_steps=1)

    return ContractCheckReport(ok=True, checked_steps=1, summary="projection matched expected abstract state")


__all__ = [
    "ContractCheckReport",
    "ContractPredicate",
    "ContractViolation",
    "FunctionContract",
    "ProjectionFn",
    "check_refinement_projection",
    "check_trace_contracts",
]
