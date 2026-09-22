"""Regression tests for the authority-owned A05 coupling denominator."""

from dataclasses import replace
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest

from flowguard.behavior_commitment import (
    BEHAVIOR_COMMITMENT_ROUTE_ID,
    behavior_commitment_contract_exhaustion_plan,
)
from flowguard.contract_exhaustion import (
    ContractAxis,
    ContractExhaustionPlan,
    ContractInteractionGroup,
    build_contract_product_signature,
    partition_context_from_accepted_authority,
    review_contract_exhaustion,
)
from flowguard.model_authority import (
    AcceptedBoundaryContract,
    AuthorityEndpointRef,
    build_boundary_contract_from_snapshot,
    load_accepted_boundary_contract,
    validate_accepted_boundary_contract_for_snapshot,
    write_content_addressed_boundary_contract,
)
from flowguard.model_authority_store import (
    activate_model_revision_set,
    bootstrap_model_authority,
    load_current_model_authority_state,
)
from flowguard.model_revision_owner_evidence import _affected_ids_by_owner
from flowguard.model_revision_set import RevisionAffectedClosure

from tests._partition_context_fixtures import accepted_authority_state
from tests.test_model_authority_store import (
    SHA_A,
    SHA_B,
    SHA_D,
    revision as store_revision,
    snapshot as store_snapshot,
)


def _producer_fixture_plan():
    axes = (
        ContractAxis(
            "boundary_state",
            model_id="authority",
            values=("ready", "blocked"),
            source_route="test_boundary_contract",
        ),
        ContractAxis(
            "boundary_mode",
            model_id="authority",
            values=("single", "nested"),
            source_route="test_boundary_contract",
        ),
    )
    group = ContractInteractionGroup(
        "boundary_state_mode",
        model_id="authority",
        axis_ids=("boundary_state", "boundary_mode"),
        max_combinations=4,
    )
    plan = ContractExhaustionPlan(
        "boundary-producer-fixture",
        model_id="authority",
        axes=axes,
        interaction_groups=(group,),
        inventory_revision="fixture-current",
    )
    return axes, (
        replace(
            group,
            product_signature=build_contract_product_signature(
                plan,
                group,
                axes=axes,
            ),
        ),
    )


def _store_boundary_contract(snapshot):
    axes, groups = _producer_fixture_plan()
    relation_id = "relation:model-realizes-purpose:authority"
    return build_boundary_contract_from_snapshot(
        snapshot,
        contract_id="boundary-contract:authority",
        model_id="authority",
        axis_payloads=tuple(axis.to_dict() for axis in axes),
        interaction_group_payloads=tuple(group.to_dict() for group in groups),
        group_relation_ids={groups[0].group_id: (relation_id,)},
    )


def test_missing_accepted_contract_cannot_use_candidate_groups_as_denominator():
    state = accepted_authority_state(BEHAVIOR_COMMITMENT_ROUTE_ID)
    state.accepted_boundary_contract = None

    with pytest.raises(ValueError, match="accepted boundary contract"):
        partition_context_from_accepted_authority(
            state,
            model_id=BEHAVIOR_COMMITMENT_ROUTE_ID,
        )


def test_foreign_contract_snapshot_is_rejected_before_matrix_generation():
    state = accepted_authority_state(BEHAVIOR_COMMITMENT_ROUTE_ID)
    state.accepted_boundary_contract = replace(
        state.accepted_boundary_contract,
        snapshot_fingerprint="sha256:" + "9" * 64,
    )

    with pytest.raises(ValueError, match="does not match the authority snapshot"):
        partition_context_from_accepted_authority(
            state,
            model_id=BEHAVIOR_COMMITMENT_ROUTE_ID,
        )


def test_candidate_axis_change_is_not_accepted_by_current_boundary():
    state = accepted_authority_state(BEHAVIOR_COMMITMENT_ROUTE_ID)
    plan = behavior_commitment_contract_exhaustion_plan(
        max_combinations=1,
        authority_state=state,
    )
    # Clear the derived field so the candidate represents a validly
    # re-fingerprinted new axis rather than merely a malformed stale payload.
    changed_axis = replace(
        plan.axes[0],
        values=("foreign-candidate-value",),
        axis_fingerprint="",
    )
    candidate = replace(plan, axes=(changed_axis, *plan.axes[1:]))

    report = review_contract_exhaustion(candidate)

    codes = {finding.code for finding in report.findings}
    assert "partition_axis_boundary_mismatch" in codes
    assert "partition_product_signature_mismatch" in codes


def test_candidate_cannot_drop_authority_relation_materialization():
    state = accepted_authority_state(BEHAVIOR_COMMITMENT_ROUTE_ID)
    plan = behavior_commitment_contract_exhaustion_plan(
        max_combinations=1,
        authority_state=state,
    )
    candidate = replace(plan, relation_materializations={})

    report = review_contract_exhaustion(candidate)

    assert any(
        finding.code == "partition_relation_materialization_missing"
        for finding in report.findings
    )


def test_current_contract_context_has_exact_accepted_product_and_relation_cells():
    state = accepted_authority_state(BEHAVIOR_COMMITMENT_ROUTE_ID)
    plan = behavior_commitment_contract_exhaustion_plan(
        max_combinations=1,
        authority_state=state,
    )
    context = plan.partition_context

    assert context is not None
    assert context.required_axes
    assert context.required_groups
    assert all(
        group.product_signature is not None
        and group.product_signature.is_self_consistent()
        for group in context.required_groups
    )
    assert set(context.group_relation_ids) == {
        group.group_id for group in context.required_groups
    }
    assert all(context.group_relation_ids.values())


def test_contract_content_address_excludes_authority_binding_and_round_trips():
    state = accepted_authority_state(BEHAVIOR_COMMITMENT_ROUTE_ID)
    contract = state.accepted_boundary_contract
    assert contract is not None

    rebound = replace(
        contract,
        snapshot_fingerprint="sha256:" + "a" * 64,
        accepted_revision_set_fingerprint="sha256:" + "b" * 64,
    )
    assert rebound.fingerprint == contract.fingerprint

    payload = contract.to_dict()
    assert "snapshot_fingerprint" not in payload
    assert "accepted_revision_set_fingerprint" not in payload
    loaded = AcceptedBoundaryContract.from_dict(payload)
    assert loaded.fingerprint == contract.fingerprint
    assert loaded.snapshot_fingerprint == ""
    assert loaded.accepted_revision_set_fingerprint == ""


def test_real_snapshot_producer_rejects_unmaterialized_relation():
    snapshot = store_snapshot("git:" + "a" * 40, SHA_A, "observed-a")
    axes, groups = _producer_fixture_plan()

    with pytest.raises(ValueError, match="unmaterialized relations"):
        build_boundary_contract_from_snapshot(
            snapshot,
            contract_id="boundary-contract:authority",
            model_id="authority",
            axis_payloads=tuple(axis.to_dict() for axis in axes),
            interaction_group_payloads=tuple(
                group.to_dict() for group in groups
            ),
            group_relation_ids={
                groups[0].group_id: ("relation:foreign",),
            },
        )


def test_structural_validator_rejects_foreign_boundary_owner_endpoint():
    base = store_snapshot("git:" + "a" * 40, SHA_A, "observed-a")
    contract = _store_boundary_contract(base)
    endpoint = AuthorityEndpointRef(
        endpoint_kind="boundary_contract",
        endpoint_id=contract.contract_id,
        fingerprint=contract.fingerprint,
        owner_route="contract_exhaustion_mesh",
    )
    candidate = replace(
        base,
        owner_artifact_refs=(*base.owner_artifact_refs, endpoint),
    )

    with pytest.raises(ValueError, match="foreign or has the wrong owner"):
        validate_accepted_boundary_contract_for_snapshot(
            contract,
            candidate,
            require_endpoint=True,
        )


def test_structural_validator_rejects_topology_from_another_snapshot():
    base = store_snapshot("git:" + "a" * 40, SHA_A, "observed-a")
    contract = _store_boundary_contract(base)
    changed_topology = store_snapshot(
        "git:" + "b" * 40,
        SHA_B,
        "observed-b",
    )

    with pytest.raises(ValueError, match="topology fingerprint is stale"):
        validate_accepted_boundary_contract_for_snapshot(
            contract,
            changed_topology,
            require_endpoint=False,
        )


def test_structural_validator_returns_current_fingerprint_for_authority_endpoint():
    base = store_snapshot("git:" + "a" * 40, SHA_A, "observed-a")
    contract = _store_boundary_contract(base)
    endpoint = AuthorityEndpointRef(
        endpoint_kind="boundary_contract",
        endpoint_id=contract.contract_id,
        fingerprint=contract.fingerprint,
        owner_route="authoritative_model_system",
    )
    candidate = replace(
        base,
        owner_artifact_refs=(*base.owner_artifact_refs, endpoint),
    )

    validator_fingerprint = validate_accepted_boundary_contract_for_snapshot(
        contract,
        candidate,
        require_endpoint=True,
    )

    assert validator_fingerprint.startswith("sha256:")


def test_boundary_endpoint_enters_existing_authority_owner_closure():
    boundary_id = "boundary_contract:authority"
    closure = RevisionAffectedClosure(
        affected_ids=(boundary_id, "model_instance:model:authority"),
        edge_ids=(),
        owner_bindings=(
            (boundary_id, "authoritative_model_system"),
            ("model_instance:model:authority", "model_test_alignment"),
        ),
    )

    affected_by_owner = _affected_ids_by_owner(closure)

    assert affected_by_owner["authoritative_model_system"] == (boundary_id,)


def test_real_boundary_contract_save_reload_and_activation_uses_same_authority_endpoint():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        manifest = root / ".flowguard" / "project.toml"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            '[flowguard]\nadopted_package_version = "0.69.0"\n',
            encoding="utf-8",
        )

        base = store_snapshot("git:" + "a" * 40, SHA_A, "observed-a")
        initial_head = bootstrap_model_authority(
            root,
            base,
            bootstrap_evidence_fingerprint=SHA_D,
        )
        contract = _store_boundary_contract(base)
        contract_path = write_content_addressed_boundary_contract(root, contract)
        loaded_contract = load_accepted_boundary_contract(contract_path)
        assert loaded_contract == contract

        endpoint = AuthorityEndpointRef(
            endpoint_kind="boundary_contract",
            endpoint_id=contract.contract_id,
            fingerprint=contract.fingerprint,
            owner_route="authoritative_model_system",
        )
        candidate_base = store_snapshot(
            "git:" + "b" * 40,
            SHA_A,
            "observed-b",
        )
        candidate = replace(
            candidate_base,
            owner_artifact_refs=(
                *candidate_base.owner_artifact_refs,
                endpoint,
            ),
        )
        accepted_revision = store_revision(
            root,
            initial_head,
            base,
            candidate,
        )

        with patch(
            "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
            return_value=candidate,
        ):
            activated_head, activation = activate_model_revision_set(
                root,
                candidate,
                accepted_revision,
            )

        current = load_current_model_authority_state(root)
        assert current.head == activated_head
        assert current.activation_receipt == activation
        assert current.snapshot == candidate
        assert current.accepted_boundary_contract == loaded_contract
        assert current.accepted_boundary_contract.fingerprint == contract.fingerprint
        assert json.loads(contract_path.read_text(encoding="utf-8"))["fingerprint"] == contract.fingerprint
