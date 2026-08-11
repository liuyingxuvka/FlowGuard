from types import SimpleNamespace

import pytest

from flowguard.evidence_receipts import fingerprint_value
from flowguard.target_system_blueprint import (
    CANONICAL_SOFTWARE_LAYER_PLAN,
    TargetSystemBlueprintError,
    TargetSystemDnaQualification,
    TargetSystemProviderDeclaration,
    TargetSystemProviderProfileDeclaration,
    TargetSystemProviderProfileRegistry,
    TargetSystemProviderRegistry,
    load_target_system_provider_profile_registry,
    qualify_target_system_dna,
    serialize_target_system_provider_profile_registry,
    validate_target_system_provider_profiles,
)


def _provider_registry() -> TargetSystemProviderRegistry:
    return TargetSystemProviderRegistry(
        registry_id="providers:test",
        declarations=(
            TargetSystemProviderDeclaration(
                provider_id="provider:test",
                provider_role="observation",
                provider_kind="neutral-observer",
                provider_version="1",
                capability_ids=("observation",),
                claim_boundary="test provider only",
            ),
        ),
    )


def _profile_registry() -> TargetSystemProviderProfileRegistry:
    return TargetSystemProviderProfileRegistry(
        registry_id="profiles:test",
        declarations=(
            TargetSystemProviderProfileDeclaration(
                provider_id="provider:test",
                target_profile=CANONICAL_SOFTWARE_LAYER_PLAN.target_profile,
                target_kind="external",
                layer_plan_id=CANONICAL_SOFTWARE_LAYER_PLAN.plan_id,
                layer_plan_fingerprint=CANONICAL_SOFTWARE_LAYER_PLAN.fingerprint,
                owner_id="owner:test",
                claim_boundary="test profile only",
            ),
        ),
    )


def test_profile_registry_binds_to_existing_provider_and_plan_authorities() -> None:
    profiles = _profile_registry()
    validate_target_system_provider_profiles(
        profiles,
        _provider_registry(),
        (CANONICAL_SOFTWARE_LAYER_PLAN,),
    )
    assert TargetSystemProviderProfileRegistry.from_dict(profiles.to_dict()) == profiles


def test_profile_registry_rejects_unknown_provider_or_stale_plan() -> None:
    profiles = _profile_registry()
    unknown = TargetSystemProviderProfileRegistry(
        registry_id="profiles:unknown",
        declarations=(
            TargetSystemProviderProfileDeclaration(
                provider_id="provider:missing",
                target_profile="software",
                target_kind="external",
                layer_plan_id=CANONICAL_SOFTWARE_LAYER_PLAN.plan_id,
                layer_plan_fingerprint=CANONICAL_SOFTWARE_LAYER_PLAN.fingerprint,
                owner_id="owner:test",
                claim_boundary="test profile only",
            ),
        ),
    )
    with pytest.raises(TargetSystemBlueprintError, match="unregistered provider"):
        validate_target_system_provider_profiles(
            unknown,
            _provider_registry(),
            (CANONICAL_SOFTWARE_LAYER_PLAN,),
        )

    stale = TargetSystemProviderProfileRegistry(
        registry_id="profiles:stale",
        declarations=(
            TargetSystemProviderProfileDeclaration(
                provider_id="provider:test",
                target_profile="software",
                target_kind="external",
                layer_plan_id=CANONICAL_SOFTWARE_LAYER_PLAN.plan_id,
                layer_plan_fingerprint=fingerprint_value({"stale": True}),
                owner_id="owner:test",
                claim_boundary="test profile only",
            ),
        ),
    )
    with pytest.raises(TargetSystemBlueprintError, match="fingerprint is stale"):
        validate_target_system_provider_profiles(
            stale,
            _provider_registry(),
            (CANONICAL_SOFTWARE_LAYER_PLAN,),
        )


def test_profile_registry_serialization_is_current_only(tmp_path) -> None:
    path = tmp_path / "profiles.json"
    path.write_bytes(serialize_target_system_provider_profile_registry(_profile_registry()))
    loaded = load_target_system_provider_profile_registry(path)
    assert loaded.fingerprint == _profile_registry().fingerprint


def _report(*, ok: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        ok=ok,
        status="pass" if ok else "blocked",
        target_profile="software",
        descriptor=SimpleNamespace(target_system_id="target:test"),
    )


def test_candidate_semantic_mesh_cannot_claim_qualified_dna() -> None:
    result = qualify_target_system_dna(
        _report(),
        qualification_id="qualification:test",
        semantic_status="candidate_defined_not_verified",
        semantic_evidence_fingerprint="fp:semantic",
        semantic_binding_current=False,
        code_binding_status="current",
        code_binding_fingerprint="fp:code",
        test_binding_status="current",
        test_binding_fingerprint="fp:test",
    )
    assert result.status == "blocked"
    assert not result.qualified
    assert result.semantic_status == "candidate"
    assert "semantic:candidate_defined_not_verified" in result.reasons
    assert TargetSystemDnaQualification.from_dict(result.to_dict()) == result


def test_fully_current_bindings_are_explicitly_qualified() -> None:
    result = qualify_target_system_dna(
        _report(),
        qualification_id="qualification:test",
        semantic_status="current",
        semantic_evidence_fingerprint="fp:semantic",
        semantic_binding_current=True,
        code_binding_status="current",
        code_binding_fingerprint="fp:code",
        test_binding_status="current",
        test_binding_fingerprint="fp:test",
    )
    assert result.status == "qualified"
    assert result.qualified
    assert result.reasons == ()
