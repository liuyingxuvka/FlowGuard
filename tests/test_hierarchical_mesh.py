import json
import unittest

from flowguard import (
    ChildModelEvidence,
    ChildReattachmentContract,
    HierarchyCoverageItem,
    HierarchyPartitionMap,
    LegacyModelRecord,
    ModelTargetSplitDerivation,
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


def target(source_model_id, child_ids, item_ids, *, state=False, side_effect=False):
    return ModelTargetSplitDerivation(
        source_model_id,
        target_child_model_ids=tuple(child_ids),
        covered_partition_item_ids=tuple(item_ids),
        state_owner_fields=("state_owner_map",) if state else (),
        side_effect_owner_fields=("side_effect_owner_map",) if side_effect else (),
        rationale="derived from parent FlowGuard model blocks, state writes, and side effects",
    )


def reattachment(child_model_id, **kwargs):
    defaults = {
        "consumed_evidence_id": f"{child_model_id}:v1",
        "expected_inputs": ("parent_input",),
        "expected_outputs": ("child_done",),
        "expected_state_owned": ("child_state",),
        "expected_side_effects_owned": ("child_effect",),
        "expected_contracts_out": ("child.guarantee",),
        "rationale": "parent consumes this child contract after a local model repair",
    }
    defaults.update(kwargs)
    return ChildReattachmentContract(child_model_id, **defaults)


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
            target_split_derivation=target(
                "checkout",
                ("payment", "inventory"),
                ("payment", "inventory", "order_status"),
            ),
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
            target_split_derivation=target("checkout", ("payment",), ("fulfillment",)),
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
            target_split_derivation=target(
                "checkout",
                ("payment", "fulfillment"),
                ("order_id",),
            ),
        )
        conflict = HierarchyPartitionMap(
            parent_model_id="checkout",
            coverage_items=(
                HierarchyCoverageItem("order_status", owner_model_id="payment"),
                HierarchyCoverageItem("order_status", owner_model_id="fulfillment"),
            ),
            child_models=(child("payment"), child("fulfillment")),
            target_split_derivation=target(
                "checkout",
                ("payment", "fulfillment"),
                ("order_status",),
            ),
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
            target_split_derivation=target(
                "checkout",
                ("payment", "fulfillment"),
                ("payment", "fulfillment"),
                state=True,
                side_effect=True,
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
            target_split_derivation=target("checkout", ("payment", "risk"), ("payment", "risk")),
        )

        report = review_hierarchical_mesh(partition)

        self.assertFalse(report.ok)
        self.assertEqual("overlap_too_high_refactor_needed", report.decision)
        self.assertIn("excessive_functional_overlap", [finding.code for finding in report.findings])

        allowed = HierarchyPartitionMap(
            parent_model_id="checkout",
            coverage_items=partition.coverage_items,
            child_models=partition.child_models,
            target_split_derivation=partition.target_split_derivation,
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
            target_split_derivation=target("checkout", ("a", "b", "c"), ("a", "b", "c")),
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
            target_split_derivation=target("workflow", ("large",), ("large",)),
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
            target_split_derivation=target("release", ("publisher",), ("publish",)),
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
            target_split_derivation=target("legacy_parent", ("old_model",), ("old",)),
        )
        report = review_hierarchical_mesh(partition)

        self.assertFalse(report.ok)
        self.assertEqual("legacy_compatibility_required", report.decision)
        self.assertIn("legacy_without_contract", [finding.code for finding in report.findings])

    def test_missing_target_split_derivation_blocks_parent_green(self):
        partition = HierarchyPartitionMap(
            parent_model_id="checkout",
            coverage_items=(HierarchyCoverageItem("payment", owner_model_id="payment"),),
            child_models=(child("payment"),),
        )

        report = review_hierarchical_mesh(partition)

        self.assertFalse(report.ok)
        self.assertEqual("target_split_derivation_required", report.decision)
        self.assertIn("missing_target_split_derivation", [finding.code for finding in report.findings])

    def test_incomplete_target_split_derivation_blocks_parent_green(self):
        partition = HierarchyPartitionMap(
            parent_model_id="checkout",
            coverage_items=(
                HierarchyCoverageItem("payment", owner_model_id="payment"),
                HierarchyCoverageItem("inventory", owner_model_id="inventory"),
            ),
            child_models=(child("payment"), child("inventory")),
            target_split_derivation=ModelTargetSplitDerivation(
                "checkout",
                target_child_model_ids=("payment",),
                covered_partition_item_ids=("payment",),
                rationale="derived from a partial parent model",
            ),
        )

        report = review_hierarchical_mesh(partition)
        codes = [finding.code for finding in report.findings]

        self.assertFalse(report.ok)
        self.assertEqual("target_split_derivation_required", report.decision)
        self.assertIn("incomplete_target_children", codes)
        self.assertIn("incomplete_target_split_coverage", codes)

    def test_child_reattachment_contract_can_continue(self):
        partition = HierarchyPartitionMap(
            parent_model_id="checkout",
            coverage_items=(HierarchyCoverageItem("payment", owner_model_id="payment"),),
            child_models=(
                child(
                    "payment",
                    evidence_id="payment:v1",
                    inputs_accepted=("parent_input",),
                    outputs_emitted=("child_done",),
                    state_owned=("child_state",),
                    side_effects_owned=("child_effect",),
                    contracts_out=("child.guarantee",),
                ),
            ),
            target_split_derivation=target(
                "checkout",
                ("payment",),
                ("payment",),
                state=True,
                side_effect=True,
            ),
            reattachment_contracts=(reattachment("payment"),),
        )

        report = review_hierarchical_mesh(partition)

        self.assertTrue(report.ok)
        self.assertEqual("mesh_green_can_continue", report.decision)

    def test_child_reattachment_requires_parent_consumed_evidence(self):
        partition = HierarchyPartitionMap(
            parent_model_id="checkout",
            coverage_items=(HierarchyCoverageItem("payment", owner_model_id="payment"),),
            child_models=(child("payment", evidence_id="payment:v2"),),
            target_split_derivation=target("checkout", ("payment",), ("payment",)),
            reattachment_contracts=(reattachment("payment", consumed_evidence_id=""),),
        )

        report = review_hierarchical_mesh(partition)

        self.assertFalse(report.ok)
        self.assertEqual("child_reattachment_required", report.decision)
        self.assertIn(
            "child_reattachment_missing_parent_consumption",
            [finding.code for finding in report.findings],
        )

    def test_child_reattachment_rejects_stale_parent_evidence_id(self):
        partition = HierarchyPartitionMap(
            parent_model_id="checkout",
            coverage_items=(HierarchyCoverageItem("payment", owner_model_id="payment"),),
            child_models=(child("payment", evidence_id="payment:v2"),),
            target_split_derivation=target("checkout", ("payment",), ("payment",)),
            reattachment_contracts=(reattachment("payment", consumed_evidence_id="payment:v1"),),
        )

        report = review_hierarchical_mesh(partition)

        self.assertFalse(report.ok)
        self.assertEqual("child_reattachment_required", report.decision)
        self.assertIn("child_reattachment_stale_evidence", [finding.code for finding in report.findings])

    def test_child_reattachment_rejects_input_and_output_drift(self):
        partition = HierarchyPartitionMap(
            parent_model_id="checkout",
            coverage_items=(HierarchyCoverageItem("payment", owner_model_id="payment"),),
            child_models=(
                child(
                    "payment",
                    evidence_id="payment:v1",
                    inputs_accepted=("unexpected_input",),
                    outputs_emitted=("child_done", "unexpected_output"),
                ),
            ),
            target_split_derivation=target("checkout", ("payment",), ("payment",)),
            reattachment_contracts=(
                reattachment(
                    "payment",
                    expected_inputs=("parent_input",),
                    expected_outputs=("child_done",),
                    expected_state_owned=(),
                    expected_side_effects_owned=(),
                    expected_contracts_out=(),
                ),
            ),
        )

        report = review_hierarchical_mesh(partition)
        codes = [finding.code for finding in report.findings]

        self.assertFalse(report.ok)
        self.assertEqual("child_reattachment_required", report.decision)
        self.assertIn("child_reattachment_missing_input", codes)
        self.assertIn("child_reattachment_extra_input", codes)
        self.assertIn("child_reattachment_extra_output", codes)

    def test_child_reattachment_rejects_ownership_and_contract_drift(self):
        partition = HierarchyPartitionMap(
            parent_model_id="checkout",
            coverage_items=(HierarchyCoverageItem("payment", owner_model_id="payment"),),
            child_models=(
                child(
                    "payment",
                    evidence_id="payment:v1",
                    inputs_accepted=("parent_input",),
                    outputs_emitted=("child_done",),
                    state_owned=("other_state",),
                    side_effects_owned=(),
                    contracts_out=("other.guarantee",),
                ),
            ),
            target_split_derivation=target(
                "checkout",
                ("payment",),
                ("payment",),
                state=True,
                side_effect=True,
            ),
            reattachment_contracts=(reattachment("payment"),),
        )

        report = review_hierarchical_mesh(partition)
        codes = [finding.code for finding in report.findings]

        self.assertFalse(report.ok)
        self.assertEqual("child_reattachment_required", report.decision)
        self.assertIn("child_reattachment_missing_state_owner", codes)
        self.assertIn("child_reattachment_missing_side_effect_owner", codes)
        self.assertIn("child_reattachment_missing_contract", codes)


if __name__ == "__main__":
    unittest.main()
