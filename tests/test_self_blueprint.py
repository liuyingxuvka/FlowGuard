from __future__ import annotations

from dataclasses import dataclass, replace
from types import SimpleNamespace
from unittest import mock

import pytest

from flowguard.blueprint_topology import TOPOLOGY_ROOT_SENTINEL
from flowguard.evidence_receipts import fingerprint_value
from flowguard.implementation_blueprint import BlueprintResourceReference
from flowguard.implementation_inventory import (
    ImplementationFileDisposition,
    ImplementationSurface,
    ImplementationSurfaceInventory,
    SoftwareBoundary,
    implementation_surface_id,
)
from flowguard.implementation_inventory_python import (
    PYTHON_AST_IMPLEMENTATION_ADAPTER_ID,
)
from flowguard.model_authority_store import (
    ModelAuthorityAuditReport,
    ModelAuthorityFinding,
)
from flowguard.model_regressions import (
    CurrentModelRegressionChildEvidence,
    CurrentModelRegressionParentEvidence,
)
from flowguard.model_path_quality import PathQualityResult, PathQualitySubject
from flowguard.self_blueprint import (
    FlowGuardSelfBlueprintError,
    _declared_owner_composite_contracts,
    _discover_surface_declarations,
    _exact_owner_composite_surface,
    _exact_owner_for_path,
    _file_dispositions,
    _flowguard_delegated_assertion_helpers,
    _native_evidence_artifacts,
    _observed_resources,
    _project_owners,
    _require_current_model_authority,
    _load_self_accepted_revision,
    _self_intent_inventory,
    _self_path_quality_bindings,
    _self_topology,
    _self_surface_disposition,
    build_flowguard_self_blueprint,
    capture_flowguard_self_blueprint_build_input_identity,
)
from flowguard.source_identity import source_file_fingerprint
from flowguard.software_blueprint_readiness import (
    IntentSourceAuthority,
    ProjectIntentContribution,
    ProjectIntentInventory,
)


@dataclass(frozen=True)
class _TestNode:
    path: str
    node_id: str
    calls: tuple[str, ...]


@dataclass(frozen=True)
class _TestInventory:
    nodes: tuple[_TestNode, ...]


def _empty_intent_inventory() -> ProjectIntentInventory:
    return ProjectIntentInventory(
        inventory_id="intent-inventory:test",
        subject_revision="fp:snapshot",
        observed_subject_revision="fp:snapshot",
        contributions=(),
        source_authorities=(),
        authority_provider_capabilities=(("provider:test", "intent_lineage"),),
        required_model_target_ids=(),
    )


def _accepted_intent_inventory(
    *target_ids: str,
) -> ProjectIntentInventory:
    contribution = ProjectIntentContribution(
        contribution_id="intent:shared-owner",
        source_kind="openspec_delta",
        source_id="openspec/specs/shared-owner/spec.md",
        source_owner_id="openspec",
        source_fingerprint="fp:intent-source",
        expectation_id="expectation:intent:shared-owner",
        expectation_fingerprint="fp:intent-expectation",
        disposition="accepted",
        target_ids=tuple(target_ids),
        rationale="The accepted intent targets this exact model owner.",
    )
    authority = IntentSourceAuthority(
        source_kind=contribution.source_kind,
        source_id=contribution.source_id,
        source_owner_id=contribution.source_owner_id,
        subject_revision="fp:snapshot",
        current_source_fingerprint=contribution.source_fingerprint,
        expectation_id=contribution.expectation_id,
        current_expectation_fingerprint=contribution.expectation_fingerprint,
        target_ids=contribution.target_ids,
        provider_id="provider:test",
        capability_id="intent_lineage",
        payload_id="intent_lineage",
    )
    return ProjectIntentInventory(
        inventory_id="intent-inventory:test",
        subject_revision="fp:snapshot",
        observed_subject_revision="fp:snapshot",
        contributions=(contribution,),
        source_authorities=(authority,),
        authority_provider_capabilities=(("provider:test", "intent_lineage"),),
        required_model_target_ids=tuple(target_ids),
    )


def _path_quality_pair(
    logical_model_id: str,
    *,
    snapshot_fingerprint: str,
) -> tuple[PathQualitySubject, PathQualityResult]:
    def identity(label: str) -> str:
        return fingerprint_value(
            {"logical_model_id": logical_model_id, "identity": label}
        )

    subject = PathQualitySubject(
        model_id=logical_model_id,
        boundary_id=f"model-boundary:{logical_model_id}",
        model_fingerprint=identity("model-instance"),
        normalized_facts_fingerprint=identity("normalized-facts"),
        retained_element_inventory_fingerprint=identity("retained-elements"),
        purpose_fingerprint=identity("purpose"),
        intent_fingerprint=identity("intent"),
        obligation_fingerprint=identity("obligation"),
        provider_fingerprint=identity("provider"),
        dependency_fingerprint=identity("dependency"),
        code_fingerprint=identity("code"),
        test_fingerprint=identity("test"),
        oracle_fingerprint=identity("oracle"),
        evidence_fingerprint=identity("evidence"),
        currentness_id=snapshot_fingerprint,
    )
    return subject, PathQualityResult(
        result_id=f"path-quality:{logical_model_id}",
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
        necessity_witness_set_fingerprint=identity("necessity-witness-set"),
        detail_evidence_fingerprint=identity("detail-evidence"),
        producer_id="flowguard-self-path-quality",
        currentness_id=snapshot_fingerprint,
    )


def _path_quality_revision(
    pairs: tuple[tuple[PathQualitySubject, PathQualityResult], ...],
    *,
    snapshot_fingerprint: str,
    added_model_ids: tuple[str, ...] = (),
    fingerprint_changed_model_ids: tuple[str, ...] = (),
) -> SimpleNamespace:
    return SimpleNamespace(
        status="accepted",
        candidate_snapshot_fingerprint=snapshot_fingerprint,
        required_path_quality_model_ids=tuple(
            sorted(subject.model_id for subject, _result in pairs)
        ),
        path_quality_subjects=tuple(subject for subject, _result in pairs),
        path_quality_results=tuple(result for _subject, result in pairs),
        added_ids=tuple(
            f"model_instance:model:{model_id}"
            for model_id in added_model_ids
        ),
        fingerprint_changed_ids=tuple(
            f"model_instance:model:{model_id}"
            for model_id in fingerprint_changed_model_ids
        ),
        affected_closure_fingerprint=fingerprint_value(
            {
                "affected_models": sorted(
                    subject.model_id for subject, _result in pairs
                )
            }
        ),
    )


def _path_quality_owners(
    *logical_model_ids: str,
) -> tuple[SimpleNamespace, ...]:
    return tuple(
        SimpleNamespace(
            model_element_id=f"model-obligation:{logical_model_id}",
            model_fingerprint=fingerprint_value(
                {"owner_closure": logical_model_id}
            ),
        )
        for logical_model_id in sorted(logical_model_ids)
    )


def _composite_contract_row(
    owner_id: str,
    surface_key: str,
    entry: dict,
) -> dict:
    purpose = entry["purpose_closure"]
    runner_path = next(
        item for item in reversed(entry["runner"]) if str(item).endswith(".py")
    )
    return {
        "owner_id": owner_id,
        "surface_key": surface_key,
        "contracts": {
            dimension: f"composite-contract:{owner_id}:{dimension}"
            for dimension in (
                "input",
                "state",
                "effect",
                "output",
                "completion",
                "semantics",
            )
        },
        "source_identity": {
            "purpose_source_id": (
                ".flowguard/model-regression-manifest.json"
                f"#model:{owner_id}:purpose-declaration"
            ),
            "purpose_source_owner_id": f"model-purpose-declaration:{owner_id}",
            "model_path": entry["model_path"],
            "model_source_fingerprint": purpose["model_sha256"],
            "runner_path": runner_path,
            "runner_source_fingerprint": purpose["runner_sha256"],
            "purpose_declaration_fingerprint": purpose[
                "declaration_fingerprint"
            ],
            "purpose_closure_fingerprint": purpose["closure_fingerprint"],
        },
    }


def _composite_contracts(
    owner_id: str,
    surface_key: str,
    entry: dict,
):
    return _declared_owner_composite_contracts(
        {
            "composite_behavior_contracts": [
                _composite_contract_row(owner_id, surface_key, entry)
            ]
        },
        {owner_id: entry},
    )


def test_self_blueprint_reports_all_current_authority_blockers(
    tmp_path,
    monkeypatch,
):
    report = ModelAuthorityAuditReport(
        root=str(tmp_path),
        status="blocked",
        findings=(
            ModelAuthorityFinding(
                "blocked",
                "accepted_revision_invalid",
                "required revision evidence leaf receipt cannot be reused "
                "across native owners",
            ),
            ModelAuthorityFinding(
                "blocked",
                "observed_source_inventory_stale",
                "stored observed snapshot differs from live source",
            ),
        ),
    )
    monkeypatch.setattr(
        "flowguard.self_blueprint.audit_model_authority",
        lambda _root: report,
    )

    with pytest.raises(FlowGuardSelfBlueprintError) as exc_info:
        _require_current_model_authority(tmp_path)

    message = str(exc_info.value)
    assert "accepted_revision_invalid" in message
    assert "leaf receipt cannot be reused" in message
    assert "observed_source_inventory_stale" in message


def test_self_blueprint_build_input_identity_is_lightweight_and_content_exact(
    tmp_path,
    monkeypatch,
):
    project_path = tmp_path / ".flowguard" / "project.toml"
    project_path.parent.mkdir(parents=True)
    project_path.write_text(
        "[model_authority]\n"
        'subject_revision = "sha256:subject"\n'
        'observed_snapshot_fingerprint = "sha256:snapshot"\n'
        'accepted_revision_set_fingerprint = "sha256:revision"\n'
        'activation_receipt_fingerprint = "sha256:activation"\n',
        encoding="utf-8",
    )
    report = ModelAuthorityAuditReport(
        root=str(tmp_path),
        status="pass",
        observed_source_revision="sha256:subject",
        observed_snapshot_fingerprint="sha256:snapshot",
    )
    definition = {
        "schema_version": "flowguard.self_blueprint_definition.v5",
        "identity": "definition",
    }
    boundary = SoftwareBoundary(
        boundary_id="boundary:identity",
        subject_revision="sha256:subject",
        production_patterns=("flowguard/**/*.py",),
    )
    file_fingerprint = ["sha256:file-one"]

    def files(*_args, **_kwargs):
        return (
            ImplementationFileDisposition(
                path="flowguard/example.py",
                category="production",
                content_fingerprint=file_fingerprint[0],
                disposition="model_implementation",
                reason="current implementation input",
                requires_adapter=True,
                adapter_id="python-ast-implementation-v1",
            ),
        )

    monkeypatch.setattr(
        "flowguard.self_blueprint._require_current_model_authority",
        lambda _root: report,
    )
    monkeypatch.setattr(
        "flowguard.self_blueprint.load_flowguard_self_blueprint_definition",
        lambda _root: definition,
    )
    monkeypatch.setattr(
        "flowguard.self_blueprint._boundary_from_definition",
        lambda *_args, **_kwargs: (boundary, {}),
    )
    monkeypatch.setattr("flowguard.self_blueprint._file_dispositions", files)
    monkeypatch.setattr(
        "flowguard.self_blueprint._load_json_object",
        lambda _path: {"semantic_mesh": "current"},
    )
    monkeypatch.setattr(
        "flowguard.self_blueprint.resolve_current_full_model_regression_parent",
        lambda _root: _current_model_parent("identity"),
    )

    first = capture_flowguard_self_blueprint_build_input_identity(tmp_path)
    second = capture_flowguard_self_blueprint_build_input_identity(tmp_path)
    file_fingerprint[0] = "sha256:file-two"
    changed = capture_flowguard_self_blueprint_build_input_identity(tmp_path)

    assert first == second
    assert first.fingerprint == second.fingerprint
    assert first.file_count == 1
    assert first.activation_receipt_fingerprint == "sha256:activation"
    assert first.model_regression_evidence_fingerprint
    assert changed.file_inventory_fingerprint != first.file_inventory_fingerprint
    assert changed.fingerprint != first.fingerprint


def test_unknown_source_path_cannot_fall_back_to_the_root_model():
    entries = {"authoritative_model_system": {}}

    with pytest.raises(FlowGuardSelfBlueprintError, match="no exact declared model owner"):
        _exact_owner_for_path(
            "flowguard/unknown_component.py",
            entries=entries,
            overrides={},
        )


def _current_model_parent(*model_ids: str) -> CurrentModelRegressionParentEvidence:
    children = tuple(
        CurrentModelRegressionChildEvidence(
            model_id=model_id,
            receipt_id=f"receipt:validation-owner:model:{model_id}:current",
            receipt_fingerprint=f"fp:receipt:{model_id}",
            model_instance_id=f"model_instance:model:{model_id}",
            model_instance_fingerprint=f"fp:model:{model_id}",
            input_inventory_fingerprint=f"fp:inputs:{model_id}",
            purpose_closure_fingerprint=f"fp:purpose:{model_id}",
        )
        for model_id in model_ids
    )
    return CurrentModelRegressionParentEvidence(
        manifest_fingerprint="fp:manifest",
        parent_artifact_path="model-parents/current.json",
        parent_artifact_fingerprint="fp:parent-artifact",
        parent_execution_receipt_id="receipt:model-regression-parent:current",
        parent_execution_receipt_fingerprint="fp:parent-execution",
        children=children,
    )


def _topology_owner(model_id: str):
    return SimpleNamespace(
        model_element_id=f"model-obligation:{model_id}",
        model_fingerprint=f"fp:model:{model_id}",
        implementation_surface_ids=(),
        portable_invariant_ids=(f"invariant:{model_id}",),
        portable_assumption_ids=(f"assumption:{model_id}",),
        portable_guarantee_ids=(f"guarantee:{model_id}",),
    )


def test_self_topology_consumes_independent_child_receipts_and_progress_evidence():
    model_ids = ("alpha", "beta")
    semantic_mesh = {
        "mesh_id": "mesh:self",
        "semantic_model_status": "complete",
        "semantic_relation_fingerprint": "fp:relations",
        "semantic_parents": (
            {"parent_id": "semantic-parent:root", "purpose": "root"},
            {"parent_id": "semantic-parent:shared", "purpose": "shared"},
        ),
        "models": (
            {
                "model_id": "alpha",
                "structural_parent_id": "semantic-parent:root",
                "cross_boundary_parent_ids": ("semantic-parent:shared",),
                "consumer_ids": ("model:beta",),
                "disposition": "connected",
                "rationale": "alpha owns one side of the feedback boundary",
            },
            {
                "model_id": "beta",
                "structural_parent_id": "semantic-parent:root",
                "cross_boundary_parent_ids": (),
                "consumer_ids": ("model:alpha",),
                "disposition": "connected",
                "rationale": "beta owns the other side of the feedback boundary",
            },
        ),
        "feedback_progress_contracts": (
            {
                "relation_id": "topology:alpha:model-obligation:beta",
                "contract_id": "progress:alpha-beta",
                "contract_kind": "progress_measure",
                "evidence_source_kind": "current_child_model_receipts",
                "evidence_model_ids": model_ids,
                "rationale": "the finite feedback packet must advance or terminate",
            },
            {
                "relation_id": "topology:beta:model-obligation:alpha",
                "contract_id": "progress:alpha-beta",
                "contract_kind": "progress_measure",
                "evidence_source_kind": "current_child_model_receipts",
                "evidence_model_ids": model_ids,
                "rationale": "the finite feedback packet must advance or terminate",
            },
        ),
    }
    (
        nodes,
        relations,
        children,
        reattachments,
        _relation_evidence,
        _refinements,
        current_progress,
        current_children,
    ) = _self_topology(
        semantic_mesh=semantic_mesh,
        owners=tuple(_topology_owner(model_id) for model_id in model_ids),
        entries={
            model_id: {
                "purpose_closure": {
                    "claim_boundary": f"claim:{model_id}",
                    "evidence_check_ids": (f"check:{model_id}",),
                }
            }
            for model_id in model_ids
        },
        inventory=SimpleNamespace(surfaces=()),
        model_regression_evidence=_current_model_parent(*model_ids),
        activation_receipt_fingerprint="fp:activation",
    )

    child_by_id = {child.model_id: child for child in children}
    assert set(child_by_id) == {
        "model-obligation:alpha",
        "model-obligation:beta",
    }
    assert all(child.evidence_current for child in children)
    assert all(not child.not_run_checks for child in children)
    assert all(
        child.validation_evidence == (child.evidence_id,)
        for child in children
    )
    assert dict(current_children) == {
        f"receipt:validation-owner:model:{model_id}:current": (
            f"fp:receipt:{model_id}"
        )
        for model_id in model_ids
    }
    assert len({row.consumed_evidence_id for row in reattachments}) == 2
    node_by_id = {node.node_id: node for node in nodes}
    roots = [
        node
        for node in nodes
        if node.structural_parent_id == TOPOLOGY_ROOT_SENTINEL
    ]
    assert len(roots) == 1
    assert roots[0].node_id == "topology-root:flowguard-self"
    assert {
        node_by_id[parent_id].structural_parent_id
        for parent_id in ("semantic-parent:root", "semantic-parent:shared")
    } == {roots[0].node_id}
    assert node_by_id["model-obligation:alpha"].structural_parent_id == (
        "semantic-parent:root"
    )
    assert node_by_id["model-obligation:alpha"].cross_boundary_parent_ids == (
        "semantic-parent:shared",
    )
    assert node_by_id["model-obligation:beta"].structural_parent_id == (
        "semantic-parent:root"
    )
    assert not node_by_id["model-obligation:beta"].cross_boundary_parent_ids
    feedback = {
        relation.relation_id: relation
        for relation in relations
        if relation.relation_kind == "produces_for"
    }
    assert set(feedback) == {
        "topology:alpha:model-obligation:beta",
        "topology:beta:model-obligation:alpha",
    }
    assert all(relation.progress_contract is not None for relation in feedback.values())
    assert len({relation.progress_contract.evidence_fingerprint for relation in feedback.values()}) == 1
    assert dict(current_progress)["progress:alpha-beta"] == next(
        relation.progress_contract.evidence_fingerprint
        for relation in feedback.values()
    )
    structural_alpha = [
        relation
        for relation in relations
        if relation.producer_id == "model-obligation:alpha"
        and relation.relation_kind == "child_to_parent"
    ]
    cross_alpha = [
        relation
        for relation in relations
        if relation.producer_id == "model-obligation:alpha"
        and relation.relation_kind == "cross_boundary_support"
    ]
    assert len(structural_alpha) == 1
    assert len(cross_alpha) == 1
    semantic_parent_attachments = {
        relation.producer_id: relation.consumer_id
        for relation in relations
        if relation.relation_kind == "delegates_to"
        and relation.producer_id.startswith("semantic-parent:")
    }
    assert semantic_parent_attachments == {
        "semantic-parent:root": roots[0].node_id,
        "semantic-parent:shared": roots[0].node_id,
    }


def test_self_topology_rejects_parent_receipt_reused_as_child_evidence():
    parent = CurrentModelRegressionParentEvidence(
        manifest_fingerprint="fp:manifest",
        parent_artifact_path="model-parents/current.json",
        parent_artifact_fingerprint="fp:parent-artifact",
        parent_execution_receipt_id="receipt:parent",
        parent_execution_receipt_fingerprint="fp:parent",
        children=(
            CurrentModelRegressionChildEvidence(
                model_id="alpha",
                receipt_id="receipt:parent",
                receipt_fingerprint="fp:parent",
            ),
            CurrentModelRegressionChildEvidence(
                model_id="beta",
                receipt_id="receipt:parent",
                receipt_fingerprint="fp:parent",
            ),
        ),
    )
    semantic_mesh = {
        "mesh_id": "mesh:self",
        "semantic_model_status": "complete",
        "semantic_relation_fingerprint": "fp:relations",
        "semantic_parents": (
            {"parent_id": "semantic-parent:root", "purpose": "root"},
        ),
        "models": tuple(
            {
                "model_id": model_id,
                "structural_parent_id": "semantic-parent:root",
                "cross_boundary_parent_ids": (),
                "consumer_ids": (),
                "disposition": "connected",
                "rationale": f"{model_id} owner",
            }
            for model_id in ("alpha", "beta")
        ),
        "feedback_progress_contracts": (),
    }

    with pytest.raises(
        FlowGuardSelfBlueprintError,
        match="unique child receipt identities",
    ):
        _self_topology(
            semantic_mesh=semantic_mesh,
            owners=tuple(
                _topology_owner(model_id) for model_id in ("alpha", "beta")
            ),
            entries={
                model_id: {"purpose_closure": {"claim_boundary": model_id}}
                for model_id in ("alpha", "beta")
            },
            inventory=SimpleNamespace(surfaces=()),
            model_regression_evidence=parent,
            activation_receipt_fingerprint="fp:activation",
        )


def test_self_topology_rejects_foreign_or_missing_semantic_mesh_rows():
    model_ids = ("alpha", "beta")
    semantic_mesh = {
        "mesh_id": "mesh:self",
        "semantic_model_status": "complete",
        "semantic_relation_fingerprint": "fp:relations",
        "semantic_parents": (
            {"parent_id": "semantic-parent:root", "purpose": "root"},
        ),
        "models": (
            {
                "model_id": "alpha",
                "structural_parent_id": "semantic-parent:root",
                "cross_boundary_parent_ids": (),
                "consumer_ids": (),
                "disposition": "connected",
                "rationale": "alpha is the only declared current mesh row",
            },
            {
                "model_id": "retired-owner",
                "structural_parent_id": "semantic-parent:root",
                "cross_boundary_parent_ids": (),
                "consumer_ids": (),
                "disposition": "connected",
                "rationale": "a retired owner must never survive by being skipped",
            },
        ),
        "feedback_progress_contracts": (),
    }

    with pytest.raises(
        FlowGuardSelfBlueprintError,
        match="semantic mesh does not exactly match the owner universe",
    ):
        _self_topology(
            semantic_mesh=semantic_mesh,
            owners=tuple(_topology_owner(model_id) for model_id in model_ids),
            entries={
                model_id: {"purpose_closure": {"claim_boundary": model_id}}
                for model_id in model_ids
            },
            inventory=SimpleNamespace(surfaces=()),
            model_regression_evidence=_current_model_parent(*model_ids),
            activation_receipt_fingerprint="fp:activation",
        )


def test_self_owner_emits_one_exact_contract_per_behavior_surface(tmp_path):
    module = ImplementationSurface(
        surface_id="surface:module",
        path="flowguard/shared_owner.py",
        symbol="<module>",
        surface_kind="module",
        parent_surface_id="",
        content_fingerprint="fp:source",
        structure_fingerprint="fp:module",
        disposition="model_implementation",
    )
    save = ImplementationSurface(
        surface_id="surface:save",
        path="flowguard/shared_owner.py",
        symbol="save",
        surface_kind="function",
        parent_surface_id=module.surface_id,
        content_fingerprint="fp:source",
        structure_fingerprint="fp:save",
        disposition="model_implementation",
        roles=("behavior",),
        parameters=("value",),
        returns_value=True,
    )
    load = ImplementationSurface(
        surface_id="surface:load",
        path="flowguard/shared_owner.py",
        symbol="load",
        surface_kind="function",
        parent_surface_id=module.surface_id,
        content_fingerprint="fp:source",
        structure_fingerprint="fp:load",
        disposition="model_implementation",
        roles=("behavior", "state_writer"),
        parameters=("key", "revision"),
        state_reads=("cache",),
        state_writes=("cache",),
        returns_value=True,
    )
    inventory = ImplementationSurfaceInventory(
        inventory_id="inventory:self-owner-test",
        boundary=SoftwareBoundary(
            boundary_id="boundary:self-owner-test",
            subject_revision="revision:test",
            production_patterns=("src/**/*.py",),
        ),
        manifest_fingerprint="fp:manifest",
        file_dispositions=(),
        surfaces=(module, save, load),
        findings=(),
        claim_boundary="test-only self owner projection",
    )
    entries = {
        "shared_owner": {
            "model_path": ".flowguard/shared_owner/model.py",
            "runner": ("{python}", ".flowguard/shared_owner/run_checks.py"),
            "purpose_closure": {
                "guarded_purpose": "preserve the shared service behavior",
                "model_sha256": "fp:model",
                "runner_sha256": "fp:runner",
                "declaration_fingerprint": "fp:declaration",
                "closure_fingerprint": "fp:closure",
                "task_intent_id": "intent:shared-owner",
                "known_good_case_id": "case:shared-owner:good",
                "protected_failure_ids": ("failure:shared-owner:rejected",),
                "failure_bindings": (
                    {
                        "known_bad_case_id": "case:shared-owner:bad",
                        "failure_id": "failure:shared-owner:rejected",
                    },
                ),
                "evidence_check_ids": ("check:shared-owner",),
            },
        }
    }

    owner = _project_owners(
        tmp_path,
        inventory,
        entries,
        {},
        _composite_contracts(
            "shared_owner",
            "flowguard/shared_owner.py#<module>",
            entries["shared_owner"],
        ),
        _TestInventory(()),
        _accepted_intent_inventory("model-obligation:shared_owner"),
    )[0]

    bindings = {
        binding.behavior_block_id: binding
        for binding in owner.portable_behavior_bindings
    }
    assert set(bindings) == {
        "behavior-block:surface:module",
        "behavior-block:surface:save",
        "behavior-block:surface:load",
    }
    assert dict(bindings["behavior-block:surface:save"].input_field_mappings) == {
        "value": (
            "semantic-member:semantic-spec:model-owner:shared_owner:"
            "surface:save:input:value"
        )
    }
    assert set(
        dict(bindings["behavior-block:surface:load"].input_field_mappings)
    ) == {"key", "revision"}
    assert set(
        dict(bindings["behavior-block:surface:load"].state_field_mappings)
    ) == {"cache"}
    cases_by_block = {
        block_id: {
            case.case_kind
            for case in owner.behavior_case_contracts
            if case.behavior_block_id == block_id
        }
        for block_id in bindings
    }
    assert cases_by_block == {
        "behavior-block:surface:module": {"good", "boundary", "bad"},
        "behavior-block:surface:save": {"good", "boundary"},
        "behavior-block:surface:load": {"good", "boundary"},
    }
    assert bindings["behavior-block:surface:module"].protected_failure_ids == (
        "failure:shared-owner:rejected",
    )
    assert not bindings["behavior-block:surface:save"].protected_failure_ids
    assert not bindings["behavior-block:surface:load"].protected_failure_ids
    composite_providers = dict(
        bindings["behavior-block:surface:module"].provider_fingerprints
    )
    assert composite_providers["composite-input-contract"] == (
        "composite-contract:shared_owner:input"
    )
    assert composite_providers["composite-state-contract"] == (
        "composite-contract:shared_owner:state"
    )
    assert composite_providers["composite-effect-contract"] == (
        "composite-contract:shared_owner:effect"
    )
    assert composite_providers["composite-output-contract"] == (
        "composite-contract:shared_owner:output"
    )
    assert composite_providers["composite-completion-contract"] == (
        "composite-contract:shared_owner:completion"
    )
    assert composite_providers["composite-semantic-contract"] == (
        "composite-contract:shared_owner:semantics"
    )
    assert "provider-declared-composite" not in dict(
        bindings["behavior-block:surface:save"].provider_fingerprints
    )
    assert all(
        case.parameter_case_id == case.case_id
        for case in owner.behavior_case_contracts
    )
    assert {
        case.source_case_id
        for case in owner.behavior_case_contracts
        if case.case_kind == "good"
    } == {"case:shared-owner:good"}
    assert (
        "openspec/specs/shared-owner/spec.md",
        "fp:intent-source",
    ) in owner.semantic_specs[0].provenance_fingerprints


def test_self_composite_registry_fails_closed_without_exact_current_contract():
    entry = {
        "model_path": ".flowguard/shared_owner/model.py",
        "runner": ("{python}", ".flowguard/shared_owner/run_checks.py"),
        "purpose_closure": {
            "model_sha256": "fp:model",
            "runner_sha256": "fp:runner",
            "declaration_fingerprint": "fp:declaration",
            "closure_fingerprint": "fp:closure",
        },
    }
    entries = {"shared_owner": entry}
    row = _composite_contract_row(
        "shared_owner",
        "flowguard/shared_owner.py#<module>",
        entry,
    )

    with pytest.raises(
        FlowGuardSelfBlueprintError,
        match="omits explicit composite behavior contracts",
    ):
        _declared_owner_composite_contracts(
            {"composite_behavior_contracts": []},
            entries,
        )

    foreign = {**row, "owner_id": "foreign_owner"}
    with pytest.raises(FlowGuardSelfBlueprintError, match="foreign owner"):
        _declared_owner_composite_contracts(
            {"composite_behavior_contracts": [foreign]},
            entries,
        )

    stale = {
        **row,
        "source_identity": {
            **row["source_identity"],
            "purpose_closure_fingerprint": "fp:stale",
        },
    }
    with pytest.raises(
        FlowGuardSelfBlueprintError,
        match="source identity is stale or foreign",
    ):
        _declared_owner_composite_contracts(
            {"composite_behavior_contracts": [stale]},
            entries,
        )

    incomplete = {
        **row,
        "contracts": {
            key: value
            for key, value in row["contracts"].items()
            if key != "effect"
        },
    }
    with pytest.raises(
        FlowGuardSelfBlueprintError,
        match="dimensions are incomplete",
    ):
        _declared_owner_composite_contracts(
            {"composite_behavior_contracts": [incomplete]},
            entries,
        )

    wrong_surface_contract = _declared_owner_composite_contracts(
        {
            "composite_behavior_contracts": [
                {
                    **row,
                    "surface_key": "flowguard/foreign.py#<module>",
                }
            ]
        },
        entries,
    )["shared_owner"]
    observed_module = ImplementationSurface(
        surface_id="surface:module",
        path="flowguard/shared_owner.py",
        symbol="<module>",
        surface_kind="module",
        parent_surface_id="",
        content_fingerprint="fp:source",
        structure_fingerprint="fp:module",
        disposition="supporting",
    )
    with pytest.raises(
        FlowGuardSelfBlueprintError,
        match="missing, foreign, or ambiguous",
    ):
        _exact_owner_composite_surface(
            "shared_owner",
            (observed_module,),
            wrong_surface_contract,
        )


def _mock_current_effective_intent_revision(
    model_ids: tuple[str, ...],
    *,
    revision_fingerprint: str,
    snapshot_fingerprint: str,
):
    contributions = tuple(
        SimpleNamespace(
            contribution_id=f"intent:{model_id}",
            decision_state="accepted",
            logical_model_id=f"model:{model_id}",
            unresolved_owner_id="",
            source_kind="design",
            source_ref=f"openspec/specs/{model_id}/spec.md",
            source_fingerprint=f"sha256:source-{model_id}",
            native_owner_id="",
            rationale=f"The complete current design directly owns model {model_id}.",
            fingerprint=f"sha256:contribution-{model_id}",
        )
        for model_id in model_ids
    )
    sources = tuple(
        SimpleNamespace(
            contribution_id=contribution.contribution_id,
            source_ref=contribution.source_ref,
            source_fingerprint=contribution.source_fingerprint,
            native_owner_id=contribution.native_owner_id,
            fingerprint=f"sha256:source-identity-{model_id}",
        )
        for model_id, contribution in zip(model_ids, contributions)
    )
    bindings = tuple(
        SimpleNamespace(
            model_owner_id=f"model-obligation:{model_id}",
            logical_model_id=model_id,
            contribution_ids=(f"intent:{model_id}",),
            fingerprint=f"sha256:owner-binding-{model_id}",
        )
        for model_id in model_ids
    )
    view = SimpleNamespace(
        complete=True,
        fingerprint="sha256:current-effective-intent-view",
        candidate_snapshot_fingerprint=snapshot_fingerprint,
        active_contributions=contributions,
        verified_source_identities=sources,
        model_owner_ids=tuple(binding.model_owner_id for binding in bindings),
        owner_bindings=bindings,
    )
    return SimpleNamespace(
        fingerprint=revision_fingerprint,
        status="accepted",
        candidate_snapshot_fingerprint=snapshot_fingerprint,
        current_effective_intent_view=view,
    )


def test_self_path_quality_projection_is_provider_neutral_and_change_exact():
    snapshot_fingerprint = fingerprint_value({"snapshot": "current"})
    logical_model_ids = ("added", "fingerprint_changed", "unchanged")
    pairs = tuple(
        _path_quality_pair(
            logical_model_id,
            snapshot_fingerprint=snapshot_fingerprint,
        )
        for logical_model_id in logical_model_ids
    )
    revision = _path_quality_revision(
        pairs,
        snapshot_fingerprint=snapshot_fingerprint,
        added_model_ids=("added",),
        fingerprint_changed_model_ids=("fingerprint_changed",),
    )
    owners = _path_quality_owners(*logical_model_ids)

    bindings = _self_path_quality_bindings(
        revision,
        observed_snapshot_fingerprint=snapshot_fingerprint,
        owners=owners,
    )

    by_id = {binding.model_element_id: binding for binding in bindings}
    owner_fingerprints = {
        owner.model_element_id: owner.model_fingerprint for owner in owners
    }
    original_by_id = {
        subject.model_id: (subject, result) for subject, result in pairs
    }
    assert {
        model_id: by_id[f"model-obligation:{model_id}"].change_kind
        for model_id in logical_model_ids
    } == {
        "added": "new",
        "fingerprint_changed": "materially_changed",
        "unchanged": "unchanged",
    }
    for logical_model_id in logical_model_ids:
        binding = by_id[f"model-obligation:{logical_model_id}"]
        original_subject, original_result = original_by_id[logical_model_id]
        assert binding.subject.model_id == binding.model_element_id
        assert (
            binding.subject.model_fingerprint
            == owner_fingerprints[binding.model_element_id]
        )
        assert binding.subject.currentness_id == snapshot_fingerprint
        assert binding.result.currentness_id == snapshot_fingerprint
        assert binding.result.subject_fingerprint == binding.subject.fingerprint
        assert (
            binding.result.detail_evidence_fingerprint
            == original_result.detail_evidence_fingerprint
        )
        assert binding.result.conclusion == original_result.conclusion
        assert binding.result.selected_candidate_lane == ""
        assert original_subject.model_id == logical_model_id
        assert original_subject.model_fingerprint != binding.subject.model_fingerprint
        if logical_model_id == "unchanged":
            assert (
                binding.affected_topology_evidence_fingerprint
                == revision.affected_closure_fingerprint
            )
            assert (
                binding.affected_topology_currentness_id
                == snapshot_fingerprint
            )
        else:
            assert not binding.affected_topology_evidence_fingerprint
            assert not binding.affected_topology_currentness_id


def test_self_path_quality_projection_rejects_missing_result():
    snapshot_fingerprint = fingerprint_value({"snapshot": "current"})
    pair = _path_quality_pair(
        "alpha",
        snapshot_fingerprint=snapshot_fingerprint,
    )
    revision = _path_quality_revision(
        (pair,),
        snapshot_fingerprint=snapshot_fingerprint,
        fingerprint_changed_model_ids=("alpha",),
    )
    revision.path_quality_results = ()

    with pytest.raises(
        FlowGuardSelfBlueprintError,
        match="path-quality material is missing, duplicated, or foreign",
    ):
        _self_path_quality_bindings(
            revision,
            observed_snapshot_fingerprint=snapshot_fingerprint,
            owners=_path_quality_owners("alpha"),
        )


def test_self_path_quality_projection_rejects_foreign_result_subject():
    snapshot_fingerprint = fingerprint_value({"snapshot": "current"})
    alpha_pair = _path_quality_pair(
        "alpha",
        snapshot_fingerprint=snapshot_fingerprint,
    )
    _beta_subject, beta_result = _path_quality_pair(
        "beta",
        snapshot_fingerprint=snapshot_fingerprint,
    )
    revision = _path_quality_revision(
        (alpha_pair,),
        snapshot_fingerprint=snapshot_fingerprint,
        fingerprint_changed_model_ids=("alpha",),
    )
    revision.path_quality_results = (beta_result,)

    with pytest.raises(
        FlowGuardSelfBlueprintError,
        match="path-quality material is missing, duplicated, or foreign",
    ):
        _self_path_quality_bindings(
            revision,
            observed_snapshot_fingerprint=snapshot_fingerprint,
            owners=_path_quality_owners("alpha"),
        )


def test_self_path_quality_projection_rejects_stale_currentness():
    snapshot_fingerprint = fingerprint_value({"snapshot": "current"})
    stale_fingerprint = fingerprint_value({"snapshot": "stale"})
    subject, result = _path_quality_pair(
        "alpha",
        snapshot_fingerprint=snapshot_fingerprint,
    )
    stale_subject = replace(subject, currentness_id=stale_fingerprint)
    stale_result = replace(
        result,
        subject_fingerprint=stale_subject.fingerprint,
        currentness_id=stale_fingerprint,
    )
    revision = _path_quality_revision(
        ((stale_subject, stale_result),),
        snapshot_fingerprint=snapshot_fingerprint,
        fingerprint_changed_model_ids=("alpha",),
    )

    with pytest.raises(
        FlowGuardSelfBlueprintError,
        match="path-quality row is stale or unresolved: alpha",
    ):
        _self_path_quality_bindings(
            revision,
            observed_snapshot_fingerprint=snapshot_fingerprint,
            owners=_path_quality_owners("alpha"),
        )


def test_self_path_quality_projection_rejects_owner_denominator_mismatch():
    snapshot_fingerprint = fingerprint_value({"snapshot": "current"})
    pair = _path_quality_pair(
        "alpha",
        snapshot_fingerprint=snapshot_fingerprint,
    )
    revision = _path_quality_revision(
        (pair,),
        snapshot_fingerprint=snapshot_fingerprint,
        fingerprint_changed_model_ids=("alpha",),
    )

    with pytest.raises(
        FlowGuardSelfBlueprintError,
        match="does not exactly match blueprint owners",
    ):
        _self_path_quality_bindings(
            revision,
            observed_snapshot_fingerprint=snapshot_fingerprint,
            owners=_path_quality_owners("beta"),
        )


def test_self_intent_inventory_consumes_complete_view_and_exact_60_owner_denominator(
    tmp_path,
    monkeypatch,
):
    revision_fingerprint = "sha256:" + "a" * 64
    snapshot_fingerprint = "sha256:" + "b" * 64
    model_ids = tuple(f"model_{index:02d}" for index in range(60))
    revision = _mock_current_effective_intent_revision(
        model_ids,
        revision_fingerprint=revision_fingerprint,
        snapshot_fingerprint=snapshot_fingerprint,
    )
    monkeypatch.setattr(
        "flowguard.self_blueprint._load_json_object",
        lambda _path: {},
    )
    monkeypatch.setattr(
        "flowguard.self_blueprint.ModelRevisionSet",
        SimpleNamespace(from_dict=lambda _payload: revision),
    )

    inventory = _self_intent_inventory(
        tmp_path,
        observed_snapshot_fingerprint=snapshot_fingerprint,
        model_target_ids=tuple(
            f"model-obligation:{model_id}" for model_id in model_ids
        ),
        authority={
            "accepted_revision_set_fingerprint": revision_fingerprint,
        },
    )

    assert inventory.subject_revision == snapshot_fingerprint
    assert inventory.observed_subject_revision == snapshot_fingerprint
    assert inventory.complete
    assert len(inventory.required_model_target_ids) == 60
    assert inventory.required_model_target_ids == tuple(
        f"model-obligation:{model_id}" for model_id in model_ids
    )
    assert {
        contribution.contribution_id: contribution.target_ids
        for contribution in inventory.contributions
    } == {
        f"intent:{model_id}": (f"model-obligation:{model_id}",)
        for model_id in model_ids
    }
    assert all(
        authority.subject_revision == snapshot_fingerprint
        for authority in inventory.source_authorities
    )
    assert all(
        authority.source_owner_id == "flowguard-model-intent-v1"
        and authority.target_ids
        == (
            "model-obligation:"
            + authority.expectation_id.removeprefix("expectation:intent:"),
        )
        for authority in inventory.source_authorities
    )


def test_self_intent_inventory_rejects_owner_missing_from_complete_denominator(
    tmp_path,
    monkeypatch,
):
    revision_fingerprint = "sha256:" + "a" * 64
    snapshot_fingerprint = "sha256:" + "b" * 64
    revision = _mock_current_effective_intent_revision(
        ("alpha",),
        revision_fingerprint=revision_fingerprint,
        snapshot_fingerprint=snapshot_fingerprint,
    )
    monkeypatch.setattr(
        "flowguard.self_blueprint._load_json_object",
        lambda _path: {},
    )
    monkeypatch.setattr(
        "flowguard.self_blueprint.ModelRevisionSet",
        SimpleNamespace(from_dict=lambda _payload: revision),
    )

    with pytest.raises(
        FlowGuardSelfBlueprintError,
        match="owner denominator does not exactly match",
    ):
        _self_intent_inventory(
            tmp_path,
            observed_snapshot_fingerprint=snapshot_fingerprint,
            model_target_ids=(
                "model-obligation:alpha",
                "model-obligation:beta",
            ),
            authority={
                "accepted_revision_set_fingerprint": revision_fingerprint,
            },
        )


def test_self_intent_inventory_never_falls_back_to_a_green_revision_delta(
    tmp_path,
    monkeypatch,
):
    revision_fingerprint = "sha256:" + "a" * 64
    snapshot_fingerprint = "sha256:" + "b" * 64
    revision = SimpleNamespace(
        fingerprint=revision_fingerprint,
        status="accepted",
        candidate_snapshot_fingerprint=snapshot_fingerprint,
        current_effective_intent_view=None,
        intent_review=SimpleNamespace(ok=True),
    )
    monkeypatch.setattr(
        "flowguard.self_blueprint._load_json_object",
        lambda _path: {},
    )
    monkeypatch.setattr(
        "flowguard.self_blueprint.ModelRevisionSet",
        SimpleNamespace(from_dict=lambda _payload: revision),
    )

    with pytest.raises(
        FlowGuardSelfBlueprintError,
        match="no complete current effective intent view",
    ):
        _self_intent_inventory(
            tmp_path,
            observed_snapshot_fingerprint=snapshot_fingerprint,
            model_target_ids=("model-obligation:alpha",),
            authority={
                "accepted_revision_set_fingerprint": revision_fingerprint,
            },
        )


def test_self_intent_inventory_rejects_cross_owner_binding(
    tmp_path,
    monkeypatch,
):
    revision_fingerprint = "sha256:" + "a" * 64
    snapshot_fingerprint = "sha256:" + "b" * 64
    revision = _mock_current_effective_intent_revision(
        ("alpha", "beta"),
        revision_fingerprint=revision_fingerprint,
        snapshot_fingerprint=snapshot_fingerprint,
    )
    alpha_binding, beta_binding = revision.current_effective_intent_view.owner_bindings
    revision.current_effective_intent_view.owner_bindings = (
        SimpleNamespace(
            **{
                **vars(alpha_binding),
                "contribution_ids": ("intent:beta",),
            }
        ),
        SimpleNamespace(
            **{
                **vars(beta_binding),
                "contribution_ids": ("intent:alpha",),
            }
        ),
    )
    monkeypatch.setattr(
        "flowguard.self_blueprint._load_json_object",
        lambda _path: {},
    )
    monkeypatch.setattr(
        "flowguard.self_blueprint.ModelRevisionSet",
        SimpleNamespace(from_dict=lambda _payload: revision),
    )

    with pytest.raises(
        FlowGuardSelfBlueprintError,
        match="cross-bound or uses a fallback owner",
    ):
        _self_intent_inventory(
            tmp_path,
            observed_snapshot_fingerprint=snapshot_fingerprint,
            model_target_ids=(
                "model-obligation:alpha",
                "model-obligation:beta",
            ),
            authority={
                "accepted_revision_set_fingerprint": revision_fingerprint,
            },
        )


def test_self_intent_inventory_rejects_root_fallback_binding(
    tmp_path,
    monkeypatch,
):
    revision_fingerprint = "sha256:" + "a" * 64
    snapshot_fingerprint = "sha256:" + "b" * 64
    revision = _mock_current_effective_intent_revision(
        ("alpha",),
        revision_fingerprint=revision_fingerprint,
        snapshot_fingerprint=snapshot_fingerprint,
    )
    revision.current_effective_intent_view.owner_bindings = (
        SimpleNamespace(
            model_owner_id="root:flowguard",
            logical_model_id="alpha",
            contribution_ids=("intent:alpha",),
            fingerprint="sha256:root-fallback",
        ),
    )
    revision.current_effective_intent_view.model_owner_ids = ("root:flowguard",)
    monkeypatch.setattr(
        "flowguard.self_blueprint._load_json_object",
        lambda _path: {},
    )
    monkeypatch.setattr(
        "flowguard.self_blueprint.ModelRevisionSet",
        SimpleNamespace(from_dict=lambda _payload: revision),
    )

    with pytest.raises(
        FlowGuardSelfBlueprintError,
        match="cross-owner or root fallback",
    ):
        _self_intent_inventory(
            tmp_path,
            observed_snapshot_fingerprint=snapshot_fingerprint,
            model_target_ids=("model-obligation:alpha",),
            authority={
                "accepted_revision_set_fingerprint": revision_fingerprint,
            },
        )


def test_self_owner_materialization_follows_sparse_surface_failure_edges(tmp_path):
    def entry(failure_count: int):
        failure_ids = tuple(
            f"failure:scaled-owner:rejected:{index:03d}"
            for index in range(failure_count)
        )
        return {
            "model_path": ".flowguard/scaled_owner/model.py",
            "runner": ("{python}", ".flowguard/scaled_owner/run_checks.py"),
            "purpose_closure": {
                "guarded_purpose": "preserve every independently declared surface",
                "model_sha256": "fp:model",
                "runner_sha256": "fp:runner",
                "declaration_fingerprint": "fp:declaration",
                "closure_fingerprint": "fp:closure",
                "task_intent_id": "intent:scaled-owner",
                "known_good_case_id": "case:scaled-owner:good",
                "protected_failure_ids": failure_ids,
                "failure_bindings": tuple(
                    {
                        "known_bad_case_id": f"case:scaled-owner:bad:{index:03d}",
                        "failure_id": failure_id,
                    }
                    for index, failure_id in enumerate(failure_ids)
                ),
                "evidence_check_ids": ("check:scaled-owner",),
            },
        }

    def counts(surface_count: int, failure_count: int) -> tuple[int, int, int, int]:
        module = ImplementationSurface(
            surface_id="surface:scaled:module",
            path="flowguard/scaled_owner.py",
            symbol="<module>",
            surface_kind="module",
            parent_surface_id="",
            content_fingerprint="fp:source",
            structure_fingerprint="fp:shape:module",
            disposition="model_implementation",
        )
        detailed_surfaces = tuple(
            ImplementationSurface(
                surface_id=f"surface:scaled:{index:03d}",
                path="flowguard/scaled_owner.py",
                symbol=f"operation_{index:03d}",
                surface_kind="function",
                parent_surface_id="",
                content_fingerprint="fp:source",
                structure_fingerprint=f"fp:shape:{index:03d}",
                disposition="model_implementation",
                roles=("behavior",),
                parameters=("value",),
                state_reads=("state",),
                state_writes=("state",),
                returns_value=True,
            )
            for index in range(surface_count - 1)
        )
        surfaces = (module, *detailed_surfaces)
        inventory = ImplementationSurfaceInventory(
            inventory_id=f"inventory:scaled:{surface_count}",
            boundary=SoftwareBoundary(
                boundary_id="boundary:scaled",
                subject_revision="revision:test",
                production_patterns=("src/**/*.py",),
            ),
            manifest_fingerprint=f"fp:manifest:{surface_count}",
            file_dispositions=(),
            surfaces=surfaces,
            findings=(),
            claim_boundary="synthetic scale projection",
        )
        owner_entry = entry(failure_count)
        owner = _project_owners(
            tmp_path,
            inventory,
            {"scaled_owner": owner_entry},
            {},
            _composite_contracts(
                "scaled_owner",
                "flowguard/scaled_owner.py#<module>",
                owner_entry,
            ),
            _TestInventory(()),
            _empty_intent_inventory(),
        )[0]
        assert {
            binding.behavior_block_id
            for binding in owner.portable_behavior_bindings
        } == {
            f"behavior-block:{surface.surface_id}" for surface in surfaces
        }
        assert all(
            case.parameter_case_id == case.case_id
            and case.source_case_id
            for case in owner.behavior_case_contracts
        )
        composite = next(
            binding
            for binding in owner.portable_behavior_bindings
            if binding.behavior_block_id == "behavior-block:surface:scaled:module"
        )
        assert len(composite.protected_failure_ids) == failure_count
        assert all(
            not binding.protected_failure_ids
            for binding in owner.portable_behavior_bindings
            if binding is not composite
        )
        return (
            len(owner.portable_behavior_bindings),
            len(owner.behavior_case_contracts),
            len(owner.checker_design_fingerprints),
            sum(
                len(binding.input_field_mappings)
                + len(binding.output_field_mappings)
                + len(binding.state_field_mappings)
                for binding in owner.portable_behavior_bindings
            ),
        )

    for surface_count, failure_count in ((12, 1), (24, 2), (48, 4)):
        binding_count, case_count, checker_count, field_count = counts(
            surface_count,
            failure_count,
        )
        expected_cases = 2 * surface_count + failure_count
        assert binding_count == surface_count
        assert case_count == expected_cases
        assert checker_count == 7 * expected_cases
        assert field_count == 3 * (surface_count - 1)


def test_self_surface_classification_keeps_complete_code_map_without_fake_blocks():
    def surface(
        symbol: str,
        *,
        path: str = "flowguard/example.py",
        surface_kind: str = "function",
        roles: tuple[str, ...] = (),
        state_writes: tuple[str, ...] = (),
    ) -> ImplementationSurface:
        return ImplementationSurface(
            surface_id=f"surface:{symbol}",
            path=path,
            symbol=symbol,
            surface_kind=surface_kind,
            parent_surface_id="",
            content_fingerprint="fp:source",
            structure_fingerprint=f"fp:{symbol}",
            disposition="unresolved",
            roles=roles,
            state_writes=state_writes,
        )

    assert _self_surface_disposition(surface("public_api")) == "model_implementation"
    assert _self_surface_disposition(surface("_pure_helper")) == "supporting"
    assert _self_surface_disposition(
        surface("outer.<locals>.inner")
    ) == "supporting"
    assert _self_surface_disposition(
        surface(
            "outer.<locals>.write_state",
            state_writes=("state",),
        )
    ) == "model_implementation"
    assert _self_surface_disposition(
        surface("_hidden_writer", state_writes=("self.state",))
    ) == "model_implementation"
    assert _self_surface_disposition(
        surface("<module>", surface_kind="module")
    ) == "supporting"
    assert _self_surface_disposition(
        surface("main", roles=("entrypoint",))
    ) == "model_implementation"
    assert _self_surface_disposition(
        surface(
            "Example",
            surface_kind="class",
            state_writes=("self.state",),
        )
    ) == "supporting"
    assert _self_surface_disposition(
        surface(
            "build_model",
            path=".flowguard/example/model.py",
            state_writes=("state",),
        )
    ) == "supporting"
    assert _self_surface_disposition(
        surface(
            "run",
            path=".flowguard/example/run_checks.py",
            roles=("entrypoint",),
        )
    ) == "supporting"


def test_self_supporting_surfaces_bind_to_one_deterministic_model_behavior(tmp_path):
    runtime_path = tmp_path / "flowguard" / "example.py"
    model_path = tmp_path / ".flowguard" / "example" / "model.py"
    runtime_path.parent.mkdir(parents=True)
    model_path.parent.mkdir(parents=True)
    runtime_path.write_text(
        "class Helper:\n    pass\n\n"
        "def _pure_helper(value):\n    return value\n\n"
        "def _finite_selector(value):\n"
        "    return tuple(getattr(value, name, None) for name in ('alpha', 'beta'))\n\n"
        "def outer(value):\n"
        "    def inner(item):\n        return item\n"
        "    def write_inner(target, item):\n"
        "        target.value = item\n"
        "        return item\n"
        "    return inner(value)\n\n"
        "def _hidden_writer(target, value):\n"
        "    target.value = value\n"
        "    return value\n",
        encoding="utf-8",
    )
    model_path.write_text(
        "def build_model():\n    return {'state': 'ready'}\n",
        encoding="utf-8",
    )
    files = tuple(
        ImplementationFileDisposition(
            path=relative_path,
            category="production",
            content_fingerprint=source_file_fingerprint(tmp_path / relative_path),
            disposition="model_implementation",
            reason="self owner fixture",
            requires_adapter=True,
            adapter_id=PYTHON_AST_IMPLEMENTATION_ADAPTER_ID,
        )
        for relative_path in (
            "flowguard/example.py",
            ".flowguard/example/model.py",
        )
    )
    entry = {
        "model_path": ".flowguard/example/model.py",
        "runner": ("{python}", ".flowguard/example/run_checks.py"),
        "purpose_closure": {
            "model_sha256": "fp:model",
            "runner_sha256": "fp:runner",
            "declaration_fingerprint": "fp:declaration",
            "closure_fingerprint": "fp:closure",
        },
    }
    composite_contracts = _composite_contracts(
        "example",
        "flowguard/example.py#<module>",
        entry,
    )
    (
        dispositions,
        supporting_owners,
        allowances,
        contracts,
        observations,
    ) = _discover_surface_declarations(
        tmp_path,
        files,
            {
                "bounded_dynamic_prefixes": (),
                "dynamic_allowances": (
                    {
                        "surface_key": "flowguard/example.py#_finite_selector",
                        "operations": ("getattr",),
                        "rationale": "legacy fixture allowance must be superseded",
                    },
                ),
                "dynamic_selector_contracts": [],
            },
        {"example": entry},
        {},
        composite_contracts,
    )
    primary_id = implementation_surface_id(
        "flowguard/example.py",
        "<module>",
        "module",
    )

    assert not allowances
    assert len(contracts) == 1
    assert contracts[0].surface_key == "flowguard/example.py#_finite_selector"
    finite_surface_id = implementation_surface_id(
        "flowguard/example.py",
        "_finite_selector",
        "function",
    )
    assert contracts[0].owner_surface_id == finite_surface_id
    assert contracts[0].operation == "getattr"
    assert contracts[0].selector_values == ("alpha", "beta")
    assert set(observations) == {
        "flowguard/example.py",
        ".flowguard/example/model.py",
    }
    assert supporting_owners
    assert set(supporting_owners.values()) == {primary_id}
    assert dispositions["flowguard/example.py#<module>"] == "model_implementation"
    for symbol in (
        "Helper",
        "_pure_helper",
        "outer.<locals>.inner",
    ):
        key = f"flowguard/example.py#{symbol}"
        assert dispositions[key] == "supporting"
        assert supporting_owners[key] == primary_id
    assert dispositions["flowguard/example.py#_finite_selector"] == (
        "model_implementation"
    )
    assert "flowguard/example.py#_finite_selector" not in supporting_owners
    finite_surface = next(
        surface
        for surface in observations["flowguard/example.py"].surfaces
        if surface.symbol == "_finite_selector"
    )
    assert "dynamic_bounded" in finite_surface.roles
    assert not any(
        finding.code == "dynamic_python_surface"
        and finding.surface_id == finite_surface.surface_id
        for finding in observations["flowguard/example.py"].findings
    )
    hidden_writer_key = "flowguard/example.py#_hidden_writer"
    assert dispositions[hidden_writer_key] == "model_implementation"
    assert hidden_writer_key not in supporting_owners
    nested_writer_key = "flowguard/example.py#outer.<locals>.write_inner"
    assert dispositions[nested_writer_key] == "model_implementation"
    assert nested_writer_key not in supporting_owners


def test_exact_module_owner_and_native_checker_identity_are_preserved():
    entries = {
        "work_context": {
            "runner": ["{python}", ".flowguard/work_context/run_checks.py"],
            "purpose_closure": {
                "evidence_check_ids": ["check:model-regression:work_context"],
                "runner_sha256": "sha256:" + "1" * 64,
            },
        }
    }

    assert _exact_owner_for_path(
        "flowguard/work_context.py",
        entries=entries,
        overrides={},
    ) == "work_context"
    artifact = _native_evidence_artifacts(entries)[0]
    assert artifact.evidence_id == "check:model-regression:work_context"
    assert artifact.artifact_path == ".flowguard/work_context/run_checks.py"
    assert artifact.artifact_fingerprint == "sha256:" + "1" * 64


def test_self_resource_observation_is_independent_from_the_declaration(tmp_path):
    resource_path = tmp_path / "runtime.txt"
    resource_path.write_text("current runtime", encoding="utf-8")
    declaration = BlueprintResourceReference(
        resource_id="resource:flowguard:runtime",
        kind="runtime",
        owner_id="blueprint:flowguard",
        artifact_id="resource-manifest:runtime",
        purpose="declare the runtime resource boundary",
        lifecycle_role="blueprint_input",
        consuming_behavior_ids=("behavior:flowguard",),
        consuming_model_ids=("model:flowguard",),
        artifact_fingerprint="sha256:declared-before-observation",
        semantics=(("requirement", "materialize the runtime manifest"),),
    )

    observed = _observed_resources(
        tmp_path,
        {"resource_groups": {"runtime": ("runtime.txt",)}},
        (declaration,),
        observed_snapshot_fingerprint="sha256:observed-snapshot",
    )[0]

    assert observed.resource_id == declaration.resource_id
    assert observed.subject_revision == "sha256:observed-snapshot"
    assert observed.current_artifact_fingerprint != declaration.artifact_fingerprint
    assert observed.provider_id == "flowguard-resource-manifest-v1"
    assert observed.capability_id == observed.payload_id == "resource_inventory"


def test_self_blueprint_initializes_observed_snapshot_before_resource_observation(
    tmp_path,
    monkeypatch,
):
    snapshot_fingerprint = "sha256:" + "a" * 64
    project_path = tmp_path / ".flowguard" / "project.toml"
    project_path.parent.mkdir(parents=True)
    project_path.write_text(
        "[model_authority]\n"
        'subject_revision = "source-inventory:current"\n'
        f'observed_snapshot_fingerprint = "{snapshot_fingerprint}"\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "flowguard.self_blueprint._require_current_model_authority",
        lambda _root: object(),
    )
    monkeypatch.setattr(
        "flowguard.self_blueprint._load_self_accepted_revision",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(
        "flowguard.self_blueprint.load_flowguard_self_blueprint_definition",
        lambda _root: {
            "owner_overrides": {},
            "composite_behavior_contracts": [],
            "inventory_id": "inventory:test",
            "claim_boundary": "test boundary",
        },
    )
    monkeypatch.setattr(
        "flowguard.self_blueprint.resolve_input_manifest",
        lambda *_args, **_kwargs: (),
    )
    monkeypatch.setattr(
        "flowguard.self_blueprint._boundary_from_definition",
        lambda *_args, **_kwargs: (object(), {}),
    )
    monkeypatch.setattr(
        "flowguard.self_blueprint._file_dispositions",
        lambda *_args, **_kwargs: (),
    )
    monkeypatch.setattr(
        "flowguard.self_blueprint._manifest_entries",
        lambda _root: ({}, {}),
    )
    monkeypatch.setattr(
        "flowguard.self_blueprint._discover_surface_declarations",
        lambda *_args, **_kwargs: ({}, {}, {}, (), ()),
    )
    monkeypatch.setattr(
        "flowguard.self_blueprint.build_implementation_surface_inventory",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(
        "flowguard.self_blueprint._flowguard_test_inventory",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(
        "flowguard.self_blueprint._self_intent_inventory",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(
        "flowguard.self_blueprint._project_owners",
        lambda *_args, **_kwargs: (),
    )
    monkeypatch.setattr(
        "flowguard.self_blueprint._resources",
        lambda *_args, **_kwargs: (),
    )

    class ObservedResourcesBoundaryReached(Exception):
        pass

    captured: list[str] = []

    def observe_resources(
        _root,
        _definition,
        resources,
        *,
        observed_snapshot_fingerprint,
    ):
        assert resources == ()
        captured.append(observed_snapshot_fingerprint)
        raise ObservedResourcesBoundaryReached

    monkeypatch.setattr(
        "flowguard.self_blueprint._observed_resources",
        observe_resources,
    )

    with pytest.raises(ObservedResourcesBoundaryReached):
        build_flowguard_self_blueprint(tmp_path)

    assert captured == [snapshot_fingerprint]


def test_self_blueprint_blocks_before_resource_observation_without_snapshot(
    tmp_path,
    monkeypatch,
):
    project_path = tmp_path / ".flowguard" / "project.toml"
    project_path.parent.mkdir(parents=True)
    project_path.write_text(
        "[model_authority]\n"
        'subject_revision = "source-inventory:current"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "flowguard.self_blueprint._require_current_model_authority",
        lambda _root: object(),
    )
    monkeypatch.setattr(
        "flowguard.self_blueprint.load_flowguard_self_blueprint_definition",
        lambda _root: {},
    )
    observer = mock.Mock()
    monkeypatch.setattr(
        "flowguard.self_blueprint._observed_resources",
        observer,
    )

    with pytest.raises(
        FlowGuardSelfBlueprintError,
        match="observed model authority snapshot fingerprint is missing",
    ):
        build_flowguard_self_blueprint(tmp_path)

    observer.assert_not_called()


def test_non_scanned_self_blueprint_files_use_typed_category_dispositions(tmp_path):
    paths_by_category = {
        "asset": "assets/icon.svg",
        "build": "pyproject.toml",
        "config": "config/settings.toml",
        "data": "data/fixture.json",
        "migration": "migrations/current.json",
        "schema": "schemas/current.json",
        "test_oracle": "tests/fixtures/result.json",
    }
    manifest = []
    for category, relative_path in paths_by_category.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(category, encoding="utf-8")
        manifest.append(
            {
                "path": relative_path,
                "sha256": source_file_fingerprint(path),
            }
        )

    rows = _file_dispositions(
        tmp_path,
        {"scan_python_patterns": (), "scoped_out_patterns": ()},
        {path: category for category, path in paths_by_category.items()},
        resolved_manifest=manifest,
    )

    by_category = {row.category: row for row in rows}
    assert {
        category: row.discovery_not_applicable_kind
        for category, row in by_category.items()
    } == {
        "asset": "non_executable_resource",
        "build": "declarative_no_internal_members",
        "config": "declarative_no_internal_members",
        "data": "non_executable_resource",
        "migration": "declarative_no_internal_members",
        "schema": "declarative_no_internal_members",
        "test_oracle": "independent_test_oracle_surface",
    }
    assert all(row.discovery_not_applicable_reason for row in rows)
    assert all(not row.requires_adapter for row in rows)
    assert by_category["test_oracle"].disposition == "supporting"
    assert "test DNA" in by_category["test_oracle"].discovery_not_applicable_reason


def test_self_helper_discovery_follows_imported_assertion_helpers(tmp_path):
    test_path = tmp_path / "tests" / "test_gate.py"
    helper_path = tmp_path / "flowguard" / "pytest_adapter.py"
    test_path.parent.mkdir(parents=True)
    helper_path.parent.mkdir(parents=True)
    test_path.write_text(
        "from flowguard.pytest_adapter import assert_no_regression\n\n"
        "def test_gate():\n    assert_no_regression(object())\n",
        encoding="utf-8",
    )
    helper_path.write_text(
        "def assert_report_ok(report):\n"
        "    if not report:\n        raise ValueError('failed')\n\n"
        "def assert_no_regression(report):\n    assert_report_ok(report)\n\n"
        "def assert_reraises():\n    raise\n",
        encoding="utf-8",
    )
    inventory = _TestInventory(
        (
            _TestNode(
                "tests/test_gate.py",
                "tests/test_gate.py::test_gate",
                ("assert_no_regression",),
            ),
        )
    )

    helpers = _flowguard_delegated_assertion_helpers(tmp_path, inventory)
    by_leaf = {
        row.helper_id.rsplit("::", 1)[-1].rsplit(".", 1)[-1]: row
        for row in helpers
    }

    assert by_leaf["assert_no_regression"].callee_member_ids == (
        by_leaf["assert_report_ok"].helper_id,
    )
    assert by_leaf["assert_report_ok"].terminal_member_fingerprints
    assert "assert_reraises" not in by_leaf


def test_self_helper_discovery_registers_nested_helpers_without_leaf_collision(
    tmp_path,
):
    test_path = tmp_path / "tests" / "test_nested.py"
    test_path.parent.mkdir(parents=True)
    test_path.write_text(
        "def test_one():\n"
        "    def assert_result(value):\n"
        "        assert value == 1\n"
        "    assert_result(1)\n\n"
        "def test_two():\n"
        "    def assert_result(value):\n"
        "        assert value == 2\n"
        "    assert_result(2)\n",
        encoding="utf-8",
    )
    inventory = _TestInventory(
        (
            _TestNode(
                "tests/test_nested.py",
                "tests/test_nested.py::test_one",
                ("assert_result",),
            ),
            _TestNode(
                "tests/test_nested.py",
                "tests/test_nested.py::test_two",
                ("assert_result",),
            ),
        )
    )

    helpers = _flowguard_delegated_assertion_helpers(tmp_path, inventory)

    assert len(helpers) == 2
    assert len({row.helper_id for row in helpers}) == 2
    assert {row.test_node_id for row in helpers} == {
        "tests/test_nested.py::test_one",
        "tests/test_nested.py::test_two",
    }
    assert all(row.terminal_member_fingerprints for row in helpers)
