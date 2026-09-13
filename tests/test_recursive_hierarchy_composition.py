"""Fixed multi-level hierarchy and cross-boundary composition fixtures.

The fixture is deliberately small but non-linear: it contains two structural
branches, a sibling interaction, and a two-member feedback SCC.  It exercises
the three independent closure surfaces without turning the whole tree into a
single Cartesian product.
"""

import unittest
from dataclasses import replace

from flowguard.blueprint_topology import (
    BlueprintTopologyNode,
    BlueprintTopologyPort,
    BlueprintTopologyPortMapping,
    BlueprintTopologyProgressContract,
    BlueprintTopologyRelation,
    TOPOLOGY_ROOT_SENTINEL,
    review_blueprint_topology,
)
from flowguard.hierarchy import (
    ChildModelEvidence,
    MeshClosureJoin,
    MeshClosureModel,
    MeshClosureTerminal,
    MeshClosureTransition,
    review_mesh_closure_model,
)
from flowguard.recursive_hierarchy import (
    RecursiveHierarchyPlan,
    RecursiveModelNode,
    VerifiedSubtreeReceipt,
    build_recursive_leaf_product_signature,
    descendant_universe_fingerprint,
    review_recursive_hierarchy,
)


CURRENT_HEAD = "sha256:" + "a" * 64
CURRENT_TOOLCHAIN = "sha256:" + "b" * 64
CURRENT_ENVIRONMENT = "sha256:" + "c" * 64


def _leaf_fields(model_id: str) -> dict[str, object]:
    input_cases = (f"{model_id}:input:empty", f"{model_id}:input:valid")
    state_cases = ("idle", "active")
    signature = build_recursive_leaf_product_signature(
        model_id,
        "input",
        input_cases,
        "state",
        state_cases,
    )
    return {
        "leaf_product_signature": signature.fingerprint,
        "leaf_input_axis_id": "input",
        "leaf_state_axis_id": "state",
        "leaf_input_cases": input_cases,
        "leaf_state_cases": state_cases,
        "leaf_axis_fingerprints": dict(signature.axis_fingerprints),
        "leaf_canonical_product": tuple(
            f"{input_case}:{state_case}"
            for input_case in input_cases
            for state_case in state_cases
        ),
        "leaf_contract_product_signature": signature,
    }


def _node(
    model_id: str,
    parent_model_id: str,
    children: tuple[str, ...],
    descendants: tuple[str, ...],
) -> RecursiveModelNode:
    values: dict[str, object] = {
        "model_id": model_id,
        "owner_id": f"owner:{model_id}",
        "parent_model_id": parent_model_id,
        "model_fingerprint": f"model:{model_id}",
        "obligation_ids": (f"obligation:{model_id}",),
        "child_model_ids": children,
        "claim_scope": "full",
        "subtree_receipt_id": f"subtree:{model_id}",
        "structural_parent_id": parent_model_id,
        "direct_child_ids": children,
        "partition_fingerprint": f"partition:{model_id}",
        "descendant_universe_fingerprint": descendant_universe_fingerprint(descendants),
        "model_authority_head_fingerprint": CURRENT_HEAD,
        "toolchain_fingerprint": CURRENT_TOOLCHAIN,
        "environment_fingerprint": CURRENT_ENVIRONMENT,
    }
    if not children:
        values.update(_leaf_fields(model_id))
    return RecursiveModelNode(**values)


def _receipt(
    model_id: str,
    parent_model_id: str,
    children: tuple[str, ...],
    descendants: tuple[str, ...],
) -> VerifiedSubtreeReceipt:
    values: dict[str, object] = {
        "receipt_id": f"subtree:{model_id}",
        "model_id": model_id,
        "owner_id": f"owner:{model_id}",
        "parent_model_id": parent_model_id,
        "claim_scope": "full",
        "model_fingerprint": f"model:{model_id}",
        "obligation_ids": (f"obligation:{model_id}",),
        "child_receipt_ids": tuple(f"subtree:{child}" for child in children),
        "child_receipt_fingerprints": {},
        "descendant_model_ids": descendants,
        "structural_parent_id": parent_model_id,
        "direct_child_ids": children,
        "partition_fingerprint": f"partition:{model_id}",
        "descendant_universe_fingerprint": descendant_universe_fingerprint(descendants),
        "model_authority_head_fingerprint": CURRENT_HEAD,
        "toolchain_fingerprint": CURRENT_TOOLCHAIN,
        "environment_fingerprint": CURRENT_ENVIRONMENT,
    }
    if not children:
        values.update(_leaf_fields(model_id))
    return VerifiedSubtreeReceipt(**values)


def _bind_receipts(receipts: tuple[VerifiedSubtreeReceipt, ...]) -> tuple[VerifiedSubtreeReceipt, ...]:
    """Bind direct-child receipt fingerprints from leaves toward the root."""

    values = list(receipts)
    by_id = {item.receipt_id: item for item in values}
    for index in sorted(
        range(len(values)),
        key=lambda item: len(values[item].descendant_model_ids),
    ):
        item = values[index]
        if not item.child_receipt_ids:
            continue
        values[index] = replace(
            item,
            child_receipt_fingerprints={
                child_id: by_id[child_id].fingerprint
                for child_id in item.child_receipt_ids
            },
            # The child map is part of the immutable receipt identity.
            fingerprint="",
        )
        by_id[item.receipt_id] = values[index]
    return tuple(values)


def branched_hierarchy_plan() -> RecursiveHierarchyPlan:
    """Return the fixed four-level branch fixture used by composition tests."""

    structure = {
        "root": ("", ("domain_a", "domain_b")),
        "domain_a": ("root", ("subsystem_a1", "subsystem_a2")),
        "subsystem_a1": ("domain_a", ("component_a1", "component_a2")),
        "component_a1": ("subsystem_a1", ("leaf_a",)),
        "component_a2": ("subsystem_a1", ("leaf_b",)),
        "subsystem_a2": ("domain_a", ("leaf_c",)),
        "domain_b": ("root", ("subsystem_b1",)),
        "subsystem_b1": ("domain_b", ("component_b1",)),
        "component_b1": ("subsystem_b1", ("leaf_d",)),
        "leaf_a": ("component_a1", ()),
        "leaf_b": ("component_a2", ()),
        "leaf_c": ("subsystem_a2", ()),
        "leaf_d": ("component_b1", ()),
    }

    def descendants(model_id: str) -> tuple[str, ...]:
        parent, children = structure[model_id]
        del parent
        return tuple(
            sorted(
                {
                    model_id,
                    *(descendant for child in children for descendant in descendants(child)),
                }
            )
        )

    nodes = tuple(
        _node(model_id, parent, children, descendants(model_id))
        for model_id, (parent, children) in structure.items()
    )
    receipts = _bind_receipts(
        tuple(
            _receipt(model_id, parent, children, descendants(model_id))
            for model_id, (parent, children) in structure.items()
        )
    )
    return RecursiveHierarchyPlan(
        "branched-four-level",
        "root",
        nodes=nodes,
        receipts=receipts,
        claim_scope="full",
        model_authority_head_fingerprint=CURRENT_HEAD,
        toolchain_fingerprint=CURRENT_TOOLCHAIN,
        environment_fingerprint=CURRENT_ENVIRONMENT,
    )


def _child(model_id: str, output: str) -> ChildModelEvidence:
    return ChildModelEvidence(
        model_id=model_id,
        model_fingerprint=f"model:{model_id}",
        outputs_emitted=(output,),
        evidence_tier="abstract_green",
        functional_areas=(model_id,),
    )


def cross_sibling_closure() -> tuple[MeshClosureModel, tuple[ChildModelEvidence, ...]]:
    children = (
        _child("leaf_a", "leaf_a.ready"),
        _child("leaf_b", "leaf_b.ready"),
        _child("leaf_c", "leaf_c.ready"),
        _child("leaf_d", "leaf_d.ready"),
    )
    transitions = (
        MeshClosureTransition(
            "start-leaf-a",
            consumes=("root.start",),
            emits=("leaf_a.ready",),
            consumer_model_id="leaf_a",
        ),
        MeshClosureTransition(
            "start-leaf-b",
            consumes=("root.start",),
            emits=("leaf_b.ready",),
            consumer_model_id="leaf_b",
        ),
        MeshClosureTransition(
            "start-leaf-c",
            consumes=("root.start",),
            emits=("leaf_c.ready",),
            consumer_model_id="leaf_c",
        ),
        MeshClosureTransition(
            "start-leaf-d",
            consumes=("root.start",),
            emits=("leaf_d.ready",),
            consumer_model_id="leaf_d",
        ),
        MeshClosureTransition(
            "cross-sibling-retry-a",
            consumes=("siblings.ready",),
            emits=("retry.pending", "retry.repair_a", "retry.feedback_a"),
            consumer_model_id="root",
            loop=True,
            progress_rule="the retry packet changes before it can circulate again",
            repeat_input_tokens=("siblings.ready",),
            progress_tokens=("retry.repair_a",),
            repair_feedback_tokens=("retry.feedback_a",),
        ),
        MeshClosureTransition(
            "cross-sibling-retry-b",
            consumes=("retry.pending",),
            emits=("retry.pending", "retry.repair_b", "retry.feedback_b"),
            consumer_model_id="root",
            loop=True,
            progress_rule="the second SCC member applies the next bounded repair",
            repeat_input_tokens=("retry.pending",),
            progress_tokens=("retry.repair_b",),
            repair_feedback_tokens=("retry.feedback_b",),
        ),
    )
    return (
        MeshClosureModel(
            parent_model_id="root",
            root_entries=("root.start",),
            transitions=transitions,
            joins=(
                MeshClosureJoin(
                    "all-siblings-ready",
                    required_inputs=(
                        "leaf_a.ready",
                        "leaf_b.ready",
                        "leaf_c.ready",
                        "leaf_d.ready",
                    ),
                    emits=("siblings.ready",),
                ),
            ),
            terminals=(
                MeshClosureTerminal(
                    "cross-sibling-complete",
                    consumes=(
                        "retry.pending",
                        "retry.repair_a",
                        "retry.feedback_a",
                        "retry.repair_b",
                        "retry.feedback_b",
                    ),
                    terminal_kind="normal_exit",
                ),
            ),
            required_outputs=(
                "retry.pending",
                "retry.repair_a",
                "retry.feedback_a",
                "retry.repair_b",
                "retry.feedback_b",
            ),
            rationale="all leaf branches join before the bounded two-member feedback SCC",
        ),
        children,
    )


def _topology_port(port_id: str, schema: str) -> BlueprintTopologyPort:
    return BlueprintTopologyPort(
        port_id=port_id,
        schema_id=f"schema:{port_id}",
        schema_fingerprint=schema,
    )


def feedback_scc_topology(*, progress: bool = True, stale: bool = False):
    """Construct a structural tree with a non-structural two-node feedback SCC."""

    relation_evidence = "sha256:" + "d" * 64
    progress_evidence = "sha256:" + "e" * 64
    nodes = (
        BlueprintTopologyNode(
            node_id="root",
            disposition="connected",
            structural_role="root",
            purpose="own the cross-sibling root",
            structural_parent_id=TOPOLOGY_ROOT_SENTINEL,
            input_ports=(
                _topology_port("root.input.a", relation_evidence),
                _topology_port("root.input.b", relation_evidence),
            ),
        ),
        BlueprintTopologyNode(
            node_id="sibling_a",
            disposition="connected",
            structural_role="child",
            purpose="first sibling in the feedback SCC",
            structural_parent_id="root",
            cross_boundary_parent_ids=("sibling_b",),
            input_ports=(_topology_port("sibling_a.input", relation_evidence),),
            output_ports=(
                _topology_port("sibling_a.output", relation_evidence),
                _topology_port("sibling_a.attach", relation_evidence),
            ),
        ),
        BlueprintTopologyNode(
            node_id="sibling_b",
            disposition="connected",
            structural_role="child",
            purpose="second sibling in the feedback SCC",
            structural_parent_id="root",
            cross_boundary_parent_ids=("sibling_a",),
            input_ports=(_topology_port("sibling_b.input", relation_evidence),),
            output_ports=(
                _topology_port("sibling_b.output", relation_evidence),
                _topology_port("sibling_b.attach", relation_evidence),
            ),
        ),
    )
    progress_contract = (
        BlueprintTopologyProgressContract(
            contract_id="progress:cross-sibling",
            contract_kind="finite_bound",
            evidence_fingerprint=progress_evidence,
            finite_bound=3,
            rationale="the SCC has at most three repair iterations",
        )
        if progress
        else None
    )
    feedback_relations = (
        BlueprintTopologyRelation(
            relation_id="feedback:a-to-b",
            producer_id="sibling_a",
            consumer_id="sibling_b",
            relation_kind="feedback",
            interface_mappings=(
                BlueprintTopologyPortMapping("sibling_a.output", "sibling_b.input"),
            ),
            evidence_fingerprint=relation_evidence,
            rationale="sibling A hands a repair packet to sibling B",
            progress_contract=progress_contract,
        ),
        BlueprintTopologyRelation(
            relation_id="feedback:b-to-a",
            producer_id="sibling_b",
            consumer_id="sibling_a",
            relation_kind="feedback",
            interface_mappings=(
                BlueprintTopologyPortMapping("sibling_b.output", "sibling_a.input"),
            ),
            evidence_fingerprint=relation_evidence,
            rationale="sibling B returns a bounded repair packet to sibling A",
            progress_contract=progress_contract,
        ),
    )
    structural_relations = (
        BlueprintTopologyRelation(
            relation_id="structure:a-to-root",
            producer_id="sibling_a",
            consumer_id="root",
            relation_kind="delegates_to",
            interface_mappings=(
                BlueprintTopologyPortMapping("sibling_a.attach", "root.input.a"),
            ),
            evidence_fingerprint=relation_evidence,
            rationale="sibling A has one structural parent",
        ),
        BlueprintTopologyRelation(
            relation_id="structure:b-to-root",
            producer_id="sibling_b",
            consumer_id="root",
            relation_kind="delegates_to",
            interface_mappings=(
                BlueprintTopologyPortMapping("sibling_b.attach", "root.input.b"),
            ),
            evidence_fingerprint=relation_evidence,
            rationale="sibling B has one structural parent",
        ),
    )
    relations = (*feedback_relations, *structural_relations)
    report = review_blueprint_topology(
        topology_id="topology:branched-feedback-scc",
        nodes=nodes,
        relations=relations,
        required_owner_ids=(),
        required_surface_ids_by_owner={},
        child_models=(),
        reattachment_contracts=(),
        current_evidence_fingerprints={},
        declared_evidence_fingerprints_by_owner={},
        current_relation_evidence_fingerprints={
            relation.relation_id: relation_evidence for relation in relations
        },
        current_refinement_fingerprints={},
        current_progress_evidence_fingerprints=(
            {"progress:cross-sibling": progress_evidence}
            if not stale
            else {"progress:cross-sibling": "sha256:" + "f" * 64}
        ),
    )
    return report


def _structural_chain(depth: int) -> RecursiveHierarchyPlan:
    """Build a read-only structural chain without native receipts."""

    nodes = tuple(
        RecursiveModelNode(
            model_id=f"chain:{index}",
            structural_parent_id=(f"chain:{index - 1}" if index else ""),
            direct_child_ids=(f"chain:{index + 1}",) if index < depth else (),
            child_model_ids=(f"chain:{index + 1}",) if index < depth else (),
        )
        for index in range(depth + 1)
    )
    return RecursiveHierarchyPlan(
        hierarchy_id=f"structural-chain-{depth}",
        root_model_id="chain:0",
        nodes=nodes,
        receipts=(),
        claim_scope="focused",
        strict=False,
    )


class RecursiveHierarchyCompositionTests(unittest.TestCase):
    def test_structural_chain_supports_arbitrary_finite_depth_without_recursion(self):
        for depth in (8, 12, 1500):
            report = review_recursive_hierarchy(_structural_chain(depth))

            self.assertTrue(report.ok, (depth, report.format_text()))
            self.assertEqual(depth, report.max_depth)
            self.assertEqual((f"chain:{depth}",), report.leaf_model_ids)

    def test_deep_branch_receipts_close_bottom_up_without_global_product(self):
        report = review_recursive_hierarchy(branched_hierarchy_plan())

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(4, report.max_depth)
        self.assertEqual(("leaf_a", "leaf_b", "leaf_c", "leaf_d"), report.leaf_model_ids)
        self.assertEqual(13, len(report.verified_receipt_ids))

    def test_cross_sibling_join_and_feedback_scc_close_independently(self):
        closure, children = cross_sibling_closure()
        report = review_mesh_closure_model(closure, children)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual("mesh_closure_green", report.decision)
        self.assertIn("siblings.ready", report.reachable_tokens)
        self.assertIn("retry.feedback_b", report.reachable_tokens)

        topology = feedback_scc_topology()
        self.assertTrue(topology.ok, topology.to_dict())
        self.assertFalse(
            any(item.code == "topology_structural_cycle" for item in topology.findings)
        )

    def test_missing_sibling_join_member_blocks_cross_child_closure(self):
        closure, children = cross_sibling_closure()
        bad = replace(
            closure,
            joins=(
                replace(
                    closure.joins[0],
                    required_inputs=tuple(
                        item
                        for item in closure.joins[0].required_inputs
                        if item != "leaf_d.ready"
                    ),
                ),
            ),
            # The fourth child output remains required, but the malformed
            # join no longer consumes it as part of the cross-sibling gate.
            terminals=(
                replace(
                    closure.terminals[0],
                    consumes=tuple(
                        item
                        for item in closure.terminals[0].consumes
                        if item != "retry.pending"
                    ),
                ),
            ),
        )
        report = review_mesh_closure_model(bad, children)

        self.assertFalse(report.ok, report.format_text())
        codes = {item.code for item in report.findings}
        self.assertIn("unconsumed_child_output", codes)

    def test_feedback_scc_requires_current_independent_progress(self):
        missing = feedback_scc_topology(progress=False)
        self.assertFalse(missing.ok, missing.to_dict())
        self.assertIn(
            "topology_feedback_progress_missing",
            {item.code for item in missing.findings},
        )

        stale = feedback_scc_topology(stale=True)
        self.assertFalse(stale.ok, stale.to_dict())
        self.assertIn(
            "topology_feedback_progress_stale",
            {item.code for item in stale.findings},
        )

    def test_stale_deep_child_does_not_promote_any_ancestor(self):
        current = branched_hierarchy_plan()
        stale_index = next(
            index for index, item in enumerate(current.receipts) if item.model_id == "leaf_c"
        )
        receipts = list(current.receipts)
        receipts[stale_index] = replace(receipts[stale_index], current=False)
        report = review_recursive_hierarchy(replace(current, receipts=tuple(receipts)))

        self.assertFalse(report.ok, report.format_text())
        self.assertNotIn("subtree:leaf_c", report.verified_receipt_ids)
        self.assertNotIn("subtree:subsystem_a2", report.verified_receipt_ids)
        self.assertNotIn("subtree:domain_a", report.verified_receipt_ids)
        self.assertNotIn("subtree:root", report.verified_receipt_ids)
        self.assertIn(
            "subtree_receipt_child_not_verified",
            {item.code for item in report.findings},
        )

    def test_blocked_child_node_does_not_promote_a_locally_passing_receipt(self):
        current = branched_hierarchy_plan()
        node_index = next(
            index for index, item in enumerate(current.nodes) if item.model_id == "leaf_c"
        )
        nodes = list(current.nodes)
        nodes[node_index] = replace(
            nodes[node_index],
            model_fingerprint="model:leaf_c-tampered",
        )
        report = review_recursive_hierarchy(replace(current, nodes=tuple(nodes)))

        self.assertFalse(report.ok, report.format_text())
        self.assertIn(
            "subtree_receipt_model_fingerprint_mismatch",
            {item.code for item in report.findings},
        )
        self.assertNotIn("subtree:leaf_c", report.verified_receipt_ids)
        self.assertNotIn("subtree:subsystem_a2", report.verified_receipt_ids)
        self.assertNotIn("subtree:domain_a", report.verified_receipt_ids)
        self.assertNotIn("subtree:root", report.verified_receipt_ids)


if __name__ == "__main__":
    unittest.main()
