from dataclasses import replace
import json
from types import SimpleNamespace
from contextlib import redirect_stdout
from io import StringIO
from unittest import mock

import pytest

import flowguard
import flowguard.affected_blueprint_reader as affected_reader_module
from flowguard.__main__ import main
from flowguard.affected_blueprint_reader import (
    AffectedBlueprintIndex,
    AffectedBlueprintReadError,
    AffectedBlueprintReader,
    _materialize_topology_invalidation_edges,
    AffectedTopologyInvalidationEdge,
    build_affected_task_context,
    materialize_affected_blueprint_index,
    read_affected_blueprint_understanding,
)
from flowguard.evidence_receipts import fingerprint_value
from flowguard.model_path_quality import PathQualityResult, PathQualitySubject
from flowguard.software_blueprint_readiness import (
    BEHAVIOR_COVERAGE_REFERENCE_SHARD_KIND,
    BEHAVIOR_COVERAGE_REFERENCE_SHARD_SCHEMA,
)
from flowguard.target_system_blueprint import (
    BlueprintGapRef,
    BlueprintLayerResult,
    BlueprintNativeReportRef,
    BlueprintReadinessLedger,
    ModelPathQualityBlueprintBinding,
)
from flowguard.existing_model_preflight import ExistingModelPreflight, ModelContextHit


def _path_quality_binding() -> ModelPathQualityBlueprintBinding:
    currentness_id = "revision:fixture"
    subject = PathQualitySubject(
        model_id="model:a",
        boundary_id="path-boundary:model:a",
        model_fingerprint=fingerprint_value({"model": "a"}),
        normalized_facts_fingerprint=fingerprint_value({"facts": "a"}),
        retained_element_inventory_fingerprint=fingerprint_value(
            {"retained": "a"}
        ),
        purpose_fingerprint=fingerprint_value({"purpose": "a"}),
        intent_fingerprint=fingerprint_value({"intent": "a"}),
        obligation_fingerprint=fingerprint_value({"obligation": "a"}),
        provider_fingerprint=fingerprint_value({"provider": "a"}),
        dependency_fingerprint=fingerprint_value({"dependency": "a"}),
        code_fingerprint=fingerprint_value({"code": "a"}),
        test_fingerprint=fingerprint_value({"test": "a"}),
        oracle_fingerprint=fingerprint_value({"oracle": "a"}),
        evidence_fingerprint=fingerprint_value({"evidence": "a"}),
        currentness_id=currentness_id,
    )
    result = PathQualityResult(
        result_id="path-quality:model:a",
        subject_fingerprint=subject.fingerprint,
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
        necessity_witness_set_fingerprint=fingerprint_value(
            {"necessity": "a"}
        ),
        detail_evidence_fingerprint=fingerprint_value({"detail": "a"}),
        producer_id="model_maturation",
        currentness_id=currentness_id,
    )
    return ModelPathQualityBlueprintBinding(
        model_element_id="model:a",
        subject_lane="observed",
        change_kind="unchanged",
        subject=subject,
        result=result,
        affected_topology_evidence_fingerprint=fingerprint_value(
            {"topology": "a"}
        ),
        affected_topology_currentness_id=currentness_id,
    )


def test_affected_index_materializes_the_object_id_denominator_once():
    class CountingDict(dict):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.iteration_count = 0

        def __iter__(self):
            self.iteration_count += 1
            return super().__iter__()

    object_ids = tuple(f"object:{index:05d}" for index in range(2_000))
    tracked = {}
    original_index_pairs = affected_reader_module._index_pairs

    def counted_index_pairs(rows, *, context):
        indexed = original_index_pairs(rows, context=context)
        if context == "object fingerprint index":
            indexed = CountingDict(indexed)
            tracked["objects"] = indexed
        return indexed

    with mock.patch.object(
        affected_reader_module,
        "_index_pairs",
        side_effect=counted_index_pairs,
    ):
        AffectedBlueprintIndex(
            blueprint_fingerprint="sha256:blueprint",
            logical_fingerprint="sha256:logical",
            target_object_id=object_ids[0],
            ledger_row_ids=object_ids,
            object_fingerprints=tuple(
                (object_id, f"sha256:{index:05d}")
                for index, object_id in enumerate(object_ids)
            ),
            shard_fingerprints=(),
            shard_member_ids=(),
            affected_edges=tuple(
                (object_id, (object_id,)) for object_id in object_ids
            ),
            topology_invalidation_edges=(),
        )

    assert tracked["objects"].iteration_count == 1


def test_affected_index_still_rejects_an_unknown_edge_reference():
    with pytest.raises(AffectedBlueprintReadError, match="edge is incomplete"):
        AffectedBlueprintIndex(
            blueprint_fingerprint="sha256:blueprint",
            logical_fingerprint="sha256:logical",
            target_object_id="object:known",
            ledger_row_ids=("object:known",),
            object_fingerprints=(("object:known", "sha256:known"),),
            shard_fingerprints=(),
            shard_member_ids=(),
            affected_edges=(
                ("object:known", ("object:known", "object:missing")),
            ),
            topology_invalidation_edges=(),
        )


def _reference_shard(shard_id, *coverage_ids):
    coverage_ids = sorted(coverage_ids)
    return {
        "schema_version": BEHAVIOR_COVERAGE_REFERENCE_SHARD_SCHEMA,
        "kind": BEHAVIOR_COVERAGE_REFERENCE_SHARD_KIND,
        "shard_id": shard_id,
        "coverage_ids": coverage_ids,
        "referenced_object_ids": coverage_ids,
    }


def _projection(*, shard_payloads, object_payloads):
    return SimpleNamespace(
        blueprint_fingerprint="sha256:blueprint",
        logical_fingerprint="sha256:logical",
        shard_fingerprints=tuple(
            (shard_id, fingerprint_value(payload))
            for shard_id, payload in shard_payloads.items()
        ),
        shard_member_ids=(
            ("shard:a", ("surface:a", "coverage:a")),
            ("shard:b", ("surface:b", "coverage:b")),
        ),
        object_fingerprints=tuple(
            (object_id, fingerprint_value(payload))
            for object_id, payload in object_payloads.items()
        ),
        topology_invalidation_edges=(),
        to_dict=mock.Mock(side_effect=AssertionError("whole projection expanded")),
    )


def test_reader_loads_only_matching_shard_references_and_required_ancestors():
    shard_payloads = {
        "shard:a": _reference_shard("shard:a", "behavior:a"),
        "shard:b": _reference_shard("shard:b", "behavior:b"),
    }
    object_payloads = {
        "behavior:a": {
            "behavior_block_id": "behavior:a",
            "ancestor_object_ids": ["owner:root"],
        },
        "owner:root": {"owner_id": "owner:root"},
        "behavior:b": {"behavior_block_id": "behavior:b"},
        "unrelated": {"value": "must stay unloaded"},
    }
    projection = _projection(
        shard_payloads=shard_payloads,
        object_payloads=object_payloads,
    )
    loaded_shards = []
    loaded_objects = []

    def load_shard(shard_id):
        loaded_shards.append(shard_id)
        return shard_payloads[shard_id]

    def load_object(object_id):
        loaded_objects.append(object_id)
        return object_payloads[object_id]

    result = AffectedBlueprintReader(
        projection,
        load_shard=load_shard,
        load_object=load_object,
    ).read(("surface:a",))

    assert loaded_shards == ["shard:a"]
    assert loaded_objects == ["behavior:a", "owner:root"]
    assert result.shard_ids == ("shard:a",)
    assert result.object_ids == ("behavior:a", "owner:root")
    assert result.ancestor_object_ids == ("owner:root",)
    assert result.requested_seed_ids == ("surface:a",)
    assert result.affected_ids == ("surface:a",)
    assert result.propagated_affected_ids == ()
    assert result.shards == (
        ("shard:a", _reference_shard("shard:a", "behavior:a")),
    )
    assert "behavior_block_id" not in result.shards[0][1]
    projection.to_dict.assert_not_called()


def test_reader_rejects_unknown_affected_id_without_loading_or_fallback():
    projection = _projection(
        shard_payloads={
            "shard:a": _reference_shard("shard:a", "behavior:a"),
            "shard:b": _reference_shard("shard:b", "behavior:b"),
        },
        object_payloads={},
    )
    load_shard = mock.Mock(side_effect=AssertionError("loader must stay idle"))
    load_object = mock.Mock(side_effect=AssertionError("loader must stay idle"))

    with pytest.raises(AffectedBlueprintReadError, match="unknown affected ids"):
        AffectedBlueprintReader(
            projection,
            load_shard=load_shard,
            load_object=load_object,
        ).read(("surface:missing",))

    load_shard.assert_not_called()
    load_object.assert_not_called()
    projection.to_dict.assert_not_called()


def test_reader_rejects_shard_fingerprint_drift_before_loading_objects():
    expected_shards = {
        "shard:a": _reference_shard("shard:a", "behavior:a"),
        "shard:b": _reference_shard("shard:b", "behavior:b"),
    }
    object_payloads = {"behavior:a": {"value": "current"}}
    projection = _projection(
        shard_payloads=expected_shards,
        object_payloads=object_payloads,
    )
    load_object = mock.Mock(side_effect=AssertionError("object load is invalid"))

    with pytest.raises(AffectedBlueprintReadError, match="shard fingerprint mismatch"):
        AffectedBlueprintReader(
            projection,
            load_shard=lambda _shard_id: {
                **_reference_shard("shard:a", "behavior:a"),
                "drift": True,
            },
            load_object=load_object,
        ).read(("surface:a",))

    load_object.assert_not_called()


def test_reader_rejects_self_consistent_legacy_full_payload_shard():
    legacy_shards = {
        "shard:a": {
            "coverage_id": "coverage:a",
            "behavior_block_id": "behavior:a",
            "referenced_object_ids": ["behavior:a"],
        },
        "shard:b": _reference_shard("shard:b", "behavior:b"),
    }
    object_payloads = {
        "behavior:a": {"behavior_block_id": "behavior:a"},
        "behavior:b": {"behavior_block_id": "behavior:b"},
    }
    projection = _projection(
        shard_payloads=legacy_shards,
        object_payloads=object_payloads,
    )

    with pytest.raises(AffectedBlueprintReadError, match="fields are not current"):
        AffectedBlueprintReader(
            projection,
            load_shard=legacy_shards.__getitem__,
            load_object=object_payloads.__getitem__,
        ).read(("surface:a",))


def test_reader_rejects_referenced_object_fingerprint_drift():
    shard_payloads = {
        "shard:a": _reference_shard("shard:a", "behavior:a"),
        "shard:b": _reference_shard("shard:b", "behavior:b"),
    }
    projection = _projection(
        shard_payloads=shard_payloads,
        object_payloads={"behavior:a": {"value": "current"}},
    )

    with pytest.raises(AffectedBlueprintReadError, match="object fingerprint mismatch"):
        AffectedBlueprintReader(
            projection,
            load_shard=shard_payloads.__getitem__,
            load_object=lambda _object_id: {"value": "drifted"},
        ).read(("surface:a",))


def _understanding_fixture(
    *,
    blocked: bool = False,
    target_profile: str = "software",
    with_path_quality: bool = False,
    omit_path_quality: bool = False,
):
    shard_payloads = {
        "shard:a": _reference_shard("shard:a", "behavior:a"),
        "shard:b": _reference_shard("shard:b", "behavior:b"),
    }
    shared_objects = {
        "behavior:a": {
            "kind": "behavior_block",
            "behavior_block_id": "behavior:a",
            "ancestor_object_ids": ["owner:a"],
        },
        "owner:a": {"kind": "behavior_owner", "owner_id": "owner:a"},
        "behavior:b": {
            "kind": "behavior_block",
            "behavior_block_id": "behavior:b",
        },
        "unrelated": {"kind": "unrelated", "value": "must stay unloaded"},
    }
    required_path_quality_model_ids: tuple[str, ...] = ()
    if with_path_quality:
        binding = _path_quality_binding()
        path_object_id = (
            "model-path-quality:model:a:"
            + binding.compact_current_fingerprint.split(":", 1)[-1]
        )
        shared_objects["behavior:a"]["model_element_id"] = "model:a"
        shared_objects["model:a"] = {
            "kind": "model_element",
            "owner_id": "owner:a",
            "referenced_object_ids": (
                [] if omit_path_quality else [path_object_id]
            ),
        }
        if not omit_path_quality:
            shared_objects[path_object_id] = {
                "kind": "model_path_quality_binding",
                **binding.to_dict(),
            }
        required_path_quality_model_ids = ("model:a",)
    projection = _projection(
        shard_payloads=shard_payloads,
        object_payloads=shared_objects,
    )
    native = BlueprintNativeReportRef(
        owner_id="owner:behavior",
        report_id="report:behavior",
        report_fingerprint=fingerprint_value({"report": "behavior"}),
    )
    if blocked:
        gap = BlueprintGapRef(
            layer="model_code_test",
            object_kind="native_report",
            object_id="report:behavior",
            status="blocked",
            owner_id="owner:behavior",
            message="exact native report is blocked",
        )
        final = BlueprintLayerResult._derived(
            layer="model_code_test",
            status="blocked",
            evidence_ids=(native.report_fingerprint,),
            gap_ids=(gap.gap_id,),
            native_reports=(native,),
            pre_code_status="blocked",
            executed_evidence_status="not_run",
        )
        gaps = (gap,)
    else:
        final = BlueprintLayerResult._derived(
            layer="model_code_test",
            status="pass",
            evidence_ids=(native.report_fingerprint,),
            native_reports=(native,),
            pre_code_status=(
                "ready" if target_profile == "software" else "not_applicable"
            ),
            executed_evidence_status=(
                "passed" if target_profile == "software" else "not_applicable"
            ),
            implementation_admitted=target_profile == "software",
        )
        gaps = ()
    ledger = BlueprintReadinessLedger(
        target_profile=target_profile,
        rows=(
            BlueprintLayerResult._derived(
                layer="implementation_inventory",
                status="pass",
                evidence_ids=(fingerprint_value({"inventory": "current"}),),
                pre_code_status=(
                    "ready"
                    if target_profile == "software"
                    else "not_applicable"
                ),
            ),
            final,
        ),
        gaps=gaps,
    )
    index, objects = materialize_affected_blueprint_index(
        projection,
        target_system_id="target:fixture",
        target_profile=target_profile,
        subject_revision="revision:fixture",
        descriptor_fingerprint=fingerprint_value({"descriptor": "fixture"}),
        target_blueprint_fingerprint=fingerprint_value(
            {"target-blueprint": "fixture", "blocked": blocked}
        ),
        layer_plan_id="plan:software",
        layer_plan_fingerprint=fingerprint_value({"plan": "software"}),
        readiness_ledger=ledger,
        shared_objects=shared_objects,
        required_path_quality_model_ids=required_path_quality_model_ids,
    )
    return projection, index, shard_payloads, dict(objects)


def test_materialization_fingerprints_each_returned_object_once():
    with mock.patch(
        "flowguard.affected_blueprint_reader.fingerprint_value",
        wraps=fingerprint_value,
    ) as tracked:
        _projection_value, index, _shards, objects = _understanding_fixture(
            blocked=True
        )

    call_count_by_object = {
        id(payload): sum(
            1 for call in tracked.call_args_list if call.args[0] is payload
        )
        for payload in objects.values()
    }
    assert set(call_count_by_object.values()) == {1}
    assert dict(index.object_fingerprints) == {
        object_id: fingerprint_value(payload)
        for object_id, payload in objects.items()
    }


def _topology_invalidation_fixture():
    shard_surface_ids = {
        "shard:child-a": "surface:child-a",
        "shard:child-b": "surface:child-b",
        "shard:parent": "surface:parent",
        "shard:unrelated": "surface:unrelated-child",
    }
    shard_payloads = {
        shard_id: _reference_shard(
            shard_id,
            "topology-node:model:" + surface_id.removeprefix("surface:"),
        )
        for shard_id, surface_id in shard_surface_ids.items()
    }
    shard_members = tuple(
        (shard_id, (surface_id,))
        for shard_id, surface_id in shard_surface_ids.items()
    )
    shared_objects = {
        "topology-node:model:child-a": {
            "kind": "blueprint_topology_node",
            "node_id": "model:child-a",
            "implementation_surface_ids": ["surface:child-a"],
        },
        "topology-node:model:child-b": {
            "kind": "blueprint_topology_node",
            "node_id": "model:child-b",
            "implementation_surface_ids": ["surface:child-b"],
        },
        "topology-node:model:parent": {
            "kind": "blueprint_topology_node",
            "node_id": "model:parent",
            "implementation_surface_ids": ["surface:parent"],
        },
        "topology-node:model:unrelated-child": {
            "kind": "blueprint_topology_node",
            "node_id": "model:unrelated-child",
            "implementation_surface_ids": ["surface:unrelated-child"],
        },
        "topology-node:model:unrelated-parent": {
            "kind": "blueprint_topology_node",
            "node_id": "model:unrelated-parent",
            "implementation_surface_ids": [],
        },
        "topology-relation:relation:child-a-parent": {
            "kind": "blueprint_topology_relation",
            "relation_id": "relation:child-a-parent",
            "relation_kind": "child_to_parent",
            "producer_id": "model:child-a",
            "consumer_id": "model:parent",
            "referenced_object_ids": [
                "topology-node:model:child-a",
                "topology-node:model:parent",
            ],
        },
        "topology-relation:relation:child-b-parent": {
            "kind": "blueprint_topology_relation",
            "relation_id": "relation:child-b-parent",
            "relation_kind": "child_to_parent",
            "producer_id": "model:child-b",
            "consumer_id": "model:parent",
            "referenced_object_ids": [
                "topology-node:model:child-b",
                "topology-node:model:parent",
            ],
        },
        "topology-relation:relation:unrelated": {
            "kind": "blueprint_topology_relation",
            "relation_id": "relation:unrelated",
            "relation_kind": "child_to_parent",
            "producer_id": "model:unrelated-child",
            "consumer_id": "model:unrelated-parent",
            "referenced_object_ids": [
                "topology-node:model:unrelated-child",
                "topology-node:model:unrelated-parent",
            ],
        },
        # These broad topology indexes deliberately mention every incident edge.
        # The affected reader must still follow only the typed propagated closure.
        "topology-index:model:child-a": {
            "kind": "blueprint_topology_index",
            "node_object_id": "topology-node:model:child-a",
            "relation_object_ids": [
                "topology-relation:relation:child-a-parent"
            ],
        },
        "topology-index:model:parent": {
            "kind": "blueprint_topology_index",
            "node_object_id": "topology-node:model:parent",
            "relation_object_ids": [
                "topology-relation:relation:child-a-parent",
                "topology-relation:relation:child-b-parent",
            ],
        },
        "topology-index:model:unrelated-child": {
            "kind": "blueprint_topology_index",
            "node_object_id": "topology-node:model:unrelated-child",
            "relation_object_ids": ["topology-relation:relation:unrelated"],
        },
    }
    projection = SimpleNamespace(
        blueprint_fingerprint="sha256:topology-blueprint",
        logical_fingerprint="sha256:topology-logical",
        shard_fingerprints=tuple(
            (shard_id, fingerprint_value(payload))
            for shard_id, payload in shard_payloads.items()
        ),
        shard_member_ids=shard_members,
        object_fingerprints=tuple(
            (object_id, fingerprint_value(payload))
            for object_id, payload in shared_objects.items()
        ),
        to_dict=mock.Mock(side_effect=AssertionError("whole projection expanded")),
    )
    ledger = BlueprintReadinessLedger(
        target_profile="software",
        rows=(
            BlueprintLayerResult._derived(
                layer="traceability",
                status="pass",
                evidence_ids=(fingerprint_value({"topology": "current"}),),
            ),
        ),
        gaps=(),
    )
    index, objects = materialize_affected_blueprint_index(
        projection,
        target_system_id="target:topology",
        target_profile="software",
        subject_revision="revision:topology",
        descriptor_fingerprint=fingerprint_value({"descriptor": "topology"}),
        target_blueprint_fingerprint=fingerprint_value(
            {"target-blueprint": "topology"}
        ),
        layer_plan_id="plan:software",
        layer_plan_fingerprint=fingerprint_value({"plan": "software"}),
        readiness_ledger=ledger,
        shared_objects=shared_objects,
    )
    return projection, index, shard_payloads, dict(objects)


def test_child_seed_propagates_to_ancestor_without_reopening_unrelated_siblings():
    projection, index, shard_payloads, objects = _topology_invalidation_fixture()
    loaded_shards = []
    loaded_objects = []

    def load_shard(shard_id):
        loaded_shards.append(shard_id)
        return shard_payloads[shard_id]

    def load_object(object_id):
        loaded_objects.append(object_id)
        return objects[object_id]

    result = AffectedBlueprintReader(
        index,
        load_shard=load_shard,
        load_object=load_object,
    ).read(("surface:child-a",))

    assert result.requested_seed_ids == ("surface:child-a",)
    assert result.affected_ids == (
        "model:child-a",
        "model:parent",
        "surface:child-a",
        "surface:parent",
    )
    assert result.propagated_affected_ids == (
        "model:child-a",
        "model:parent",
        "surface:parent",
    )
    typed_edges = {
        (edge.source_id, edge.target_id, edge.edge_kind, edge.via_node_id)
        for edge in index.topology_invalidation_edges
    }
    assert (
        "model:child-a",
        "model:parent",
        "ancestor",
        "model:parent",
    ) in typed_edges
    assert not any(edge[2] == "sibling" for edge in typed_edges)
    assert (
        "model:parent",
        "model:child-a",
        "child",
        "model:parent",
    ) in typed_edges
    assert loaded_shards == ["shard:child-a", "shard:parent"]
    assert not any("unrelated" in object_id for object_id in loaded_objects)
    assert "topology-relation:relation:child-a-parent" in loaded_objects
    assert "topology-relation:relation:child-b-parent" in loaded_objects
    projection.to_dict.assert_not_called()


def test_parent_seed_propagates_to_required_children_and_round_trips_current_index():
    projection, index, shard_payloads, objects = _topology_invalidation_fixture()
    current = AffectedBlueprintIndex.from_dict(index.to_dict())

    result = AffectedBlueprintReader(
        current,
        load_shard=shard_payloads.__getitem__,
        load_object=objects.__getitem__,
    ).read(("model:parent",))

    assert result.requested_seed_ids == ("model:parent",)
    assert {"model:child-a", "model:child-b"}.issubset(result.affected_ids)
    assert {"surface:child-a", "surface:child-b"}.issubset(result.affected_ids)
    assert not any("unrelated" in affected_id for affected_id in result.affected_ids)
    assert current.schema_version == "flowguard.affected_blueprint_index.v3"
    assert current.fingerprint == index.fingerprint
    projection.to_dict.assert_not_called()


def _semantic_relation_fixture(relations):
    node_ids = {
        *(
            producer_id
            for _relation_id, _kind, producer_id, _consumer_id in relations
        ),
        *(
            consumer_id
            for _relation_id, _kind, _producer_id, consumer_id in relations
        ),
        "model:unrelated",
    }
    shard_payloads = {
        f"shard:{node_id}": _reference_shard(
            f"shard:{node_id}", f"topology-node:{node_id}"
        )
        for node_id in sorted(node_ids)
    }
    shared_objects = {
        f"topology-node:{node_id}": {
            "kind": "blueprint_topology_node",
            "node_id": node_id,
            "implementation_surface_ids": [f"surface:{node_id}"],
        }
        for node_id in sorted(node_ids)
    }
    for relation_id, relation_kind, producer_id, consumer_id in relations:
        shared_objects[f"topology-relation:{relation_id}"] = {
            "kind": "blueprint_topology_relation",
            "relation_id": relation_id,
            "relation_kind": relation_kind,
            "producer_id": producer_id,
            "consumer_id": consumer_id,
            "referenced_object_ids": [
                f"topology-node:{producer_id}",
                f"topology-node:{consumer_id}",
            ],
        }
    projection = SimpleNamespace(
        blueprint_fingerprint="sha256:semantic-topology-blueprint",
        logical_fingerprint="sha256:semantic-topology-logical",
        shard_fingerprints=tuple(
            (shard_id, fingerprint_value(payload))
            for shard_id, payload in shard_payloads.items()
        ),
        shard_member_ids=tuple(
            (
                shard_id,
                (f"surface:{shard_id.removeprefix('shard:')}",),
            )
            for shard_id in shard_payloads
        ),
        object_fingerprints=tuple(
            (object_id, fingerprint_value(payload))
            for object_id, payload in shared_objects.items()
        ),
        to_dict=mock.Mock(side_effect=AssertionError("whole projection expanded")),
    )
    ledger = BlueprintReadinessLedger(
        target_profile="software",
        rows=(
            BlueprintLayerResult._derived(
                layer="traceability",
                status="pass",
                evidence_ids=(fingerprint_value({"topology": "semantic-current"}),),
            ),
        ),
        gaps=(),
    )
    index, objects = materialize_affected_blueprint_index(
        projection,
        target_system_id="target:semantic-topology",
        target_profile="software",
        subject_revision="revision:semantic-topology",
        descriptor_fingerprint=fingerprint_value(
            {"descriptor": "semantic-topology"}
        ),
        target_blueprint_fingerprint=fingerprint_value(
            {"target-blueprint": "semantic-topology"}
        ),
        layer_plan_id="plan:software",
        layer_plan_fingerprint=fingerprint_value({"plan": "software"}),
        readiness_ledger=ledger,
        shared_objects=shared_objects,
    )
    return projection, index, shard_payloads, dict(objects)


def test_every_non_structural_relation_kind_declares_one_invalidation_direction():
    assert set(
        affected_reader_module._TOPOLOGY_RELATION_INVALIDATION_DIRECTIONS
    ) == set(affected_reader_module.TOPOLOGY_RELATION_KINDS) - {
        "child_to_parent"
    }


@pytest.mark.parametrize(
    ("relation_kind", "source_id", "target_id"),
    (
        ("produces_for", "model:producer", "model:consumer"),
        ("delegates_to", "model:consumer", "model:producer"),
        ("supports", "model:producer", "model:consumer"),
        ("cross_boundary_support", "model:producer", "model:consumer"),
        ("feedback", "model:producer", "model:consumer"),
        ("retry", "model:producer", "model:consumer"),
        ("repair", "model:producer", "model:consumer"),
        ("shared_resource", "model:producer", "model:consumer"),
        ("affected_sibling", "model:producer", "model:consumer"),
    ),
)
def test_semantic_relation_follows_its_exact_invalidation_direction(
    relation_kind, source_id, target_id
):
    relation_id = f"relation:{relation_kind}"
    projection, index, shard_payloads, objects = _semantic_relation_fixture(
        ((relation_id, relation_kind, "model:producer", "model:consumer"),)
    )
    current = AffectedBlueprintIndex.from_dict(index.to_dict())
    reader = AffectedBlueprintReader(
        current,
        load_shard=shard_payloads.__getitem__,
        load_object=objects.__getitem__,
    )

    propagated = reader.read((f"surface:{source_id}",))
    opposite_only = reader.read((f"surface:{target_id}",))

    assert {
        source_id,
        target_id,
        f"surface:{source_id}",
        f"surface:{target_id}",
    }.issubset(propagated.affected_ids)
    assert source_id not in opposite_only.affected_ids
    assert f"surface:{source_id}" not in opposite_only.affected_ids
    assert "topology-relation:" + relation_id in propagated.object_ids
    semantic_edges = tuple(
        edge
        for edge in current.topology_invalidation_edges
        if edge.edge_kind == relation_kind
    )
    assert tuple(
        (edge.source_id, edge.target_id) for edge in semantic_edges
    ) == ((source_id, target_id),)
    assert current.fingerprint == index.fingerprint
    projection.to_dict.assert_not_called()


@pytest.mark.parametrize(
    "relation_kind",
    (
        "child_to_parent",
        "produces_for",
        "delegates_to",
        "supports",
        "cross_boundary_support",
        "feedback",
        "retry",
        "repair",
        "shared_resource",
        "affected_sibling",
    ),
)
def test_relation_identity_seed_invalidates_both_exact_endpoints(relation_kind):
    relation_id = f"relation:{relation_kind}"
    projection, index, shard_payloads, objects = _semantic_relation_fixture(
        ((relation_id, relation_kind, "model:producer", "model:consumer"),)
    )

    result = AffectedBlueprintReader(
        index,
        load_shard=shard_payloads.__getitem__,
        load_object=objects.__getitem__,
    ).read((relation_id,))

    assert {
        relation_id,
        "model:producer",
        "model:consumer",
        "surface:model:producer",
        "surface:model:consumer",
    }.issubset(result.affected_ids)
    assert "topology-relation:" + relation_id in result.object_ids
    assert not any("unrelated" in affected_id for affected_id in result.affected_ids)
    projection.to_dict.assert_not_called()


def test_semantic_relation_cycle_terminates_with_one_stable_affected_closure():
    projection, index, shard_payloads, objects = _semantic_relation_fixture(
        (
            ("relation:a-b", "produces_for", "model:a", "model:b"),
            ("relation:b-a", "supports", "model:b", "model:a"),
        )
    )
    reader = AffectedBlueprintReader(
        index,
        load_shard=shard_payloads.__getitem__,
        load_object=objects.__getitem__,
    )

    first = reader.read(("surface:model:a",))
    second = reader.read(("surface:model:a",))

    assert first.fingerprint == second.fingerprint
    assert first.affected_ids == (
        "model:a",
        "model:b",
        "surface:model:a",
        "surface:model:b",
    )
    identities = tuple(edge.identity for edge in index.topology_invalidation_edges)
    assert len(identities) == len(set(identities))
    projection.to_dict.assert_not_called()


@pytest.mark.parametrize(
    ("relation_kind", "forward_edge_kind"),
    (("child_to_parent", "ancestor"), ("supports", "supports")),
)
def test_parallel_relations_coalesce_one_edge_and_preserve_all_evidence(
    relation_kind, forward_edge_kind
):
    relation_ids = ("relation:parallel-a", "relation:parallel-b")
    _projection, index, shard_payloads, objects = _semantic_relation_fixture(
        tuple(
            (relation_id, relation_kind, "model:producer", "model:consumer")
            for relation_id in relation_ids
        )
    )

    forward_edges = tuple(
        edge
        for edge in index.topology_invalidation_edges
        if edge.source_id == "model:producer"
        and edge.target_id == "model:consumer"
        and edge.edge_kind == forward_edge_kind
    )
    result = AffectedBlueprintReader(
        index,
        load_shard=shard_payloads.__getitem__,
        load_object=objects.__getitem__,
    ).read(("surface:model:producer",))

    assert len(forward_edges) == 1
    assert forward_edges[0].evidence_object_ids == tuple(
        f"topology-relation:{relation_id}" for relation_id in relation_ids
    )
    assert set(forward_edges[0].evidence_object_ids).issubset(result.object_ids)
    assert not any(
        edge.edge_kind == "sibling" for edge in index.topology_invalidation_edges
    )


def test_sibling_invalidation_edges_scale_linearly_for_flat_model_families():
    child_count = 40
    objects = {
        "topology-node:model:parent": {
            "kind": "blueprint_topology_node",
            "node_id": "model:parent",
            "implementation_surface_ids": [],
        }
    }
    for index in range(child_count):
        child_id = f"model:child-{index:02d}"
        objects[f"topology-node:{child_id}"] = {
            "kind": "blueprint_topology_node",
            "node_id": child_id,
            "implementation_surface_ids": [],
        }
        objects[f"topology-relation:relation:child-{index:02d}"] = {
            "kind": "blueprint_topology_relation",
            "relation_id": f"relation:child-{index:02d}",
            "relation_kind": "child_to_parent",
            "producer_id": child_id,
            "consumer_id": "model:parent",
        }

    edges, _ = _materialize_topology_invalidation_edges(
        objects,
        include_sibling_invalidation=True,
    )
    sibling_edges = tuple(edge for edge in edges if edge.edge_kind == "sibling")

    assert len(sibling_edges) == 2 * (child_count - 1)
    adjacency = {}
    for edge in sibling_edges:
        adjacency.setdefault(edge.source_id, set()).add(edge.target_id)
    reached = {"model:child-39"}
    frontier = list(reached)
    while frontier:
        source_id = frontier.pop()
        for target_id in adjacency.get(source_id, ()):
            if target_id not in reached:
                reached.add(target_id)
                frontier.append(target_id)
    assert len(reached) == child_count


def test_understanding_is_derived_from_affected_content_without_whole_builder():
    projection, index, shard_payloads, objects = _understanding_fixture()
    loaded_shards = []
    loaded_objects = []

    def load_shard(shard_id):
        loaded_shards.append(shard_id)
        return shard_payloads[shard_id]

    def load_object(object_id):
        loaded_objects.append(object_id)
        return objects[object_id]

    with mock.patch(
        "flowguard.project_blueprint.build_project_blueprint",
        side_effect=AssertionError("whole builder invoked"),
    ), mock.patch(
        "flowguard.target_system_blueprint.project_blueprint_understanding",
        side_effect=AssertionError("whole summary invoked"),
    ):
        result = read_affected_blueprint_understanding(
            index,
            affected_ids=("surface:a",),
            load_shard=load_shard,
            load_object=load_object,
        )

    assert loaded_shards == ["shard:a"]
    assert "behavior:b" not in loaded_objects
    assert "unrelated" not in loaded_objects
    assert result.target_system_id == "target:fixture"
    assert result.target_profile == "software"
    assert result.subject_revision == "revision:fixture"
    assert result.requested_seed_ids == ("surface:a",)
    assert result.affected_ids == ("surface:a",)
    assert result.propagated_affected_ids == ()
    assert result.layer_statuses == (
        ("implementation_inventory", "pass"),
        ("model_code_test", "pass"),
    )
    assert result.deepest_proven_layer == "model_code_test"
    assert result.first_gap is None
    assert result.gap_count == 0
    assert result.implementation_admitted is True
    projection.to_dict.assert_not_called()


def test_basic_cli_navigation_without_projection_is_success_with_scoped_deep_gap(
    tmp_path,
):
    preflight = ExistingModelPreflight(
        "preflight:basic-navigation",
        "locate alpha owner",
        mode="light",
        inventory_scope="selected_owner_closure",
        existing_modeled_system=True,
        grounding_state="modeled_current",
        authority_required=True,
        authority_status="pass",
        authority_integrity="pass",
        selected_source_currentness="current",
        execution_evidence_status="not_run",
        authority_snapshot_fingerprint="sha256:snapshot",
        authority_subject_revision="revision:accepted",
        as_of={
            "snapshot_fingerprint": "sha256:snapshot",
            "subject_revision": "revision:accepted",
        },
        relevant_models=(
            ModelContextHit(
                model_id="alpha",
                model_path=".flowguard/models/alpha.py",
                evidence_id="model-authority:sha256:alpha",
                evidence_tier="authoritative_observed",
                evidence_current=True,
            ),
        ),
        selected_model_paths=(".flowguard/models/alpha.py",),
        selected_runner_paths=(".flowguard/runners/alpha.py",),
        selected_input_paths=(".flowguard/inputs/alpha.json",),
        selected_closure={
            "selected_model_ids": ["alpha"],
            "producer_count": 0,
            "write_count": 0,
        },
    )
    output = StringIO()
    with mock.patch(
        "flowguard.existing_model_preflight.existing_model_preflight_from_project",
        return_value=preflight,
    ), redirect_stdout(output):
        exit_code = main(
            [
                "affected-blueprint-understanding",
                "--root",
                str(tmp_path),
                "--task-summary",
                "locate alpha owner",
                "--json",
            ]
        )

    payload = json.loads(output.getvalue())
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["status"] == "basic_navigation"
    assert payload["selected_model_ids"] == ["alpha"]
    assert payload["as_of"]["snapshot_fingerprint"] == "sha256:snapshot"
    assert payload["producer_count"] == 0
    assert payload["write_count"] == 0
    deep_gap = next(
        gap for gap in payload["gaps"] if gap["code"] == "deep_projection_not_requested"
    )
    assert deep_gap["severity"] == "scoped"


def test_affected_understanding_loads_only_exact_compact_path_quality() -> None:
    projection, index, shard_payloads, objects = _understanding_fixture(
        with_path_quality=True
    )
    loaded_objects: list[str] = []

    def load_object(object_id: str):
        loaded_objects.append(object_id)
        return objects[object_id]

    result = read_affected_blueprint_understanding(
        index,
        affected_ids=("surface:a",),
        load_shard=shard_payloads.__getitem__,
        load_object=load_object,
    )

    assert result.required_path_quality_model_ids == ("model:a",)
    assert len(result.path_quality_bindings) == 1
    binding = result.path_quality_bindings[0]
    assert binding.model_element_id == "model:a"
    assert binding.ready
    assert binding.detail_evidence_fingerprint == (
        binding.result.detail_evidence_fingerprint
    )
    assert any(
        object_id.startswith("model-path-quality:model:a:")
        for object_id in loaded_objects
    )
    assert not any("candidate" in object_id for object_id in loaded_objects)
    projection.to_dict.assert_not_called()


def test_affected_understanding_rejects_pass_without_required_path_quality() -> None:
    _projection_value, index, shard_payloads, objects = _understanding_fixture(
        with_path_quality=True,
        omit_path_quality=True,
    )

    with pytest.raises(
        AffectedBlueprintReadError,
        match="passes despite incomplete path-quality closure",
    ):
        read_affected_blueprint_understanding(
            index,
            affected_ids=("surface:a",),
            load_shard=shard_payloads.__getitem__,
            load_object=objects.__getitem__,
        )


def test_affected_understanding_rejects_readdressed_path_projection_drift() -> None:
    _projection_value, index, shard_payloads, objects = _understanding_fixture(
        with_path_quality=True
    )
    path_object_id = next(
        object_id
        for object_id in objects
        if object_id.startswith("model-path-quality:model:a:")
    )
    objects[path_object_id] = {
        **objects[path_object_id],
        "detail_evidence_fingerprint": fingerprint_value(
            {"detail": "tampered"}
        ),
    }
    fingerprints = dict(index.object_fingerprints)
    fingerprints[path_object_id] = fingerprint_value(objects[path_object_id])
    index = replace(
        index,
        object_fingerprints=tuple(sorted(fingerprints.items())),
    )

    with pytest.raises(
        AffectedBlueprintReadError,
        match="path-quality object is invalid",
    ):
        read_affected_blueprint_understanding(
            index,
            affected_ids=("surface:a",),
            load_shard=shard_payloads.__getitem__,
            load_object=objects.__getitem__,
        )


def test_understanding_preserves_complete_affected_ledger_gap():
    _projection_value, index, shard_payloads, objects = _understanding_fixture(
        blocked=True
    )

    result = read_affected_blueprint_understanding(
        index,
        affected_ids=("behavior:a",),
        load_shard=shard_payloads.__getitem__,
        load_object=objects.__getitem__,
    )

    assert result.status == "blocked"
    assert result.deepest_proven_layer == "implementation_inventory"
    assert result.first_gap is not None
    assert result.first_gap.object_id == "report:behavior"
    assert result.gap_ids == (result.first_gap.gap_id,)
    assert result.gap_count == 1
    assert result.implementation_admitted is False


def test_understanding_preserves_non_code_profile_without_code_admission():
    _projection_value, index, shard_payloads, objects = _understanding_fixture(
        target_profile="non_code_workflow"
    )

    result = read_affected_blueprint_understanding(
        index,
        affected_ids=("surface:a",),
        load_shard=shard_payloads.__getitem__,
        load_object=objects.__getitem__,
    )

    assert result.target_profile == "non_code_workflow"
    assert result.deepest_proven_layer == "model_code_test"
    assert result.gap_count == 0
    assert result.implementation_admitted is False


@pytest.mark.parametrize("missing_kind", ("ledger", "native"))
def test_understanding_rejects_missing_ledger_or_native_object(missing_kind):
    _projection_value, index, shard_payloads, objects = _understanding_fixture()
    if missing_kind == "ledger":
        missing_id = index.ledger_row_ids[-1]
    else:
        row = objects[index.ledger_row_ids[-1]]
        missing_id = row["native_report_object_ids"][0]
    del objects[missing_id]

    with pytest.raises(AffectedBlueprintReadError, match="failed to load"):
        read_affected_blueprint_understanding(
            index,
            affected_ids=("surface:a",),
            load_shard=shard_payloads.__getitem__,
            load_object=objects.__getitem__,
        )


def test_understanding_rejects_hash_drift_before_readiness_derivation():
    _projection_value, index, shard_payloads, objects = _understanding_fixture()
    objects[index.target_object_id] = {
        **objects[index.target_object_id],
        "subject_revision": "revision:drifted",
    }

    with pytest.raises(AffectedBlueprintReadError, match="fingerprint mismatch"):
        read_affected_blueprint_understanding(
            index,
            affected_ids=("surface:a",),
            load_shard=shard_payloads.__getitem__,
            load_object=objects.__getitem__,
        )


def test_understanding_rejects_ledger_omission_even_with_readdressed_target():
    _projection_value, index, shard_payloads, objects = _understanding_fixture()
    target = dict(objects[index.target_object_id])
    target["ledger_row_ids"] = target["ledger_row_ids"][:-1]
    target["referenced_object_ids"] = target["referenced_object_ids"][:-1]
    objects[index.target_object_id] = target
    object_fingerprints = dict(index.object_fingerprints)
    object_fingerprints[index.target_object_id] = fingerprint_value(target)
    index = replace(
        index,
        object_fingerprints=tuple(sorted(object_fingerprints.items())),
    )

    with pytest.raises(AffectedBlueprintReadError, match="omits or reorders"):
        read_affected_blueprint_understanding(
            index,
            affected_ids=("surface:a",),
            load_shard=shard_payloads.__getitem__,
            load_object=objects.__getitem__,
        )


def test_understanding_rejects_plain_projection_instead_of_falling_back():
    projection = _projection(
        shard_payloads={"shard:a": [], "shard:b": []},
        object_payloads={},
    )

    with pytest.raises(
        AffectedBlueprintReadError,
        match="no current affected-read ledger index",
    ):
        read_affected_blueprint_understanding(
            projection,
            affected_ids=("surface:a",),
            load_shard=lambda _item: [],
            load_object=lambda _item: {},
        )


def test_affected_understanding_api_has_one_existing_kernel_owner():
    names = {
        "AffectedBlueprintIndex",
        "AffectedBlueprintUnderstanding",
        "materialize_affected_blueprint_index",
        "read_affected_blueprint_understanding",
    }

    assert names.issubset(
        flowguard.FLOWGUARD_ROUTE_API["model_first_function_flow"]
    )
    for route_id, route_names in flowguard.FLOWGUARD_ROUTE_API.items():
        if route_id != "model_first_function_flow":
            assert names.isdisjoint(route_names), route_id


def test_task_context_resolves_changed_surface_coordinates_and_owner():
    _projection_value, index, shard_payloads, object_payloads = _understanding_fixture(
        blocked=True
    )
    read_result = AffectedBlueprintReader(
        index,
        load_shard=shard_payloads.__getitem__,
        load_object=object_payloads.__getitem__,
    ).read(("surface:a",))

    context = affected_reader_module.build_affected_task_context(
        read_result,
        index,
        changed_paths=("pkg\\module.py",),
        surface_catalog={
            "surface:a": {
                "path": "pkg/module.py",
                "symbol": "run",
                "line_start": 11,
                "line_end": 27,
                "owner_id": "owner:a",
                "content_fingerprint": "sha256:" + "a" * 64,
                "calls": ("surface:b",),
            }
        },
    )

    row = context["selected_change_points"][0]
    assert row["surface_id"] == "surface:a"
    assert row["path"] == "pkg/module.py"
    assert row["symbol"] == "run"
    assert row["line_start"] == 11 and row["line_end"] == 27
    assert row["owner_id"] == "owner:a"
    assert row["evidence_class"] == "observed_structure"
    assert row["calls"] == ["surface:b"]
    assert not any(
        path.get("edge_kind") == "calls"
        for path in context["impact_paths"]
    )


def test_task_context_preserves_structured_contract_and_verified_intent():
    _projection_value, index, shard_payloads, object_payloads = _understanding_fixture(
        blocked=True
    )
    reader_result = AffectedBlueprintReader(
        index,
        load_shard=shard_payloads.__getitem__,
        load_object=object_payloads.__getitem__,
    ).read(("surface:a",))
    objects = dict(reader_result.objects)
    objects["behavior:a"] = {
        "kind": "behavior_block",
        "behavior_block_id": "behavior:a",
        "implementation_surface_id": "surface:a",
        "model_element_id": "model:a",
        "owner_id": "owner:a",
        "owner_contract_id": "contract:a",
        "function_relation": "Input x State -> Set(Output x State)",
        "source_fingerprint": "sha256:" + "b" * 64,
        "dimensions": [
            {"dimension": "input", "semantics": "x is a finite bit"},
            {"dimension": "state", "semantics": "pre-state bit"},
            {"dimension": "output", "semantics": "xor result"},
        ],
        "semantic_spec_ids": ["semantic:a"],
        "oracle_ids": ["oracle:a"],
        "intent_contribution_ids": ["intent:a"],
        "portable_binding_ids": ["binding:a"],
        "referenced_object_ids": [
            "owner:a",
            "intent:a",
            "semantic:a",
            "oracle:a",
            "binding:a",
            "case:a",
        ],
    }
    objects.update(
        {
            "intent:a": {
                "contribution_id": "intent:a",
                "source_kind": "requirement",
                "source_id": "req:a",
                "source_owner_id": "owner:req",
                "source_fingerprint": "sha256:" + "c" * 64,
                "expectation_id": "expect:a",
                "expectation_fingerprint": "sha256:" + "d" * 64,
                "disposition": "accepted",
                "rationale": "accepted finite behavior",
            },
            "semantic:a": {
                "semantic_spec_id": "semantic:a",
                "semantics": {"input": "finite bit"},
            },
            "oracle:a": {
                "oracle_id": "oracle:a",
                "semantics": {"output": "xor"},
            },
            "binding:a": {
                "kind": "portable_behavior_binding",
                "binding_id": "binding:a",
                "behavior_block_id": "behavior:a",
                "input_field_mappings": {"x": "x"},
                "state_field_mappings": {"s": "state"},
                "output_field_mappings": {"y": "result"},
                "invariant_ids": ["invariant:a"],
                "protected_failure_ids": ["failure:a"],
            },
            "case:a": {
                "kind": "behavior_case_contract",
                "case_id": "case:a",
                "behavior_block_id": "behavior:a",
                "case_kind": "good",
                "input_values": {"x": "1"},
                "initial_state": {"s": "0"},
                "expected_output": {"y": "1"},
                "expected_state": {"s": "1"},
                "expected_effects": ["none"],
                "expected_errors": [],
                "oracle_id": "oracle:a",
            },
        }
    )
    rich_result = replace(reader_result, objects=tuple(sorted(objects.items())))
    current_snapshot = "sha256:" + "e" * 64
    with mock.patch(
        "flowguard.model_authority_store.load_current_model_authority_state",
        return_value=SimpleNamespace(
            snapshot=SimpleNamespace(
                fingerprint=current_snapshot,
                subject_revision="revision:accepted",
            ),
            head=SimpleNamespace(
                fingerprint="sha256:" + "f" * 64,
                subject_revision="revision:accepted",
                accepted_revision_set_fingerprint="revision-set:current",
            ),
            accepted_revision=None,
        ),
    ):
        context = affected_reader_module.build_affected_task_context(
            rich_result,
            index,
                accepted_snapshot={
                    "verified": True,
                    "as_of": "revision:accepted",
                    "snapshot_fingerprint": current_snapshot,
                    "authority_head_fingerprint": "sha256:" + "f" * 64,
                    "accepted_revision_set_fingerprint": "revision-set:current",
                    "affected_index_fingerprint": index.fingerprint,
                    "blueprint_fingerprint": index.blueprint_fingerprint,
                    "claim_boundary": "accepted snapshot only",
                },
            authority_root="fixture-root",
        )

    assert context["accepted_intent"][0]["accepted_revision"] == "revision:accepted"
    assert context["accepted_intent"][0]["evidence_class"] == "accepted_contract"
    preserve = context["must_preserve"][0]
    assert preserve["inputs"]["semantics"] == "x is a finite bit"
    assert preserve["case_contracts"][0]["expected_state"] == {"s": "1"}
    assert preserve["oracle_members"][0]["oracle_id"] == "oracle:a"
    assert not any(
        gap["code"] == "accepted_snapshot_unavailable"
        for gap in context["gaps"]
    )


def test_task_context_does_not_trust_caller_verified_snapshot_without_authority():
    _projection_value, index, shard_payloads, object_payloads = _understanding_fixture(
        blocked=True
    )
    reader_result = AffectedBlueprintReader(
        index,
        load_shard=shard_payloads.__getitem__,
        load_object=object_payloads.__getitem__,
    ).read(("surface:a",))
    context = affected_reader_module.build_affected_task_context(
        reader_result,
        index,
        accepted_snapshot={
            "verified": True,
            "status": "verified",
            "as_of": "caller-fake-revision",
            "snapshot_fingerprint": "sha256:" + "c" * 64,
        },
        accepted_snapshot_verified=True,
    )

    assert context["accepted_snapshot"]["status"] == "unavailable"
    assert context["accepted_snapshot"]["verification_reason"] == (
        "authority root was not supplied"
    )
    assert any(
        gap["code"] == "accepted_snapshot_unavailable"
        for gap in context["gaps"]
    )


def test_task_context_binds_verified_snapshot_to_the_loaded_affected_index():
    _projection_value, index, shard_payloads, object_payloads = _understanding_fixture(
        blocked=True
    )
    reader_result = AffectedBlueprintReader(
        index,
        load_shard=shard_payloads.__getitem__,
        load_object=object_payloads.__getitem__,
    ).read(("surface:a",))
    current_snapshot = "sha256:" + "e" * 64
    with mock.patch(
        "flowguard.model_authority_store.load_current_model_authority_state",
        return_value=SimpleNamespace(
            snapshot=SimpleNamespace(
                fingerprint=current_snapshot,
                subject_revision="revision:accepted",
            ),
            head=SimpleNamespace(
                fingerprint="sha256:" + "f" * 64,
                subject_revision="revision:accepted",
                accepted_revision_set_fingerprint="revision-set:current",
            ),
            accepted_revision=None,
        ),
    ):
        context = affected_reader_module.build_affected_task_context(
            reader_result,
            index,
            accepted_snapshot={
                "verified": True,
                "as_of": "revision:accepted",
                "snapshot_fingerprint": current_snapshot,
                "authority_head_fingerprint": "sha256:" + "f" * 64,
                "accepted_revision_set_fingerprint": "revision-set:current",
                "affected_index_fingerprint": "sha256:" + "0" * 64,
                "blueprint_fingerprint": index.blueprint_fingerprint,
            },
            authority_root="fixture-root",
        )

    assert context["accepted_snapshot"]["status"] == "unavailable"
    assert context["accepted_snapshot"]["verification_reason"] == (
        "accepted snapshot affected index fingerprint is stale"
    )
    assert any(
        gap["code"] == "accepted_snapshot_unavailable"
        for gap in context["gaps"]
    )


def test_modified_surface_catalog_cannot_replace_loaded_owner_or_coordinates():
    _projection_value, index, shard_payloads, object_payloads = _understanding_fixture(
        blocked=True
    )
    reader_result = AffectedBlueprintReader(
        index,
        load_shard=shard_payloads.__getitem__,
        load_object=object_payloads.__getitem__,
    ).read(("surface:a",))
    objects = dict(reader_result.objects)
    objects["behavior:a"] = {
        "kind": "behavior_block",
        "behavior_block_id": "behavior:a",
        "implementation_surface_id": "surface:a",
        "owner_id": "owner:canonical",
        "source_fingerprint": "sha256:" + "b" * 64,
    }
    rich_result = replace(reader_result, objects=tuple(sorted(objects.items())))
    context = affected_reader_module.build_affected_task_context(
        rich_result,
        index,
        changed_paths=("wrong/path.py",),
        surface_catalog={
            "_flowguard_catalog_identity": {
                "affected_index_fingerprint": index.fingerprint,
                "blueprint_fingerprint": index.blueprint_fingerprint,
            },
            "surfaces": [
                {
                    "surface_id": "surface:a",
                    "path": "wrong/path.py",
                    "symbol": "wrong_symbol",
                    "owner_id": "owner:caller",
                    "source_fingerprint": "sha256:" + "c" * 64,
                }
            ],
        },
    )

    assert any(
        gap["code"] == "surface_catalog_identity_mismatch"
        for gap in context["gaps"]
    )
    selected = context["selected_change_points"]
    assert not selected
    assert any(gap["code"] == "unknown_change_point" for gap in context["gaps"])


def test_task_context_impact_paths_use_typed_edges_only():
    _projection_value, index, shard_payloads, object_payloads = _understanding_fixture(
        blocked=True
    )
    edge = AffectedTopologyInvalidationEdge(
        source_id="surface:a",
        target_id="surface:b",
        edge_kind="delegates_to",
        evidence_object_ids=("topology:evidence",),
    )
    object_fingerprints = dict(index.object_fingerprints)
    object_fingerprints["topology:evidence"] = fingerprint_value(
        {"kind": "topology-evidence"}
    )
    index = replace(
        index,
        object_fingerprints=tuple(sorted(object_fingerprints.items())),
        topology_invalidation_edges=(edge,),
    )
    read_result = AffectedBlueprintReader(
        index,
        load_shard=shard_payloads.__getitem__,
        load_object=object_payloads.__getitem__,
    ).read(("surface:a",))
    context = affected_reader_module.build_affected_task_context(read_result, index)

    paths = context["impact_paths"]
    assert any(
        row["edge_kind"] == "delegates_to"
        and row["evidence_refs"] == ["topology:evidence"]
        and row["reason"] == "declared delegation dependency"
        for row in paths
    )
    assert all(row["evidence_class"] == "observed_structure" for row in paths)


def test_task_context_impact_paths_use_only_edges_traversed_by_seed_closure():
    _projection, index, shard_payloads, objects = _topology_invalidation_fixture()
    read_result = AffectedBlueprintReader(
        index,
        load_shard=shard_payloads.__getitem__,
        load_object=objects.__getitem__,
    ).read(("surface:child-a",))
    context = affected_reader_module.build_affected_task_context(read_result, index)

    assert all(
        not (
            row["source_id"] == "model:parent"
            and row["target_id"] == "model:child-b"
        )
        for row in context["impact_paths"]
    )
    assert all(
        row["source_id"] != "model:parent"
        or row["target_id"] != "model:child-b"
        for row in context["impact_paths"]
    )


def test_task_context_consumes_reader_reason_paths_without_a_second_bfs():
    _projection, index, shard_payloads, objects = _topology_invalidation_fixture()
    read_result = AffectedBlueprintReader(
        index,
        load_shard=shard_payloads.__getitem__,
        load_object=objects.__getitem__,
    ).read(("surface:child-a",))

    assert read_result.traversed_topology_paths
    with mock.patch.object(
        affected_reader_module,
        "deque",
        side_effect=AssertionError("task context must not run a second BFS"),
    ):
        context = affected_reader_module.build_affected_task_context(
            read_result,
            index,
        )

    assert context["impact_paths"]
    assert not any(
        row["target_id"] == "model:child-b"
        for row in context["impact_paths"]
    )
