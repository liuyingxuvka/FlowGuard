"""Portable, code-independent finite model interchange for FlowGuard.

The current schema is deliberately small.  It represents the finite relation
``Input x State -> Set(Output x State)`` as an explicit transition table.  It
does not serialize Python callables or infer a graph from production code.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence


PORTABLE_MODEL_SCHEMA_VERSION = "flowguard.portable_model.v1"
PORTABLE_REFINEMENT_SCHEMA_VERSION = "flowguard.portable_refinement.v1"
PORTABLE_TEMPORAL_KINDS = (
    "eventually",
    "bounded_eventually",
    "terminal_progress",
    "weak_fairness",
)


class PortableModelError(ValueError):
    """Raised when a portable artifact is not the exact current shape."""


def _ensure_json_value(value: Any, path: str = "value") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise PortableModelError(f"{path} contains a non-finite number")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _ensure_json_value(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise PortableModelError(f"{path} contains a non-string object key")
            _ensure_json_value(item, f"{path}.{key}")
        return
    raise PortableModelError(f"{path} is not a JSON value: {type(value).__name__}")


def _strict_object(
    value: Any,
    *,
    context: str,
    required: Sequence[str],
    optional: Sequence[str] = (),
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PortableModelError(f"{context} must be an object")
    missing = sorted(set(required) - set(value))
    unknown = sorted(set(value) - set(required) - set(optional))
    if missing:
        raise PortableModelError(f"{context} missing fields: {', '.join(missing)}")
    if unknown:
        raise PortableModelError(f"{context} has unknown fields: {', '.join(unknown)}")
    return value


def _string(value: Any, *, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PortableModelError(f"{context} must be a non-empty string")
    return value


def _string_tuple(value: Any, *, context: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise PortableModelError(f"{context} must be an array")
    result = tuple(_string(item, context=f"{context}[]") for item in value)
    if len(set(result)) != len(result):
        raise PortableModelError(f"{context} contains duplicate ids")
    return result


def canonical_json_bytes(value: Any) -> bytes:
    """Return canonical UTF-8 JSON bytes for a JSON-compatible value."""

    _ensure_json_value(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_identity(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


@dataclass(frozen=True)
class PortableState:
    state_id: str
    payload: Any = None

    def __post_init__(self) -> None:
        _string(self.state_id, context="state_id")
        _ensure_json_value(self.payload, f"state:{self.state_id}.payload")

    def to_dict(self) -> dict[str, Any]:
        return {"state_id": self.state_id, "payload": self.payload}

    @classmethod
    def from_dict(cls, value: Any) -> "PortableState":
        data = _strict_object(value, context="state", required=("state_id", "payload"))
        return cls(state_id=_string(data["state_id"], context="state.state_id"), payload=data["payload"])


@dataclass(frozen=True)
class PortableTransition:
    transition_id: str
    source_state: str
    input_symbol: Any
    output_symbol: Any
    target_state: str
    label: str = ""

    def __post_init__(self) -> None:
        _string(self.transition_id, context="transition_id")
        _string(self.source_state, context=f"transition:{self.transition_id}.source_state")
        _string(self.target_state, context=f"transition:{self.transition_id}.target_state")
        _ensure_json_value(self.input_symbol, f"transition:{self.transition_id}.input_symbol")
        _ensure_json_value(self.output_symbol, f"transition:{self.transition_id}.output_symbol")
        if not isinstance(self.label, str):
            raise PortableModelError(f"transition:{self.transition_id}.label must be a string")

    def to_dict(self) -> dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "source_state": self.source_state,
            "input_symbol": self.input_symbol,
            "output_symbol": self.output_symbol,
            "target_state": self.target_state,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "PortableTransition":
        data = _strict_object(
            value,
            context="transition",
            required=(
                "transition_id",
                "source_state",
                "input_symbol",
                "output_symbol",
                "target_state",
                "label",
            ),
        )
        return cls(
            transition_id=_string(data["transition_id"], context="transition.transition_id"),
            source_state=_string(data["source_state"], context="transition.source_state"),
            input_symbol=data["input_symbol"],
            output_symbol=data["output_symbol"],
            target_state=_string(data["target_state"], context="transition.target_state"),
            label=data["label"],
        )


@dataclass(frozen=True)
class PortableInvariant:
    invariant_id: str
    forbidden_state_ids: tuple[str, ...]
    description: str = ""

    def __post_init__(self) -> None:
        _string(self.invariant_id, context="invariant_id")
        object.__setattr__(self, "forbidden_state_ids", tuple(self.forbidden_state_ids))
        if not isinstance(self.description, str):
            raise PortableModelError(f"invariant:{self.invariant_id}.description must be a string")

    def to_dict(self) -> dict[str, Any]:
        return {
            "invariant_id": self.invariant_id,
            "forbidden_state_ids": list(self.forbidden_state_ids),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "PortableInvariant":
        data = _strict_object(
            value,
            context="invariant",
            required=("invariant_id", "forbidden_state_ids", "description"),
        )
        return cls(
            invariant_id=_string(data["invariant_id"], context="invariant.invariant_id"),
            forbidden_state_ids=_string_tuple(
                data["forbidden_state_ids"], context="invariant.forbidden_state_ids"
            ),
            description=data["description"],
        )


@dataclass(frozen=True)
class PortableTemporalObligation:
    obligation_id: str
    kind: str
    trigger_state_ids: tuple[str, ...] = ()
    target_state_ids: tuple[str, ...] = ()
    transition_ids: tuple[str, ...] = ()
    max_steps: int | None = None
    description: str = ""

    def __post_init__(self) -> None:
        _string(self.obligation_id, context="obligation_id")
        if self.kind not in PORTABLE_TEMPORAL_KINDS:
            raise PortableModelError(
                f"obligation:{self.obligation_id}.kind must be one of {PORTABLE_TEMPORAL_KINDS!r}"
            )
        object.__setattr__(self, "trigger_state_ids", tuple(self.trigger_state_ids))
        object.__setattr__(self, "target_state_ids", tuple(self.target_state_ids))
        object.__setattr__(self, "transition_ids", tuple(self.transition_ids))
        if self.max_steps is not None and (isinstance(self.max_steps, bool) or self.max_steps < 0):
            raise PortableModelError(f"obligation:{self.obligation_id}.max_steps must be non-negative")
        if self.kind == "bounded_eventually" and self.max_steps is None:
            raise PortableModelError(f"obligation:{self.obligation_id} requires max_steps")
        if self.kind != "bounded_eventually" and self.max_steps is not None:
            raise PortableModelError(f"obligation:{self.obligation_id} cannot declare max_steps")
        if self.kind in {"eventually", "bounded_eventually"} and not self.target_state_ids:
            raise PortableModelError(f"obligation:{self.obligation_id} requires target_state_ids")
        if self.kind == "weak_fairness" and (not self.trigger_state_ids or not self.transition_ids):
            raise PortableModelError(
                f"obligation:{self.obligation_id} requires enabled trigger states and transitions"
            )
        if self.kind == "terminal_progress" and self.target_state_ids:
            raise PortableModelError(
                f"obligation:{self.obligation_id} uses model terminal states and cannot declare targets"
            )
        if not isinstance(self.description, str):
            raise PortableModelError(f"obligation:{self.obligation_id}.description must be a string")

    def to_dict(self) -> dict[str, Any]:
        return {
            "obligation_id": self.obligation_id,
            "kind": self.kind,
            "trigger_state_ids": list(self.trigger_state_ids),
            "target_state_ids": list(self.target_state_ids),
            "transition_ids": list(self.transition_ids),
            "max_steps": self.max_steps,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "PortableTemporalObligation":
        data = _strict_object(
            value,
            context="temporal_obligation",
            required=(
                "obligation_id",
                "kind",
                "trigger_state_ids",
                "target_state_ids",
                "transition_ids",
                "max_steps",
                "description",
            ),
        )
        max_steps = data["max_steps"]
        if max_steps is not None and (not isinstance(max_steps, int) or isinstance(max_steps, bool)):
            raise PortableModelError("temporal_obligation.max_steps must be an integer or null")
        return cls(
            obligation_id=_string(data["obligation_id"], context="temporal_obligation.obligation_id"),
            kind=_string(data["kind"], context="temporal_obligation.kind"),
            trigger_state_ids=_string_tuple(
                data["trigger_state_ids"], context="temporal_obligation.trigger_state_ids"
            ),
            target_state_ids=_string_tuple(
                data["target_state_ids"], context="temporal_obligation.target_state_ids"
            ),
            transition_ids=_string_tuple(
                data["transition_ids"], context="temporal_obligation.transition_ids"
            ),
            max_steps=max_steps,
            description=data["description"],
        )


@dataclass(frozen=True)
class PortableModel:
    model_id: str
    states: tuple[PortableState, ...]
    transitions: tuple[PortableTransition, ...]
    initial_state_ids: tuple[str, ...]
    terminal_state_ids: tuple[str, ...] = ()
    invariants: tuple[PortableInvariant, ...] = ()
    temporal_obligations: tuple[PortableTemporalObligation, ...] = ()
    assumptions: tuple[str, ...] = ()
    guarantees: tuple[str, ...] = ()
    conflicts: tuple[tuple[str, str], ...] = ()
    metadata: Any = field(default_factory=dict, compare=False)
    schema_version: str = PORTABLE_MODEL_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _string(self.model_id, context="model_id")
        for name in (
            "states",
            "transitions",
            "initial_state_ids",
            "terminal_state_ids",
            "invariants",
            "temporal_obligations",
            "assumptions",
            "guarantees",
            "conflicts",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        _ensure_json_value(self.metadata, "model.metadata")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "model_id": self.model_id,
            "states": [item.to_dict() for item in self.states],
            "transitions": [item.to_dict() for item in self.transitions],
            "initial_state_ids": list(self.initial_state_ids),
            "terminal_state_ids": list(self.terminal_state_ids),
            "invariants": [item.to_dict() for item in self.invariants],
            "temporal_obligations": [item.to_dict() for item in self.temporal_obligations],
            "assumptions": list(self.assumptions),
            "guarantees": list(self.guarantees),
            "conflicts": [list(item) for item in self.conflicts],
            "metadata": self.metadata,
        }

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())

    @property
    def fingerprint(self) -> str:
        return canonical_identity(self.to_dict())

    @classmethod
    def from_dict(cls, value: Any) -> "PortableModel":
        data = _strict_object(
            value,
            context="portable_model",
            required=(
                "schema_version",
                "model_id",
                "states",
                "transitions",
                "initial_state_ids",
                "terminal_state_ids",
                "invariants",
                "temporal_obligations",
                "assumptions",
                "guarantees",
                "conflicts",
                "metadata",
            ),
        )
        if data["schema_version"] != PORTABLE_MODEL_SCHEMA_VERSION:
            raise PortableModelError(
                f"portable_model.schema_version must be {PORTABLE_MODEL_SCHEMA_VERSION!r}"
            )
        for key in ("states", "transitions", "invariants", "temporal_obligations", "conflicts"):
            if not isinstance(data[key], list):
                raise PortableModelError(f"portable_model.{key} must be an array")
        conflicts: list[tuple[str, str]] = []
        for index, item in enumerate(data["conflicts"]):
            if not isinstance(item, list) or len(item) != 2:
                raise PortableModelError(f"portable_model.conflicts[{index}] must contain two tokens")
            left = _string(item[0], context=f"portable_model.conflicts[{index}][0]")
            right = _string(item[1], context=f"portable_model.conflicts[{index}][1]")
            if left == right:
                raise PortableModelError(f"portable_model.conflicts[{index}] cannot self-conflict")
            conflicts.append(tuple(sorted((left, right))))
        model = cls(
            schema_version=data["schema_version"],
            model_id=_string(data["model_id"], context="portable_model.model_id"),
            states=tuple(PortableState.from_dict(item) for item in data["states"]),
            transitions=tuple(PortableTransition.from_dict(item) for item in data["transitions"]),
            initial_state_ids=_string_tuple(
                data["initial_state_ids"], context="portable_model.initial_state_ids"
            ),
            terminal_state_ids=_string_tuple(
                data["terminal_state_ids"], context="portable_model.terminal_state_ids"
            ),
            invariants=tuple(PortableInvariant.from_dict(item) for item in data["invariants"]),
            temporal_obligations=tuple(
                PortableTemporalObligation.from_dict(item) for item in data["temporal_obligations"]
            ),
            assumptions=_string_tuple(data["assumptions"], context="portable_model.assumptions"),
            guarantees=_string_tuple(data["guarantees"], context="portable_model.guarantees"),
            conflicts=tuple(conflicts),
            metadata=data["metadata"],
        )
        errors = validate_portable_model(model)
        if errors:
            raise PortableModelError("; ".join(errors))
        return model


@dataclass(frozen=True)
class RefinementBinding:
    parent_model_id: str
    child_model_id: str
    state_mapping: tuple[tuple[str, str], ...]
    transition_mapping: tuple[tuple[str, str], ...]
    allowed_stutter_transition_ids: tuple[str, ...] = ()
    parent_model_fingerprint: str = ""
    child_model_fingerprint: str = ""
    schema_version: str = PORTABLE_REFINEMENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _string(self.parent_model_id, context="refinement.parent_model_id")
        _string(self.child_model_id, context="refinement.child_model_id")
        object.__setattr__(self, "state_mapping", tuple(tuple(item) for item in self.state_mapping))
        object.__setattr__(self, "transition_mapping", tuple(tuple(item) for item in self.transition_mapping))
        object.__setattr__(
            self, "allowed_stutter_transition_ids", tuple(self.allowed_stutter_transition_ids)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "parent_model_id": self.parent_model_id,
            "child_model_id": self.child_model_id,
            "parent_model_fingerprint": self.parent_model_fingerprint,
            "child_model_fingerprint": self.child_model_fingerprint,
            "state_mapping": {key: value for key, value in self.state_mapping},
            "transition_mapping": {key: value for key, value in self.transition_mapping},
            "allowed_stutter_transition_ids": list(self.allowed_stutter_transition_ids),
        }

    @classmethod
    def from_dict(cls, value: Any) -> "RefinementBinding":
        data = _strict_object(
            value,
            context="refinement_binding",
            required=(
                "schema_version",
                "parent_model_id",
                "child_model_id",
                "parent_model_fingerprint",
                "child_model_fingerprint",
                "state_mapping",
                "transition_mapping",
                "allowed_stutter_transition_ids",
            ),
        )
        if data["schema_version"] != PORTABLE_REFINEMENT_SCHEMA_VERSION:
            raise PortableModelError(
                f"refinement_binding.schema_version must be {PORTABLE_REFINEMENT_SCHEMA_VERSION!r}"
            )
        pairs: dict[str, tuple[tuple[str, str], ...]] = {}
        for key in ("state_mapping", "transition_mapping"):
            mapping = data[key]
            if not isinstance(mapping, Mapping):
                raise PortableModelError(f"refinement_binding.{key} must be an object")
            pairs[key] = tuple(
                sorted(
                    (
                        _string(child, context=f"refinement_binding.{key}.key"),
                        _string(parent, context=f"refinement_binding.{key}.{child}"),
                    )
                    for child, parent in mapping.items()
                )
            )
        return cls(
            schema_version=data["schema_version"],
            parent_model_id=_string(data["parent_model_id"], context="refinement.parent_model_id"),
            child_model_id=_string(data["child_model_id"], context="refinement.child_model_id"),
            parent_model_fingerprint=str(data["parent_model_fingerprint"]),
            child_model_fingerprint=str(data["child_model_fingerprint"]),
            state_mapping=pairs["state_mapping"],
            transition_mapping=pairs["transition_mapping"],
            allowed_stutter_transition_ids=_string_tuple(
                data["allowed_stutter_transition_ids"],
                context="refinement_binding.allowed_stutter_transition_ids",
            ),
        )


def validate_portable_model(model: PortableModel) -> tuple[str, ...]:
    """Return structural errors without executing the model."""

    errors: list[str] = []
    if model.schema_version != PORTABLE_MODEL_SCHEMA_VERSION:
        errors.append(f"schema_version must be {PORTABLE_MODEL_SCHEMA_VERSION!r}")
    state_ids = [item.state_id for item in model.states]
    transition_ids = [item.transition_id for item in model.transitions]
    invariant_ids = [item.invariant_id for item in model.invariants]
    obligation_ids = [item.obligation_id for item in model.temporal_obligations]
    for label, values in (
        ("state", state_ids),
        ("transition", transition_ids),
        ("invariant", invariant_ids),
        ("obligation", obligation_ids),
        ("assumption", list(model.assumptions)),
        ("guarantee", list(model.guarantees)),
        ("conflict", list(model.conflicts)),
    ):
        if len(set(values)) != len(values):
            errors.append(f"duplicate {label} ids")
    known_states = set(state_ids)
    known_transitions = set(transition_ids)
    if not model.states:
        errors.append("states cannot be empty")
    if not model.initial_state_ids:
        errors.append("initial_state_ids cannot be empty")
    for state_id in model.initial_state_ids:
        if state_id not in known_states:
            errors.append(f"initial state {state_id!r} is not declared")
    for state_id in model.terminal_state_ids:
        if state_id not in known_states:
            errors.append(f"terminal state {state_id!r} is not declared")
    for transition in model.transitions:
        if transition.source_state not in known_states:
            errors.append(
                f"transition {transition.transition_id!r} source {transition.source_state!r} is not declared"
            )
        if transition.target_state not in known_states:
            errors.append(
                f"transition {transition.transition_id!r} target {transition.target_state!r} is not declared"
            )
    for invariant in model.invariants:
        for state_id in invariant.forbidden_state_ids:
            if state_id not in known_states:
                errors.append(
                    f"invariant {invariant.invariant_id!r} references unknown state {state_id!r}"
                )
    for obligation in model.temporal_obligations:
        for state_id in obligation.trigger_state_ids + obligation.target_state_ids:
            if state_id not in known_states:
                errors.append(
                    f"obligation {obligation.obligation_id!r} references unknown state {state_id!r}"
                )
        for transition_id in obligation.transition_ids:
            if transition_id not in known_transitions:
                errors.append(
                    f"obligation {obligation.obligation_id!r} references unknown transition {transition_id!r}"
                )
    for left, right in model.conflicts:
        if not left or not right or left == right:
            errors.append("conflicts must contain two distinct non-empty tokens")
    return tuple(sorted(set(errors)))


def load_portable_model(path: str | Path) -> PortableModel:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PortableModelError(f"cannot read portable model {path!s}: {exc}") from exc
    return PortableModel.from_dict(payload)


def load_refinement_binding(path: str | Path) -> RefinementBinding:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PortableModelError(f"cannot read refinement binding {path!s}: {exc}") from exc
    return RefinementBinding.from_dict(payload)


def write_portable_model(model: PortableModel, path: str | Path) -> Path:
    errors = validate_portable_model(model)
    if errors:
        raise PortableModelError("; ".join(errors))
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(model.canonical_bytes + b"\n")
    return target


__all__ = [
    "PORTABLE_MODEL_SCHEMA_VERSION",
    "PORTABLE_REFINEMENT_SCHEMA_VERSION",
    "PORTABLE_TEMPORAL_KINDS",
    "PortableInvariant",
    "PortableModel",
    "PortableModelError",
    "PortableState",
    "PortableTemporalObligation",
    "PortableTransition",
    "RefinementBinding",
    "canonical_identity",
    "canonical_json_bytes",
    "load_portable_model",
    "load_refinement_binding",
    "validate_portable_model",
    "write_portable_model",
]
