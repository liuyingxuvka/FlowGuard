"""Run a small hierarchical model-mesh review example."""

from __future__ import annotations

from flowguard import (
    ChildModelEvidence,
    ChildReattachmentContract,
    HierarchyCoverageItem,
    HierarchyPartitionMap,
    LegacyModelRecord,
    MeshClosureJoin,
    MeshClosureModel,
    MeshClosureTerminal,
    MeshClosureTransition,
    ModelTargetSplitDerivation,
    classify_legacy_model,
    review_hierarchical_mesh,
)


def _child(model_id: str, **kwargs) -> ChildModelEvidence:
    defaults = {
        "evidence_tier": "abstract_green",
        "functional_areas": (model_id,),
        "state_owned": (f"{model_id}_state",),
    }
    defaults.update(kwargs)
    return ChildModelEvidence(model_id, **defaults)


def _target(parent_id: str, child_ids: tuple[str, ...], item_ids: tuple[str, ...]) -> ModelTargetSplitDerivation:
    return ModelTargetSplitDerivation(
        parent_id,
        target_child_model_ids=child_ids,
        covered_partition_item_ids=item_ids,
        state_owner_fields=("state_owner_map",),
        side_effect_owner_fields=("side_effect_owner_map",),
        rationale="derived from parent model blocks, state writes, and side effects",
    )


def build_root_partition() -> HierarchyPartitionMap:
    return HierarchyPartitionMap(
        parent_model_id="checkout_root",
        coverage_items=(
            HierarchyCoverageItem("payment", "function", "payment"),
            HierarchyCoverageItem("inventory", "function", "inventory"),
            HierarchyCoverageItem("fulfillment", "function", "fulfillment"),
            HierarchyCoverageItem("order_status", "state", ownership="parent"),
        ),
        child_models=(
            _child(
                "payment",
                evidence_id="payment:model-check:v1",
                inputs_accepted=("payment_request",),
                outputs_emitted=("payment_result",),
                side_effects_owned=("charge_card",),
                contracts_out=("payment.result",),
            ),
            _child("inventory", outputs_emitted=("inventory_result",), side_effects_owned=("reserve_stock",)),
            _child("fulfillment", outputs_emitted=("fulfillment_result",), side_effects_owned=("ship_order",)),
        ),
        target_split_derivation=_target(
            "checkout_root",
            ("payment", "inventory", "fulfillment"),
            ("payment", "inventory", "fulfillment", "order_status"),
        ),
        reattachment_contracts=(
            ChildReattachmentContract(
                "payment",
                consumed_evidence_id="payment:model-check:v1",
                expected_inputs=("payment_request",),
                expected_outputs=("payment_result",),
                expected_state_owned=("payment_state",),
                expected_side_effects_owned=("charge_card",),
                expected_contracts_out=("payment.result",),
                rationale="checkout parent consumes the repaired payment child handoff",
            ),
        ),
        closure_model=MeshClosureModel(
            "checkout_root",
            root_entries=("checkout_start",),
            transitions=(
                MeshClosureTransition(
                    "payment_handoff",
                    consumes=("checkout_start",),
                    emits=("payment_result",),
                    consumer_model_id="payment",
                ),
                MeshClosureTransition(
                    "inventory_handoff",
                    consumes=("checkout_start",),
                    emits=("inventory_result",),
                    consumer_model_id="inventory",
                ),
                MeshClosureTransition(
                    "fulfillment_handoff",
                    consumes=("checkout_start",),
                    emits=("fulfillment_result",),
                    consumer_model_id="fulfillment",
                ),
            ),
            joins=(
                MeshClosureJoin(
                    "checkout_ready",
                    required_inputs=("payment_result", "inventory_result", "fulfillment_result"),
                    emits=("order_complete_ready",),
                    rationale="all child regions must finish before the checkout parent can close",
                ),
            ),
            terminals=(
                MeshClosureTerminal("checkout_complete", consumes=("order_complete_ready",)),
            ),
            rationale="parent-level closure over child model outputs without expanding child internals",
        ),
    )


def build_nested_fulfillment_partition() -> HierarchyPartitionMap:
    return HierarchyPartitionMap(
        parent_model_id="fulfillment",
        coverage_items=(
            HierarchyCoverageItem("packing", "function", "packing"),
            HierarchyCoverageItem("shipping", "function", "shipping"),
            HierarchyCoverageItem("tracking", "state", "shipping"),
        ),
        child_models=(
            _child("packing", side_effects_owned=("create_package",)),
            _child("shipping", side_effects_owned=("buy_label", "notify_carrier")),
        ),
        target_split_derivation=_target(
            "fulfillment",
            ("packing", "shipping"),
            ("packing", "shipping", "tracking"),
        ),
    )


def build_bad_partition() -> HierarchyPartitionMap:
    return HierarchyPartitionMap(
        parent_model_id="checkout_root",
        coverage_items=(
            HierarchyCoverageItem("payment", "function", "payment"),
            HierarchyCoverageItem("inventory", "function", ""),
            HierarchyCoverageItem("order_status", "state", "payment"),
            HierarchyCoverageItem("order_status", "state", "fulfillment"),
        ),
        child_models=(
            _child("payment", functional_areas=("payment", "fraud"), side_effects_owned=("send_email",)),
            _child("fulfillment", functional_areas=("fulfillment", "fraud"), side_effects_owned=("send_email",)),
        ),
        target_split_derivation=_target(
            "checkout_root",
            ("payment", "fulfillment"),
            ("payment", "inventory", "order_status"),
        ),
    )


def build_large_legacy_record() -> LegacyModelRecord:
    return LegacyModelRecord(
        "legacy_checkout_model",
        model_file=".flowguard/checkout/model.py",
        observed_state_count=25_000,
        functional_area_count=3,
        has_compatibility_contract=False,
    )


def main() -> int:
    root = review_hierarchical_mesh(build_root_partition())
    nested = review_hierarchical_mesh(build_nested_fulfillment_partition())
    bad = review_hierarchical_mesh(build_bad_partition())
    legacy = classify_legacy_model(build_large_legacy_record())

    print(root.format_text())
    print()
    print(nested.format_text())
    print()
    print(bad.format_text())
    print()
    print(legacy.to_dict())

    if not root.ok or not nested.ok:
        return 1
    if bad.ok:
        return 1
    if not legacy.requires_split_review or legacy.can_be_strong_evidence:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
