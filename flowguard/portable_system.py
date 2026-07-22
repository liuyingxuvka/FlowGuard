"""Strict bounded system-composition artifacts for portable FlowGuard models."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .portable_model import PortableModel, PortableModelError, canonical_identity


PORTABLE_SYSTEM_SCHEMA_VERSION = "flowguard.portable_system.v1"
PORTABLE_SYSTEM_REQUEST_SCHEMA_VERSION = "flowguard.system_composition_request.v1"
SYSTEM_PROPERTY_KINDS = (
    "safety",
    "eventually",
    "bounded_eventually",
    "terminal_progress",
    "weak_fairness",
)


def _object(value: Any, context: str, required: Sequence[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PortableModelError(f"{context} must be an object")
    missing = sorted(set(required) - set(value))
    unknown = sorted(set(value) - set(required))
    if missing:
        raise PortableModelError(f"{context} missing fields: {', '.join(missing)}")
    if unknown:
        raise PortableModelError(f"{context} has unknown fields: {', '.join(unknown)}")
    return value


def _text(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PortableModelError(f"{context} must be a non-empty string")
    return value


def _array(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise PortableModelError(f"{context} must be an array")
    return value


def _texts(value: Any, context: str) -> tuple[str, ...]:
    result = tuple(_text(item, f"{context}[]") for item in _array(value, context))
    if len(result) != len(set(result)):
        raise PortableModelError(f"{context} contains duplicate ids")
    return tuple(sorted(result))


def _pairs(value: Any, context: str) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for index, item in enumerate(_array(value, context)):
        if not isinstance(item, list) or len(item) != 2:
            raise PortableModelError(f"{context}[{index}] must contain two strings")
        pairs.append((_text(item[0], f"{context}[{index}][0]"), _text(item[1], f"{context}[{index}][1]")))
    if len(pairs) != len(set(pairs)):
        raise PortableModelError(f"{context} contains duplicate pairs")
    return tuple(sorted(pairs))


@dataclass(frozen=True)
class SystemComponentRef:
    component_id: str
    model_id: str
    model_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {"component_id": self.component_id, "model_id": self.model_id, "model_fingerprint": self.model_fingerprint}

    @classmethod
    def from_dict(cls, value: Any) -> "SystemComponentRef":
        data = _object(value, "component", ("component_id", "model_id", "model_fingerprint"))
        return cls(*(_text(data[key], f"component.{key}") for key in ("component_id", "model_id", "model_fingerprint")))


@dataclass(frozen=True)
class SystemDependency:
    dependency_id: str
    source_component_id: str
    target_component_id: str
    kind: str

    def to_dict(self) -> dict[str, Any]:
        return {"dependency_id": self.dependency_id, "source_component_id": self.source_component_id, "target_component_id": self.target_component_id, "kind": self.kind}

    @classmethod
    def from_dict(cls, value: Any) -> "SystemDependency":
        data = _object(value, "dependency", ("dependency_id", "source_component_id", "target_component_id", "kind"))
        return cls(*(_text(data[key], f"dependency.{key}") for key in ("dependency_id", "source_component_id", "target_component_id", "kind")))


@dataclass(frozen=True)
class SystemEventPort:
    port_id: str
    component_id: str
    direction: str
    event_type: str

    def __post_init__(self) -> None:
        if self.direction not in {"input", "output"}:
            raise PortableModelError(f"port:{self.port_id}.direction must be input or output")

    def to_dict(self) -> dict[str, Any]:
        return {"port_id": self.port_id, "component_id": self.component_id, "direction": self.direction, "event_type": self.event_type}

    @classmethod
    def from_dict(cls, value: Any) -> "SystemEventPort":
        data = _object(value, "port", ("port_id", "component_id", "direction", "event_type"))
        return cls(*(_text(data[key], f"port.{key}") for key in ("port_id", "component_id", "direction", "event_type")))


@dataclass(frozen=True)
class SystemEventBinding:
    binding_id: str
    producer_port_id: str
    consumer_port_id: str
    delivery: str
    ordering: str
    identity_mapping: tuple[tuple[str, str], ...] = ()
    queue_component_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "identity_mapping", tuple(sorted(self.identity_mapping)))
        if self.delivery not in {"at_most_once", "at_least_once", "manual"}:
            raise PortableModelError(f"binding:{self.binding_id}.delivery is unsupported")
        if self.ordering not in {"fifo", "unordered"}:
            raise PortableModelError(f"binding:{self.binding_id}.ordering is unsupported")
        if self.delivery == "at_least_once" and not self.identity_mapping:
            raise PortableModelError(f"binding:{self.binding_id} requires identity_mapping for at_least_once")

    def to_dict(self) -> dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "producer_port_id": self.producer_port_id,
            "consumer_port_id": self.consumer_port_id,
            "delivery": self.delivery,
            "ordering": self.ordering,
            "identity_mapping": [list(item) for item in self.identity_mapping],
            "queue_component_id": self.queue_component_id,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "SystemEventBinding":
        data = _object(value, "binding", ("binding_id", "producer_port_id", "consumer_port_id", "delivery", "ordering", "identity_mapping", "queue_component_id"))
        queue = data["queue_component_id"]
        if not isinstance(queue, str):
            raise PortableModelError("binding.queue_component_id must be a string")
        return cls(
            binding_id=_text(data["binding_id"], "binding.binding_id"),
            producer_port_id=_text(data["producer_port_id"], "binding.producer_port_id"),
            consumer_port_id=_text(data["consumer_port_id"], "binding.consumer_port_id"),
            delivery=_text(data["delivery"], "binding.delivery"),
            ordering=_text(data["ordering"], "binding.ordering"),
            identity_mapping=_pairs(data["identity_mapping"], "binding.identity_mapping"),
            queue_component_id=queue,
        )


@dataclass(frozen=True)
class SystemSharedResource:
    resource_id: str
    owner_component_id: str
    reader_component_ids: tuple[str, ...] = ()
    writer_component_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "reader_component_ids", tuple(sorted(self.reader_component_ids)))
        object.__setattr__(self, "writer_component_ids", tuple(sorted(self.writer_component_ids)))

    def to_dict(self) -> dict[str, Any]:
        return {"resource_id": self.resource_id, "owner_component_id": self.owner_component_id, "reader_component_ids": list(self.reader_component_ids), "writer_component_ids": list(self.writer_component_ids)}

    @classmethod
    def from_dict(cls, value: Any) -> "SystemSharedResource":
        data = _object(value, "resource", ("resource_id", "owner_component_id", "reader_component_ids", "writer_component_ids"))
        return cls(_text(data["resource_id"], "resource.resource_id"), _text(data["owner_component_id"], "resource.owner_component_id"), _texts(data["reader_component_ids"], "resource.reader_component_ids"), _texts(data["writer_component_ids"], "resource.writer_component_ids"))


@dataclass(frozen=True)
class SystemTransitionRef:
    component_id: str
    transition_id: str

    def to_dict(self) -> dict[str, Any]:
        return {"component_id": self.component_id, "transition_id": self.transition_id}

    @classmethod
    def from_dict(cls, value: Any) -> "SystemTransitionRef":
        data = _object(value, "transition_ref", ("component_id", "transition_id"))
        return cls(_text(data["component_id"], "transition_ref.component_id"), _text(data["transition_id"], "transition_ref.transition_id"))


@dataclass(frozen=True)
class SystemStep:
    step_id: str
    transition_refs: tuple[SystemTransitionRef, ...]
    relation_ids: tuple[str, ...] = ()
    code_targets: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "transition_refs", tuple(sorted(self.transition_refs, key=lambda item: (item.component_id, item.transition_id))))
        object.__setattr__(self, "relation_ids", tuple(sorted(self.relation_ids)))
        object.__setattr__(self, "code_targets", tuple(sorted(self.code_targets)))
        if not self.transition_refs:
            raise PortableModelError(f"step:{self.step_id} requires transition_refs")
        components = [item.component_id for item in self.transition_refs]
        if len(components) != len(set(components)):
            raise PortableModelError(f"step:{self.step_id} cannot reference two transitions from one component")

    def to_dict(self) -> dict[str, Any]:
        return {"step_id": self.step_id, "transition_refs": [item.to_dict() for item in self.transition_refs], "relation_ids": list(self.relation_ids), "code_targets": list(self.code_targets)}

    @classmethod
    def from_dict(cls, value: Any) -> "SystemStep":
        data = _object(value, "step", ("step_id", "transition_refs", "relation_ids", "code_targets"))
        return cls(_text(data["step_id"], "step.step_id"), tuple(SystemTransitionRef.from_dict(item) for item in _array(data["transition_refs"], "step.transition_refs")), _texts(data["relation_ids"], "step.relation_ids"), _texts(data["code_targets"], "step.code_targets"))


@dataclass(frozen=True)
class SystemStatePattern:
    pattern_id: str
    component_states: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "component_states", tuple(sorted(self.component_states)))
        if not self.component_states:
            raise PortableModelError(f"pattern:{self.pattern_id} requires component_states")
        components = [item[0] for item in self.component_states]
        if len(components) != len(set(components)):
            raise PortableModelError(f"pattern:{self.pattern_id} repeats a component")

    def to_dict(self) -> dict[str, Any]:
        return {"pattern_id": self.pattern_id, "component_states": [list(item) for item in self.component_states]}

    @classmethod
    def from_dict(cls, value: Any) -> "SystemStatePattern":
        data = _object(value, "pattern", ("pattern_id", "component_states"))
        return cls(_text(data["pattern_id"], "pattern.pattern_id"), _pairs(data["component_states"], "pattern.component_states"))


@dataclass(frozen=True)
class SystemProperty:
    property_id: str
    owner_id: str
    kind: str
    trigger_pattern_ids: tuple[str, ...] = ()
    target_pattern_ids: tuple[str, ...] = ()
    step_ids: tuple[str, ...] = ()
    max_steps: int | None = None

    def __post_init__(self) -> None:
        for name in ("trigger_pattern_ids", "target_pattern_ids", "step_ids"):
            object.__setattr__(self, name, tuple(sorted(getattr(self, name))))
        if self.kind not in SYSTEM_PROPERTY_KINDS:
            raise PortableModelError(f"property:{self.property_id}.kind is unsupported")
        if self.kind == "safety" and not self.target_pattern_ids:
            raise PortableModelError(f"property:{self.property_id} safety requires forbidden target patterns")
        if self.kind in {"eventually", "bounded_eventually"} and not self.target_pattern_ids:
            raise PortableModelError(f"property:{self.property_id} requires target patterns")
        if self.kind == "bounded_eventually" and (not isinstance(self.max_steps, int) or isinstance(self.max_steps, bool) or self.max_steps < 0):
            raise PortableModelError(f"property:{self.property_id} requires non-negative max_steps")
        if self.kind != "bounded_eventually" and self.max_steps is not None:
            raise PortableModelError(f"property:{self.property_id} cannot declare max_steps")
        if self.kind == "weak_fairness" and (not self.trigger_pattern_ids or not self.step_ids):
            raise PortableModelError(f"property:{self.property_id} weak_fairness requires triggers and steps")

    def to_dict(self) -> dict[str, Any]:
        return {"property_id": self.property_id, "owner_id": self.owner_id, "kind": self.kind, "trigger_pattern_ids": list(self.trigger_pattern_ids), "target_pattern_ids": list(self.target_pattern_ids), "step_ids": list(self.step_ids), "max_steps": self.max_steps}

    @classmethod
    def from_dict(cls, value: Any) -> "SystemProperty":
        data = _object(value, "property", ("property_id", "owner_id", "kind", "trigger_pattern_ids", "target_pattern_ids", "step_ids", "max_steps"))
        return cls(_text(data["property_id"], "property.property_id"), _text(data["owner_id"], "property.owner_id"), _text(data["kind"], "property.kind"), _texts(data["trigger_pattern_ids"], "property.trigger_pattern_ids"), _texts(data["target_pattern_ids"], "property.target_pattern_ids"), _texts(data["step_ids"], "property.step_ids"), data["max_steps"])


@dataclass(frozen=True)
class PortableSystemDefinition:
    system_id: str
    components: tuple[SystemComponentRef, ...]
    dependencies: tuple[SystemDependency, ...]
    ports: tuple[SystemEventPort, ...]
    bindings: tuple[SystemEventBinding, ...]
    resources: tuple[SystemSharedResource, ...]
    steps: tuple[SystemStep, ...]
    state_patterns: tuple[SystemStatePattern, ...]
    properties: tuple[SystemProperty, ...]
    unresolved_dependency_ids: tuple[str, ...] = ()
    discovery_evidence_id: str = "declared-only"
    scheduler_policy: str = "interleaving_v1"
    schema_version: str = PORTABLE_SYSTEM_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name, key in (("components", "component_id"), ("dependencies", "dependency_id"), ("ports", "port_id"), ("bindings", "binding_id"), ("resources", "resource_id"), ("steps", "step_id"), ("state_patterns", "pattern_id"), ("properties", "property_id")):
            values = tuple(sorted(getattr(self, name), key=lambda item: getattr(item, key)))
            object.__setattr__(self, name, values)
            ids = [getattr(item, key) for item in values]
            if len(ids) != len(set(ids)):
                raise PortableModelError(f"system.{name} contains duplicate ids")
        object.__setattr__(self, "unresolved_dependency_ids", tuple(sorted(self.unresolved_dependency_ids)))
        if self.schema_version != PORTABLE_SYSTEM_SCHEMA_VERSION:
            raise PortableModelError(f"system.schema_version must be {PORTABLE_SYSTEM_SCHEMA_VERSION!r}")
        if self.scheduler_policy != "interleaving_v1":
            raise PortableModelError("system.scheduler_policy must be 'interleaving_v1'")
        errors = validate_system_definition(self)
        if errors:
            raise PortableModelError("; ".join(errors))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version, "system_id": self.system_id,
            "components": [item.to_dict() for item in self.components], "dependencies": [item.to_dict() for item in self.dependencies],
            "ports": [item.to_dict() for item in self.ports], "bindings": [item.to_dict() for item in self.bindings],
            "resources": [item.to_dict() for item in self.resources], "steps": [item.to_dict() for item in self.steps],
            "state_patterns": [item.to_dict() for item in self.state_patterns], "properties": [item.to_dict() for item in self.properties],
            "unresolved_dependency_ids": list(self.unresolved_dependency_ids), "discovery_evidence_id": self.discovery_evidence_id,
            "scheduler_policy": self.scheduler_policy,
        }

    @property
    def fingerprint(self) -> str:
        return canonical_identity(self.to_dict())

    @classmethod
    def from_dict(cls, value: Any) -> "PortableSystemDefinition":
        keys = ("schema_version", "system_id", "components", "dependencies", "ports", "bindings", "resources", "steps", "state_patterns", "properties", "unresolved_dependency_ids", "discovery_evidence_id", "scheduler_policy")
        data = _object(value, "portable_system", keys)
        if data["schema_version"] != PORTABLE_SYSTEM_SCHEMA_VERSION:
            raise PortableModelError(f"portable_system.schema_version must be {PORTABLE_SYSTEM_SCHEMA_VERSION!r}")
        return cls(
            system_id=_text(data["system_id"], "portable_system.system_id"),
            components=tuple(SystemComponentRef.from_dict(item) for item in _array(data["components"], "portable_system.components")),
            dependencies=tuple(SystemDependency.from_dict(item) for item in _array(data["dependencies"], "portable_system.dependencies")),
            ports=tuple(SystemEventPort.from_dict(item) for item in _array(data["ports"], "portable_system.ports")),
            bindings=tuple(SystemEventBinding.from_dict(item) for item in _array(data["bindings"], "portable_system.bindings")),
            resources=tuple(SystemSharedResource.from_dict(item) for item in _array(data["resources"], "portable_system.resources")),
            steps=tuple(SystemStep.from_dict(item) for item in _array(data["steps"], "portable_system.steps")),
            state_patterns=tuple(SystemStatePattern.from_dict(item) for item in _array(data["state_patterns"], "portable_system.state_patterns")),
            properties=tuple(SystemProperty.from_dict(item) for item in _array(data["properties"], "portable_system.properties")),
            unresolved_dependency_ids=_texts(data["unresolved_dependency_ids"], "portable_system.unresolved_dependency_ids"),
            discovery_evidence_id=_text(data["discovery_evidence_id"], "portable_system.discovery_evidence_id"),
            scheduler_policy=_text(data["scheduler_policy"], "portable_system.scheduler_policy"),
            schema_version=data["schema_version"],
        )


@dataclass(frozen=True)
class SystemCompositionRequest:
    request_id: str
    system_id: str
    system_fingerprint: str
    changed_component_ids: tuple[str, ...]
    selected_property_ids: tuple[str, ...] = ()
    requested_component_ids: tuple[str, ...] = ()
    environment_guarantees: tuple[str, ...] = ()
    max_states: int = 10000
    schema_version: str = PORTABLE_SYSTEM_REQUEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("changed_component_ids", "selected_property_ids", "requested_component_ids", "environment_guarantees"):
            object.__setattr__(self, name, tuple(sorted(getattr(self, name))))
        if not self.changed_component_ids:
            raise PortableModelError("request.changed_component_ids must not be empty")
        if not isinstance(self.max_states, int) or isinstance(self.max_states, bool) or self.max_states <= 0:
            raise PortableModelError("request.max_states must be a positive integer")
        if self.schema_version != PORTABLE_SYSTEM_REQUEST_SCHEMA_VERSION:
            raise PortableModelError(f"request.schema_version must be {PORTABLE_SYSTEM_REQUEST_SCHEMA_VERSION!r}")

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "request_id": self.request_id, "system_id": self.system_id, "system_fingerprint": self.system_fingerprint, "changed_component_ids": list(self.changed_component_ids), "selected_property_ids": list(self.selected_property_ids), "requested_component_ids": list(self.requested_component_ids), "environment_guarantees": list(self.environment_guarantees), "max_states": self.max_states}

    @property
    def fingerprint(self) -> str:
        return canonical_identity(self.to_dict())

    @classmethod
    def from_dict(cls, value: Any) -> "SystemCompositionRequest":
        keys = ("schema_version", "request_id", "system_id", "system_fingerprint", "changed_component_ids", "selected_property_ids", "requested_component_ids", "environment_guarantees", "max_states")
        data = _object(value, "system_request", keys)
        return cls(_text(data["request_id"], "request.request_id"), _text(data["system_id"], "request.system_id"), _text(data["system_fingerprint"], "request.system_fingerprint"), _texts(data["changed_component_ids"], "request.changed_component_ids"), _texts(data["selected_property_ids"], "request.selected_property_ids"), _texts(data["requested_component_ids"], "request.requested_component_ids"), _texts(data["environment_guarantees"], "request.environment_guarantees"), data["max_states"], data["schema_version"])


@dataclass(frozen=True)
class PortableSystemSlice:
    system_id: str
    system_fingerprint: str
    request_fingerprint: str
    included_component_ids: tuple[str, ...]
    excluded_component_ids: tuple[str, ...]
    selected_property_ids: tuple[str, ...]
    blockers: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"system_id": self.system_id, "system_fingerprint": self.system_fingerprint, "request_fingerprint": self.request_fingerprint, "included_component_ids": list(self.included_component_ids), "excluded_component_ids": list(self.excluded_component_ids), "selected_property_ids": list(self.selected_property_ids), "blockers": list(self.blockers)}

    @property
    def fingerprint(self) -> str:
        return canonical_identity(self.to_dict())

    @property
    def complete(self) -> bool:
        return not self.blockers


def validate_system_definition(system: PortableSystemDefinition) -> tuple[str, ...]:
    errors: list[str] = []
    component_ids = {item.component_id for item in system.components}
    ports = {item.port_id: item for item in system.ports}
    relation_ids = {item.dependency_id for item in system.dependencies} | {item.binding_id for item in system.bindings} | {item.resource_id for item in system.resources}
    patterns = {item.pattern_id for item in system.state_patterns}
    steps = {item.step_id for item in system.steps}
    for dependency in system.dependencies:
        for value in (dependency.source_component_id, dependency.target_component_id):
            if value not in component_ids:
                errors.append(f"dependency:{dependency.dependency_id} references unknown component {value!r}")
    for port in system.ports:
        if port.component_id not in component_ids:
            errors.append(f"port:{port.port_id} references unknown component {port.component_id!r}")
    for binding in system.bindings:
        producer = ports.get(binding.producer_port_id)
        consumer = ports.get(binding.consumer_port_id)
        if producer is None or producer.direction != "output":
            errors.append(f"binding:{binding.binding_id} producer port is missing or not output")
        if consumer is None or consumer.direction != "input":
            errors.append(f"binding:{binding.binding_id} consumer port is missing or not input")
        if producer and consumer and producer.event_type != consumer.event_type:
            errors.append(f"binding:{binding.binding_id} event types differ")
        if binding.queue_component_id and binding.queue_component_id not in component_ids:
            errors.append(f"binding:{binding.binding_id} queue component is unknown")
    for resource in system.resources:
        for value in (resource.owner_component_id, *resource.reader_component_ids, *resource.writer_component_ids):
            if value not in component_ids:
                errors.append(f"resource:{resource.resource_id} references unknown component {value!r}")
    for step in system.steps:
        for ref in step.transition_refs:
            if ref.component_id not in component_ids:
                errors.append(f"step:{step.step_id} references unknown component {ref.component_id!r}")
        for relation_id in step.relation_ids:
            if relation_id not in relation_ids:
                errors.append(f"step:{step.step_id} references unknown relation {relation_id!r}")
    for pattern in system.state_patterns:
        for component_id, _state_id in pattern.component_states:
            if component_id not in component_ids:
                errors.append(f"pattern:{pattern.pattern_id} references unknown component {component_id!r}")
    for prop in system.properties:
        for pattern_id in (*prop.trigger_pattern_ids, *prop.target_pattern_ids):
            if pattern_id not in patterns:
                errors.append(f"property:{prop.property_id} references unknown pattern {pattern_id!r}")
        for step_id in prop.step_ids:
            if step_id not in steps:
                errors.append(f"property:{prop.property_id} references unknown step {step_id!r}")
    return tuple(sorted(set(errors)))


def validate_system_components(system: PortableSystemDefinition, models: Sequence[PortableModel]) -> tuple[str, ...]:
    errors: list[str] = []
    by_model_id = {item.model_id: item for item in models}
    if len(by_model_id) != len(models):
        errors.append("supplied component model ids must be unique")
    referenced_model_ids = {item.model_id for item in system.components}
    extra = sorted(set(by_model_id) - referenced_model_ids)
    if extra:
        errors.append("unreferenced component models supplied: " + ", ".join(extra))
    transitions_by_component: dict[str, set[str]] = {}
    states_by_component: dict[str, set[str]] = {}
    for ref in system.components:
        model = by_model_id.get(ref.model_id)
        if model is None:
            errors.append(f"component:{ref.component_id} model {ref.model_id!r} is missing")
            continue
        if model.fingerprint != ref.model_fingerprint:
            errors.append(f"component:{ref.component_id} model fingerprint is stale")
        transitions_by_component[ref.component_id] = {item.transition_id for item in model.transitions}
        states_by_component[ref.component_id] = {item.state_id for item in model.states}
    covered: dict[str, set[str]] = {component_id: set() for component_id in transitions_by_component}
    for step in system.steps:
        for ref in step.transition_refs:
            if ref.transition_id not in transitions_by_component.get(ref.component_id, set()):
                errors.append(f"step:{step.step_id} references unknown transition {ref.component_id}:{ref.transition_id}")
            covered.setdefault(ref.component_id, set()).add(ref.transition_id)
    for component_id, transition_ids in transitions_by_component.items():
        missing = sorted(transition_ids - covered.get(component_id, set()))
        if missing:
            errors.append(f"component:{component_id} transitions are not covered by system steps: {', '.join(missing)}")
    for pattern in system.state_patterns:
        for component_id, state_id in pattern.component_states:
            if state_id not in states_by_component.get(component_id, set()):
                errors.append(f"pattern:{pattern.pattern_id} references unknown state {component_id}:{state_id}")
    return tuple(sorted(set(errors)))


def derive_system_slice(system: PortableSystemDefinition, request: SystemCompositionRequest) -> PortableSystemSlice:
    component_ids = {item.component_id for item in system.components}
    property_ids = {item.property_id for item in system.properties}
    blockers: list[str] = []
    if request.system_id != system.system_id or request.system_fingerprint != system.fingerprint:
        blockers.append("system request identity is stale")
    unknown_roots = sorted(set(request.changed_component_ids) - component_ids)
    unknown_properties = sorted(set(request.selected_property_ids) - property_ids)
    if unknown_roots:
        blockers.append("unknown changed components: " + ", ".join(unknown_roots))
    if unknown_properties:
        blockers.append("unknown selected properties: " + ", ".join(unknown_properties))
    if system.unresolved_dependency_ids:
        blockers.append("unresolved dependencies: " + ", ".join(system.unresolved_dependency_ids))
    included = set(request.changed_component_ids) & component_ids
    selected = set(request.selected_property_ids) or property_ids
    patterns = {item.pattern_id: item for item in system.state_patterns}
    steps = {item.step_id: item for item in system.steps}
    ports = {item.port_id: item for item in system.ports}
    for prop in system.properties:
        if prop.property_id not in selected:
            continue
        for pattern_id in (*prop.trigger_pattern_ids, *prop.target_pattern_ids):
            included.update(component for component, _state in patterns[pattern_id].component_states)
        for step_id in prop.step_ids:
            included.update(ref.component_id for ref in steps[step_id].transition_refs)
    groups: list[set[str]] = []
    groups.extend({item.source_component_id, item.target_component_id} for item in system.dependencies)
    groups.extend({ref.component_id for ref in item.transition_refs} for item in system.steps)
    for binding in system.bindings:
        members = {ports[binding.producer_port_id].component_id, ports[binding.consumer_port_id].component_id}
        if binding.queue_component_id:
            members.add(binding.queue_component_id)
        groups.append(members)
    groups.extend({item.owner_component_id, *item.reader_component_ids, *item.writer_component_ids} for item in system.resources)
    changed = True
    while changed:
        changed = False
        for group in groups:
            if included.intersection(group) and not group.issubset(included):
                included.update(group)
                changed = True
    if request.requested_component_ids:
        unknown_subset = sorted(set(request.requested_component_ids) - component_ids)
        omitted = sorted(included - set(request.requested_component_ids))
        if unknown_subset:
            blockers.append("requested subset has unknown components: " + ", ".join(unknown_subset))
        if omitted:
            blockers.append("requested subset omits closure members: " + ", ".join(omitted))
    return PortableSystemSlice(system.system_id, system.fingerprint, request.fingerprint, tuple(sorted(included)), tuple(sorted(component_ids - included)), tuple(sorted(selected)), tuple(sorted(blockers)))


def load_portable_system(path: str | Path) -> PortableSystemDefinition:
    return PortableSystemDefinition.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def load_system_composition_request(path: str | Path) -> SystemCompositionRequest:
    return SystemCompositionRequest.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def write_portable_system(system: PortableSystemDefinition, path: str | Path) -> Path:
    target = Path(path)
    target.write_text(json.dumps(system.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def write_system_composition_request(request: SystemCompositionRequest, path: str | Path) -> Path:
    target = Path(path)
    target.write_text(json.dumps(request.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


__all__ = [
    "PORTABLE_SYSTEM_REQUEST_SCHEMA_VERSION", "PORTABLE_SYSTEM_SCHEMA_VERSION", "PortableSystemDefinition", "PortableSystemSlice",
    "SystemComponentRef", "SystemCompositionRequest", "SystemDependency", "SystemEventBinding", "SystemEventPort", "SystemProperty",
    "SystemSharedResource", "SystemStatePattern", "SystemStep", "SystemTransitionRef", "derive_system_slice", "load_portable_system",
    "load_system_composition_request", "validate_system_components", "validate_system_definition", "write_portable_system", "write_system_composition_request",
]
