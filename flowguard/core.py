"""Core value objects and duck-typed block helpers for flowguard."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from inspect import signature
from typing import Any, Callable, Iterable, Mapping, Protocol, runtime_checkable


FrozenMetadata = tuple[tuple[str, Any], ...]


def _ensure_hashable(value: Any, field_name: str) -> None:
    try:
        hash(value)
    except TypeError as exc:
        raise TypeError(f"{field_name} must be hashable: {value!r}") from exc


def freeze_metadata(metadata: Mapping[str, Any] | Iterable[tuple[str, Any]] | None) -> FrozenMetadata:
    """Return metadata as a deterministic tuple of key/value pairs."""

    if metadata is None:
        return ()
    if isinstance(metadata, tuple):
        pairs = metadata
    elif isinstance(metadata, Mapping):
        pairs = tuple(metadata.items())
    else:
        pairs = tuple(metadata)
    return tuple(sorted(((str(key), value) for key, value in pairs), key=lambda item: item[0]))


@dataclass(frozen=True)
class FunctionResult:
    """One possible output/state pair from a function block."""

    output: Any
    new_state: Any
    label: str = ""
    reason: str = ""
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        _ensure_hashable(self.output, "output")
        _ensure_hashable(self.new_state, "new_state")
        object.__setattr__(self, "label", str(self.label or ""))
        object.__setattr__(self, "reason", str(self.reason or ""))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    @property
    def state(self) -> Any:
        """Compatibility alias for older examples that used `state`."""

        return self.new_state


@runtime_checkable
class FunctionBlock(Protocol):
    """Protocol for executable abstract behavior blocks.

    A block models:

        Input x State -> Set(Output x State)
    """

    name: str
    reads: tuple[str, ...]
    writes: tuple[str, ...]
    input_description: str
    output_description: str
    idempotency: str

    def apply(self, input_obj: Any, state: Any) -> Iterable[FunctionResult]:
        """Return every possible result for this abstract input/state pair."""


@dataclass(frozen=True)
class InvariantResult:
    """Structured result of checking one invariant on one trace."""

    ok: bool
    message: str = ""
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "ok", bool(self.ok))
        object.__setattr__(self, "message", str(self.message or ""))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    @property
    def violation(self) -> bool:
        return not self.ok

    @property
    def passed(self) -> bool:
        return self.ok

    @classmethod
    def pass_(cls) -> "InvariantResult":
        return cls(ok=True)

    @classmethod
    def fail(cls, message: str, metadata: Mapping[str, Any] | None = None) -> "InvariantResult":
        return cls(ok=False, message=message, metadata=freeze_metadata(metadata))


@dataclass(frozen=True)
class Invariant:
    """A named rule that must hold for reachable state/trace pairs."""

    name: str
    description: str
    predicate: Callable[[Any, Any], bool | InvariantResult]
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def check(self, state: Any, trace: Any) -> InvariantResult:
        try:
            result = self.predicate(state, trace)
        except Exception as exc:
            return InvariantResult.fail(
                f"invariant raised {type(exc).__name__}: {exc}",
                {"invariant": self.name},
            )
        if isinstance(result, InvariantResult):
            return result
        passed = bool(result)
        if passed:
            return InvariantResult.pass_()
        return InvariantResult.fail(f"invariant failed: {self.name}")


def block_name(block: Any) -> str:
    explicit_name = getattr(block, "name", None)
    if explicit_name:
        return str(explicit_name)
    if hasattr(block, "__name__"):
        return str(block.__name__)
    return type(block).__name__


def _call_with_supported_arity(func: Callable[..., Any], *args: Any) -> Any:
    """Call a hook with the longest supported prefix of args."""

    try:
        parameter_count = len(
            [
                parameter
                for parameter in signature(func).parameters.values()
                if parameter.kind
                in (
                    parameter.POSITIONAL_ONLY,
                    parameter.POSITIONAL_OR_KEYWORD,
                    parameter.KEYWORD_ONLY,
                )
                and parameter.default is parameter.empty
            ]
        )
    except (TypeError, ValueError):
        parameter_count = len(args)
    return func(*args[:parameter_count])


def block_accepts_input(block: Any, input_obj: Any, state: Any) -> bool:
    """Evaluate optional block input acceptance hooks."""

    can_accept = getattr(block, "can_accept", None)
    if can_accept is not None:
        return bool(_call_with_supported_arity(can_accept, input_obj, state))

    accepted_type = getattr(block, "accepted_input_type", None)
    if accepted_type is None:
        accepted_type = getattr(block, "accepted_input_types", None)
    if accepted_type is None:
        return True
    if isinstance(accepted_type, tuple):
        return isinstance(input_obj, accepted_type)
    if isinstance(accepted_type, type):
        return isinstance(input_obj, accepted_type)
    if callable(accepted_type):
        return bool(accepted_type(input_obj))
    raise TypeError(f"{block_name(block)} accepted_input_type must be a type, tuple, or callable")


def invoke_block(block: Any, input_obj: Any, state: Any) -> Any:
    """Invoke a block through supported duck-typed entry points."""

    apply = getattr(block, "apply", None)
    if apply is not None:
        return apply(input_obj, state)
    run = getattr(block, "run", None)
    if run is not None:
        return run(input_obj, state)
    transition = getattr(block, "transition", None)
    if transition is not None:
        return transition(input_obj, state)
    if callable(block):
        return block(input_obj, state)
    raise TypeError(f"{block_name(block)} has no apply/run/transition method")


def coerce_function_result(value: Any) -> FunctionResult:
    if isinstance(value, FunctionResult):
        return value
    if hasattr(value, "output") and (hasattr(value, "new_state") or hasattr(value, "state")):
        return FunctionResult(
            output=getattr(value, "output"),
            new_state=getattr(value, "new_state", getattr(value, "state", None)),
            label=getattr(value, "label", ""),
            reason=getattr(value, "reason", ""),
            metadata=getattr(value, "metadata", None),
        )
    if isinstance(value, tuple) and len(value) == 2:
        output, new_state = value
        return FunctionResult(output=output, new_state=new_state)
    raise TypeError("function blocks must return FunctionResult objects or (output, new_state) tuples")


def normalize_function_results(raw_results: Any) -> tuple[FunctionResult, ...]:
    """Normalize a block return value into a tuple of FunctionResult objects."""

    if raw_results is None:
        return ()
    if isinstance(raw_results, FunctionResult):
        return (raw_results,)
    if isinstance(raw_results, tuple) and len(raw_results) == 2:
        first_is_result = isinstance(raw_results[0], FunctionResult) or hasattr(raw_results[0], "output")
        second_is_result = isinstance(raw_results[1], FunctionResult) or hasattr(raw_results[1], "output")
        if not first_is_result and not second_is_result:
            return (coerce_function_result(raw_results),)
    if isinstance(raw_results, (str, bytes, bytearray, Mapping)):
        raise TypeError("function block results must be an iterable of result objects")
    items = tuple(raw_results)
    if isinstance(raw_results, (set, frozenset)):
        items = tuple(sorted(items, key=repr))
    return tuple(coerce_function_result(item) for item in items)


__all__ = [
    "FunctionBlock",
    "FunctionResult",
    "FrozenMetadata",
    "Invariant",
    "InvariantResult",
    "block_accepts_input",
    "block_name",
    "coerce_function_result",
    "freeze_metadata",
    "invoke_block",
    "normalize_function_results",
    "replace",
]
