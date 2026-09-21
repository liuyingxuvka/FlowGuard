from __future__ import annotations

import pytest

from flowguard.execution_profiles import (
    EXECUTION_PROFILE_AFFECTED,
    EXECUTION_PROFILE_FULL,
    EXECUTION_PROFILE_LIGHT,
    MODELING_MODE_LAYERED_BOUNDARY_PROOF,
    MODELING_MODE_MODEL_MAINTENANCE,
    MODELING_MODE_READ_ONLY_AUDIT,
    LIFECYCLE_CHANGE,
    LIFECYCLE_READ,
    LIFECYCLE_RELEASE,
    OPERATION_KIND_CHANGE,
    OPERATION_KIND_QUALIFICATION,
    OPERATION_KIND_READ_ONLY,
    ExecutionProfileError,
    select_execution_profile,
    validate_execution_profile_decision,
)


def test_read_only_defaults_to_light_and_declares_all_entry_fields() -> None:
    decision = select_execution_profile(operation_kind=OPERATION_KIND_READ_ONLY)
    assert decision.execution_profile == EXECUTION_PROFILE_LIGHT
    assert decision.modeling_mode == MODELING_MODE_READ_ONLY_AUDIT
    assert decision.ok
    payload = decision.to_dict()
    assert {
        "execution_profile",
        "modeling_mode",
        "claim_boundary",
        "selection_reason",
        "closed_obligations",
        "not_run_obligations",
        "escalation_triggers",
    } <= set(payload)
    assert validate_execution_profile_decision(payload).ok


def test_change_defaults_to_affected_and_specialist_does_not_escalate() -> None:
    decision = select_execution_profile(
        operation_kind=OPERATION_KIND_CHANGE,
        route_kind="model_test_alignment",
        changed_paths=("flowguard/example.py",),
        modeling_mode=MODELING_MODE_MODEL_MAINTENANCE,
    )
    assert decision.execution_profile == EXECUTION_PROFILE_AFFECTED
    assert decision.modeling_mode == MODELING_MODE_MODEL_MAINTENANCE
    assert decision.ok
    assert "specialist route" in decision.selection_reason


def test_typed_operation_kind_selects_exactly_one_profile() -> None:
    light = select_execution_profile(
        operation_kind=OPERATION_KIND_READ_ONLY,
        changed_paths=("flowguard/example.py",),
    )
    assert light.ok
    assert light.execution_profile == EXECUTION_PROFILE_LIGHT

    affected = select_execution_profile(
        operation_kind=OPERATION_KIND_CHANGE,
        changed_paths=("flowguard/example.py",),
    )
    assert affected.ok
    assert affected.execution_profile == EXECUTION_PROFILE_AFFECTED

    full = select_execution_profile(
        operation_kind=OPERATION_KIND_QUALIFICATION,
        governed_writes_frozen=True,
        projections_frozen=True,
        openspec_frozen=True,
        owner_dag_frozen=True,
        reverse_input_frozen=True,
    )
    assert full.ok
    assert full.execution_profile == EXECUTION_PROFILE_FULL


def test_internal_profile_names_are_rejected_at_the_public_boundary() -> None:
    for retired_name in (EXECUTION_PROFILE_LIGHT, EXECUTION_PROFILE_AFFECTED, EXECUTION_PROFILE_FULL):
        with pytest.raises(ExecutionProfileError, match="lifecycle must be one of"):
            select_execution_profile(retired_name)

    with pytest.raises(ExecutionProfileError, match="lifecycle conflicts"):
        select_execution_profile(
            LIFECYCLE_READ,
            operation_kind=OPERATION_KIND_CHANGE,
            changed_paths=("flowguard/example.py",),
        )


def test_release_requires_every_freeze_gate() -> None:
    blocked = select_execution_profile(
        LIFECYCLE_RELEASE,
        modeling_mode=MODELING_MODE_LAYERED_BOUNDARY_PROOF,
    )
    assert not blocked.ok
    assert blocked.status == "blocked"
    assert set(blocked.escalation_triggers) == {
        "governed_writes_not_frozen",
        "projections_not_frozen",
        "openspec_not_frozen",
        "owner_dag_not_frozen",
        "reverse_input_not_frozen",
    }
    ready = select_execution_profile(
        LIFECYCLE_RELEASE,
        modeling_mode=MODELING_MODE_LAYERED_BOUNDARY_PROOF,
        governed_writes_frozen=True,
        projections_frozen=True,
        openspec_frozen=True,
        owner_dag_frozen=True,
        reverse_input_frozen=True,
    )
    assert ready.ok
    assert ready.escalation_triggers == ()


def test_profile_and_mode_validation_is_fail_closed() -> None:
    with pytest.raises(ExecutionProfileError):
        select_execution_profile("full", modeling_mode="full")
    payload = select_execution_profile(operation_kind=OPERATION_KIND_READ_ONLY).to_dict()
    payload["ok"] = True
    payload["status"] = "blocked"
    with pytest.raises(ExecutionProfileError):
        validate_execution_profile_decision(payload)


def test_prose_operation_selector_is_not_a_compatibility_route() -> None:
    with pytest.raises(TypeError):
        select_execution_profile(operation="audit")  # type: ignore[call-arg]
