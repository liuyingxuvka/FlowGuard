from __future__ import annotations

from types import SimpleNamespace

import pytest

from flowguard.implementation_inventory import ImplementationInventoryAuditReport
from flowguard.project_blueprint import ProjectBlueprintBundle
from flowguard.self_blueprint import FlowGuardSelfBlueprintBundle
from flowguard.target_system_blueprint import (
    CANONICAL_SOFTWARE_LAYER_PLAN,
    BlueprintLayerResult,
    FrozenTargetSystemEvidence,
    ProviderCapabilityBinding,
    TargetSystemDescriptor,
    TargetSystemProviderDeclaration,
    TargetSystemProviderResult,
    build_target_system_provider_registry,
    capture_target_system_snapshot,
    _assemble_target_system_blueprint,
    project_blueprint_understanding,
)
from flowguard.project_blueprint import _project_native_report_refs


def _namespace(**values):
    return SimpleNamespace(**values)


def _project_bundle(**overrides):
    values = {
        "inventory": _namespace(
            inventory_id="inventory:test",
            inventory_fingerprint="sha256:inventory",
            file_dispositions=(),
            surfaces=(),
        ),
        "implementation_inventory_audit": ImplementationInventoryAuditReport(
            ok=True,
            status="complete",
            inventory_fingerprint="sha256:inventory",
            required_surface_ids=(),
            findings=(),
            claim_boundary="aggregate fixture",
        ),
        "binding_report": _namespace(ok=True, fingerprint="sha256:binding", bindings=(), semantic_specs=(), test_evidence_ids=(), oracles=()),
        "manifest": _namespace(blueprint_id="blueprint:test", fingerprint="sha256:manifest", resources=()),
        "qualification": _namespace(
            blueprint_id="blueprint:test",
            static_manifest_status="complete",
            static_manifest_ready=True,
            fingerprint="sha256:qualification",
        ),
        "model_test_alignment_report": _namespace(
            model_id="model:test",
            pre_code_status="ready",
            executed_evidence_status="not_run",
            fingerprint="sha256:mta",
        ),
        "topology_report": _namespace(topology_id="topology:test", ok=True, fingerprint="sha256:topology"),
        "behavior_report": _namespace(
            complete=True,
            pre_code_status="ready",
            executed_evidence_status="not_run",
            fingerprint="sha256:behavior",
            contracts=(),
            coverage_edges=(),
        ),
        "resource_inventory": _namespace(inventory_id="resources:test", complete=True, fingerprint="sha256:resource"),
        "intent_inventory": _namespace(inventory_id="intent:test", complete=True, fingerprint="sha256:intent"),
        "normalized_projection": _namespace(fingerprint="sha256:projection"),
        "static_readiness": _namespace(status="ready", fingerprint="sha256:readiness"),
        "target_system_report": None,
        "understanding_summary": None,
        "normalized_shared_objects": (),
        "test_inventory": _namespace(
            inventory_id="tests:test",
            inventory_fingerprint="sha256:tests",
            nodes=(),
        ),
    }
    refs = _project_native_report_refs(_namespace(**values))
    refs_by_layer = {
        "implementation_inventory": (refs["implementation_inventory"],),
        "traceability": (refs["binding"], refs["topology"]),
        "independent_semantics": (refs["behavior"],),
        "model_code_test": (
            refs["model_test_alignment"],
            refs["test_inventory"],
        ),
        "resource_oracle": (
            refs["resource_inventory"],
            refs["intent_inventory"],
        ),
        "static_blueprint": (
            refs["manifest"],
            refs["qualification"],
            refs["normalized_projection"],
            refs["static_readiness"],
        ),
    }
    descriptor = TargetSystemDescriptor(
        target_system_id="target:test",
        target_kind="software",
        target_profile="software",
        subject_revision="revision:test",
        boundary_fingerprint="sha256:boundary",
        required_observation_capabilities=(),
        required_authority_capabilities=(),
        claim_boundary="aggregate fixture",
    )
    declaration = TargetSystemProviderDeclaration(
        provider_id="provider:test",
        provider_role="observation",
        provider_kind="aggregate_fixture",
        provider_version="1",
        capability_ids=("fixture",),
        claim_boundary="aggregate fixture",
    )
    provider = TargetSystemProviderResult(
        provider_id=declaration.provider_id,
        provider_role=declaration.provider_role,
        provider_kind=declaration.provider_kind,
        provider_version=declaration.provider_version,
        target_system_id=descriptor.target_system_id,
        subject_revision=descriptor.subject_revision,
        capability_ids=declaration.capability_ids,
        input_fingerprints=(("input", "sha256:input"),),
        payload_fingerprints=(("payload", "sha256:payload"),),
        capability_bindings=(
            ProviderCapabilityBinding(
                capability_id="fixture",
                input_ids=("input",),
                payload_ids=("payload",),
            ),
        ),
        claim_boundary="aggregate fixture",
    )
    registry = build_target_system_provider_registry(
        "registry:test", (declaration,)
    )
    snapshot = capture_target_system_snapshot(
        "snapshot:test", descriptor, registry, (provider,)
    )
    frozen = FrozenTargetSystemEvidence(
        evidence_id="frozen:test",
        layer_plan=CANONICAL_SOFTWARE_LAYER_PLAN,
        provider_registry=registry,
        provider_results=(provider,),
        snapshot=snapshot,
        claim_boundary="aggregate fixture",
    )
    target_report = _assemble_target_system_blueprint(
        descriptor,
        frozen,
        downstream_layers=tuple(
            BlueprintLayerResult._derived(
                layer=layer_id,
                status="pass",
                evidence_ids=tuple(
                    row.report_fingerprint for row in refs_by_layer[layer_id]
                ),
                native_reports=refs_by_layer[layer_id],
                pre_code_status="ready",
                executed_evidence_status=(
                    "not_run"
                    if layer_id in {"independent_semantics", "model_code_test"}
                    else "not_applicable"
                ),
            )
            for layer_id in CANONICAL_SOFTWARE_LAYER_PLAN.layer_ids[1:]
        ),
    )
    values["target_system_report"] = target_report
    values["understanding_summary"] = project_blueprint_understanding(target_report)
    values.update(overrides)
    return ProjectBlueprintBundle(**values)


def test_project_bundle_success_is_only_the_canonical_ledger_result():
    bundle = _project_bundle()

    assert bundle.ok
    assert bundle.readiness_ledger.ok
    assert bundle.implementation_admitted


@pytest.mark.parametrize(
    "field,value",
    (
        ("binding_report", _namespace(ok=False, fingerprint="sha256:binding-blocked", bindings=(), semantic_specs=(), test_evidence_ids=(), oracles=())),
        ("model_test_alignment_report", _namespace(model_id="model:test", pre_code_status="blocked", executed_evidence_status="not_run", fingerprint="sha256:mta-blocked")),
        ("topology_report", _namespace(topology_id="topology:test", ok=False, fingerprint="sha256:topology-blocked")),
        ("behavior_report", _namespace(complete=False, pre_code_status="blocked", executed_evidence_status="not_run", fingerprint="sha256:behavior-blocked", contracts=(), coverage_edges=())),
        ("resource_inventory", _namespace(inventory_id="resources:test", complete=False, fingerprint="sha256:resource-blocked")),
        ("intent_inventory", _namespace(inventory_id="intent:test", complete=False, fingerprint="sha256:intent-blocked")),
    ),
)
def test_project_bundle_cannot_omit_a_blocked_native_report(field, value):
    bundle = _project_bundle(**{field: value})

    assert not bundle.ok


def _self_bundle(**overrides):
    project = _project_bundle(**overrides)
    return FlowGuardSelfBlueprintBundle(
        test_inventory=_namespace(
            inventory_id="tests:test",
            inventory_fingerprint="sha256:tests",
            nodes=(),
        ),
        inventory=project.inventory,
        implementation_inventory_audit=project.implementation_inventory_audit,
        binding_report=project.binding_report,
        manifest=project.manifest,
        qualification=project.qualification,
        model_test_alignment_report=project.model_test_alignment_report,
        topology_report=project.topology_report,
        behavior_report=project.behavior_report,
        resource_inventory=project.resource_inventory,
        intent_inventory=project.intent_inventory,
        normalized_projection=project.normalized_projection,
        static_readiness=project.static_readiness,
        target_system_report=project.target_system_report,
        understanding_summary=project.understanding_summary,
        normalized_shared_objects=(),
    )


@pytest.mark.parametrize(
    "field,value",
    (
        ("binding_report", _namespace(ok=False, fingerprint="sha256:binding-blocked", bindings=(), semantic_specs=(), test_evidence_ids=(), oracles=())),
        ("model_test_alignment_report", _namespace(model_id="model:test", pre_code_status="blocked", executed_evidence_status="not_run", fingerprint="sha256:mta-blocked")),
        ("topology_report", _namespace(topology_id="topology:test", ok=False, fingerprint="sha256:topology-blocked")),
        ("resource_inventory", _namespace(inventory_id="resources:test", complete=False, fingerprint="sha256:resource-blocked")),
        ("intent_inventory", _namespace(inventory_id="intent:test", complete=False, fingerprint="sha256:intent-blocked")),
    ),
)
def test_self_bundle_cannot_upgrade_a_blocked_public_child(field, value):
    bundle = _self_bundle(**{field: value})

    assert not bundle.ok
