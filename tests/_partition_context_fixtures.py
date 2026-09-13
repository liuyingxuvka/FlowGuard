"""Small accepted-authority fixtures for partitioned contract tests."""

from dataclasses import replace
from types import SimpleNamespace

from flowguard.canonical_relation import CanonicalRelation
from flowguard.contract_exhaustion import (
    ContractExhaustionPlan,
    build_contract_product_signature,
)
from flowguard.model_authority import (
    AcceptedBoundaryContract,
    boundary_topology_fingerprint,
    canonical_fingerprint,
)


def accepted_authority_state(model_id: str):
    """Return the smallest accepted observed authority for one route model.

    The fixture deliberately carries the same identity fields that the runtime
    adapter validates: accepted revision, active observed snapshot, complete
    finite boundary, and an evidenced model-to-code relation.  It is not a
    replacement for the project store; it keeps the route tests deterministic
    while exercising the adapter's fail-closed checks.
    """

    model_id = str(model_id)
    head_fingerprint = "sha256:" + "1" * 64
    snapshot_fingerprint = "sha256:" + "2" * 64
    revision_fingerprint = "sha256:" + "3" * 64
    boundary_fingerprint = "sha256:" + "4" * 64
    evidence_fingerprint = "sha256:" + "5" * 64
    model_fingerprint = "sha256:" + "6" * 64
    relation_id = f"authority-relation:{model_id}"

    endpoint = lambda kind, endpoint_id, fingerprint: SimpleNamespace(
        endpoint_kind=kind,
        endpoint_id=endpoint_id,
        fingerprint=fingerprint,
        owner_route=model_id,
    )
    relation = SimpleNamespace(
        relation_id=relation_id,
        kind="realizes",
        source=endpoint("model_instance", f"model:{model_id}", model_fingerprint),
        target=endpoint("code_contract", f"contract:{model_id}", model_fingerprint),
        evidence_fingerprints=(evidence_fingerprint,),
    )
    coverage = SimpleNamespace(
        complete=True,
        boundary_id=f"authority-boundary:{model_id}",
        fingerprint=boundary_fingerprint,
    )
    snapshot = SimpleNamespace(
        fingerprint=snapshot_fingerprint,
        lifecycle="active",
        subject_lane="observed_implementation",
        coverage=coverage,
        coverage_status="complete_within_declared_boundary",
        unresolved_gap_ids=(),
        model_instances=(
            SimpleNamespace(logical_model_id=model_id, fingerprint=model_fingerprint),
        ),
        relations=(relation,),
    )
    head = SimpleNamespace(
        fingerprint=head_fingerprint,
        snapshot_fingerprint=snapshot_fingerprint,
        accepted_revision_set_fingerprint=revision_fingerprint,
    )
    accepted_revision = SimpleNamespace(
        status="accepted",
        fingerprint=revision_fingerprint,
    )
    if model_id == "behavior_commitment_ledger":
        from flowguard.behavior_commitment import (
            default_behavior_commitment_axes,
            default_behavior_commitment_interaction_groups,
        )

        axes = default_behavior_commitment_axes(model_id=model_id)
        groups = default_behavior_commitment_interaction_groups(model_id=model_id)
    elif model_id == "primary_path_authority":
        from flowguard.primary_path_authority import (
            default_primary_path_authority_axes,
            default_primary_path_authority_interaction_groups,
        )

        axes = default_primary_path_authority_axes(model_id=model_id)
        groups = default_primary_path_authority_interaction_groups(model_id=model_id)
    else:
        axes = ()
        groups = ()
    if axes and groups:
        fixture_plan = ContractExhaustionPlan(
            plan_id=f"accepted-boundary-fixture:{model_id}",
            model_id=model_id,
            axes=axes,
            interaction_groups=groups,
            inventory_revision=f"authority:{head_fingerprint}",
        )
        groups = tuple(
            replace(
                group,
                product_signature=build_contract_product_signature(
                    fixture_plan,
                    group,
                    axes=tuple(
                        next(axis for axis in axes if axis.axis_id == axis_id)
                        for axis_id in group.axis_ids
                    ),
                ),
            )
            for group in groups
        )
        canonical_relation = CanonicalRelation(
            relation_id=relation_id,
            relation_type="realizes",
            source_endpoint_kind="model_instance",
            source_endpoint_id=f"model:{model_id}",
            target_endpoint_kind="code_contract",
            target_endpoint_id=f"contract:{model_id}",
            source_ids=(evidence_fingerprint,),
            metadata={
                "authority_snapshot_fingerprint": snapshot_fingerprint,
                "authority_head_fingerprint": head_fingerprint,
            },
        )
        topology_fingerprint = boundary_topology_fingerprint(
            snapshot.model_instances,
            (canonical_relation,),
        )
        boundary_contract = AcceptedBoundaryContract(
            contract_id=f"boundary-contract:{model_id}",
            model_id=model_id,
            boundary_source_id=coverage.boundary_id,
            boundary_source_fingerprint=boundary_fingerprint,
            snapshot_fingerprint=snapshot_fingerprint,
            accepted_revision_set_fingerprint=revision_fingerprint,
            topology_fingerprint=topology_fingerprint,
            axis_payloads=tuple(axis.to_dict() for axis in axes),
            interaction_group_payloads=tuple(group.to_dict() for group in groups),
            group_relation_ids={
                group.group_id: (relation_id,) for group in groups
            },
        )
    else:
        boundary_contract = None
    return SimpleNamespace(
        head=head,
        snapshot=snapshot,
        accepted_revision=accepted_revision,
        transition_kind="activation",
        accepted_boundary_contract=boundary_contract,
    )
