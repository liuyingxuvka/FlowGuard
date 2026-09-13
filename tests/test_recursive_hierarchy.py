import unittest
from dataclasses import replace
import hashlib
import json

from flowguard.recursive_hierarchy import (
    RecursiveHierarchyPlan,
    RecursiveModelNode,
    VerifiedSubtreeReceipt,
    build_recursive_leaf_product_signature,
    descendant_universe_fingerprint,
    review_recursive_hierarchy,
)
from flowguard.native_case_protocol import (
    GOOD_DIMENSIONS,
    NativeModelCaseContract,
    NativeModelCaseResult,
)


CURRENT_HEAD = "sha256:" + "a" * 64
CURRENT_TOOLCHAIN = "sha256:" + "b" * 64
CURRENT_ENVIRONMENT = "sha256:" + "c" * 64


def node(model_id, parent_model_id="", children=()):
    data = dict(
        model_id=model_id,
        owner_id=f"owner:{model_id}",
        parent_model_id=parent_model_id,
        model_fingerprint=f"model:{model_id}",
        obligation_ids=(f"obligation:{model_id}",),
        child_model_ids=children,
        claim_scope="full",
        subtree_receipt_id=f"subtree:{model_id}",
        structural_parent_id=parent_model_id,
        direct_child_ids=children,
        partition_fingerprint=f"partition:{model_id}",
        model_authority_head_fingerprint=CURRENT_HEAD,
        toolchain_fingerprint=CURRENT_TOOLCHAIN,
        environment_fingerprint=CURRENT_ENVIRONMENT,
    )
    if not children:
        input_cases = (f"{model_id}:input:empty", f"{model_id}:input:valid")
        state_cases = ("idle", "active")
        signature = build_recursive_leaf_product_signature(
            model_id, "input", input_cases, "state", state_cases
        )
        data.update(
            leaf_product_signature=signature.fingerprint,
            leaf_input_axis_id="input",
            leaf_state_axis_id="state",
            leaf_input_cases=input_cases,
            leaf_state_cases=state_cases,
            leaf_axis_fingerprints=dict(signature.axis_fingerprints),
            leaf_canonical_product=tuple(
                f"{input_case}:{state_case}"
                for input_case in input_cases
                for state_case in state_cases
            ),
            leaf_contract_product_signature=signature,
        )
    return RecursiveModelNode(**data)


def receipt(
    model_id,
    parent_model_id,
    children=(),
    descendants=(),
    receipt_id=None,
    child_receipt_ids=None,
    partition_fingerprint=None,
    model_authority_head_fingerprint=CURRENT_HEAD,
    toolchain_fingerprint=CURRENT_TOOLCHAIN,
    environment_fingerprint=CURRENT_ENVIRONMENT,
    child_receipt_fingerprints=None,
):
    receipt_id = receipt_id or f"subtree:{model_id}"
    child_receipt_ids = (
        tuple(f"subtree:{child}" for child in children)
        if child_receipt_ids is None
        else tuple(child_receipt_ids)
    )
    data = dict(
        receipt_id=receipt_id,
        model_id=model_id,
        owner_id=f"owner:{model_id}",
        parent_model_id=parent_model_id,
        claim_scope="full",
        model_fingerprint=f"model:{model_id}",
        obligation_ids=(f"obligation:{model_id}",),
        child_receipt_ids=child_receipt_ids,
        child_receipt_fingerprints=dict(child_receipt_fingerprints or {}),
        descendant_model_ids=tuple(descendants) or (model_id,),
        structural_parent_id=parent_model_id,
        direct_child_ids=children,
        partition_fingerprint=partition_fingerprint or f"partition:{model_id}",
        descendant_universe_fingerprint=descendant_universe_fingerprint(
            tuple(descendants) or (model_id,)
        ),
        model_authority_head_fingerprint=model_authority_head_fingerprint,
        toolchain_fingerprint=toolchain_fingerprint,
        environment_fingerprint=environment_fingerprint,
    )
    if not children:
        input_cases = (f"{model_id}:input:empty", f"{model_id}:input:valid")
        state_cases = ("idle", "active")
        signature = build_recursive_leaf_product_signature(
            model_id, "input", input_cases, "state", state_cases
        )
        data.update(
            leaf_product_signature=signature.fingerprint,
            leaf_input_axis_id="input",
            leaf_state_axis_id="state",
            leaf_input_cases=input_cases,
            leaf_state_cases=state_cases,
            leaf_axis_fingerprints=dict(signature.axis_fingerprints),
            leaf_canonical_product=tuple(
                f"{input_case}:{state_case}"
                for input_case in input_cases
                for state_case in state_cases
            ),
            leaf_contract_product_signature=signature,
        )
    return VerifiedSubtreeReceipt(**data)


def bind_child_receipt_fingerprints(receipts):
    """Wire exact child receipt content into every parent fixture receipt."""

    values = list(receipts)
    by_id = {item.receipt_id: item for item in values}
    # Children must be finalized before their parents because a parent binds
    # the child's final content fingerprint, not a pre-binding placeholder.
    order = sorted(
        range(len(values)),
        key=lambda index: len(values[index].descendant_model_ids),
    )
    for index in order:
        item = values[index]
        if not item.child_receipt_ids:
            continue
        child_fingerprints = {
            child_id: by_id[child_id].fingerprint
            for child_id in item.child_receipt_ids
            if child_id in by_id
        }
        values[index] = replace(
            item,
            child_receipt_fingerprints=child_fingerprints,
            # The child binding is part of the receipt identity.  Recompute
            # the immutable receipt fingerprint after wiring the map instead
            # of retaining the pre-binding fingerprint.
            fingerprint="",
        )
        by_id[item.receipt_id] = values[index]
    return tuple(values)


def five_level_plan(receipts=None, **overrides):
    nodes = (
        node("root", children=("domain",)),
        node("domain", "root", ("subsystem",)),
        node("subsystem", "domain", ("component",)),
        node("component", "subsystem", ("leaf",)),
        node("leaf", "component"),
    )
    # Fill the node-side universe only after the complete structure exists;
    # this prevents a fixture from accidentally becoming the source of the
    # descendant denominator.
    node_descendants = {
        "leaf": ("leaf",),
        "component": ("component", "leaf"),
        "subsystem": ("component", "leaf", "subsystem"),
        "domain": ("component", "domain", "leaf", "subsystem"),
        "root": ("component", "domain", "leaf", "root", "subsystem"),
    }
    nodes = tuple(
        replace(
            item,
            descendant_universe_fingerprint=descendant_universe_fingerprint(
                node_descendants[item.model_id]
            ),
        )
        for item in nodes
    )
    default_receipts = (
        receipt("leaf", "component"),
        receipt("component", "subsystem", ("leaf",), ("component", "leaf")),
        receipt("subsystem", "domain", ("component",), ("component", "leaf", "subsystem")),
        receipt("domain", "root", ("subsystem",), ("component", "domain", "leaf", "subsystem")),
        receipt("root", "", ("domain",), ("component", "domain", "leaf", "root", "subsystem")),
    )
    default_receipts = bind_child_receipt_fingerprints(default_receipts)
    data = {
        "hierarchy_id": "five-level",
        "root_model_id": "root",
        "nodes": nodes,
        "receipts": default_receipts if receipts is None else receipts,
        "claim_scope": "full",
        "model_authority_head_fingerprint": CURRENT_HEAD,
        "toolchain_fingerprint": CURRENT_TOOLCHAIN,
        "environment_fingerprint": CURRENT_ENVIRONMENT,
    }
    data.update(overrides)
    return RecursiveHierarchyPlan(**data)


class RecursiveHierarchyTests(unittest.TestCase):
    def _native_rows(self, plan, root):
        """Build producer-shaped rows for every node in the five-level tree."""

        def fp(value):
            return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()

        contracts = []
        results = []
        for node_item in plan.nodes:
            case_id = f"native:{node_item.model_id}:good"
            contracts.append(
                NativeModelCaseContract(
                    owner_id=node_item.owner_id,
                    source_case_id=case_id,
                    case_kind="good",
                    callable_ref=f"model.{node_item.model_id}.run",
                    result_selector=f"result.{case_id}",
                    expected_status="pass",
                    covered_dimensions=GOOD_DIMENSIONS,
                    oracle_member_ids=tuple(
                        f"oracle:{dimension}" for dimension in GOOD_DIMENSIONS
                    ),
                    evidence_scope="implementation_boundary",
                    input_contract_fingerprint=fp(f"input:{node_item.model_id}"),
                    oracle_content_fingerprint=fp(f"oracle:{node_item.model_id}"),
                )
            )
            raw_path = root / f"{node_item.model_id}.raw.json"
            raw_path.write_text(
                json.dumps(
                    {"owner": node_item.owner_id, "case": case_id},
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            raw_fingerprint = "sha256:" + hashlib.sha256(
                raw_path.read_bytes()
            ).hexdigest()
            results.append(
                NativeModelCaseResult(
                    owner_id=node_item.owner_id,
                    source_case_id=case_id,
                    outcome="pass",
                    observed_status="pass",
                    executed_dimensions=GOOD_DIMENSIONS,
                    oracle_results=tuple(
                        {
                            "dimension": dimension,
                            "oracle_member_id": f"oracle:{dimension}",
                            "status": "pass",
                            "ok": True,
                        }
                        for dimension in GOOD_DIMENSIONS
                    ),
                    result_artifact_fingerprint=raw_fingerprint,
                    input_fingerprint=fp(f"input:{node_item.model_id}"),
                    model_fingerprint=fp(f"model:{node_item.model_id}"),
                    code_fingerprint=fp(f"code:{node_item.model_id}"),
                    test_fingerprint=fp(f"test:{node_item.model_id}"),
                    oracle_fingerprint=fp(f"oracle:{node_item.model_id}"),
                    toolchain_fingerprint=fp("toolchain:current"),
                    environment_fingerprint=fp("environment:current"),
                    raw_artifact_path=str(raw_path),
                )
            )
        return tuple(contracts), tuple(results)

    def test_native_five_level_execution_promotes_only_exact_rows(self):
        from tempfile import TemporaryDirectory

        plan = five_level_plan()
        with TemporaryDirectory() as temporary:
            contracts, results = self._native_rows(plan, __import__("pathlib").Path(temporary))
            report = review_recursive_hierarchy(
                plan,
                native_case_contracts=contracts,
                native_case_results=results,
                raw_artifact_root=temporary,
                require_native_execution=True,
            )

        self.assertTrue(report.ok, report.format_text())
        self.assertTrue(report.execution_verified_receipt_ids)
        self.assertEqual(
            set(report.verified_receipt_ids),
            set(report.execution_verified_receipt_ids),
        )
        self.assertEqual(5, len(report.execution_verified_receipt_ids))
        self.assertTrue(report.execution_verified)
        self.assertTrue(report.to_dict()["execution_verified"])

    def test_native_missing_leaf_cell_blocks_ancestor_promotion(self):
        from tempfile import TemporaryDirectory

        plan = five_level_plan()
        with TemporaryDirectory() as temporary:
            root = __import__("pathlib").Path(temporary)
            contracts, results = self._native_rows(plan, root)
            missing = tuple(
                result
                for result in results
                if result.owner_id != "owner:leaf"
            )
            report = review_recursive_hierarchy(
                plan,
                native_case_contracts=contracts,
                native_case_results=missing,
                raw_artifact_root=root,
                require_native_execution=True,
            )

        self.assertFalse(report.ok, report.format_text())
        self.assertIn(
            "native_case_execution_blocked",
            {finding.code for finding in report.findings},
        )
        self.assertFalse(report.execution_verified)
        self.assertFalse(report.to_dict()["execution_verified"])
        self.assertNotIn("subtree:leaf", report.execution_verified_receipt_ids)
        self.assertNotIn("subtree:root", report.execution_verified_receipt_ids)

    def test_five_levels_close_bottom_up(self):
        report = review_recursive_hierarchy(five_level_plan())

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(4, report.max_depth)
        self.assertEqual(("leaf",), report.leaf_model_ids)
        self.assertEqual("subtree:root", report.terminal_receipt_id)
        self.assertEqual(5, len(report.verified_receipt_ids))
        self.assertFalse(report.execution_verified)
        self.assertFalse(report.to_dict()["execution_verified"])

    def test_non_leaf_without_receipt_is_blocked(self):
        receipts = tuple(
            receipt_item
            for receipt_item in five_level_plan().receipts
            if receipt_item.model_id != "component"
        )
        report = review_recursive_hierarchy(five_level_plan(receipts))

        self.assertFalse(report.ok)
        self.assertIn("subtree_receipt_missing", {finding.code for finding in report.findings})

    def test_receipt_from_wrong_parent_or_owner_is_blocked(self):
        receipts = list(five_level_plan().receipts)
        index = next(index for index, item in enumerate(receipts) if item.model_id == "component")
        receipts[index] = replace(
            receipts[index],
            parent_model_id="wrong-parent",
            structural_parent_id="wrong-parent",
        )
        report = review_recursive_hierarchy(five_level_plan(tuple(receipts)))

        self.assertFalse(report.ok)
        codes = {finding.code for finding in report.findings}
        self.assertIn("subtree_receipt_structural_parent_id_mismatch", codes)
        self.assertIn("subtree_receipt_not_verified", codes)

    def test_stale_receipt_cannot_be_reused(self):
        receipts = list(five_level_plan().receipts)
        index = next(index for index, item in enumerate(receipts) if item.model_id == "leaf")
        receipts[index] = replace(receipts[index], current=False, fingerprint=receipts[index].fingerprint)
        report = review_recursive_hierarchy(five_level_plan(tuple(receipts)))

        self.assertFalse(report.ok)
        self.assertIn("subtree_receipt_not_verified", {finding.code for finding in report.findings})

    def test_strict_recursive_leaf_denominator_is_kernel_derived(self):
        current = five_level_plan()
        leaf_index = next(
            index for index, item in enumerate(current.nodes) if item.model_id == "leaf"
        )
        leaf = current.nodes[leaf_index]
        receipt_index = next(
            index for index, item in enumerate(current.receipts) if item.model_id == "leaf"
        )
        receipt_item = current.receipts[receipt_index]
        smaller_denominator = (leaf.leaf_canonical_product[0],)
        nodes = list(current.nodes)
        nodes[leaf_index] = replace(leaf, leaf_canonical_product=smaller_denominator)
        receipts = list(current.receipts)
        receipts[receipt_index] = replace(
            receipt_item, leaf_canonical_product=smaller_denominator
        )

        report = review_recursive_hierarchy(
            replace(current, nodes=tuple(nodes), receipts=tuple(receipts))
        )

        self.assertFalse(report.ok, report.format_text())
        codes = {finding.code for finding in report.findings}
        self.assertIn("leaf_denominator_mismatch", codes)
        self.assertIn("subtree_receipt_not_verified", codes)

    def test_strict_recursive_leaf_requires_typed_product_and_axes(self):
        current = five_level_plan()
        leaf_index = next(
            index for index, item in enumerate(current.nodes) if item.model_id == "leaf"
        )
        receipt_index = next(
            index for index, item in enumerate(current.receipts) if item.model_id == "leaf"
        )
        nodes = list(current.nodes)
        nodes[leaf_index] = replace(
            nodes[leaf_index],
            leaf_input_cases=(),
            leaf_state_cases=(),
            leaf_axis_fingerprints={},
            leaf_canonical_product=(),
            leaf_product_signature="",
            leaf_contract_product_signature=None,
        )
        receipts = list(current.receipts)
        receipts[receipt_index] = replace(
            receipts[receipt_index],
            leaf_input_cases=(),
            leaf_state_cases=(),
            leaf_axis_fingerprints={},
            leaf_canonical_product=(),
            leaf_product_signature="",
            leaf_contract_product_signature=None,
        )

        report = review_recursive_hierarchy(
            replace(current, nodes=tuple(nodes), receipts=tuple(receipts))
        )

        self.assertFalse(report.ok, report.format_text())
        codes = {finding.code for finding in report.findings}
        self.assertIn("leaf_input_axis_missing", codes)
        self.assertIn("leaf_state_axis_missing", codes)
        self.assertIn("leaf_denominator_missing", codes)

    def test_broad_recursive_claim_cannot_be_downgraded_with_strict_false(self):
        current = five_level_plan(strict=False)
        leaf_index = next(
            index for index, item in enumerate(current.nodes) if item.model_id == "leaf"
        )
        nodes = list(current.nodes)
        nodes[leaf_index] = replace(
            nodes[leaf_index],
            leaf_input_cases=(),
            leaf_state_cases=(),
            leaf_axis_fingerprints={},
            leaf_canonical_product=(),
            leaf_product_signature="",
            leaf_contract_product_signature=None,
        )

        report = review_recursive_hierarchy(replace(current, nodes=tuple(nodes)))

        self.assertFalse(report.ok, report.format_text())
        self.assertIn(
            "leaf_denominator_missing",
            {finding.code for finding in report.findings},
        )

    def test_cycle_is_blocked(self):
        cyclic = (
            node("root", children=("child",)),
            node("child", "root", ("root",)),
        )
        report = review_recursive_hierarchy(
            RecursiveHierarchyPlan(
                "cycle",
                "root",
                nodes=cyclic,
                claim_scope="routine",
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("hierarchy_cycle", {finding.code for finding in report.findings})

    def test_routine_structure_can_be_reviewed_without_terminal_receipts(self):
        report = review_recursive_hierarchy(
            RecursiveHierarchyPlan(
                "routine",
                "root",
                nodes=(node("root", children=("leaf",)), node("leaf", "root")),
                claim_scope="routine",
            )
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(1, report.max_depth)

    def test_parent_consumes_child_declared_custom_receipt_id(self):
        nodes = (
            node("root", children=("child",)),
            node("child", "root"),
        )
        nodes = (
            replace(
                nodes[0],
                subtree_receipt_id="root-proof",
                descendant_universe_fingerprint=descendant_universe_fingerprint(
                    ("child", "root")
                ),
            ),
            replace(
                nodes[1],
                subtree_receipt_id="child-proof",
                descendant_universe_fingerprint=descendant_universe_fingerprint(
                    ("child",)
                ),
            ),
        )
        plan = RecursiveHierarchyPlan(
            "custom-receipt-ids",
            "root",
            nodes=nodes,
            receipts=bind_child_receipt_fingerprints((
                receipt("child", "root", receipt_id="child-proof"),
                receipt(
                    "root",
                    "",
                    children=("child",),
                    child_receipt_ids=("child-proof",),
                    descendants=("child", "root"),
                    receipt_id="root-proof",
                ),
            )),
            claim_scope="full",
            model_authority_head_fingerprint=CURRENT_HEAD,
            toolchain_fingerprint=CURRENT_TOOLCHAIN,
            environment_fingerprint=CURRENT_ENVIRONMENT,
        )

        report = review_recursive_hierarchy(plan)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual("root-proof", report.terminal_receipt_id)

    def test_parent_binds_each_child_receipt_fingerprint(self):
        current = five_level_plan()
        root_index = next(
            index for index, item in enumerate(current.receipts) if item.model_id == "root"
        )
        root = current.receipts[root_index]
        changed = dict(root.child_receipt_fingerprints)
        changed["subtree:domain"] = "sha256:" + "d" * 64
        receipts = list(current.receipts)
        receipts[root_index] = replace(
            root,
            child_receipt_fingerprints=changed,
        )

        report = review_recursive_hierarchy(
            replace(current, receipts=tuple(receipts))
        )

        self.assertFalse(report.ok, report.format_text())
        codes = {finding.code for finding in report.findings}
        self.assertIn(
            "subtree_receipt_child_receipt_fingerprints_mismatch",
            codes,
        )
        self.assertNotIn("subtree:root", report.verified_receipt_ids)

    def test_parent_is_not_verified_when_direct_child_is_not_verified(self):
        current = five_level_plan()
        component_index = next(
            index for index, item in enumerate(current.receipts) if item.model_id == "component"
        )
        component = current.receipts[component_index]
        receipts = list(current.receipts)
        # Keep the receipt's canonical fingerprint self-consistent while making
        # the direct leaf receipt stale.  This models a parent that has a
        # locally passing child receipt but an unverified descendant.
        leaf_index = next(
            index for index, item in enumerate(receipts) if item.model_id == "leaf"
        )
        receipts[leaf_index] = replace(receipts[leaf_index], current=False)
        receipts[component_index] = replace(
            component,
            child_receipt_fingerprints={
                "subtree:leaf": receipts[leaf_index].fingerprint,
            },
        )
        # Parent receipts must bind the final child content after the stale
        # mutation; the reviewer should still refuse the stale branch and all
        # of its ancestors.
        receipts = bind_child_receipt_fingerprints(receipts)

        report = review_recursive_hierarchy(
            replace(current, receipts=receipts)
        )

        self.assertFalse(report.ok, report.format_text())
        codes = {finding.code for finding in report.findings}
        self.assertIn("subtree_receipt_child_not_verified", codes)
        self.assertNotIn("subtree:component", report.verified_receipt_ids)
        self.assertNotIn("subtree:root", report.verified_receipt_ids)

    def test_current_wire_requires_child_receipt_fingerprint_mapping(self):
        payload = five_level_plan().receipts[-1].to_dict()
        payload.pop("child_receipt_fingerprints")
        with self.assertRaises(ValueError):
            VerifiedSubtreeReceipt.from_dict(payload)

    def test_authority_fields_are_in_canonical_identity_and_round_trip(self):
        plan = five_level_plan()
        root = plan.nodes[0]
        root_payload = root.to_dict()
        receipt_payload = plan.receipts[-1].to_dict()

        for field_name in (
            "structural_parent_id",
            "direct_child_ids",
            "partition_fingerprint",
            "descendant_universe_fingerprint",
            "model_authority_head_fingerprint",
            "toolchain_fingerprint",
            "environment_fingerprint",
        ):
            self.assertIn(field_name, root_payload)
            self.assertIn(field_name, receipt_payload)

        self.assertEqual(root, RecursiveModelNode.from_dict(root_payload))
        self.assertEqual(
            plan.receipts[-1],
            VerifiedSubtreeReceipt.from_dict(receipt_payload),
        )
        round_tripped_plan = RecursiveHierarchyPlan.from_dict(plan.to_dict())
        self.assertEqual(plan.to_dict(), round_tripped_plan.to_dict())

    def test_missing_authority_binding_blocks_recursive_parent(self):
        receipts = list(five_level_plan().receipts)
        index = next(index for index, item in enumerate(receipts) if item.model_id == "component")
        receipts[index] = replace(receipts[index], partition_fingerprint="")
        report = review_recursive_hierarchy(five_level_plan(tuple(receipts)))

        self.assertFalse(report.ok)
        codes = {finding.code for finding in report.findings}
        self.assertIn("subtree_receipt_not_verified", codes)
        self.assertIn("subtree_receipt_partition_fingerprint_mismatch", codes)

    def test_postorder_rejects_caller_supplied_descendant_universe(self):
        receipts = list(five_level_plan().receipts)
        index = next(index for index, item in enumerate(receipts) if item.model_id == "domain")
        receipts[index] = replace(
            receipts[index],
            descendant_model_ids=("domain",),
            descendant_universe_fingerprint=descendant_universe_fingerprint(("domain",)),
        )
        report = review_recursive_hierarchy(five_level_plan(tuple(receipts)))

        self.assertFalse(report.ok)
        self.assertIn(
            "subtree_receipt_descendant_model_ids_mismatch",
            {finding.code for finding in report.findings},
        )

    def test_root_receipt_must_match_current_authority_head(self):
        receipts = list(five_level_plan().receipts)
        index = next(index for index, item in enumerate(receipts) if item.model_id == "root")
        receipts[index] = replace(
            receipts[index],
            model_authority_head_fingerprint="sha256:" + "d" * 64,
        )
        report = review_recursive_hierarchy(five_level_plan(tuple(receipts)))

        self.assertFalse(report.ok)
        codes = {finding.code for finding in report.findings}
        self.assertIn("subtree_receipt_not_verified", codes)
        self.assertIn("subtree_receipt_model_authority_head_fingerprint_mismatch", codes)

    def test_unrelated_authority_pointer_advance_keeps_functional_subtrees_current(self):
        current = five_level_plan()
        advanced = replace(
            current,
            model_authority_head_fingerprint="sha256:" + "e" * 64,
            metadata={
                "authority_pointer_mode": "functional_reuse",
                "authority_pointer_changed_model_ids": ("unrelated-model",),
            },
        )
        report = review_recursive_hierarchy(advanced)

        self.assertTrue(report.ok, report.to_dict())
        self.assertIn(
            "node_model_authority_pointer_advanced",
            {finding.code for finding in report.findings},
        )

    def test_affected_authority_pointer_advance_still_blocks_old_subtree(self):
        current = five_level_plan()
        advanced = replace(
            current,
            model_authority_head_fingerprint="sha256:" + "e" * 64,
            metadata={
                "authority_pointer_mode": "functional_reuse",
                "authority_pointer_changed_model_ids": ("root",),
            },
        )
        report = review_recursive_hierarchy(advanced)

        self.assertFalse(report.ok)
        self.assertIn(
            "node_model_authority_head_mismatch",
            {finding.code for finding in report.findings},
        )

    def test_duplicate_owner_and_foreign_child_are_blockers(self):
        nodes = (
            node("root", children=("child", "foreign")),
            node("child", "root"),
            replace(node("other", "root"), owner_id="owner:child"),
        )
        report = review_recursive_hierarchy(
            RecursiveHierarchyPlan(
                "authority-negatives",
                "root",
                nodes=nodes,
                claim_scope="routine",
            )
        )

        self.assertFalse(report.ok)
        codes = {finding.code for finding in report.findings}
        self.assertIn("child_model_foreign", codes)
        self.assertIn("duplicate_owner", codes)

    def test_current_wire_loader_rejects_legacy_parent_child_spellings(self):
        payload = five_level_plan().receipts[-1].to_dict()
        payload["parent_model_id"] = payload["structural_parent_id"]
        with self.assertRaises(ValueError):
            VerifiedSubtreeReceipt.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
