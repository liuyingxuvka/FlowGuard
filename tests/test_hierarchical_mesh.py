import json
import unittest

from flowguard import (
    ChildModelEvidence,
    HierarchyCoverageItem,
    HierarchyPartitionMap,
    LegacyModelRecord,
    classify_legacy_model,
    review_hierarchical_mesh,
)


def child(model_id, **kwargs):
    defaults = {
        "evidence_tier": "abstract_green",
        "functional_areas": (model_id,),
    }
    defaults.update(kwargs)
    return ChildModelEvidence(model_id, **defaults)


class HierarchicalMeshTests(unittest.TestCase):
    def test_complete_partition_map_can_continue(self):
        partition = HierarchyPartitionMap(
            parent_model_id="checkout",
            coverage_items=(
                HierarchyCoverageItem("payment", owner_model_id="payment"),
                HierarchyCoverageItem("inventory", owner_model_id="inventory"),
                HierarchyCoverageItem("order_status", ownership="parent"),
            ),
            child_models=(child("payment"), child("inventory")),
        )

        report = review_hierarchical_mesh(partition)

        self.assertTrue(report.ok)
        self.assertEqual("mesh_green_can_continue", report.decision)
        self.assertEqual([], report.to_dict()["findings"])
        self.assertIn("flowguard hierarchical mesh", report.format_text())

    def test_missing_owner_is_coverage_gap(self):
        partition = HierarchyPartitionMap(
            parent_model_id="checkout",
            coverage_items=(HierarchyCoverageItem("fulfillment", owner_model_id=""),),
            child_models=(child("payment"),),
        )

        report = review_hierarchical_mesh(partition)

        self.assertFalse(report.ok)
        self.assertEqual("coverage_gap_blocked", report.decision)
        self.assertIn("coverage_gap", [finding.code for finding in report.findings])

    def test_read_only_overlap_is_allowed_but_duplicate_write_owner_fails(self):
        allowed = HierarchyPartitionMap(
            parent_model_id="checkout",
            coverage_items=(
                HierarchyCoverageItem("order_id", owner_model_id="payment"),
                HierarchyCoverageItem("order_id", owner_model_id="fulfillment", ownership="read_only"),
            ),
            child_models=(child("payment"), child("fulfillment")),
        )
        conflict = HierarchyPartitionMap(
            parent_model_id="checkout",
            coverage_items=(
                HierarchyCoverageItem("order_status", owner_model_id="payment"),
                HierarchyCoverageItem("order_status", owner_model_id="fulfillment"),
            ),
            child_models=(child("payment"), child("fulfillment")),
        )

        self.assertTrue(review_hierarchical_mesh(allowed).ok)
        report = review_hierarchical_mesh(conflict)
        self.assertFalse(report.ok)
        self.assertIn("duplicate_coverage_owner", [finding.code for finding in report.findings])

    def test_duplicate_state_and_side_effect_ownership_fail(self):
        partition = HierarchyPartitionMap(
            parent_model_id="checkout",
            coverage_items=(
                HierarchyCoverageItem("payment", owner_model_id="payment"),
                HierarchyCoverageItem("fulfillment", owner_model_id="fulfillment"),
            ),
            child_models=(
                child("payment", state_owned=("order_status",), side_effects_owned=("send_email",)),
                child("fulfillment", state_owned=("order_status",), side_effects_owned=("send_email",)),
            ),
        )

        report = review_hierarchical_mesh(partition)

        self.assertFalse(report.ok)
        self.assertEqual("ownership_conflict", report.decision)
        self.assertIn("duplicate_state_owner", [finding.code for finding in report.findings])
        self.assertIn("duplicate_side_effect_owner", [finding.code for finding in report.findings])

    def test_functional_overlap_requires_shared_kernel(self):
        partition = HierarchyPartitionMap(
            parent_model_id="checkout",
            coverage_items=(
                HierarchyCoverageItem("payment", owner_model_id="payment"),
                HierarchyCoverageItem("risk", owner_model_id="risk"),
            ),
            child_models=(
                child("payment", functional_areas=("payment", "fraud")),
                child("risk", functional_areas=("fraud", "risk")),
            ),
        )

        report = review_hierarchical_mesh(partition)

        self.assertFalse(report.ok)
        self.assertEqual("overlap_too_high_refactor_needed", report.decision)
        self.assertIn("excessive_functional_overlap", [finding.code for finding in report.findings])

        allowed = HierarchyPartitionMap(
            parent_model_id="checkout",
            coverage_items=partition.coverage_items,
            child_models=partition.child_models,
            allowed_shared_areas=("fraud",),
        )
        self.assertTrue(review_hierarchical_mesh(allowed).ok)

    def test_quantity_and_large_model_activation_triggers_are_reported(self):
        partition = HierarchyPartitionMap(
            parent_model_id="checkout",
            coverage_items=(
                HierarchyCoverageItem("a", owner_model_id="a"),
                HierarchyCoverageItem("b", owner_model_id="b"),
                HierarchyCoverageItem("c", owner_model_id="c"),
            ),
            child_models=(
                child("a"),
                child("b", estimated_state_count=10_001, structurally_cohesive=True),
                child("c"),
            ),
        )

        report = review_hierarchical_mesh(partition)

        self.assertTrue(report.ok)
        self.assertIn("model_count", report.activation_reasons)
        self.assertIn("large_model:b", report.activation_reasons)
        self.assertEqual({"b": "keep_as_single_model"}, report.split_decisions)

    def test_large_model_with_separable_areas_requires_split_review(self):
        partition = HierarchyPartitionMap(
            parent_model_id="workflow",
            coverage_items=(HierarchyCoverageItem("large", owner_model_id="large"),),
            child_models=(
                child(
                    "large",
                    estimated_state_count=20_000,
                    unrelated_functional_areas=True,
                    structurally_cohesive=False,
                ),
            ),
        )

        report = review_hierarchical_mesh(partition)

        self.assertFalse(report.ok)
        self.assertEqual("large_model_split_review_required", report.decision)
        self.assertEqual({"large": "split_into_children"}, report.split_decisions)

    def test_stale_skipped_and_insufficient_evidence_are_visible(self):
        partition = HierarchyPartitionMap(
            parent_model_id="release",
            required_evidence_tier="conformance_green",
            coverage_items=(HierarchyCoverageItem("publish", owner_model_id="publisher"),),
            child_models=(
                child(
                    "publisher",
                    evidence_tier="abstract_green",
                    evidence_current=False,
                    skipped_checks=("conformance",),
                    not_run_checks=("live_projection",),
                ),
            ),
        )

        report = review_hierarchical_mesh(partition)
        codes = [finding.code for finding in report.findings]

        self.assertFalse(report.ok)
        self.assertIn("stale_child_evidence", codes)
        self.assertIn("missing_or_skipped_child_check", codes)
        self.assertIn("insufficient_evidence_tier", codes)
        self.assertIn("skipped_checks", json.dumps(report.to_dict()))

    def test_legacy_model_requires_contract_before_strong_evidence(self):
        record = LegacyModelRecord("old_model", observed_state_count=15_000, functional_area_count=2)
        classification = classify_legacy_model(record)

        self.assertTrue(classification.requires_split_review)
        self.assertFalse(classification.can_be_strong_evidence)
        self.assertIn("legacy_large_review_needed", classification.labels)
        self.assertIn("legacy_without_contract", classification.labels)

        partition = HierarchyPartitionMap(
            parent_model_id="legacy_parent",
            coverage_items=(HierarchyCoverageItem("old", owner_model_id="old_model"),),
            child_models=(child("old_model", is_legacy=True, has_compatibility_contract=False),),
        )
        report = review_hierarchical_mesh(partition)

        self.assertFalse(report.ok)
        self.assertEqual("legacy_compatibility_required", report.decision)
        self.assertIn("legacy_without_contract", [finding.code for finding in report.findings])


if __name__ == "__main__":
    unittest.main()
