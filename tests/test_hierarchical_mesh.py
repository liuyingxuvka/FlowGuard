import json
import unittest

from flowguard import (
    ChildModelEvidence,
    ChildReattachmentContract,
    HierarchyCoverageItem,
    HierarchyPartitionMap,
    MeshClosureJoin,
    MeshClosureModel,
    MeshClosureTerminal,
    MeshClosureTransition,
    ModelTargetSplitDerivation,
    review_hierarchical_mesh,
    review_mesh_closure_model,
    summarize_child_boundary_change,
)
from flowguard.model_path_quality import (
    PathQualityResult,
    PathQualitySubject,
    canonical_fingerprint,
)


def path_fp(value):
    return canonical_fingerprint({"value": value})


def path_quality(model_id="payment", currentness_id="snapshot:current"):
    owner = PathQualitySubject(
        model_id=model_id,
        boundary_id=f"boundary:{model_id}",
        model_fingerprint=path_fp(f"model:{model_id}"),
        normalized_facts_fingerprint=path_fp(f"facts:{model_id}"),
        retained_element_inventory_fingerprint=path_fp(f"retained:{model_id}"),
        purpose_fingerprint=path_fp(f"purpose:{model_id}"),
        intent_fingerprint=path_fp(f"intent:{model_id}"),
        obligation_fingerprint=path_fp(f"obligations:{model_id}"),
        provider_fingerprint=path_fp(f"provider:{model_id}"),
        dependency_fingerprint=path_fp(f"dependencies:{model_id}"),
        code_fingerprint=path_fp(f"code:{model_id}"),
        test_fingerprint=path_fp(f"tests:{model_id}"),
        oracle_fingerprint=path_fp(f"oracles:{model_id}"),
        evidence_fingerprint=path_fp(f"evidence:{model_id}"),
        currentness_id=currentness_id,
    )
    result = PathQualityResult(
        result_id=f"path-quality:{model_id}",
        subject_fingerprint=owner.fingerprint,
        mode="lightweight",
        trigger_ids=(),
        finding_ids=(),
        candidate_ids=(),
        rewrite_rule_ids=(),
        conclusion="single_clear_path",
        unresolved_ids=(),
        selected_candidate_id="",
        selected_candidate_lane="",
        comparison_boundary_id="",
        candidate_set_fingerprint="",
        rewrite_set_fingerprint="",
        necessity_witness_set_fingerprint=path_fp(f"witnesses:{model_id}"),
        detail_evidence_fingerprint=path_fp(f"detail:{model_id}"),
        producer_id="model_maturation",
        currentness_id=currentness_id,
    )
    return owner, result


def child(model_id, **kwargs):
    defaults = {
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
        "expected_inputs": ("parent_input",),
        "expected_outputs": ("child_done",),
        "expected_state_owned": ("child_state",),
        "expected_side_effects_owned": ("child_effect",),
        "expected_contracts_out": ("child.guarantee",),
        "rationale": "parent consumes this child contract after a local model repair",
    }
    defaults.update(kwargs)
    return ChildReattachmentContract(child_model_id, **defaults)


def reattachment_empty(child_model_id, **kwargs):
    defaults = {
        "expected_inputs": (),
        "expected_outputs": (),
        "expected_state_owned": (),
        "expected_side_effects_owned": (),
        "expected_contracts_out": (),
        "rationale": "parent consumes current child evidence without extra handoff expectations",
    }
    defaults.update(kwargs)
    return ChildReattachmentContract(child_model_id, **defaults)


def closure_model(**kwargs):
    defaults = {
        "parent_model_id": "checkout",
        "root_entries": ("root_start",),
        "transitions": (
            MeshClosureTransition(
                "start_payment",
                consumes=("root_start",),
                emits=("payment_result",),
                consumer_model_id="payment",
            ),
            MeshClosureTransition(
                "start_inventory",
                consumes=("root_start",),
                emits=("inventory_result",),
                consumer_model_id="inventory",
            ),
        ),
        "joins": (
            MeshClosureJoin(
                "checkout_ready",
                required_inputs=("payment_result", "inventory_result"),
                emits=("order_ready",),
            ),
        ),
        "terminals": (
            MeshClosureTerminal(
                "order_complete",
                consumes=("order_ready",),
                terminal_kind="normal_exit",
            ),
        ),
    }
    defaults.update(kwargs)
    return MeshClosureModel(**defaults)


def reattachment_closure(output="payment_reattached"):
    return MeshClosureModel(
        parent_model_id="checkout",
        root_entries=("root_start",),
        transitions=(
            MeshClosureTransition(
                "reattach_payment",
                consumes=("root_start",),
                emits=(output,),
                consumer_model_id="payment",
            ),
        ),
        terminals=(MeshClosureTerminal("reattached", consumes=(output,)),),
    )


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


    def test_child_output_without_handoff_needs_no_closure_model(self):
        partition = HierarchyPartitionMap(
            parent_model_id="checkout",
            coverage_items=(HierarchyCoverageItem("payment", owner_model_id="payment"),),
            child_models=(child("payment", outputs_emitted=("payment_result",)),),
            target_split_derivation=target("checkout", ("payment",), ("payment",)),
        )

        report = review_hierarchical_mesh(partition)

        self.assertTrue(report.ok)
        self.assertEqual("mesh_green_can_continue", report.decision)
        self.assertNotIn("mesh_closure_required", [finding.code for finding in report.findings])

    def test_reattachment_without_handoff_needs_no_closure_model(self):
        partition = HierarchyPartitionMap(
            parent_model_id="checkout",
            coverage_items=(HierarchyCoverageItem("payment", owner_model_id="payment"),),
            child_models=(child("payment"),),
            target_split_derivation=target("checkout", ("payment",), ("payment",)),
            reattachment_contracts=(reattachment_empty("payment"),),
        )

        report = review_hierarchical_mesh(partition)

        self.assertTrue(report.ok)
        self.assertEqual("mesh_green_can_continue", report.decision)

    def test_mesh_closure_complete_model_can_continue(self):
        report = review_mesh_closure_model(
            closure_model(),
            (
                child("payment", outputs_emitted=("payment_result",)),
                child("inventory", outputs_emitted=("inventory_result",)),
            ),
        )

        self.assertTrue(report.ok)
        self.assertEqual("mesh_closure_green", report.decision)
        self.assertIn("order_ready", report.reachable_tokens)

    def test_mesh_closure_requires_root_entry(self):
        report = review_mesh_closure_model(
            closure_model(root_entries=()),
            (child("payment", outputs_emitted=("payment_result",)),),
        )

        self.assertFalse(report.ok)
        self.assertEqual("missing_root_entry", report.decision)
        self.assertIn("missing_root_entry", [finding.code for finding in report.findings])

    def test_repeat_input_loop_requires_repair_feedback(self):
        report = review_mesh_closure_model(
            closure_model(
                root_entries=("rejected_packet",),
                transitions=(
                    MeshClosureTransition(
                        "retry_same_packet",
                        consumes=("rejected_packet",),
                        emits=("rejected_packet", "blocked"),
                        loop=True,
                        repeat_input_tokens=("rejected_packet",),
                        blocker_tokens=("blocked",),
                        max_iterations=1,
                    ),
                ),
                joins=(),
                terminals=(MeshClosureTerminal("blocked", consumes=("blocked",)),),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual("loop_repair_feedback_required", report.decision)
        self.assertIn("loop_repair_feedback_required", [finding.code for finding in report.findings])

    def test_repeat_input_loop_requires_structured_no_delta_disposition(self):
        report = review_mesh_closure_model(
            closure_model(
                root_entries=("rejected_packet",),
                transitions=(
                    MeshClosureTransition(
                        "retry_same_packet",
                        consumes=("rejected_packet",),
                        emits=("rejected_packet", "repair_feedback"),
                        loop=True,
                        progress_rule="agent should change the packet",
                        repeat_input_tokens=("rejected_packet",),
                        repair_feedback_tokens=("repair_feedback",),
                    ),
                ),
                joins=(),
                terminals=(MeshClosureTerminal("retry_terminal", consumes=("repair_feedback",)),),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual("loop_no_delta_disposition_required", report.decision)
        self.assertIn("loop_no_delta_disposition_required", [finding.code for finding in report.findings])

    def test_guarded_repeat_input_loop_can_close(self):
        report = review_mesh_closure_model(
            closure_model(
                root_entries=("rejected_packet",),
                transitions=(
                    MeshClosureTransition(
                        "retry_same_packet",
                        consumes=("rejected_packet",),
                        emits=("repair_feedback", "blocked"),
                        loop=True,
                        repeat_input_tokens=("rejected_packet",),
                        repair_feedback_tokens=("repair_feedback",),
                        blocker_tokens=("blocked",),
                    ),
                ),
                joins=(),
                terminals=(MeshClosureTerminal("blocked", consumes=("blocked",)),),
            )
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual("mesh_closure_green", report.decision)

    def test_mesh_closure_rejects_unconsumed_child_output(self):
        report = review_mesh_closure_model(
            closure_model(
                transitions=(
                    MeshClosureTransition(
                        "start_payment",
                        consumes=("root_start",),
                        emits=("payment_result",),
                        consumer_model_id="payment",
                    ),
                ),
                joins=(),
                terminals=(
                    MeshClosureTerminal("payment_done", consumes=("payment_result",)),
                ),
            ),
            (
                child("payment", outputs_emitted=("payment_result",)),
                child("fraud", outputs_emitted=("manual_review_needed",)),
            ),
        )

        self.assertFalse(report.ok)
        self.assertIn("unconsumed_child_output", [finding.code for finding in report.findings])

    def test_mesh_closure_rejects_unknown_output_reference(self):
        report = review_mesh_closure_model(
            closure_model(
                transitions=(
                    MeshClosureTransition(
                        "foreign_consume",
                        consumes=("foreign_output",),
                        emits=("payment_result",),
                    ),
                ),
                joins=(),
                terminals=(MeshClosureTerminal("payment_done", consumes=("payment_result",)),),
            ),
            (child("payment", outputs_emitted=("payment_result",)),),
        )

        self.assertFalse(report.ok)
        self.assertIn("unknown_closure_reference", [finding.code for finding in report.findings])

    def test_mesh_closure_rejects_incomplete_join(self):
        report = review_mesh_closure_model(
            closure_model(
                joins=(
                    MeshClosureJoin(
                        "checkout_ready",
                        required_inputs=("payment_result", "inventory_result", "tax_result"),
                        emits=("order_ready",),
                    ),
                ),
            ),
            (
                child("payment", outputs_emitted=("payment_result",)),
                child("inventory", outputs_emitted=("inventory_result",)),
            ),
        )

        self.assertFalse(report.ok)
        self.assertIn("missing_join_point", [finding.code for finding in report.findings])

    def test_mesh_closure_requires_out_of_scope_rationale(self):
        report = review_mesh_closure_model(
            closure_model(
                transitions=(
                    MeshClosureTransition("start_payment", consumes=("root_start",), emits=("payment_result",)),
                ),
                joins=(),
                terminals=(
                    MeshClosureTerminal(
                        "ignore_payment",
                        consumes=("payment_result",),
                        terminal_kind="out_of_scope",
                    ),
                ),
            ),
            (child("payment", outputs_emitted=("payment_result",)),),
        )

        self.assertFalse(report.ok)
        self.assertIn("out_of_scope_rationale_required", [finding.code for finding in report.findings])

    def test_mesh_closure_rejects_terminal_leak(self):
        report = review_mesh_closure_model(
            closure_model(
                transitions=(
                    MeshClosureTransition("start_payment", consumes=("root_start",), emits=("payment_result",)),
                    MeshClosureTransition("start_inventory", consumes=("root_start",), emits=("inventory_result",)),
                ),
                joins=(),
                terminals=(
                    MeshClosureTerminal("premature_done", consumes=("payment_result",)),
                ),
            ),
            (
                child("payment", outputs_emitted=("payment_result",)),
                child("inventory", outputs_emitted=("inventory_result",)),
            ),
        )

        self.assertFalse(report.ok)
        self.assertIn("terminal_leak", [finding.code for finding in report.findings])

    def test_mesh_closure_rejects_loop_without_progress(self):
        report = review_mesh_closure_model(
            closure_model(
                transitions=(
                    MeshClosureTransition(
                        "retry_payment",
                        consumes=("payment_result",),
                        emits=("payment_result",),
                        consumer_model_id="payment",
                        loop=True,
                    ),
                ),
                joins=(),
                terminals=(MeshClosureTerminal("payment_done", consumes=("payment_result",)),),
            ),
            (child("payment", outputs_emitted=("payment_result",)),),
        )

        self.assertFalse(report.ok)
        self.assertIn("loop_progress_required", [finding.code for finding in report.findings])

    def test_mesh_closure_allows_bounded_loop(self):
        report = review_mesh_closure_model(
            closure_model(
                transitions=(
                    MeshClosureTransition(
                        "retry_payment",
                        consumes=("root_start",),
                        emits=("payment_result",),
                        consumer_model_id="payment",
                        loop=True,
                        max_iterations=3,
                    ),
                ),
                joins=(),
                terminals=(MeshClosureTerminal("payment_done", consumes=("payment_result",)),),
            ),
            (child("payment", outputs_emitted=("payment_result",)),),
        )

        self.assertTrue(report.ok)

    def test_parent_mesh_consumes_closure_model_before_green(self):
        partition = HierarchyPartitionMap(
            parent_model_id="checkout",
            coverage_items=(
                HierarchyCoverageItem("payment", owner_model_id="payment"),
                HierarchyCoverageItem("inventory", owner_model_id="inventory"),
            ),
            child_models=(
                child("payment", outputs_emitted=("payment_result",)),
                child("inventory", outputs_emitted=("inventory_result",)),
            ),
            target_split_derivation=target(
                "checkout",
                ("payment", "inventory"),
                ("payment", "inventory"),
            ),
            closure_model=closure_model(
                transitions=(
                    MeshClosureTransition(
                        "start_payment",
                        consumes=("root_start",),
                        emits=("payment_result",),
                    ),
                ),
                joins=(),
                terminals=(MeshClosureTerminal("payment_done", consumes=("payment_result",)),),
            ),
        )

        report = review_hierarchical_mesh(partition)

        self.assertFalse(report.ok)
        self.assertEqual("unconsumed_child_output", report.decision)
        self.assertIsNotNone(report.closure_report)
        self.assertIn("closure_report", report.to_dict())

    def test_parent_mesh_green_when_closure_model_passes(self):
        partition = HierarchyPartitionMap(
            parent_model_id="checkout",
            coverage_items=(
                HierarchyCoverageItem("payment", owner_model_id="payment"),
                HierarchyCoverageItem("inventory", owner_model_id="inventory"),
            ),
            child_models=(
                child("payment", outputs_emitted=("payment_result",)),
                child("inventory", outputs_emitted=("inventory_result",)),
            ),
            target_split_derivation=target(
                "checkout",
                ("payment", "inventory"),
                ("payment", "inventory"),
            ),
            closure_model=closure_model(),
        )

        report = review_hierarchical_mesh(partition)

        self.assertTrue(report.ok)
        self.assertEqual("mesh_green_can_continue", report.decision)
        self.assertEqual("mesh_closure_green", report.closure_report.decision)

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

    def test_model_count_does_not_activate_mesh_but_large_model_does(self):
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
        self.assertNotIn("model_count", report.activation_reasons)
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
            closure_model=reattachment_closure("child_done"),
        )

        report = review_hierarchical_mesh(partition)

        self.assertTrue(report.ok)
        self.assertEqual("mesh_green_can_continue", report.decision)


    def test_child_reattachment_rejects_input_and_output_drift(self):
        partition = HierarchyPartitionMap(
            parent_model_id="checkout",
            coverage_items=(HierarchyCoverageItem("payment", owner_model_id="payment"),),
            child_models=(
                child(
                    "payment",

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


    def test_boundary_diff_non_intersecting_sibling_stays_fresh(self):
        previous = child("payment",  state_owned=("payment_state",))
        current = child("payment",  state_owned=("payment_state",))
        inventory = child("inventory",  state_owned=("inventory_state",))
        summary = summarize_child_boundary_change(previous, current, sibling_models=(inventory,))
        partition = HierarchyPartitionMap(
            parent_model_id="checkout",
            coverage_items=(
                HierarchyCoverageItem("payment", owner_model_id="payment"),
                HierarchyCoverageItem("inventory", owner_model_id="inventory"),
            ),
            child_models=(current, inventory),
            target_split_derivation=target(
                "checkout",
                ("payment", "inventory"),
                ("payment", "inventory"),
                state=True,
            ),
            reattachment_contracts=(
                reattachment_empty("payment",  expected_state_owned=("payment_state",)),
            ),
            boundary_changes=(summary,),
            closure_model=reattachment_closure(),
        )

        report = review_hierarchical_mesh(partition)

        self.assertTrue(report.ok)
        self.assertEqual("unaffected", summary.propagation)
        self.assertEqual("mesh_green_can_continue", report.decision)


    def test_boundary_diff_parent_rerun_required_on_handoff_drift(self):
        previous = child(
            "payment",

            inputs_accepted=("parent_input",),
            outputs_emitted=("child_done",),
        )
        current = child(
            "payment",

            inputs_accepted=("parent_input", "manual_retry"),
            outputs_emitted=("child_done",),
        )
        summary = summarize_child_boundary_change(
            previous,
            current,
            parent_contract=reattachment(
                "payment",

                expected_inputs=("parent_input",),
                expected_outputs=("child_done",),
                expected_state_owned=(),
                expected_side_effects_owned=(),
                expected_contracts_out=(),
            ),
        )
        partition = HierarchyPartitionMap(
            parent_model_id="checkout",
            coverage_items=(HierarchyCoverageItem("payment", owner_model_id="payment"),),
            child_models=(current,),
            target_split_derivation=target("checkout", ("payment",), ("payment",)),
            reattachment_contracts=(
                reattachment_empty(
                    "payment",

                    expected_inputs=("parent_input", "manual_retry"),
                    expected_outputs=("child_done",),
                ),
            ),
            boundary_changes=(summary,),
        )

        report = review_hierarchical_mesh(partition)

        self.assertFalse(report.ok)
        self.assertEqual("parent_rerun_required", summary.propagation)
        self.assertEqual("parent_rerun_required", report.decision)
        self.assertIn("boundary_change_parent_rerun_required", [finding.code for finding in report.findings])

    def test_boundary_diff_sibling_rerun_required_on_shared_state(self):
        previous = child("payment",  state_owned=("payment_state",))
        current = child("payment",  state_owned=("order_state",))
        fulfillment = child("fulfillment",  depends_on=("order_state",))
        summary = summarize_child_boundary_change(previous, current, sibling_models=(fulfillment,))
        partition = HierarchyPartitionMap(
            parent_model_id="checkout",
            coverage_items=(
                HierarchyCoverageItem("payment", owner_model_id="payment"),
                HierarchyCoverageItem("fulfillment", owner_model_id="fulfillment"),
            ),
            child_models=(current, fulfillment),
            target_split_derivation=target(
                "checkout",
                ("payment", "fulfillment"),
                ("payment", "fulfillment"),
                state=True,
            ),
            reattachment_contracts=(
                reattachment_empty("payment",  expected_state_owned=("order_state",)),
            ),
            boundary_changes=(summary,),
        )

        report = review_hierarchical_mesh(partition)

        self.assertFalse(report.ok)
        self.assertEqual("sibling_rerun_required", summary.propagation)
        self.assertEqual("sibling_rerun_required", report.decision)
        self.assertIn("boundary_change_sibling_rerun_required", [finding.code for finding in report.findings])

    def test_boundary_diff_rejects_observed_bug_as_only_model_target(self):
        previous = child("dedupe",  risk_boundary="duplicate-job-risk")
        current = child("dedupe",  risk_boundary="BUG-123")
        summary = summarize_child_boundary_change(previous, current, current_bug_id="BUG-123")
        partition = HierarchyPartitionMap(
            parent_model_id="job-flow",
            coverage_items=(HierarchyCoverageItem("dedupe", owner_model_id="dedupe"),),
            child_models=(current,),
            target_split_derivation=target("job-flow", ("dedupe",), ("dedupe",)),
            reattachment_contracts=(reattachment_empty("dedupe"),),
            boundary_changes=(summary,),
        )

        report = review_hierarchical_mesh(partition)
        codes = [finding.code for finding in report.findings]

        self.assertFalse(report.ok)
        self.assertTrue(summary.current_bug_is_only_model_target)
        self.assertEqual("parent_rerun_required", report.decision)
        self.assertIn("missing_bug_class_responsibility", codes)
        self.assertIn("point_fix_only_model_target", codes)

    def test_boundary_diff_routes_large_child_to_split_review(self):
        previous = child("audit",  observed_state_count=900)
        current = child("audit",  observed_state_count=10_001, risk_boundary="audit lifecycle")
        summary = summarize_child_boundary_change(previous, current)
        partition = HierarchyPartitionMap(
            parent_model_id="release",
            coverage_items=(HierarchyCoverageItem("audit", owner_model_id="audit"),),
            child_models=(current,),
            target_split_derivation=target("release", ("audit",), ("audit",)),
            reattachment_contracts=(reattachment_empty("audit"),),
            boundary_changes=(summary,),
        )

        report = review_hierarchical_mesh(partition)

        self.assertFalse(report.ok)
        self.assertEqual("split_review_required", summary.propagation)
        self.assertEqual("split_review_required", report.decision)
        self.assertIn("boundary_change_split_review_required", [finding.code for finding in report.findings])


def test_non_boundary_count_change_is_unaffected():
    previous = child("audit", observed_state_count=900)
    current = child("audit", observed_state_count=10_001)
    summary = summarize_child_boundary_change(previous, current)
    assert summary.changed_fields == ()
    assert summary.propagation == "unaffected"


def test_mesh_child_ids_must_be_registered_models(tmp_path, monkeypatch):
    from dataclasses import replace
    from flowguard.hierarchy import child_evidence_from_model

    models = tmp_path / '.flowguard/models'
    models.mkdir(parents=True)
    (tmp_path / 'counter.py').write_text('class Counter:\n    def tick(self):\n        self.value += 1\n    def reset(self):\n        self.other = 0\n')
    literals = '''COMPONENTS = ["counter"]
IMPLEMENTED_BY = {"Tick": "counter.py:Counter.tick"}
TESTED_BY = {"non_negative": ["tests/test_counter.py:test_tick"]}
def build_explorer(): raise AssertionError("static lookup must not execute models")
raise AssertionError("static lookup must not import models")
'''
    (models / 'parent.py').write_text('import child_a\nMODEL_ID = "parent"\n' + literals)
    (models / 'child_a.py').write_text('MODEL_ID = "child_a"\n' + literals)
    child_b = models / 'child_b.py'
    child_b.write_text('MODEL_ID = "child_b"\nPARENT = "parent"\n' +
                       literals.replace('Counter.tick', 'Counter.reset').replace('non_negative', 'reset_rule'))
    runner = tmp_path / '.flowguard/verification/owners/runner/run_checks.py'
    runner.parent.mkdir(parents=True)
    runner.write_text('raise AssertionError("runner must not execute")\n')
    data = dict(schema='flowguard.map.v1', components=[dict(id='counter', files=['counter.py'],
        tests=[], models=['.flowguard/verification/owners/runner/run_checks.py'], depends_on=[],
        status='draft', summary='Counter', responsibilities=['count'])])
    map_path = tmp_path / '.flowguard/map.json'
    map_path.write_text(json.dumps(data))
    a = child_evidence_from_model('.flowguard/models/child_a.py', root=tmp_path)
    b = child_evidence_from_model(child_b, root=tmp_path)
    assert a.model_id == 'child_a' and a.parent_model_id == 'parent' and a.owner_id == 'counter'
    assert a.functions_owned == ('counter.py:Counter.tick',)
    assert a.invariants_owned == ('non_negative',) and a.state_owned == ('Counter.value',)
    assert a.inputs_accepted == a.outputs_emitted == a.side_effects_owned == ()
    bare = child_evidence_from_model(models / 'child_a.py')
    assert bare.parent_model_id == bare.owner_id == '' and bare.state_owned == ()
    partition = HierarchyPartitionMap('parent', child_models=(a, b),
        target_split_derivation=target('parent', ('child_a', 'child_b'), (), state=True))
    report = review_hierarchical_mesh(partition, root=tmp_path)
    assert report.ok, report.format_text()
    typo = review_hierarchical_mesh(replace(partition, child_models=(replace(a, model_id='child_aa'),)), root=tmp_path)
    assert typo.decision == 'model_ids_unresolved'
    assert any(f.code == 'unknown_child_model' and 'child_a' in f.message for f in typo.findings)
    for invalid_parent in ('counter', 'system', 'runner'):
        unknown = review_hierarchical_mesh(replace(partition, parent_model_id=invalid_parent), root=tmp_path)
        assert unknown.decision == 'model_ids_unresolved'
        assert any(f.code == 'unknown_parent_model' for f in unknown.findings)
    child_b.write_text(child_b.read_text().replace('PARENT = "parent"', 'PARENT = "counter"'))
    moved = review_hierarchical_mesh(partition, root=tmp_path)
    assert any(f.code == 'child_not_under_parent' and "parent 'counter'" in f.message for f in moved.findings)
    # An equal parent string naming a component is still not a model-parent edge.
    data['components'].append(dict(id='parent', files=[], tests=[], models=[], depends_on=[],
        status='draft', summary='Other component', responsibilities=['other']))
    map_path.write_text(json.dumps(data))
    child_b.write_text(child_b.read_text().replace('PARENT = "counter"', 'PARENT = "parent"'))
    assert any(f.code == 'child_not_under_parent' for f in review_hierarchical_mesh(partition, root=tmp_path).findings)
    monkeypatch.chdir(tmp_path)
    pure = replace(partition, parent_model_id='not_registered')
    assert review_hierarchical_mesh(pure).ok


def test_single_child_mesh_needs_no_closure_model():
    from dataclasses import replace

    producer = child('producer', outputs_emitted=('handoff',), inputs_accepted=('handoff',))
    partition = HierarchyPartitionMap('parent', child_models=(producer,),
        target_split_derivation=target('parent', ('producer',), ()))
    assert review_hierarchical_mesh(partition).ok
    independent = child('independent', inputs_accepted=('other',))
    pair = replace(partition, child_models=(producer, independent),
        target_split_derivation=target('parent', ('producer', 'independent'), ()))
    assert review_hierarchical_mesh(pair).ok
    handoff = replace(pair, child_models=(producer, replace(independent, inputs_accepted=('handoff',))))
    report = review_hierarchical_mesh(handoff)
    assert not report.ok and report.decision == 'mesh_closure_required'
    # An explicit closure is always checked, even when no inter-child handoff requires one.
    invalid = replace(partition, closure_model=MeshClosureModel('parent', root_entries=('start',)))
    assert not review_hierarchical_mesh(invalid).ok


def test_reattach_only_change_needs_a_reattachment_contract():
    from dataclasses import replace
    from flowguard import ChildBoundaryChangeSummary

    previous = child("payment", outputs_emitted=("old_done",))
    current = child("payment", outputs_emitted=("new_done",))
    assert summarize_child_boundary_change(previous, current).propagation == "parent_rerun_required"
    change = ChildBoundaryChangeSummary("payment", propagation="reattach_only",
        changed_fields=("outputs_emitted",), added_by_field={"outputs_emitted": ("new_done",)},
        removed_by_field={"outputs_emitted": ("old_done",)})
    partition = HierarchyPartitionMap("checkout", child_models=(current,),
        target_split_derivation=target("checkout", ("payment",), ()), boundary_changes=(change,),
        closure_model=MeshClosureModel("checkout", root_entries=("start",),
            transitions=(MeshClosureTransition("payment_done", consumes=("start",),
                emits=("new_done",), consumer_model_id="payment"),),
            terminals=(MeshClosureTerminal("done", consumes=("new_done",)),)))
    missing = review_hierarchical_mesh(partition)
    assert "boundary_change_reattachment_required" in {f.code for f in missing.findings}
    contract = ChildReattachmentContract("payment", expected_outputs=("new_done",))
    attached = review_hierarchical_mesh(replace(partition, reattachment_contracts=(contract,)))
    assert attached.ok, attached.format_text()
    drift = review_hierarchical_mesh(replace(partition,
        reattachment_contracts=(replace(contract, expected_outputs=("old_done",)),)))
    assert "child_reattachment_missing_output" in {f.code for f in drift.findings}


def test_model_mesh_renamed_output_gives_child_reattachment_missing_output():
    from flowguard import (ChildModelEvidence, ChildReattachmentContract, HierarchyCoverageItem,
                           HierarchyPartitionMap, ModelTargetSplitDerivation, review_hierarchical_mesh)

    def partition(outputs):
        return HierarchyPartitionMap(
            parent_model_id="checkout",
            coverage_items=(HierarchyCoverageItem("payment", owner_model_id="payment"),),
            child_models=(ChildModelEvidence(
                "payment", functional_areas=("payment",),
                 inputs_accepted=("parent_input",), outputs_emitted=outputs),),
            target_split_derivation=ModelTargetSplitDerivation(
                "checkout", target_child_model_ids=("payment",), covered_partition_item_ids=("payment",),
                rationale="derived from parent model blocks"),
            reattachment_contracts=(ChildReattachmentContract(
                "payment",  expected_inputs=("parent_input",),
                expected_outputs=("payment:settled",), rationale="parent consumes the settled event"),),
        )

    renamed = review_hierarchical_mesh(partition(("payment:captured",)))
    assert not renamed.ok
    assert "child_reattachment_missing_output" in {f.code for f in renamed.findings}
    same = review_hierarchical_mesh(partition(("payment:settled",)))
    assert "child_reattachment_missing_output" not in {f.code for f in same.findings}


if __name__ == "__main__":
    unittest.main()
