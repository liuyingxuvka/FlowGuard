from flowguard.blueprint_topology import (
    BlueprintTopologyNode,
    BlueprintTopologyRelation,
    review_blueprint_topology,
)


def _relation(**updates):
    values = {
        "relation_id": "relation:child-parent",
        "producer_id": "model:child",
        "consumer_id": "model:parent",
        "relation_kind": "child_to_parent",
        "interface_mappings": (("output:result", "input:result"),),
        "evidence_fingerprint": "fp:relation",
        "rationale": "the parent consumes the child's declared result",
    }
    values.update(updates)
    return BlueprintTopologyRelation(**values)


def _review(*, nodes=None, relations=None):
    return review_blueprint_topology(
        topology_id="topology:fixture",
        nodes=(
            nodes
            if nodes is not None
            else (
            BlueprintTopologyNode(
                "model:child", "connected", "produce the result", ("surface:child",)
            ),
            BlueprintTopologyNode("model:parent", "connected", "consume the result"),
            )
        ),
        relations=relations if relations is not None else (_relation(),),
        required_owner_ids=("model:child",),
        required_surface_ids_by_owner={"model:child": ("surface:child",)},
    )


def test_exact_parent_child_output_input_mapping_closes_topology():
    report = _review()

    assert report.ok
    assert report.relations[0].interface_mappings == (
        ("output:result", "input:result"),
    )


def test_missing_endpoint_and_surface_mismatch_are_visible():
    report = _review(
        nodes=(
            BlueprintTopologyNode(
                "model:child", "connected", "produce the result", ("surface:wrong",)
            ),
        ),
        relations=(_relation(),),
    )

    assert {finding.code for finding in report.findings} >= {
        "topology_endpoint_missing",
        "topology_surface_binding_mismatch",
    }


def test_disconnected_non_leaf_owner_cannot_claim_topology_closure():
    report = _review(
        nodes=(
            BlueprintTopologyNode(
                "model:child", "connected", "produce the result", ("surface:child",)
            ),
        ),
        relations=(),
    )

    assert "topology_owner_disconnected" in {
        finding.code for finding in report.findings
    }
