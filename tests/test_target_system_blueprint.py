from __future__ import annotations

from flowguard.evidence_receipts import fingerprint_value
from flowguard.target_system_blueprint import (
    BLUEPRINT_LAYER_ORDER,
    BlueprintLayerResult,
    ProviderCapabilityBinding,
    TargetSystemDescriptor,
    TargetSystemProviderDeclaration,
    TargetSystemProviderResult,
    build_target_system_provider_registry,
    capture_target_system_snapshot,
    compile_target_system_blueprint,
    project_blueprint_understanding,
)


SHA_A = fingerprint_value({"fixture": "a"})
SHA_B = fingerprint_value({"fixture": "b"})


def _descriptor(*, kind: str = "workflow") -> TargetSystemDescriptor:
    return TargetSystemDescriptor(
        target_system_id="target:order-approval",
        target_kind=kind,
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
) -> TargetSystemProviderResult:
    return TargetSystemProviderResult(
        provider_id=provider_id,
        provider_role=role,
        provider_kind=kind,
        provider_version="1",
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


def _passing_layers() -> tuple[BlueprintLayerResult, ...]:
    return tuple(
        BlueprintLayerResult(layer=layer, status="pass", evidence_ids=(SHA_A,))
        for layer in BLUEPRINT_LAYER_ORDER[1:]
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


def _whole_report(
    descriptor: TargetSystemDescriptor,
    providers: tuple[TargetSystemProviderResult, ...],
):
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
    return compile_target_system_blueprint(
        descriptor,
        providers,
        downstream_layers=_passing_layers(),
        provider_registry=registry,
        snapshot=snapshot,
    )


def test_non_code_workflow_uses_the_same_provider_neutral_core() -> None:
    report = _whole_report(_descriptor(), _providers())

    assert report.ok
    assert report.descriptor.target_kind == "workflow"
    assert "empirical_reconstruction_status" not in report.to_dict()
    assert all("python" not in row.provider_kind for row in report.provider_results)


def test_fake_javascript_and_mixed_providers_do_not_need_a_python_gate() -> None:
    providers = (
        _provider(
            "provider:javascript-ast",
            "observation",
            ("behavior_inventory",),
            kind="javascript_ast",
        ),
        _provider(
            "provider:http-trace",
            "observation",
            ("test_inventory",),
            kind="runtime_trace",
        ),
        _provider(
            "provider:service-contract",
            "authority",
            ("behavior_semantics", "intent_lineage"),
            kind="service_contract",
        ),
    )

    report = _whole_report(_descriptor(kind="mixed"), providers)

    assert report.ok
    assert {row.provider_kind for row in report.provider_results} == {
        "javascript_ast",
        "runtime_trace",
        "service_contract",
    }


def test_missing_provider_is_an_exact_gap_not_an_unsupported_target() -> None:
    report = compile_target_system_blueprint(
        _descriptor(),
        _providers()[:-1],
        downstream_layers=_passing_layers(),
        scope="affected",
    )

    assert not report.ok
    assert report.layers[0].status == "incomplete"
    assert {row.object_id for row in report.gaps if row.layer == "evidence_qualification"} == {
        "behavior_semantics",
        "intent_lineage",
    }
    assert report.descriptor.target_kind == "workflow"


def test_stale_provider_blocks_later_passing_layers() -> None:
    providers = _providers()[:-1] + (
        _provider(
            "provider:workflow-authority",
            "authority",
            ("behavior_semantics", "intent_lineage"),
            kind="declared_model",
            revision="revision:old",
        ),
    )
    report = compile_target_system_blueprint(
        _descriptor(),
        providers,
        downstream_layers=_passing_layers(),
        scope="affected",
    )

    assert report.layers[0].status == "stale"
    assert all(row.status != "pass" for row in report.layers[1:])
    assert report.deepest_proven_layer == ""


def test_compact_understanding_is_a_read_only_projection() -> None:
    report = compile_target_system_blueprint(
        _descriptor(),
        _providers(),
        downstream_layers=_passing_layers(),
        scope="affected",
    )
    summary = project_blueprint_understanding(
        report,
        affected_surface_ids=("workflow-step:approve",),
    )

    assert summary.scope == "affected"
    assert summary.deepest_proven_layer == "static_blueprint"
    assert summary.first_gap is None
    assert summary.gap_count == 0
    assert "empirical_reconstruction_status" not in summary.to_dict()
    assert summary.affected_surface_ids == ("workflow-step:approve",)


def test_whole_scope_requires_frozen_registry_and_snapshot() -> None:
    report = compile_target_system_blueprint(
        _descriptor(),
        _providers(),
        downstream_layers=_passing_layers(),
    )

    assert not report.ok
    assert report.layers[0].status == "incomplete"
    assert {
        row.object_kind
        for row in report.gaps
        if row.layer == "evidence_qualification"
    } >= {"provider_registry", "target_system_snapshot"}


def test_current_provider_capability_requires_matching_payload_and_input_lineage() -> None:
    providers = list(_providers())
    authority = providers[-1]
    providers[-1] = TargetSystemProviderResult(
        provider_id=authority.provider_id,
        provider_role=authority.provider_role,
        provider_kind=authority.provider_kind,
        provider_version=authority.provider_version,
        target_system_id=authority.target_system_id,
        subject_revision=authority.subject_revision,
        capability_ids=authority.capability_ids,
        input_fingerprints=authority.input_fingerprints,
        payload_fingerprints=(("unrelated_inventory", SHA_B),),
        capability_bindings=tuple(
            ProviderCapabilityBinding(
                capability_id=capability,
                input_ids=("missing_input",),
                payload_ids=("missing_payload",),
            )
            for capability in authority.capability_ids
        ),
        claim_boundary=authority.claim_boundary,
    )

    report = compile_target_system_blueprint(
        _descriptor(),
        tuple(providers),
        downstream_layers=_passing_layers(),
        scope="affected",
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


def test_frozen_registry_and_snapshot_reject_provider_identity_drift() -> None:
    providers = _providers()
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
        _descriptor(),
        registry,
        providers,
    )
    current = compile_target_system_blueprint(
        _descriptor(),
        providers,
        downstream_layers=_passing_layers(),
        provider_registry=registry,
        snapshot=snapshot,
    )
    assert current.ok
    assert current.provider_registry_fingerprint == registry.fingerprint
    assert current.snapshot_fingerprint == snapshot.fingerprint

    drifted = providers[:-1] + (
        _provider(
            "provider:workflow-authority",
            "authority",
            ("behavior_semantics", "intent_lineage"),
            kind="another-authority-kind",
        ),
    )
    blocked = compile_target_system_blueprint(
        _descriptor(),
        drifted,
        downstream_layers=_passing_layers(),
        provider_registry=registry,
        snapshot=snapshot,
    )
    assert not blocked.ok
    assert {
        row.object_kind
        for row in blocked.gaps
        if row.layer == "evidence_qualification"
    } >= {"provider_registration", "target_system_snapshot"}
