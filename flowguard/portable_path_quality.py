"""Internal provider adapter for portable-model path-quality intake.

The adapter preserves ``PortableModel`` v1 as-is.  It projects the portable
relation into the provider-neutral fact vocabulary consumed by the internal
path-quality kernel and validates compact result bindings without becoming a
second path-quality owner.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .model_path_quality import (
    PathQualityResult,
    PathQualitySubject,
    canonical_fingerprint,
    derive_retained_elements,
    normalized_model_facts_fingerprint,
)
from .portable_model import (
    PortableModel,
    PortableModelError,
    PortableTemporalObligation,
    canonical_identity,
    canonical_json_bytes,
    validate_portable_model,
)


def _state_id(state_id: str) -> str:
    return f"state:{state_id}"


def _transition_id(transition_id: str) -> str:
    return f"transition:{transition_id}"


def _output_id(transition_id: str) -> str:
    return f"output:{transition_id}"


def _portable_obligation_id(kind: str, obligation_id: str) -> str:
    return f"obligation:{kind}:{obligation_id}"


def _temporal_obligation_payload(
    obligation: PortableTemporalObligation,
) -> dict[str, Any]:
    return {
        "id": _portable_obligation_id("temporal", obligation.obligation_id),
        "kind": obligation.kind,
        "trigger_state_ids": sorted(_state_id(value) for value in obligation.trigger_state_ids),
        "target_state_ids": sorted(_state_id(value) for value in obligation.target_state_ids),
        "transition_ids": sorted(
            _transition_id(value) for value in obligation.transition_ids
        ),
        "max_steps": obligation.max_steps,
        "description": obligation.description,
    }


def compile_portable_path_quality_facts(model: PortableModel) -> dict[str, Any]:
    """Compile one exact PortableModel into language-neutral path-quality facts."""

    if not isinstance(model, PortableModel):
        raise TypeError("model must be a PortableModel")
    errors = validate_portable_model(model)
    if errors:
        raise PortableModelError("; ".join(errors))

    initial = set(model.initial_state_ids)
    terminal = set(model.terminal_state_ids)
    states = [
        {
            "id": _state_id(state.state_id),
            "initial": state.state_id in initial,
            "terminal": state.state_id in terminal,
            "payload": state.payload,
        }
        for state in sorted(model.states, key=lambda item: item.state_id)
    ]

    transitions: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    branch_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for transition in sorted(model.transitions, key=lambda item: item.transition_id):
        transition_id = _transition_id(transition.transition_id)
        output_id = _output_id(transition.transition_id)
        trigger_id = canonical_identity({"input_symbol": transition.input_symbol})
        transitions.append(
            {
                "id": transition_id,
                "source": _state_id(transition.source_state),
                "target": _state_id(transition.target_state),
                "trigger": trigger_id,
                "guard": "",
                "outputs": [output_id],
                "state_updates": [],
                "effects": [],
                "errors": [],
                "input_symbol": transition.input_symbol,
                "output_symbol": transition.output_symbol,
                "label": transition.label,
            }
        )
        outputs.append(
            {
                "id": output_id,
                "terminal": True,
                "producer_id": transition_id,
                "symbol": transition.output_symbol,
            }
        )
        branch_groups[(_state_id(transition.source_state), trigger_id)].append(transition_id)

    branches = []
    for (source, trigger_id), transition_ids in sorted(branch_groups.items()):
        if len(transition_ids) < 2:
            continue
        branches.append(
            {
                "id": f"branch:{canonical_identity({'source': source, 'trigger': trigger_id})}",
                "source": source,
                "trigger": trigger_id,
                "transition_ids": sorted(transition_ids),
            }
        )

    evidence_boundary_id = f"portable-model:{model.fingerprint}"
    obligations: list[dict[str, Any]] = []
    validations: list[dict[str, Any]] = []
    for invariant in sorted(model.invariants, key=lambda item: item.invariant_id):
        obligation_id = _portable_obligation_id("invariant", invariant.invariant_id)
        obligation = {
            "id": obligation_id,
            "kind": "invariant",
            "forbidden_state_ids": sorted(
                _state_id(value) for value in invariant.forbidden_state_ids
            ),
            "description": invariant.description,
        }
        obligations.append(obligation)
        validations.append(
            {
                "id": f"validation:invariant:{invariant.invariant_id}",
                "obligation_id": obligation_id,
                "oracle_id": f"oracle:portable-invariant:{invariant.invariant_id}",
                "subject_fingerprint": model.fingerprint,
                "evidence_boundary_id": evidence_boundary_id,
                "contract": obligation,
            }
        )
    for temporal in sorted(
        model.temporal_obligations,
        key=lambda item: item.obligation_id,
    ):
        obligation = _temporal_obligation_payload(temporal)
        obligations.append(obligation)
        validations.append(
            {
                "id": f"validation:temporal:{temporal.obligation_id}",
                "obligation_id": obligation["id"],
                "oracle_id": f"oracle:portable-temporal:{temporal.obligation_id}",
                "subject_fingerprint": model.fingerprint,
                "evidence_boundary_id": evidence_boundary_id,
                "contract": obligation,
            }
        )

    inputs_by_identity = {
        canonical_json_bytes(transition.input_symbol): transition.input_symbol
        for transition in model.transitions
    }
    return {
        "provider_kind": "flowguard.portable_model.v1",
        "model_id": model.model_id,
        "model_fingerprint": model.fingerprint,
        "states": states,
        "transitions": transitions,
        "branches": branches,
        "function_blocks": [],
        "fields": [],
        "effects": [],
        "outputs": outputs,
        "validations": validations,
        "owners": [],
        "initial_state_ids": sorted(_state_id(value) for value in model.initial_state_ids),
        "terminal_state_ids": sorted(_state_id(value) for value in model.terminal_state_ids),
        "inputs": [inputs_by_identity[key] for key in sorted(inputs_by_identity)],
        "obligations": sorted(obligations, key=lambda row: row["id"]),
        "assumptions": sorted(model.assumptions),
        "guarantees": sorted(model.guarantees),
        "conflicts": [list(pair) for pair in sorted(model.conflicts)],
        "metadata": model.metadata,
    }


def path_quality_binding_errors(
    subject: PathQualitySubject | None,
    result: PathQualityResult | None,
    *,
    portable_model: PortableModel | None = None,
) -> tuple[str, ...]:
    """Return exact intake binding errors without rejudging path quality."""

    errors: set[str] = set()
    if subject is None and result is None:
        return ()
    if subject is None:
        errors.add("path_quality_subject_missing")
    elif not isinstance(subject, PathQualitySubject):
        errors.add("path_quality_subject_type_invalid")
    if result is None:
        errors.add("path_quality_result_missing")
    elif not isinstance(result, PathQualityResult):
        errors.add("path_quality_result_type_invalid")
    if errors:
        return tuple(sorted(errors))

    assert subject is not None and result is not None
    if result.subject_fingerprint != subject.fingerprint:
        errors.add("path_quality_result_subject_mismatch")
    if result.currentness_id != subject.currentness_id:
        errors.add("path_quality_result_currentness_mismatch")
    if not result.current:
        errors.add("path_quality_result_stale")
    if result.producer_id != "model_maturation":
        errors.add("path_quality_result_producer_mismatch")

    if portable_model is not None:
        if not isinstance(portable_model, PortableModel):
            errors.add("path_quality_portable_model_type_invalid")
            return tuple(sorted(errors))
        model_errors = validate_portable_model(portable_model)
        errors.update(f"portable_model_invalid:{message}" for message in model_errors)
        if not model_errors:
            if subject.model_id != portable_model.model_id:
                errors.add("path_quality_model_id_mismatch")
            if subject.model_fingerprint != portable_model.fingerprint:
                errors.add("path_quality_model_fingerprint_mismatch")
            facts = compile_portable_path_quality_facts(portable_model)
            if (
                subject.normalized_facts_fingerprint
                != normalized_model_facts_fingerprint(facts)
            ):
                errors.add("path_quality_normalized_facts_mismatch")
            retained_fingerprint = canonical_fingerprint(
                dict(derive_retained_elements(facts))
            )
            if (
                subject.retained_element_inventory_fingerprint
                != retained_fingerprint
            ):
                errors.add("path_quality_retained_inventory_mismatch")
    return tuple(sorted(errors))


__all__ = [
    "compile_portable_path_quality_facts",
    "path_quality_binding_errors",
]
