"""Run a small hierarchical model-mesh review example."""

from __future__ import annotations

from flowguard import (
    ChildModelEvidence,
    HierarchyCoverageItem,
    HierarchyPartitionMap,
    LegacyModelRecord,
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
            _child("payment", side_effects_owned=("charge_card",)),
            _child("inventory", side_effects_owned=("reserve_stock",)),
            _child("fulfillment", side_effects_owned=("ship_order",)),
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
