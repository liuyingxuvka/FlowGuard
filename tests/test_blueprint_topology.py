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
from flowguard.hierarchy import ChildModelEvidence, ChildReattachmentContract


SCHEMA_REQUEST = "sha256:schema-request"
SCHEMA_RESULT = "sha256:schema-result"
RELATION_EVIDENCE = "sha256:relation-evidence"
PROGRESS_EVIDENCE = "sha256:progress-evidence"
CHILD_EVIDENCE = "sha256:child-evidence-v1"
VALIDATION_EVIDENCE = "sha256:child-validation-v1"
RUNTIME_EVIDENCE = "sha256:child-runtime-v1"


def _port(port_id: str, schema_fingerprint: str) -> BlueprintTopologyPort:
    return BlueprintTopologyPort(
        port_id=port_id,
        schema_id=f"schema:{port_id}",
        schema_fingerprint=schema_fingerprint,
    )


def _child_node(*, extra_output: bool = False) -> BlueprintTopologyNode:
    outputs = [_port("output:result", SCHEMA_RESULT)]
    if extra_output:
        outputs.append(_port("output:audit", SCHEMA_RESULT))
    return BlueprintTopologyNode(
        node_id="model:child",
        disposition="connected",
        structural_role="child",
        purpose="produce the result",
        structural_parent_id="model:parent",
        implementation_surface_ids=("surface:child",),
        input_ports=(_port("input:request", SCHEMA_REQUEST),),
        output_ports=tuple(outputs),
        state_owned=("child_state",),
        side_effects_owned=("child_effect",),
    )


def _parent_node(node_id: str = "model:parent") -> BlueprintTopologyNode:
    is_root = node_id == "model:parent"
    return BlueprintTopologyNode(
        node_id=node_id,
        disposition="connected",
        structural_role="root" if is_root else "child",
        purpose="consume the result",
        structural_parent_id=(
            TOPOLOGY_ROOT_SENTINEL if is_root else "model:parent"
        ),
        implementation_surface_ids=(),
        input_ports=(_port("input:result", SCHEMA_RESULT),),
        output_ports=(),
    )


def _secondary_parent_relation(node_id: str) -> BlueprintTopologyRelation:
    return BlueprintTopologyRelation(
        relation_id=f"relation:{node_id}-parent",
        producer_id=node_id,
        consumer_id="model:parent",
        relation_kind="delegates_to",
        interface_mappings=(
            BlueprintTopologyPortMapping(
                f"output:attach:{node_id}",
                f"input:attach:{node_id}",
            ),
        ),
        evidence_fingerprint=RELATION_EVIDENCE,
        rationale="secondary topology fixture attaches to the sole root",
    )


def _attached_secondary_parent(node_id: str):
    secondary = replace(
        _parent_node(node_id),
        output_ports=(_port(f"output:attach:{node_id}", SCHEMA_RESULT),),
    )
    root = replace(
        _parent_node(),
        input_ports=(
            *_parent_node().input_ports,
            _port(f"input:attach:{node_id}", SCHEMA_RESULT),
        ),
    )
    return secondary, root, _secondary_parent_relation(node_id)


def _child_evidence(*, extra_output: bool = False, evidence_id: str = "child:v1"):
    outputs = ["output:result"]
    if extra_output:
        outputs.append("output:audit")
    return ChildModelEvidence(
        model_id="model:child",
        evidence_id=evidence_id,
        inputs_accepted=("input:request",),
        outputs_emitted=tuple(outputs),
        state_owned=("child_state",),
        side_effects_owned=("child_effect",),
        contracts_out=("child.guarantee",),
        validation_evidence=("validation:child:v1",),
        runtime_path_evidence_ids=("runtime:child:v1",),
    )


def _reattachment(*, consumed_evidence_id: str = "child:v1"):
    return ChildReattachmentContract(
        child_model_id="model:child",
        consumed_evidence_id=consumed_evidence_id,
        consumed_runtime_path_evidence_ids=("runtime:child:v1",),
        expected_inputs=("input:request",),
        expected_outputs=("output:result",),
        expected_state_owned=("child_state",),
        expected_side_effects_owned=("child_effect",),
        expected_contracts_out=("child.guarantee",),
        rationale="the parent consumes the exact current child contract",
    )


def _relation(**updates):
    values = {
        "relation_id": "relation:child-parent",
        "producer_id": "model:child",
        "consumer_id": "model:parent",
        "relation_kind": "child_to_parent",
        "interface_mappings": (
            BlueprintTopologyPortMapping("output:result", "input:result"),
        ),
        "evidence_fingerprint": RELATION_EVIDENCE,
        "consumed_child_evidence_id": "child:v1",
        "consumed_runtime_path_evidence_ids": ("runtime:child:v1",),
        "rationale": "the parent consumes the child's declared result",
    }
    values.update(updates)
    return BlueprintTopologyRelation(**values)


def _review(
    *,
    nodes=None,
    relations=None,
    child_models=None,
    reattachments=None,
    current_relation_evidence=None,
    current_evidence=None,
    declared_evidence_by_owner=None,
    current_refinements=None,
    current_progress=None,
    required_owner_ids=("model:child", "model:parent"),
    required_surface_ids_by_owner=None,
):
    return review_blueprint_topology(
        topology_id="topology:fixture",
        nodes=nodes if nodes is not None else (_child_node(), _parent_node()),
        relations=relations if relations is not None else (_relation(),),
        required_owner_ids=required_owner_ids,
        required_surface_ids_by_owner=(
            required_surface_ids_by_owner
            if required_surface_ids_by_owner is not None
            else {"model:child": ("surface:child",), "model:parent": ()}
        ),
        child_models=child_models if child_models is not None else (_child_evidence(),),
        reattachment_contracts=(
            reattachments if reattachments is not None else (_reattachment(),)
        ),
        current_evidence_fingerprints=(
            current_evidence
            if current_evidence is not None
            else {
                "child:v1": CHILD_EVIDENCE,
                "validation:child:v1": VALIDATION_EVIDENCE,
                "runtime:child:v1": RUNTIME_EVIDENCE,
            }
        ),
        declared_evidence_fingerprints_by_owner=(
            declared_evidence_by_owner
            if declared_evidence_by_owner is not None
            else {
                "model:child": {
                    "child:v1": CHILD_EVIDENCE,
                    "validation:child:v1": VALIDATION_EVIDENCE,
                    "runtime:child:v1": RUNTIME_EVIDENCE,
                }
            }
        ),
        current_relation_evidence_fingerprints=(
            current_relation_evidence
            if current_relation_evidence is not None
            else {"relation:child-parent": RELATION_EVIDENCE}
        ),
        current_refinement_fingerprints=current_refinements or {},
        current_progress_evidence_fingerprints=current_progress or {},
    )


def _codes(report):
    return {finding.code for finding in report.findings}


def test_exact_typed_parent_child_mapping_and_reattachment_close_topology():
    report = _review()

    assert report.ok, report.to_dict()
    assert report.relations[0].interface_mappings[0].producer_output_id == "output:result"
    assert report.relations[0].consumed_child_evidence_id == "child:v1"


def test_node_serialization_carries_separate_structural_and_cross_boundary_parents():
    node = replace(
        _child_node(),
        cross_boundary_parent_ids=("model:shared", "model:ancestor"),
    )

    payload = node.to_dict()

    assert payload["structural_parent_id"] == "model:parent"
    assert payload["cross_boundary_parent_ids"] == [
        "model:ancestor",
        "model:shared",
    ]


def test_missing_and_foreign_structural_parents_fail_closed():
    missing = _review(nodes=(replace(_child_node(), structural_parent_id=""), _parent_node()))
    assert "topology_structural_parent_missing" in _codes(missing)

    foreign = _review(
        nodes=(
            replace(_child_node(), structural_parent_id="model:ghost-parent"),
            _parent_node(),
        )
    )
    assert _codes(foreign) >= {
        "topology_structural_parent_foreign",
        "topology_structural_parent_mismatch",
    }


def test_exactly_one_root_sentinel_is_required():
    no_root = _review(
        nodes=(
            replace(_child_node(), structural_parent_id="model:parent"),
            replace(
                _parent_node(),
                structural_role="child",
                structural_parent_id="model:child",
            ),
        )
    )
    assert "topology_root_count_invalid" in _codes(no_root)

    second_root = replace(
        _parent_node("model:other-parent"),
        structural_role="root",
        structural_parent_id=TOPOLOGY_ROOT_SENTINEL,
    )
    multiple_roots = _review(
        nodes=(_child_node(), _parent_node(), second_root),
        required_owner_ids=(),
        required_surface_ids_by_owner={},
    )
    assert "topology_root_count_invalid" in _codes(multiple_roots)


def test_nonexistent_producer_output_and_consumer_input_are_rejected():
    report = _review(
        relations=(
            _relation(
                interface_mappings=(
                    BlueprintTopologyPortMapping(
                        "output:does-not-exist", "input:does-not-exist"
                    ),
                )
            ),
        )
    )

    assert _codes(report) >= {
        "topology_producer_output_missing",
        "topology_consumer_input_missing",
    }


def test_schema_mismatch_requires_current_exact_refinement():
    parent = replace(
        _parent_node(),
        input_ports=(_port("input:result", "sha256:another-schema"),),
    )
    report = _review(nodes=(_child_node(), parent))
    assert "topology_schema_mismatch" in _codes(report)

    mapping = BlueprintTopologyPortMapping(
        "output:result",
        "input:result",
        refinement_id="refinement:result-v1-to-v2",
        refinement_fingerprint="sha256:refinement",
    )
    refined = _review(
        nodes=(_child_node(), parent),
        relations=(_relation(interface_mappings=(mapping,)),),
        current_refinements={"refinement:result-v1-to-v2": "sha256:refinement"},
    )
    assert refined.ok, refined.to_dict()


def test_stale_relation_evidence_is_rejected():
    report = _review(
        current_relation_evidence={"relation:child-parent": "sha256:new-evidence"}
    )
    assert "topology_relation_evidence_stale" in _codes(report)


def test_stale_child_and_runtime_evidence_are_rejected():
    stale_child = _review(
        relations=(_relation(consumed_child_evidence_id="child:v0"),)
    )
    assert _codes(stale_child) >= {
        "topology_child_evidence_stale",
        "topology_evidence_cross_revision",
        "topology_evidence_owner_mismatch",
        "topology_evidence_ghost",
    }

    stale_runtime = _review(
        relations=(
            _relation(consumed_runtime_path_evidence_ids=("runtime:child:v0",)),
        )
    )
    assert _codes(stale_runtime) >= {
        "topology_runtime_evidence_stale",
        "topology_evidence_cross_revision",
        "topology_evidence_owner_mismatch",
        "topology_evidence_ghost",
    }


def test_child_validation_and_runtime_evidence_must_exist_in_current_registry():
    report = _review(
        current_evidence={
            "child:v1": CHILD_EVIDENCE,
        }
    )

    ghosts = [
        finding
        for finding in report.findings
        if finding.code == "topology_evidence_ghost"
    ]
    assert len(ghosts) == 4
    assert {subject for finding in ghosts for subject in finding.subject_ids} >= {
        "validation:child:v1",
        "runtime:child:v1",
        "relation:child-parent",
        "reattachment:model:child",
    }


def test_declared_evidence_fingerprint_must_match_current_registry():
    report = _review(
        declared_evidence_by_owner={
            "model:child": {
                "child:v1": CHILD_EVIDENCE,
                "validation:child:v1": "sha256:old-validation",
                "runtime:child:v1": RUNTIME_EVIDENCE,
            }
        }
    )

    stale = [
        finding
        for finding in report.findings
        if finding.code == "topology_evidence_fingerprint_stale"
    ]
    assert len(stale) == 1
    assert "validation:child:v1" in stale[0].subject_ids


def test_evidence_cannot_be_borrowed_from_another_child_owner():
    report = _review(
        declared_evidence_by_owner={
            "model:child": {
                "child:v1": CHILD_EVIDENCE,
                "runtime:child:v1": RUNTIME_EVIDENCE,
            },
            "model:other-child": {
                "validation:child:v1": VALIDATION_EVIDENCE,
            },
        }
    )

    assert _codes(report) >= {
        "topology_child_evidence_binding_mismatch",
        "topology_evidence_owner_mismatch",
    }
    mismatch = next(
        finding
        for finding in report.findings
        if finding.code == "topology_evidence_owner_mismatch"
    )
    assert set(mismatch.subject_ids) >= {
        "model:child",
        "model:other-child",
        "validation:child:v1",
    }


def test_duplicate_evidence_ownership_and_extra_child_binding_are_rejected():
    report = _review(
        declared_evidence_by_owner={
            "model:child": {
                "child:v1": CHILD_EVIDENCE,
                "validation:child:v1": VALIDATION_EVIDENCE,
                "runtime:child:v1": RUNTIME_EVIDENCE,
                "validation:unused": "sha256:unused",
            },
            "model:other-child": {
                "child:v1": CHILD_EVIDENCE,
            },
        },
        current_evidence={
            "child:v1": CHILD_EVIDENCE,
            "validation:child:v1": VALIDATION_EVIDENCE,
            "runtime:child:v1": RUNTIME_EVIDENCE,
            "validation:unused": "sha256:unused",
        },
    )

    assert _codes(report) >= {
        "topology_child_evidence_binding_mismatch",
        "topology_evidence_owner_duplicated",
    }


def test_reattachment_consumed_evidence_is_validated_against_real_registry():
    report = _review(
        reattachments=(_reattachment(consumed_evidence_id="child:ghost"),)
    )

    assert _codes(report) >= {
        "topology_child_reattachment_stale",
        "topology_evidence_cross_revision",
        "topology_evidence_owner_mismatch",
        "topology_evidence_ghost",
    }


def test_child_to_parent_requires_reattachment_contract():
    report = _review(reattachments=())
    assert "topology_child_reattachment_missing" in _codes(report)


def test_every_required_child_output_must_be_reattached():
    report = _review(
        nodes=(_child_node(extra_output=True), _parent_node()),
        child_models=(_child_evidence(extra_output=True),),
    )
    assert "topology_child_output_unconsumed" in _codes(report)


def test_structural_child_cannot_have_multiple_parents():
    second_parent, root, parent_relation = _attached_secondary_parent(
        "model:other-parent"
    )
    second_relation = _relation(
        relation_id="relation:child-other-parent",
        consumer_id="model:other-parent",
    )
    report = _review(
        nodes=(_child_node(), root, second_parent),
        relations=(_relation(), second_relation, parent_relation),
        current_relation_evidence={
            "relation:child-parent": RELATION_EVIDENCE,
            "relation:child-other-parent": RELATION_EVIDENCE,
            parent_relation.relation_id: RELATION_EVIDENCE,
        },
        required_owner_ids=("model:child", "model:parent", "model:other-parent"),
        required_surface_ids_by_owner={
            "model:child": ("surface:child",),
            "model:parent": (),
            "model:other-parent": (),
        },
    )
    assert "topology_multiple_structural_parents" in _codes(report)


def test_cross_boundary_support_preserves_relation_without_second_parent():
    second_parent, root, parent_relation = _attached_secondary_parent(
        "model:other-parent"
    )
    child = replace(
        _child_node(),
        cross_boundary_parent_ids=("model:other-parent",),
    )
    cross_boundary = _relation(
        relation_id="relation:child-cross-boundary",
        consumer_id="model:other-parent",
        relation_kind="cross_boundary_support",
        consumed_child_evidence_id="",
        consumed_runtime_path_evidence_ids=(),
    )
    report = _review(
        nodes=(child, root, second_parent),
        relations=(_relation(), cross_boundary, parent_relation),
        current_relation_evidence={
            "relation:child-parent": RELATION_EVIDENCE,
            "relation:child-cross-boundary": RELATION_EVIDENCE,
            parent_relation.relation_id: RELATION_EVIDENCE,
        },
        required_owner_ids=("model:child", "model:parent", "model:other-parent"),
        required_surface_ids_by_owner={
            "model:child": ("surface:child",),
            "model:parent": (),
            "model:other-parent": (),
        },
    )

    assert report.ok, report.to_dict()
    assert "topology_multiple_structural_parents" not in _codes(report)


def _cycle_node(node_id: str) -> BlueprintTopologyNode:
    return BlueprintTopologyNode(
        node_id=node_id,
        disposition="connected",
        structural_role="child",
        purpose=f"cycle fixture {node_id}",
        structural_parent_id="",
        implementation_surface_ids=(),
        input_ports=(_port(f"input:{node_id}", SCHEMA_RESULT),),
        output_ports=(_port(f"output:{node_id}", SCHEMA_RESULT),),
    )


def _cycle_relation(relation_id: str, producer: str, consumer: str):
    return BlueprintTopologyRelation(
        relation_id=relation_id,
        producer_id=producer,
        consumer_id=consumer,
        relation_kind="child_to_parent",
        interface_mappings=(
            BlueprintTopologyPortMapping(
                f"output:{producer}",
                f"input:{consumer}",
            ),
        ),
        evidence_fingerprint=RELATION_EVIDENCE,
        rationale="structural cycle fixture",
    )


def test_self_two_node_and_long_structural_cycles_are_rejected():
    self_node = _cycle_node("model:self")
    self_report = _review(
        nodes=(self_node,),
        relations=(_cycle_relation("relation:self", "model:self", "model:self"),),
        child_models=(),
        reattachments=(),
        current_relation_evidence={"relation:self": RELATION_EVIDENCE},
        required_owner_ids=(),
        required_surface_ids_by_owner={},
    )
    assert "topology_structural_cycle" in _codes(self_report)

    for names in (("model:a", "model:b"), ("model:a", "model:b", "model:c")):
        nodes = tuple(_cycle_node(name) for name in names)
        relations = tuple(
            _cycle_relation(
                f"relation:{index}",
                names[index],
                names[(index + 1) % len(names)],
            )
            for index in range(len(names))
        )
        report = _review(
            nodes=nodes,
            relations=relations,
            child_models=(),
            reattachments=(),
            current_relation_evidence={
                relation.relation_id: RELATION_EVIDENCE for relation in relations
            },
            required_owner_ids=(),
            required_surface_ids_by_owner={},
        )
        assert "topology_structural_cycle" in _codes(report)


def _feedback_node(node_id: str) -> BlueprintTopologyNode:
    return BlueprintTopologyNode(
        node_id=node_id,
        disposition="connected",
        structural_role="child",
        purpose=f"feedback fixture {node_id}",
        structural_parent_id="model:feedback-root",
        implementation_surface_ids=(),
        input_ports=(_port(f"input:{node_id}", SCHEMA_RESULT),),
        output_ports=(
            _port(f"output:{node_id}", SCHEMA_RESULT),
            _port(f"output:attach:{node_id}", SCHEMA_RESULT),
        ),
    )


def _feedback_relation(
    relation_id: str,
    producer: str,
    consumer: str,
    *,
    progress=None,
    relation_kind: str = "produces_for",
):
    return BlueprintTopologyRelation(
        relation_id=relation_id,
        producer_id=producer,
        consumer_id=consumer,
        relation_kind=relation_kind,
        interface_mappings=(
            BlueprintTopologyPortMapping(f"output:{producer}", f"input:{consumer}"),
        ),
        evidence_fingerprint=RELATION_EVIDENCE,
        rationale="feedback fixture",
        progress_contract=progress,
    )


def _feedback_structure(nodes):
    root = BlueprintTopologyNode(
        node_id="model:feedback-root",
        disposition="connected",
        structural_role="root",
        purpose="own the feedback fixture structural root",
        structural_parent_id=TOPOLOGY_ROOT_SENTINEL,
        input_ports=tuple(
            _port(f"input:attach:{node.node_id}", SCHEMA_RESULT)
            for node in nodes
        ),
    )
    relations = tuple(
        BlueprintTopologyRelation(
            relation_id=f"relation:attach:{node.node_id}",
            producer_id=node.node_id,
            consumer_id=root.node_id,
            relation_kind="delegates_to",
            interface_mappings=(
                BlueprintTopologyPortMapping(
                    f"output:attach:{node.node_id}",
                    f"input:attach:{node.node_id}",
                ),
            ),
            evidence_fingerprint=RELATION_EVIDENCE,
            rationale="feedback fixture has one independent structural parent",
        )
        for node in nodes
    )
    return root, relations


def test_feedback_cycle_requires_current_progress_contract():
    nodes = (_feedback_node("model:a"), _feedback_node("model:b"))
    feedback_relations = (
        _feedback_relation("relation:a-b", "model:a", "model:b"),
        _feedback_relation("relation:b-a", "model:b", "model:a"),
    )
    root, structural_relations = _feedback_structure(nodes)
    relations = (*feedback_relations, *structural_relations)
    missing = _review(
        nodes=(*nodes, root),
        relations=relations,
        child_models=(),
        reattachments=(),
        current_relation_evidence={
            relation.relation_id: RELATION_EVIDENCE for relation in relations
        },
        required_owner_ids=(),
        required_surface_ids_by_owner={},
    )
    assert "topology_feedback_progress_missing" in _codes(missing)

    progress = BlueprintTopologyProgressContract(
        contract_id="progress:feedback",
        contract_kind="finite_bound",
        evidence_fingerprint=PROGRESS_EVIDENCE,
        finite_bound=3,
        rationale="the feedback terminates after at most three passes",
    )
    closed_relations = tuple(
        replace(relation, progress_contract=progress)
        for relation in feedback_relations
    ) + structural_relations
    closed = _review(
        nodes=(*nodes, root),
        relations=closed_relations,
        child_models=(),
        reattachments=(),
        current_relation_evidence={
            relation.relation_id: RELATION_EVIDENCE for relation in relations
        },
        current_progress={"progress:feedback": PROGRESS_EVIDENCE},
        required_owner_ids=(),
        required_surface_ids_by_owner={},
    )
    assert closed.ok, closed.to_dict()


def test_retry_repair_and_explicit_feedback_cycles_all_require_progress():
    nodes = (_feedback_node("model:a"), _feedback_node("model:b"))
    root, structural_relations = _feedback_structure(nodes)
    progress = BlueprintTopologyProgressContract(
        contract_id="progress:typed-feedback",
        contract_kind="finite_bound",
        evidence_fingerprint=PROGRESS_EVIDENCE,
        finite_bound=2,
        rationale="typed feedback terminates after at most two passes",
    )

    for relation_kind in ("feedback", "retry", "repair"):
        feedback_relations = (
            _feedback_relation(
                f"relation:{relation_kind}:a-b",
                "model:a",
                "model:b",
                relation_kind=relation_kind,
            ),
            _feedback_relation(
                f"relation:{relation_kind}:b-a",
                "model:b",
                "model:a",
                relation_kind=relation_kind,
            ),
        )
        relations = (*feedback_relations, *structural_relations)
        current_relations = {
            relation.relation_id: RELATION_EVIDENCE for relation in relations
        }
        missing = _review(
            nodes=(*nodes, root),
            relations=relations,
            child_models=(),
            reattachments=(),
            current_relation_evidence=current_relations,
            required_owner_ids=(),
            required_surface_ids_by_owner={},
        )
        assert "topology_feedback_progress_missing" in _codes(missing)

        closed = _review(
            nodes=(*nodes, root),
            relations=tuple(
                replace(relation, progress_contract=progress)
                for relation in feedback_relations
            )
            + structural_relations,
            child_models=(),
            reattachments=(),
            current_relation_evidence=current_relations,
            current_progress={"progress:typed-feedback": PROGRESS_EVIDENCE},
            required_owner_ids=(),
            required_surface_ids_by_owner={},
        )
        assert closed.ok, (relation_kind, closed.to_dict())


def test_shared_resource_and_affected_sibling_edges_remain_non_feedback():
    nodes = (_feedback_node("model:a"), _feedback_node("model:b"))
    root, structural_relations = _feedback_structure(nodes)
    for relation_kind in ("shared_resource", "affected_sibling"):
        semantic_relations = (
            _feedback_relation(
                f"relation:{relation_kind}:a-b",
                "model:a",
                "model:b",
                relation_kind=relation_kind,
            ),
            _feedback_relation(
                f"relation:{relation_kind}:b-a",
                "model:b",
                "model:a",
                relation_kind=relation_kind,
            ),
        )
        relations = (*semantic_relations, *structural_relations)
        report = _review(
            nodes=(*nodes, root),
            relations=relations,
            child_models=(),
            reattachments=(),
            current_relation_evidence={
                relation.relation_id: RELATION_EVIDENCE for relation in relations
            },
            required_owner_ids=(),
            required_surface_ids_by_owner={},
        )
        assert report.ok, (relation_kind, report.to_dict())


def test_missing_endpoint_and_surface_mismatch_remain_visible():
    report = _review(
        nodes=(replace(_child_node(), implementation_surface_ids=("surface:wrong",)),),
    )
    assert _codes(report) >= {
        "topology_endpoint_missing",
        "topology_surface_binding_mismatch",
    }
