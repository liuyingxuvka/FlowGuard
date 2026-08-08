from __future__ import annotations

from dataclasses import replace
import json

import pytest

from flowguard.evidence_receipts import fingerprint_value
from flowguard.model_path_quality import PathQualityResult, PathQualitySubject
from flowguard.target_system_blueprint import (
    CANONICAL_NON_CODE_WORKFLOW_LAYER_PLAN,
    CANONICAL_SOFTWARE_LAYER_PLAN,
    BlueprintLayerResult,
    BlueprintNativeReportRef,
    FrozenTargetSystemEvidence,
    ModelPathQualityBlueprintBinding,
    ProviderCapabilityBinding,
    TargetSystemBlueprintError,
    TargetSystemDescriptor,
    TargetSystemLayerPlan,
    TargetSystemProviderDeclaration,
    TargetSystemProviderResult,
    build_target_system_provider_registry,
    capture_target_system_snapshot,
    _assemble_target_system_blueprint,
    load_target_system_descriptor,
    load_target_system_layer_plan,
    load_target_system_provider_registry,
    load_target_system_provider_result,
    load_target_system_snapshot,
    project_blueprint_understanding,
    serialize_target_system_layer_plan,
    serialize_target_system_descriptor,
    serialize_target_system_provider_registry,
    serialize_target_system_provider_result,
    serialize_target_system_snapshot,
)


SHA_A = fingerprint_value({"fixture": "a"})
SHA_B = fingerprint_value({"fixture": "b"})


def _path_quality_binding(
    *,
    model_id: str = "model:order-approval",
    lane: str = "observed",
    current: bool = True,
) -> ModelPathQualityBlueprintBinding:
    subject = PathQualitySubject(
        model_id=model_id,
        boundary_id=f"path-boundary:{model_id}",
        model_fingerprint=SHA_A,
        normalized_facts_fingerprint=SHA_B,
        retained_element_inventory_fingerprint=SHA_A,
        purpose_fingerprint=SHA_B,
        intent_fingerprint=SHA_A,
        obligation_fingerprint=SHA_B,
        provider_fingerprint=SHA_A,
        dependency_fingerprint=SHA_B,
        code_fingerprint=SHA_A,
        test_fingerprint=SHA_B,
        oracle_fingerprint=SHA_A,
        evidence_fingerprint=SHA_B,
        currentness_id="revision:current",
    )
    result = PathQualityResult(
        result_id=f"path-quality:{model_id}",
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
        necessity_witness_set_fingerprint=SHA_A,
        detail_evidence_fingerprint=SHA_B,
        producer_id="model_maturation",
        currentness_id=subject.currentness_id,
        current=current,
    )
    return ModelPathQualityBlueprintBinding(
        model_element_id=model_id,
        subject_lane=lane,
        change_kind="unchanged",
        subject=subject,
        result=result,
        affected_topology_evidence_fingerprint=SHA_B,
        affected_topology_currentness_id=subject.currentness_id,
    )


def test_layer_status_cannot_be_asserted_through_the_public_value_constructor():
    with pytest.raises(
        TargetSystemBlueprintError,
        match="derived by the native qualifier",
    ):
        BlueprintLayerResult(
            layer="static_blueprint",
            status="pass",
            evidence_ids=("caller:asserted-pass",),
            implementation_admitted=True,
        )


def test_target_blueprint_carries_exact_provider_neutral_path_quality() -> None:
    descriptor = _descriptor()
    providers = _providers()
    binding = _path_quality_binding()
    report = _assemble_target_system_blueprint(
        descriptor,
        _frozen(descriptor, providers),
        downstream_layers=_passing_layers(CANONICAL_SOFTWARE_LAYER_PLAN),
        required_path_quality_model_ids=(binding.model_element_id,),
        path_quality_bindings=(binding,),
    )

    assert report.ok
    assert report.path_quality_bindings == (binding,)
    assert report.to_dict()["path_quality_bindings"][0][
        "compact_current_fingerprint"
    ] == binding.compact_current_fingerprint
    assert report.to_dict()["path_quality_bindings"][0][
        "detail_evidence_fingerprint"
    ] == binding.detail_evidence_fingerprint
    assert ModelPathQualityBlueprintBinding.from_dict(binding.to_dict()) == binding
    summary = project_blueprint_understanding(report)
    assert summary.path_quality_bindings == (binding,)
    assert "python" not in json.dumps(summary.to_dict()).lower()

    missing = _assemble_target_system_blueprint(
        descriptor,
        _frozen(descriptor, providers),
        downstream_layers=_passing_layers(CANONICAL_SOFTWARE_LAYER_PLAN),
        required_path_quality_model_ids=(binding.model_element_id,),
    )
    assert not missing.ok
    assert any(
        gap.object_kind == "model_path_quality_missing"
        and gap.object_id == binding.model_element_id
        for gap in missing.gaps
    )

    stale_binding = replace(
        binding,
        result=replace(binding.result, current=False),
    )
    stale = _assemble_target_system_blueprint(
        descriptor,
        _frozen(descriptor, providers),
        downstream_layers=_passing_layers(CANONICAL_SOFTWARE_LAYER_PLAN),
        required_path_quality_model_ids=(binding.model_element_id,),
        path_quality_bindings=(stale_binding,),
    )
    assert not stale.ok
    assert any(
        gap.object_kind == "model_path_quality_stale"
        for gap in stale.gaps
    )


def test_non_code_workflow_uses_the_same_path_quality_record() -> None:
    descriptor = _descriptor(kind="workflow", profile="non_code_workflow")
    providers = _providers()
    binding = _path_quality_binding(model_id="model:approval-workflow")
    report = _assemble_target_system_blueprint(
        descriptor,
        _frozen(
            descriptor,
            providers,
            plan=CANONICAL_NON_CODE_WORKFLOW_LAYER_PLAN,
        ),
        downstream_layers=_passing_layers(
            CANONICAL_NON_CODE_WORKFLOW_LAYER_PLAN
        ),
        required_path_quality_model_ids=(binding.model_element_id,),
        path_quality_bindings=(binding,),
    )

    assert report.ok
    assert report.target_profile == "non_code_workflow"
    assert report.path_quality_bindings == (binding,)
    assert report.implementation_admitted is False


def _descriptor(
    *,
    kind: str = "software",
    profile: str = "software",
) -> TargetSystemDescriptor:
    return TargetSystemDescriptor(
        target_system_id="target:order-approval",
        target_kind=kind,
        target_profile=profile,
        subject_revision="revision:current",
        boundary_fingerprint=SHA_A,
        required_observation_capabilities=("behavior_inventory", "test_inventory"),
        required_authority_capabilities=("behavior_semantics", "intent_lineage"),
        claim_boundary="the declared order-approval target only",
    )


def _provider(
    provider_id: str,
    role: str,
    capabilities: tuple[str, ...],
    *,
    kind: str,
    revision: str = "revision:current",
    version: str = "1",
) -> TargetSystemProviderResult:
    return TargetSystemProviderResult(
        provider_id=provider_id,
        provider_role=role,
        provider_kind=kind,
        provider_version=version,
        target_system_id="target:order-approval",
        subject_revision=revision,
        capability_ids=capabilities,
        input_fingerprints=(("fixture", SHA_A),),
        payload_fingerprints=tuple(
            (capability, fingerprint_value({"capability": capability}))
            for capability in capabilities
        ),
        capability_bindings=tuple(
            ProviderCapabilityBinding(
                capability_id=capability,
                input_ids=("fixture",),
                payload_ids=(capability,),
            )
            for capability in capabilities
        ),
        claim_boundary="the provider's exact declared fixture",
    )


def _providers() -> tuple[TargetSystemProviderResult, ...]:
    return (
        _provider(
            "provider:declared-workflow",
            "observation",
            ("behavior_inventory",),
            kind="declared_workflow",
        ),
        _provider(
            "provider:workflow-tests",
            "observation",
            ("test_inventory",),
            kind="declared_cases",
        ),
        _provider(
            "provider:workflow-authority",
            "authority",
            ("behavior_semantics", "intent_lineage"),
            kind="declared_model",
        ),
    )


def _frozen(
    descriptor: TargetSystemDescriptor,
    providers: tuple[TargetSystemProviderResult, ...],
    *,
    plan=CANONICAL_SOFTWARE_LAYER_PLAN,
) -> FrozenTargetSystemEvidence:
    registry = build_target_system_provider_registry(
        "registry:workflow",
        tuple(
            TargetSystemProviderDeclaration(
                row.provider_id,
                row.provider_role,
                row.provider_kind,
                row.provider_version,
                row.capability_ids,
                row.claim_boundary,
            )
            for row in providers
        ),
    )
    snapshot = capture_target_system_snapshot(
        "snapshot:workflow",
        descriptor,
        registry,
        providers,
    )
    return FrozenTargetSystemEvidence(
        evidence_id="frozen:workflow",
        layer_plan=plan,
        provider_registry=registry,
        provider_results=providers,
        snapshot=snapshot,
        claim_boundary="pre-established provider artifacts for this fixture",
    )


def _passing_layers(plan) -> tuple[BlueprintLayerResult, ...]:
    return tuple(
        BlueprintLayerResult._derived(
            layer=layer,
            status="pass",
            evidence_ids=(SHA_A,),
            native_reports=(
                BlueprintNativeReportRef(
                    owner_id=f"owner:{layer}",
                    report_id=f"report:{layer}",
                    report_fingerprint=SHA_A,
                ),
            ),
            pre_code_status=(
                "not_applicable"
                if plan.target_profile == "non_code_workflow"
                else "ready"
            ),
            executed_evidence_status="not_run",
        )
        for layer in plan.layer_ids[1:]
    )


def _whole_report(
    descriptor: TargetSystemDescriptor,
    providers: tuple[TargetSystemProviderResult, ...],
    *,
    plan=CANONICAL_SOFTWARE_LAYER_PLAN,
):
    return _assemble_target_system_blueprint(
        descriptor,
        _frozen(descriptor, providers, plan=plan),
        downstream_layers=_passing_layers(plan),
    )


def test_strict_external_artifacts_round_trip_and_compile(tmp_path) -> None:
    descriptor = _descriptor()
    frozen = _frozen(descriptor, _providers())
    result_path = tmp_path / "provider.json"
    registry_path = tmp_path / "registry.json"
    snapshot_path = tmp_path / "snapshot.json"
    plan_path = tmp_path / "plan.json"
    descriptor_path = tmp_path / "descriptor.json"
    result_path.write_bytes(
        serialize_target_system_provider_result(frozen.provider_results[0]) + b"\n"
    )
    registry_path.write_bytes(
        serialize_target_system_provider_registry(frozen.provider_registry) + b"\n"
    )
    snapshot_path.write_bytes(
        serialize_target_system_snapshot(frozen.snapshot) + b"\n"
    )
    plan_path.write_bytes(
        serialize_target_system_layer_plan(frozen.layer_plan) + b"\n"
    )
    descriptor_path.write_bytes(serialize_target_system_descriptor(descriptor) + b"\n")

    loaded = FrozenTargetSystemEvidence(
        evidence_id="frozen:loaded",
        layer_plan=load_target_system_layer_plan(plan_path),
        provider_registry=load_target_system_provider_registry(registry_path),
        provider_results=(
            load_target_system_provider_result(result_path),
            *frozen.provider_results[1:],
        ),
        snapshot=load_target_system_snapshot(snapshot_path),
        claim_boundary="artifacts were loaded before compilation",
    )
    loaded_descriptor = load_target_system_descriptor(descriptor_path)
    report = _assemble_target_system_blueprint(
        loaded_descriptor,
        loaded,
        downstream_layers=_passing_layers(loaded.layer_plan),
    )

    assert report.ok
    assert loaded_descriptor.fingerprint == descriptor.fingerprint
    assert report.layer_plan_fingerprint == loaded.layer_plan.fingerprint
    assert report.target_profile == "software"


@pytest.mark.parametrize(
    "layer_ids",
    (
        ("evidence_qualification",),
        (
            "evidence_qualification",
            "traceability",
            "implementation_inventory",
            "independent_semantics",
            "model_code_test",
            "resource_oracle",
            "static_blueprint",
        ),
    ),
)
def test_profile_plan_cannot_shrink_or_reorder_canonical_layers(layer_ids) -> None:
    descriptor = _descriptor()
    plan = TargetSystemLayerPlan(
        plan_id="target-system-layer-plan:software:tampered",
        target_profile="software",
        layer_ids=layer_ids,
        claim_boundary="A non-canonical plan must remain blocked.",
    )
    report = _assemble_target_system_blueprint(
        descriptor,
        _frozen(descriptor, _providers(), plan=plan),
        downstream_layers=_passing_layers(plan),
    )
    assert not report.ok
    assert not report.implementation_admitted
    assert any(
        gap.object_kind == "target_profile_layer_plan" for gap in report.gaps
    )


@pytest.mark.parametrize(
    ("serializer", "loader", "artifact"),
    (
        (
            serialize_target_system_provider_result,
            load_target_system_provider_result,
            lambda frozen: frozen.provider_results[0],
        ),
        (
            serialize_target_system_provider_registry,
            load_target_system_provider_registry,
            lambda frozen: frozen.provider_registry,
        ),
        (
            serialize_target_system_snapshot,
            load_target_system_snapshot,
            lambda frozen: frozen.snapshot,
        ),
        (
            serialize_target_system_layer_plan,
            load_target_system_layer_plan,
            lambda frozen: frozen.layer_plan,
        ),
    ),
)
def test_strict_loaders_reject_fingerprint_tampering(
    tmp_path, serializer, loader, artifact
) -> None:
    frozen = _frozen(_descriptor(), _providers())
    payload = json.loads(serializer(artifact(frozen)))
    payload["fingerprint"] = "sha256:" + ("0" * 64)
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(TargetSystemBlueprintError, match="fingerprint mismatch"):
        loader(path)


def test_strict_provider_loader_rejects_missing_and_unknown_fields(tmp_path) -> None:
    result = _providers()[0]
    payload = json.loads(serialize_target_system_provider_result(result))
    payload.pop("provider_version")
    path = tmp_path / "missing.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(TargetSystemBlueprintError, match="fields differ"):
        load_target_system_provider_result(path)

    payload = json.loads(serialize_target_system_provider_result(result))
    payload["unexpected"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(TargetSystemBlueprintError, match="fields differ"):
        load_target_system_provider_result(path)


def test_provider_payload_drift_after_freeze_is_not_self_certified() -> None:
    descriptor = _descriptor()
    frozen = _frozen(descriptor, _providers())
    changed = replace(
        frozen.provider_results[-1],
        payload_fingerprints=(("behavior_semantics", SHA_B), ("intent_lineage", SHA_B)),
    )
    drifted = replace(
        frozen,
        provider_results=(*frozen.provider_results[:-1], changed),
    )

    report = _assemble_target_system_blueprint(
        descriptor,
        drifted,
        downstream_layers=_passing_layers(frozen.layer_plan),
    )

    assert not report.ok
    assert "target_system_snapshot" in {gap.object_kind for gap in report.gaps}


def test_provider_version_and_registry_drift_after_freeze_are_visible() -> None:
    descriptor = _descriptor()
    frozen = _frozen(descriptor, _providers())
    changed = replace(frozen.provider_results[-1], provider_version="2")
    drifted = replace(
        frozen,
        provider_results=(*frozen.provider_results[:-1], changed),
    )

    report = _assemble_target_system_blueprint(
        descriptor,
        drifted,
        downstream_layers=_passing_layers(frozen.layer_plan),
    )

    assert not report.ok
    assert {gap.object_kind for gap in report.gaps} >= {
        "provider_registration",
        "target_system_snapshot",
    }


def test_non_code_workflow_uses_only_its_real_profile_layers() -> None:
    descriptor = _descriptor(kind="workflow", profile="non_code_workflow")
    providers = _providers()
    report = _whole_report(
        descriptor,
        providers,
        plan=CANONICAL_NON_CODE_WORKFLOW_LAYER_PLAN,
    )

    assert report.ok
    assert report.target_profile == "non_code_workflow"
    assert "implementation_inventory" not in {row.layer for row in report.layers}
    assert "model_code_test" not in {row.layer for row in report.layers}
    assert report.status == "pass"


def test_workflow_rejects_fabricated_software_profile_plan() -> None:
    descriptor = _descriptor(kind="workflow", profile="non_code_workflow")
    frozen = _frozen(
        descriptor,
        _providers(),
        plan=CANONICAL_SOFTWARE_LAYER_PLAN,
    )
    report = _assemble_target_system_blueprint(
        descriptor,
        frozen,
        downstream_layers=_passing_layers(frozen.layer_plan),
    )

    assert not report.ok
    assert "target_profile" in {gap.object_kind for gap in report.gaps}
    assert report.layers[0].status == "blocked"


def test_missing_required_workflow_layer_blocks_ordered_prefix() -> None:
    descriptor = _descriptor(kind="workflow", profile="non_code_workflow")
    plan = CANONICAL_NON_CODE_WORKFLOW_LAYER_PLAN
    frozen = _frozen(descriptor, _providers(), plan=plan)
    layers = tuple(
        row for row in _passing_layers(plan) if row.layer != "workflow_transitions"
    )
    report = _assemble_target_system_blueprint(
        descriptor,
        frozen,
        downstream_layers=layers,
    )

    assert not report.ok
    transition = next(row for row in report.layers if row.layer == "workflow_transitions")
    assert transition.status == "incomplete"
    assert report.deepest_proven_layer == "workflow_states"
    assert any(
        gap.object_kind == "required_layer" and gap.object_id == "workflow_transitions"
        for gap in report.gaps
    )


def test_undeclared_substitute_layer_cannot_repair_workflow_plan() -> None:
    descriptor = _descriptor(kind="workflow", profile="non_code_workflow")
    plan = CANONICAL_NON_CODE_WORKFLOW_LAYER_PLAN
    frozen = _frozen(descriptor, _providers(), plan=plan)
    report = _assemble_target_system_blueprint(
        descriptor,
        frozen,
        downstream_layers=(
            *_passing_layers(plan),
            BlueprintLayerResult._derived(
                layer="static_blueprint",
                status="pass",
                evidence_ids=(SHA_A,),
            ),
        ),
    )

    assert not report.ok
    assert any(
        gap.object_kind == "undeclared_layer" and gap.object_id == "static_blueprint"
        for gap in report.gaps
    )


def test_missing_provider_remains_an_exact_capability_gap() -> None:
    descriptor = _descriptor()
    providers = _providers()
    frozen = _frozen(descriptor, providers)
    missing = replace(frozen, provider_results=providers[:-1])
    report = _assemble_target_system_blueprint(
        descriptor,
        missing,
        downstream_layers=_passing_layers(frozen.layer_plan),
        scope="affected",
    )

    assert not report.ok
    assert {row.object_id for row in report.gaps if row.object_kind.endswith("provider_capability")} == {
        "behavior_semantics",
        "intent_lineage",
    }


def test_stale_provider_blocks_later_passing_layers() -> None:
    descriptor = _descriptor()
    frozen = _frozen(descriptor, _providers())
    stale = replace(
        frozen.provider_results[-1],
        subject_revision="revision:old",
    )
    evidence = replace(
        frozen,
        provider_results=(*frozen.provider_results[:-1], stale),
    )
    report = _assemble_target_system_blueprint(
        descriptor,
        evidence,
        downstream_layers=_passing_layers(frozen.layer_plan),
        scope="affected",
    )

    assert report.layers[0].status == "stale"
    assert all(row.status != "pass" for row in report.layers[1:])
    assert report.deepest_proven_layer == ""


def test_compact_understanding_uses_exact_plan_order_and_final_status() -> None:
    descriptor = _descriptor(kind="workflow", profile="non_code_workflow")
    report = _whole_report(
        descriptor,
        _providers(),
        plan=CANONICAL_NON_CODE_WORKFLOW_LAYER_PLAN,
    )
    summary = project_blueprint_understanding(
        report,
        affected_surface_ids=("workflow-step:approve",),
    )

    assert summary.status == "pass"
    assert summary.target_profile == "non_code_workflow"
    assert summary.layer_plan_fingerprint == report.layer_plan_fingerprint
    assert tuple(layer for layer, _status in summary.layer_statuses) == tuple(
        row.layer for row in report.layers
    )
    assert summary.deepest_proven_layer == "workflow_verification"
    assert summary.first_gap is None
    assert summary.affected_surface_ids == ("workflow-step:approve",)
    assert summary.implementation_admitted is False
    payload = summary.to_dict()
    assert [row["layer"] for row in payload["layer_statuses"]] == [
        row.layer for row in report.layers
    ]
    assert payload["affected_ids"] == ["workflow-step:approve"]
    assert "affected_surface_ids" not in payload


def test_software_readiness_ledger_carries_exact_native_reports_and_admission() -> None:
    report = _whole_report(_descriptor(), _providers())
    ledger = report.readiness_ledger

    assert ledger.ok
    assert ledger.implementation_admitted is True
    assert ledger.executed_evidence_status == "not_run"
    assert ledger.rows[-1].implementation_admitted is True
    assert ledger.rows[1].native_reports == (
        BlueprintNativeReportRef(
            owner_id="owner:implementation_inventory",
            report_id="report:implementation_inventory",
            report_fingerprint=SHA_A,
        ),
    )
    assert project_blueprint_understanding(report).implementation_admitted is True


def test_passing_layer_without_exact_native_report_identity_is_an_integrity_gap() -> None:
    descriptor = _descriptor()
    frozen = _frozen(descriptor, _providers())
    layers = list(_passing_layers(frozen.layer_plan))
    layers[0] = replace(layers[0], native_reports=())

    report = _assemble_target_system_blueprint(
        descriptor,
        frozen,
        downstream_layers=tuple(layers),
    )

    assert not report.ok
    assert report.deepest_proven_layer == "evidence_qualification"
    assert any(
        gap.object_kind == "native_report_identity"
        and gap.object_id == "implementation_inventory"
        for gap in report.gaps
    )


def test_not_run_execution_evidence_does_not_turn_static_design_into_failure() -> None:
    report = _whole_report(_descriptor(), _providers())

    assert report.ok
    assert report.readiness_ledger.pre_code_status == "ready"
    assert report.readiness_ledger.executed_evidence_status == "not_run"
    assert report.readiness_ledger.implementation_admitted is True


def test_current_provider_capability_requires_matching_payload_and_input_lineage() -> None:
    descriptor = _descriptor()
    frozen = _frozen(descriptor, _providers())
    authority = frozen.provider_results[-1]
    changed = replace(
        authority,
        payload_fingerprints=(("unrelated_inventory", SHA_B),),
        capability_bindings=tuple(
            ProviderCapabilityBinding(
                capability_id=capability,
                input_ids=("missing_input",),
                payload_ids=("missing_payload",),
            )
            for capability in authority.capability_ids
        ),
    )
    report = _assemble_target_system_blueprint(
        descriptor,
        replace(
            frozen,
            provider_results=(*frozen.provider_results[:-1], changed),
        ),
        downstream_layers=_passing_layers(frozen.layer_plan),
    )

    assert not report.ok
    assert {
        row.object_id
        for row in report.gaps
        if row.object_kind == "provider_capability_lineage"
    } == {
        "provider:workflow-authority:behavior_semantics",
        "provider:workflow-authority:intent_lineage",
    }
