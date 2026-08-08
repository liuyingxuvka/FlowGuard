from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from flowguard.evidence_receipts import (
    EvidenceReceipt,
    ReceiptVerificationContext,
    ReceiptVerificationResult,
    build_environment_fingerprint,
    fingerprint_value,
    snapshot_bytes,
    verify_evidence_receipt,
)
from flowguard.portable_model import (
    PortableModel,
    PortableInvariant,
    PortableState,
    PortableTemporalObligation,
    PortableTransition,
    RefinementBinding,
)
from flowguard.target_native_qualification import (
    TARGET_NATIVE_INTENT_SOURCE_KINDS,
    TargetBlueprintNativeReportSet,
    TargetNativeMember,
    TargetNativeModelRef,
    load_target_blueprint_native_report_set,
    qualify_target_system_from_native_reports,
    serialize_target_blueprint_native_report_set,
    target_native_test_obligation_id,
)
from flowguard.target_system_blueprint import (
    CANONICAL_NON_CODE_WORKFLOW_LAYER_PLAN,
    CANONICAL_SOFTWARE_LAYER_PLAN,
    BlueprintLayerResult,
    BlueprintNativeReportRef,
    FrozenTargetSystemEvidence,
    ProviderCapabilityBinding,
    TargetSystemDescriptor,
    TargetSystemBlueprintError,
    TargetSystemLayerPlan,
    TargetSystemProviderDeclaration,
    TargetSystemProviderResult,
    build_target_system_provider_registry,
    capture_target_system_snapshot,
    _assemble_target_system_blueprint,
    load_frozen_target_system_evidence,
    project_blueprint_understanding,
    serialize_frozen_target_system_evidence,
)
from flowguard.validation_ownership import ValidationOwnerContract


def _tree_state(root: Path) -> tuple[tuple[str, str, int, int, str], ...]:
    """Capture target-owned names, contents, and modification identities."""

    rows: list[tuple[str, str, int, int, str]] = []
    for path in (root, *sorted(root.rglob("*"))):
        stat = path.stat()
        relative = "." if path == root else path.relative_to(root).as_posix()
        if path.is_dir():
            rows.append((relative, "directory", stat.st_size, stat.st_mtime_ns, ""))
        else:
            rows.append(
                (
                    relative,
                    "file",
                    stat.st_size,
                    stat.st_mtime_ns,
                    fingerprint_value({"bytes_hex": path.read_bytes().hex()}),
                )
            )
    return tuple(rows)


def _fingerprints(values: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    return tuple(
        (identity, fingerprint_value(value))
        for identity, value in sorted(values.items())
    )


def _provider(
    *,
    provider_id: str,
    provider_role: str,
    provider_kind: str,
    target_system_id: str,
    subject_revision: str,
    inputs: Mapping[str, Any],
    payloads: Mapping[str, Any],
    bindings: Mapping[str, tuple[tuple[str, ...], tuple[str, ...]]],
) -> TargetSystemProviderResult:
    return TargetSystemProviderResult(
        provider_id=provider_id,
        provider_role=provider_role,
        provider_kind=provider_kind,
        provider_version="synthetic-v1",
        target_system_id=target_system_id,
        subject_revision=subject_revision,
        capability_ids=tuple(bindings),
        input_fingerprints=_fingerprints(inputs),
        payload_fingerprints=_fingerprints(payloads),
        capability_bindings=tuple(
            ProviderCapabilityBinding(
                capability_id=capability_id,
                input_ids=input_ids,
                payload_ids=payload_ids,
            )
            for capability_id, (input_ids, payload_ids) in bindings.items()
        ),
        claim_boundary="Only the explicitly fingerprinted target inputs and payloads.",
    )


def _freeze(
    *,
    descriptor: TargetSystemDescriptor,
    plan: TargetSystemLayerPlan,
    providers: tuple[TargetSystemProviderResult, ...],
    label: str,
) -> FrozenTargetSystemEvidence:
    registry = build_target_system_provider_registry(
        f"registry:{label}",
        tuple(
            TargetSystemProviderDeclaration(
                provider_id=provider.provider_id,
                provider_role=provider.provider_role,
                provider_kind=provider.provider_kind,
                provider_version=provider.provider_version,
                capability_ids=provider.capability_ids,
                claim_boundary=provider.claim_boundary,
            )
            for provider in providers
        ),
    )
    snapshot = capture_target_system_snapshot(
        f"snapshot:{label}", descriptor, registry, providers
    )
    return FrozenTargetSystemEvidence(
        evidence_id=f"frozen:{label}",
        layer_plan=plan,
        provider_registry=registry,
        provider_results=providers,
        snapshot=snapshot,
        claim_boundary="Frozen before target-system blueprint compilation.",
    )


def _passing_layers(
    plan: TargetSystemLayerPlan, *, label: str
) -> tuple[BlueprintLayerResult, ...]:
    rows = []
    for layer_id in plan.layer_ids[1:]:
        fingerprint = fingerprint_value(
            {"acceptance": label, "layer": layer_id}
        )
        rows.append(
            BlueprintLayerResult._derived(
                layer=layer_id,
                status="pass",
                evidence_ids=(fingerprint,),
                native_reports=(
                    BlueprintNativeReportRef(
                        owner_id=f"acceptance-owner:{layer_id}",
                        report_id=f"acceptance-report:{label}:{layer_id}",
                        report_fingerprint=fingerprint,
                    ),
                ),
                pre_code_status=(
                    "ready"
                    if plan.target_profile == "software"
                    else "not_applicable"
                ),
                executed_evidence_status="not_applicable",
            )
        )
    return tuple(rows)


def _minimal_software_case(*, missing_provider_capability: str = ""):
    target_system_id = "target:public-negative-fixture"
    subject_revision = "revision:public-negative-v1"
    observed_payloads = {
        "implementation_inventory": {"surface": "service#run"},
        "resource_inventory": {"resource": "service-config"},
        "test_inventory": {"test": "service-test#run"},
    }
    authority_payloads = {
        "behavior_semantics": {"transition": "idle->done"},
        "intent_lineage": {"source": "user-objective:current"},
    }
    observation = _provider(
        provider_id="provider:public-negative-observer",
        provider_role="observation",
        provider_kind="synthetic.provider-neutral.observer",
        target_system_id=target_system_id,
        subject_revision=subject_revision,
        inputs={"observed_target": observed_payloads},
        payloads=observed_payloads,
        bindings={
            capability: (("observed_target",), (capability,))
            for capability in observed_payloads
        },
    )
    authority = _provider(
        provider_id="provider:public-negative-authority",
        provider_role="authority",
        provider_kind="synthetic.provider-neutral.authority",
        target_system_id=target_system_id,
        subject_revision=subject_revision,
        inputs={"declared_target": authority_payloads},
        payloads=authority_payloads,
        bindings={
            capability: (("declared_target",), (capability,))
            for capability in authority_payloads
        },
    )
    required_observation = tuple(observed_payloads)
    if missing_provider_capability:
        required_observation = (
            *required_observation,
            missing_provider_capability,
        )
    descriptor = TargetSystemDescriptor(
        target_system_id=target_system_id,
        target_kind="software",
        target_profile="software",
        subject_revision=subject_revision,
        boundary_fingerprint=fingerprint_value(
            {"target_system_id": target_system_id, "revision": subject_revision}
        ),
        required_observation_capabilities=required_observation,
        required_authority_capabilities=tuple(authority_payloads),
        claim_boundary="Only the synthetic provider-neutral public fixture.",
    )
    frozen = _freeze(
        descriptor=descriptor,
        plan=CANONICAL_SOFTWARE_LAYER_PLAN,
        providers=(observation, authority),
        label="public-negative-fixture",
    )
    return descriptor, frozen


def _compile_whole_and_affected(
    descriptor: TargetSystemDescriptor,
    frozen: FrozenTargetSystemEvidence,
    *,
    label: str,
):
    layers = _passing_layers(frozen.layer_plan, label=label)
    return {
        scope: _assemble_target_system_blueprint(
            descriptor,
            frozen,
            downstream_layers=layers,
            scope=scope,
        )
        for scope in ("whole", "affected")
    }


def _json_values(values: tuple[Any, ...]) -> list[Any]:
    """Return deterministic unique JSON values for synthetic typed ports."""

    by_fingerprint = {fingerprint_value(value): value for value in values}
    return [by_fingerprint[key] for key in sorted(by_fingerprint)]


def _related_member_ids(
    members_by_kind: Mapping[str, tuple[tuple[str, tuple[str, ...]], ...]],
    kind: str,
    behavior_ids: tuple[str, ...],
) -> list[str]:
    expected = set(behavior_ids)
    return sorted(
        member_id
        for member_id, related_behavior_ids in members_by_kind.get(kind, ())
        if expected.intersection(related_behavior_ids)
    )


def _related_transition_ids(
    *,
    behavior_ids: tuple[str, ...],
    model: PortableModel,
    transition_overrides: Mapping[str, tuple[str, ...]],
) -> tuple[str, ...]:
    transition_ids: set[str] = set()
    for behavior_id in behavior_ids:
        transition_ids.update(
            transition_overrides.get(
                behavior_id,
                tuple(row.transition_id for row in model.transitions),
            )
        )
    return tuple(sorted(transition_ids))


def _native_member_details(
    *,
    target_system_id: str,
    target_profile: str,
    evidence_role: str,
    member_id: str,
    member_kind: str,
    behavior_ids: tuple[str, ...],
    subject_revision: str,
    model: PortableModel,
    members_by_kind: Mapping[str, tuple[tuple[str, tuple[str, ...]], ...]],
    transition_overrides: Mapping[str, tuple[str, ...]],
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    transition_ids = _related_transition_ids(
        behavior_ids=behavior_ids,
        model=model,
        transition_overrides=transition_overrides,
    )
    transitions_by_id = {row.transition_id: row for row in model.transitions}
    transitions = tuple(
        transitions_by_id[transition_id]
        for transition_id in transition_ids
        if transition_id in transitions_by_id
    )
    input_ids = _related_member_ids(members_by_kind, "input", behavior_ids)
    state_ids = _related_member_ids(members_by_kind, "state", behavior_ids)
    output_ids = _related_member_ids(members_by_kind, "output", behavior_ids)
    effect_ids = sorted(
        f"effect:{behavior_id}:state-transition" for behavior_id in behavior_ids
    )
    error_ids = sorted(
        f"error:{behavior_id}:invalid-input" for behavior_id in behavior_ids
    )
    port_contract = {
        "input_ids": input_ids,
        "state_ids": state_ids,
        "output_ids": output_ids,
        "effect_ids": effect_ids,
        "error_ids": error_ids,
    }
    if member_kind in {"behavior", "transition", "interface"}:
        details: dict[str, Any] = dict(port_contract)
    elif member_kind == "implementation":
        path, separator, symbol = member_id.rpartition("#")
        details = {
            "path": path if separator else member_id,
            "symbol": symbol if separator else member_id.rsplit(":", 1)[-1],
            "content_fingerprint": fingerprint_value(
                {
                    "member_id": member_id,
                    "subject_revision": subject_revision,
                    "content": "synthetic-current-content",
                }
            ),
            "structure_fingerprint": fingerprint_value(
                {
                    "member_id": member_id,
                    "structure": port_contract,
                }
            ),
            **port_contract,
        }
    elif member_kind == "external_owner":
        details = {
            "owner_id": member_id,
            "contract_id": f"contract:{member_id}",
            "contract_fingerprint": fingerprint_value(
                {"member_id": member_id, "contract": port_contract}
            ),
            **port_contract,
        }
    elif member_kind == "input":
        details = {
            "value_schema": {"type": "json-value"},
            "model_input_values": _json_values(
                tuple(row.input_symbol for row in transitions)
            ),
        }
    elif member_kind == "state":
        details = {
            "value_schema": {"type": "state-id"},
            "model_state_ids": sorted(
                {
                    state_id
                    for row in transitions
                    for state_id in (row.source_state, row.target_state)
                }
            ),
        }
    elif member_kind == "output":
        details = {
            "value_schema": {"type": "json-value"},
            "model_output_values": _json_values(
                tuple(row.output_symbol for row in transitions)
            ),
        }
    elif member_kind in {"test", "verification"}:
        details = {
            "validation_owner_id": (
                f"native-owner:{evidence_role}:{member_kind}:{member_id}"
            ),
            "obligation_id": target_native_test_obligation_id(
                target_system_id=target_system_id,
                target_profile=target_profile,
                subject_revision=subject_revision,
                evidence_role=evidence_role,
                member_kind=member_kind,
                member_id=member_id,
            ),
            "checker_id": f"checker:{member_id}",
            "oracle_id": f"oracle:{member_id}",
            "source_ref": member_id,
            "source_fingerprint": fingerprint_value(
                {"source_ref": member_id, "subject_revision": subject_revision}
            ),
            "receipt_id": "",
            "receipt_fingerprint": "",
            "execution_status": "not_run",
        }
    elif member_kind == "resource":
        details = {
            "resource_kind": "target_resource",
            "owner_id": f"owner:{member_id}",
            "source_ref": member_id,
            "current_fingerprint": fingerprint_value(
                {"resource": member_id, "subject_revision": subject_revision}
            ),
            "lifecycle_status": "current",
        }
    elif member_kind == "intent":
        details = {
            "source_kind": "target_contract",
            "source_id": f"source:{member_id}",
            "authority_id": f"authority:{member_id}",
            "authority_revision": subject_revision,
            "authority_fingerprint": "",
            "contribution_id": f"contribution:{member_id}",
            "contribution_fingerprint": "",
            "behavior_ids": list(sorted(behavior_ids)),
            "model_ids": [model.model_id],
            "model_transition_ids": list(transition_ids),
            "contribution_status": "current",
            "conflicts_with_contribution_ids": [],
        }
    elif member_kind == "boundary":
        details = {
            "boundary_fingerprint": fingerprint_value(
                {"boundary": member_id, "subject_revision": subject_revision}
            ),
            "scope_ids": list(sorted(behavior_ids)),
        }
    elif member_kind == "actor":
        details = {
            "role_ids": [f"role:{member_id}"],
            "permission_ids": [f"permission:{member_id}"],
        }
    elif member_kind == "topology":
        details = {
            "producer_output_ids": output_ids,
            "consumer_input_ids": input_ids,
            "relation_fingerprint": fingerprint_value(port_contract),
        }
    else:  # pragma: no cover - the runtime owns rejection of unknown kinds
        raise AssertionError(f"unhandled synthetic member kind: {member_kind}")
    details.update(dict(overrides or {}))
    if member_kind == "intent":
        details["authority_fingerprint"] = fingerprint_value(
            {
                "source_kind": details["source_kind"],
                "source_id": details["source_id"],
                "authority_id": details["authority_id"],
                "authority_revision": details["authority_revision"],
            }
        )
        details["contribution_fingerprint"] = fingerprint_value(
            {
                "source_kind": details["source_kind"],
                "source_id": details["source_id"],
                "authority_id": details["authority_id"],
                "authority_revision": details["authority_revision"],
                "authority_fingerprint": details["authority_fingerprint"],
                "contribution_id": details["contribution_id"],
                "behavior_ids": details["behavior_ids"],
                "contribution_status": details["contribution_status"],
                "conflicts_with_contribution_ids": details[
                    "conflicts_with_contribution_ids"
                ],
            }
        )
    return details


def _portable_native_fixture(
    *,
    target_system_id: str,
    target_kind: str,
    target_profile: str,
    subject_revision: str,
    plan: TargetSystemLayerPlan,
    observed_model: PortableModel,
    authority_model: PortableModel,
    refinement_binding: RefinementBinding,
    members_by_kind: Mapping[str, tuple[tuple[str, tuple[str, ...]], ...]],
    authority_members_by_kind: Mapping[
        str, tuple[tuple[str, tuple[str, ...]], ...]
    ] | None = None,
    observed_model_transition_ids: Mapping[str, tuple[str, ...]] | None = None,
    authority_model_transition_ids: Mapping[str, tuple[str, ...]] | None = None,
    observed_detail_overrides: Mapping[
        tuple[str, str], Mapping[str, Any]
    ] | None = None,
    authority_detail_overrides: Mapping[
        tuple[str, str], Mapping[str, Any]
    ] | None = None,
    validation_owner_contracts: tuple[ValidationOwnerContract, ...] = (),
    execution_receipts: tuple[EvidenceReceipt, ...] = (),
    receipt_verifications: tuple[ReceiptVerificationResult, ...] = (),
):
    authority_member_rows = authority_members_by_kind or members_by_kind
    observed_transition_overrides = observed_model_transition_ids or {}
    authority_transition_overrides = authority_model_transition_ids or {}
    detail_overrides_by_role = {
        "observation": observed_detail_overrides or {},
        "authority": authority_detail_overrides or {},
    }
    boundary_payload = {
        "target_system_id": target_system_id,
        "target_kind": target_kind,
        "target_profile": target_profile,
        "subject_revision": subject_revision,
    }
    boundary_fingerprint = fingerprint_value(boundary_payload)
    observed_payloads: dict[str, Any] = {
        "portable_model": observed_model.to_dict(),
    }
    authority_payloads: dict[str, Any] = {
        "portable_model": authority_model.to_dict(),
    }
    observed_bindings: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
        "portable_model": (
            ("target_boundary", "target_artifacts"),
            ("portable_model",),
        ),
    }
    authority_bindings: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
        "portable_model": (
            ("target_boundary", "target_authority"),
            ("portable_model",),
        ),
    }
    for kind, rows in sorted(members_by_kind.items()):
        capability_id = f"{kind}_inventory"
        payload_ids = []
        for member_id, behavior_ids in rows:
            details = _native_member_details(
                target_system_id=target_system_id,
                target_profile=target_profile,
                evidence_role="observation",
                member_id=member_id,
                member_kind=kind,
                behavior_ids=behavior_ids,
                subject_revision=subject_revision,
                model=observed_model,
                members_by_kind=members_by_kind,
                transition_overrides=observed_transition_overrides,
                overrides=detail_overrides_by_role["observation"].get(
                    (kind, member_id)
                ),
            )
            payload_id = f"member:{kind}:{member_id}"
            payload_ids.append(payload_id)
            observed_payloads[payload_id] = {
                "member_id": member_id,
                "member_kind": kind,
                "subject_revision": subject_revision,
                "behavior_ids": list(sorted(behavior_ids)),
                "model_transition_ids": (
                    list(
                        _related_transition_ids(
                            behavior_ids=behavior_ids,
                            model=observed_model,
                            transition_overrides=observed_transition_overrides,
                        )
                    )
                    if kind in {"behavior", "transition", "intent"}
                    else []
                ),
                "details": details,
                "status": "current",
            }
        observed_bindings[capability_id] = (
            ("target_boundary", "target_artifacts"),
            tuple(payload_ids),
        )
    for kind, rows in sorted(authority_member_rows.items()):
        capability_id = f"{kind}_inventory"
        payload_ids = []
        for member_id, behavior_ids in rows:
            details = _native_member_details(
                target_system_id=target_system_id,
                target_profile=target_profile,
                evidence_role="authority",
                member_id=member_id,
                member_kind=kind,
                behavior_ids=behavior_ids,
                subject_revision=subject_revision,
                model=authority_model,
                members_by_kind=authority_member_rows,
                transition_overrides=authority_transition_overrides,
                overrides=detail_overrides_by_role["authority"].get(
                    (kind, member_id)
                ),
            )
            payload_id = f"member:{kind}:{member_id}"
            payload_ids.append(payload_id)
            authority_payloads[payload_id] = {
                "member_id": member_id,
                "member_kind": kind,
                "subject_revision": subject_revision,
                "behavior_ids": list(sorted(behavior_ids)),
                "model_transition_ids": (
                    list(
                        _related_transition_ids(
                            behavior_ids=behavior_ids,
                            model=authority_model,
                            transition_overrides=authority_transition_overrides,
                        )
                    )
                    if kind in {"behavior", "transition", "intent"}
                    else []
                ),
                "details": details,
                "status": "current",
            }
        authority_bindings[capability_id] = (
            ("target_boundary", "target_authority"),
            tuple(payload_ids),
        )

    observation = _provider(
        provider_id=f"provider:{target_system_id}:observation",
        provider_role="observation",
        provider_kind="synthetic.provider-neutral.target-adapter",
        target_system_id=target_system_id,
        subject_revision=subject_revision,
        inputs={
            "target_boundary": boundary_payload,
            "target_artifacts": observed_payloads,
        },
        payloads=observed_payloads,
        bindings=observed_bindings,
    )
    authority = _provider(
        provider_id=f"provider:{target_system_id}:authority",
        provider_role="authority",
        provider_kind="synthetic.provider-neutral.target-authority",
        target_system_id=target_system_id,
        subject_revision=subject_revision,
        inputs={
            "target_boundary": boundary_payload,
            "target_authority": authority_payloads,
        },
        payloads=authority_payloads,
        bindings=authority_bindings,
    )
    descriptor = TargetSystemDescriptor(
        target_system_id=target_system_id,
        target_kind=target_kind,
        target_profile=target_profile,
        subject_revision=subject_revision,
        boundary_fingerprint=boundary_fingerprint,
        required_observation_capabilities=tuple(observed_bindings),
        required_authority_capabilities=tuple(authority_bindings),
        claim_boundary="The exact synthetic target adapter and authority artifacts.",
    )
    frozen = _freeze(
        descriptor=descriptor,
        plan=plan,
        providers=(observation, authority),
        label=target_system_id,
    )

    members: list[TargetNativeMember] = []
    providers = {
        "observation": observation,
        "authority": authority,
    }
    rows_by_role = {
        "observation": members_by_kind,
        "authority": authority_member_rows,
    }
    for role, provider in providers.items():
        payload_fingerprints = dict(provider.payload_fingerprints)
        for kind, rows in sorted(rows_by_role[role].items()):
            capability_id = f"{kind}_inventory"
            for member_id, behavior_ids in rows:
                payload_id = f"member:{kind}:{member_id}"
                model = observed_model if role == "observation" else authority_model
                transition_overrides = (
                    observed_transition_overrides
                    if role == "observation"
                    else authority_transition_overrides
                )
                details = _native_member_details(
                    target_system_id=target_system_id,
                    target_profile=target_profile,
                    evidence_role=role,
                    member_id=member_id,
                    member_kind=kind,
                    behavior_ids=behavior_ids,
                    subject_revision=subject_revision,
                    model=model,
                    members_by_kind=rows_by_role[role],
                    transition_overrides=transition_overrides,
                    overrides=detail_overrides_by_role[role].get((kind, member_id)),
                )
                members.append(
                    TargetNativeMember(
                        member_id=member_id,
                        member_kind=kind,
                        evidence_role=role,
                        subject_revision=subject_revision,
                        provider_id=provider.provider_id,
                        capability_id=capability_id,
                        payload_id=payload_id,
                        payload_fingerprint=payload_fingerprints[payload_id],
                        behavior_ids=behavior_ids,
                        model_transition_ids=(
                            _related_transition_ids(
                                behavior_ids=behavior_ids,
                                model=model,
                                transition_overrides=transition_overrides,
                            )
                            if kind in {"behavior", "transition", "intent"}
                            else ()
                        ),
                        details=details,
                    )
                )
    model_refs = tuple(
        TargetNativeModelRef(
            evidence_role=role,
            provider_id=provider.provider_id,
            capability_id="portable_model",
            payload_id="portable_model",
            payload_fingerprint=dict(provider.payload_fingerprints)[
                "portable_model"
            ],
            model_id=(
                observed_model.model_id
                if role == "observation"
                else authority_model.model_id
            ),
            model_fingerprint=(
                observed_model.fingerprint
                if role == "observation"
                else authority_model.fingerprint
            ),
        )
        for role, provider in providers.items()
    )
    native = TargetBlueprintNativeReportSet(
        target_system_id=target_system_id,
        target_profile=target_profile,
        subject_revision=subject_revision,
        descriptor_fingerprint=descriptor.fingerprint,
        boundary_fingerprint=descriptor.boundary_fingerprint,
        frozen_evidence_fingerprint=frozen.fingerprint,
        observed_model=observed_model,
        authority_model=authority_model,
        refinement_binding=refinement_binding,
        model_refs=model_refs,
        members=tuple(members),
        validation_owner_contracts=validation_owner_contracts,
        execution_receipts=execution_receipts,
        receipt_verifications=receipt_verifications,
        claim_boundary="Exact observed-vs-declared native target members and portable behavior.",
    )
    return descriptor, frozen, native


def _content_address_native_receipt(
    receipt: EvidenceReceipt,
    *,
    owner_id: str,
) -> EvidenceReceipt:
    payload = receipt.to_dict()
    payload["receipt_id"] = "<CONTENT_ADDRESS>"
    digest = fingerprint_value(payload).split(":", 1)[1]
    return replace(
        receipt,
        receipt_id=f"receipt:validation-owner:{owner_id}:{digest[:32]}",
    )


def _valid_native_execution_evidence(
    *,
    target_system_id: str,
    target_profile: str,
    subject_revision: str,
    evidence_role: str,
    member_kind: str,
    member_id: str,
) -> tuple[
    dict[str, str],
    ValidationOwnerContract,
    EvidenceReceipt,
    ReceiptVerificationResult,
]:
    owner_id = f"native-owner:{evidence_role}:{member_kind}:{member_id}"
    obligation_id = target_native_test_obligation_id(
        target_system_id=target_system_id,
        target_profile=target_profile,
        subject_revision=subject_revision,
        evidence_role=evidence_role,
        member_kind=member_kind,
        member_id=member_id,
    )
    source_path = member_id.split("#", 1)[0]
    contract = ValidationOwnerContract(
        owner_id=owner_id,
        command=("python", "-m", "pytest", source_path),
        input_patterns=(source_path,),
        obligation_ids=(obligation_id,),
    )
    environment = build_environment_fingerprint(
        {
            "python_implementation": "CPython",
            "python_version": "3.12.10",
            "platform_system": "Windows",
            "platform_machine": "AMD64",
            "flowguard_version": "0.68.7",
        }
    )
    snapshot = snapshot_bytes(
        f"input:validation-owner:{owner_id}",
        b"exact-current-native-test-input",
        path_token=f"<WORKSPACE>/<OWNER_INPUT:{owner_id}>",
        obligation_ids=(obligation_id,),
    )
    contract_hash = fingerprint_value(
        {**contract.to_dict(), "command": list(contract.command)}
    )
    check_manifest_hash = fingerprint_value(
        {
            "owner_id": owner_id,
            "command": list(contract.command),
            "obligations": [obligation_id],
        }
    )
    suite_map_hash = fingerprint_value(
        {
            "owner_id": owner_id,
            "patterns": list(contract.input_patterns),
            "projected_inputs": [],
            "obligations": [obligation_id],
        }
    )
    proof_fingerprint = fingerprint_value(
        {
            "owner_id": owner_id,
            "subject_revision": subject_revision,
            "obligation_id": obligation_id,
        }
    )
    receipt = EvidenceReceipt(
        receipt_id=f"receipt:validation-owner:{owner_id}:" + "0" * 32,
        subject_id=f"validation-owner:{owner_id}",
        subject_kind="validation_owner",
        producer_id=f"validation-owner:{owner_id}",
        producer_version="0.68.7",
        claim_scope="full",
        command=contract.command,
        working_directory_token="<WORKSPACE>",
        started_at="2026-08-04T08:00:00+00:00",
        finished_at="2026-08-04T08:00:01+00:00",
        exit_code=0,
        environment_fingerprint=environment.fingerprint,
        environment_metadata=environment.metadata,
        contract_hash=contract_hash,
        check_manifest_hash=check_manifest_hash,
        suite_map_hash=suite_map_hash,
        input_snapshots=(snapshot,),
        proof_artifact_id=f"proof:validation-owner:{owner_id}",
        proof_artifact_fingerprint=proof_fingerprint,
        result_status="pass",
        result_fingerprint=proof_fingerprint,
        covered_obligations=(obligation_id,),
        claim_boundary="One exact native member execution.",
    )
    receipt = _content_address_native_receipt(receipt, owner_id=owner_id)
    verification = verify_evidence_receipt(
        receipt,
        ReceiptVerificationContext(
            input_snapshots={snapshot.artifact_id: snapshot},
            contract_hash=contract_hash,
            check_manifest_hash=check_manifest_hash,
            suite_map_hash=suite_map_hash,
            producer_id=receipt.producer_id,
            producer_version=receipt.producer_version,
            environment_fingerprint=environment.fingerprint,
            proof_artifact_fingerprint=proof_fingerprint,
            result_fingerprint=proof_fingerprint,
            command=receipt.command,
            working_directory_token=receipt.working_directory_token,
            proof_artifact_id=receipt.proof_artifact_id,
            required_obligation_ids=(obligation_id,),
            eligible_claim_scopes=("full",),
        ),
    )
    assert verification.ok
    assert not verification.findings
    return (
        {
            "validation_owner_id": owner_id,
            "obligation_id": obligation_id,
            "receipt_id": receipt.receipt_id,
            "receipt_fingerprint": receipt.fingerprint,
            "execution_status": "passed",
        },
        contract,
        receipt,
        verification,
    )


@pytest.mark.parametrize(
    ("missing_kind", "missing_layer"),
    (
        ("provider", "evidence_qualification"),
        ("behavior", "independent_semantics"),
        ("resource", "resource_oracle"),
        ("test", "model_code_test"),
    ),
)
def test_public_target_compiler_blocks_each_missing_blueprint_capability(
    missing_kind: str,
    missing_layer: str,
) -> None:
    descriptor, frozen = _minimal_software_case(
        missing_provider_capability=(
            "missing_provider_capability" if missing_kind == "provider" else ""
        )
    )
    layers = _passing_layers(
        CANONICAL_SOFTWARE_LAYER_PLAN,
        label=f"missing-{missing_kind}",
    )
    if missing_kind != "provider":
        layers = tuple(row for row in layers if row.layer != missing_layer)

    report = _assemble_target_system_blueprint(
        descriptor,
        frozen,
        downstream_layers=layers,
        scope="whole",
    )

    assert not report.ok
    assert report.implementation_admitted is False
    first_gap = report.readiness_ledger.first_gap
    assert first_gap is not None
    assert first_gap.layer == missing_layer
    if missing_kind == "provider":
        assert first_gap.object_kind == "observation_provider_capability"
        assert first_gap.object_id == "missing_provider_capability"
    else:
        assert first_gap.object_kind == "required_layer"
        assert first_gap.object_id == missing_layer
    assert report.readiness_ledger.gap_count >= 1


def test_target_kernel_accepts_typescript_provider_envelope_without_claiming_native_semantics(
    tmp_path: Path, monkeypatch
) -> None:
    target_root = tmp_path / "typescript-order-service"
    (target_root / "src").mkdir(parents=True)
    (target_root / "tests").mkdir()
    (target_root / "package.json").write_text(
        json.dumps(
            {
                "name": "typescript-order-service",
                "scripts": {"build": "tsc", "test": "vitest run"},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (target_root / "src" / "order-machine.ts").write_text(
        "export const transition = (state: string, event: string) => "
        "`${state}:${event}`;\n",
        encoding="utf-8",
    )
    (target_root / "tests" / "order-machine.spec.ts").write_text(
        "import { transition } from '../src/order-machine';\n"
        "test('submit', () => expect(transition('draft', 'submit'))"
        ".toBe('draft:submit'));\n",
        encoding="utf-8",
    )

    target_inputs = {
        "npm_manifest": json.loads((target_root / "package.json").read_text()),
        "typescript_source": (target_root / "src" / "order-machine.ts").read_text(),
        "typescript_test": (
            target_root / "tests" / "order-machine.spec.ts"
        ).read_text(),
    }
    observed_payloads = {
        "behavior_inventory": {
            "states": ["draft", "submitted"],
            "transitions": ["submit"],
        },
        "implementation_inventory": {
            "language": "TypeScript",
            "owner": "src/order-machine.ts#transition",
        },
        "interface_inventory": {
            "input": ["state", "event"],
            "output": ["next_state"],
        },
        "test_inventory": ["tests/order-machine.spec.ts#submit"],
        "resource_inventory": ["package.json#scripts"],
    }
    intent_payloads = {
        "behavior_semantics": {
            "submit": {"from": "draft", "to": "submitted"}
        },
        "intent_lineage": {"source": "product-intent:order-lifecycle"},
    }
    target_system_id = "target:typescript-order-service"
    subject_revision = "revision:typescript-fixture-v1"
    providers = (
        _provider(
            provider_id="provider:typescript-manifest-observer",
            provider_role="observation",
            provider_kind="synthetic.typescript-manifest.adapter",
            target_system_id=target_system_id,
            subject_revision=subject_revision,
            inputs=target_inputs,
            payloads=observed_payloads,
            bindings={
                capability: (
                    tuple(target_inputs),
                    (capability,),
                )
                for capability in observed_payloads
            },
        ),
        _provider(
            provider_id="provider:product-intent-authority",
            provider_role="authority",
            provider_kind="synthetic.product-intent.authority",
            target_system_id=target_system_id,
            subject_revision=subject_revision,
            inputs={"declared_intent": intent_payloads},
            payloads=intent_payloads,
            bindings={
                capability: (("declared_intent",), (capability,))
                for capability in intent_payloads
            },
        ),
    )
    descriptor = TargetSystemDescriptor(
        target_system_id=target_system_id,
        target_kind="software",
        target_profile="software",
        subject_revision=subject_revision,
        boundary_fingerprint=fingerprint_value(target_inputs),
        required_observation_capabilities=tuple(observed_payloads),
        required_authority_capabilities=tuple(intent_payloads),
        claim_boundary="The declared TypeScript service and its manifest only.",
    )
    frozen = _freeze(
        descriptor=descriptor,
        plan=CANONICAL_SOFTWARE_LAYER_PLAN,
        providers=providers,
        label="typescript-order-service",
    )
    evidence_path = tmp_path / "typescript-frozen-evidence.json"
    evidence_path.write_bytes(serialize_frozen_target_system_evidence(frozen))

    before = _tree_state(target_root)
    monkeypatch.chdir(target_root)
    loaded = load_frozen_target_system_evidence(evidence_path)
    reports = _compile_whole_and_affected(
        descriptor, loaded, label="typescript-order-service"
    )
    after = _tree_state(target_root)

    assert before == after
    assert not tuple(target_root.rglob("*.py"))
    assert {
        row.provider_kind for row in loaded.provider_results
    } == {
        "synthetic.typescript-manifest.adapter",
        "synthetic.product-intent.authority",
    }
    assert all("python" not in row.provider_kind.lower() for row in loaded.provider_results)
    assert loaded.provider_registry.fingerprint == frozen.provider_registry.fingerprint
    assert loaded.snapshot.fingerprint == frozen.snapshot.fingerprint
    assert {report.scope for report in reports.values()} == {"whole", "affected"}
    for report in reports.values():
        assert report.ok
        assert tuple(row.layer for row in report.layers) == tuple(
            CANONICAL_SOFTWARE_LAYER_PLAN.layer_ids
        )
        assert {row.status for row in report.layers} == {"pass"}
        assert report.provider_registry_fingerprint == loaded.provider_registry.fingerprint
        assert report.snapshot_fingerprint == loaded.snapshot.fingerprint

    affected = project_blueprint_understanding(
        reports["affected"],
        affected_surface_ids=("typescript:src/order-machine.ts#transition",),
    )
    assert affected.scope == "affected"
    assert affected.affected_surface_ids == (
        "typescript:src/order-machine.ts#transition",
    )


def test_target_kernel_accepts_non_code_provider_envelope_without_claiming_native_semantics(
    tmp_path: Path, monkeypatch
) -> None:
    target_root = tmp_path / "expense-approval-workflow"
    target_root.mkdir()
    target_semantics = {
        "actors": [
            {
                "actor_id": "employee",
                "roles": ["requester"],
                "permissions": ["submit_own_request", "withdraw_pending_request"],
            },
            {
                "actor_id": "finance_reviewer",
                "roles": ["reviewer"],
                "permissions": ["approve_within_limit", "return_for_correction"],
            },
        ],
        "states": ["draft", "pending_review", "approved", "returned"],
        "transitions": [
            {"event": "submit", "from": "draft", "to": "pending_review"},
            {
                "event": "approve",
                "from": "pending_review",
                "to": "approved",
                "allowed_actor": "finance_reviewer",
            },
        ],
        "inputs": ["expense_request", "supporting_receipt"],
        "outputs": ["approval_decision", "decision_reason"],
    }
    verification_cases = [
        {
            "case": "reviewer approves a valid request",
            "input_state": "pending_review",
            "actor": "finance_reviewer",
            "output_state": "approved",
        }
    ]
    intent = {
        "goal": "Every expense decision is attributable and policy-bounded.",
        "source": "expense-policy:current",
    }
    (target_root / "workflow-model.json").write_text(
        json.dumps(target_semantics, sort_keys=True), encoding="utf-8"
    )
    (target_root / "verification-cases.json").write_text(
        json.dumps(verification_cases, sort_keys=True), encoding="utf-8"
    )
    (target_root / "intent.json").write_text(
        json.dumps(intent, sort_keys=True), encoding="utf-8"
    )

    workflow_inputs = {
        "workflow_model": target_semantics,
        "verification_cases": verification_cases,
        "declared_intent": intent,
    }
    target_system_id = "target:expense-approval-workflow"
    subject_revision = "revision:workflow-fixture-v1"
    observed_payloads = {
        "workflow_inventory": {
            "state_ids": target_semantics["states"],
            "transition_ids": [
                transition["event"] for transition in target_semantics["transitions"]
            ],
        },
        "verification_cases": verification_cases,
    }
    authority_payloads = {
        "target_owned_workflow_semantics": target_semantics,
        "target_owned_intent_lineage": intent,
    }
    providers = (
        _provider(
            provider_id="provider:workflow-manifest-observer",
            provider_role="observation",
            provider_kind="synthetic.workflow-manifest.adapter",
            target_system_id=target_system_id,
            subject_revision=subject_revision,
            inputs=workflow_inputs,
            payloads=observed_payloads,
            bindings={
                "workflow_inventory": (
                    ("workflow_model",),
                    ("workflow_inventory",),
                ),
                "verification_cases": (
                    ("verification_cases",),
                    ("verification_cases",),
                ),
            },
        ),
        _provider(
            provider_id="provider:workflow-policy-authority",
            provider_role="authority",
            provider_kind="synthetic.workflow-policy.authority",
            target_system_id=target_system_id,
            subject_revision=subject_revision,
            inputs={
                "workflow_model": target_semantics,
                "declared_intent": intent,
            },
            payloads=authority_payloads,
            bindings={
                "workflow_semantics": (
                    ("workflow_model",),
                    ("target_owned_workflow_semantics",),
                ),
                "intent_lineage": (
                    ("declared_intent",),
                    ("target_owned_intent_lineage",),
                ),
            },
        ),
    )
    descriptor = TargetSystemDescriptor(
        target_system_id=target_system_id,
        target_kind="business_approval_process",
        target_profile="non_code_workflow",
        subject_revision=subject_revision,
        boundary_fingerprint=fingerprint_value(workflow_inputs),
        required_observation_capabilities=(
            "workflow_inventory",
            "verification_cases",
        ),
        required_authority_capabilities=("workflow_semantics", "intent_lineage"),
        claim_boundary="The declared expense-approval process only.",
    )
    frozen = _freeze(
        descriptor=descriptor,
        plan=CANONICAL_NON_CODE_WORKFLOW_LAYER_PLAN,
        providers=providers,
        label="expense-approval-workflow",
    )
    evidence_path = tmp_path / "workflow-frozen-evidence.json"
    evidence_path.write_bytes(serialize_frozen_target_system_evidence(frozen))

    before = _tree_state(target_root)
    monkeypatch.chdir(target_root)
    loaded = load_frozen_target_system_evidence(evidence_path)
    reports = _compile_whole_and_affected(
        descriptor, loaded, label="expense-approval-workflow"
    )
    after = _tree_state(target_root)

    assert before == after
    assert loaded.layer_plan == CANONICAL_NON_CODE_WORKFLOW_LAYER_PLAN
    assert loaded.provider_registry.fingerprint == frozen.provider_registry.fingerprint
    assert loaded.snapshot.fingerprint == frozen.snapshot.fingerprint

    authority = next(
        row for row in loaded.provider_results if row.provider_role == "authority"
    )
    assert dict(authority.payload_fingerprints)[
        "target_owned_workflow_semantics"
    ] == fingerprint_value(target_semantics)
    semantics_binding = next(
        row
        for row in authority.capability_bindings
        if row.capability_id == "workflow_semantics"
    )
    assert semantics_binding.payload_ids == ("target_owned_workflow_semantics",)
    assert target_semantics["actors"][1]["permissions"] == [
        "approve_within_limit",
        "return_for_correction",
    ]

    flowguard_control_plane = json.dumps(
        {
            "descriptor": descriptor.to_dict(),
            "provider_registry": loaded.provider_registry.to_dict(),
        },
        sort_keys=True,
    )
    assert "finance_reviewer" not in flowguard_control_plane
    assert "approve_within_limit" not in flowguard_control_plane
    assert {row.provider_role for row in loaded.provider_results} == {
        "observation",
        "authority",
    }

    assert {report.scope for report in reports.values()} == {"whole", "affected"}
    for report in reports.values():
        assert report.ok
        assert report.target_profile == "non_code_workflow"
        assert tuple(row.layer for row in report.layers) == tuple(
            CANONICAL_NON_CODE_WORKFLOW_LAYER_PLAN.layer_ids
        )
        assert {row.status for row in report.layers} == {"pass"}
        assert "implementation_inventory" not in {
            row.layer for row in report.layers
        }
        assert "model_code_test" not in {row.layer for row in report.layers}

    affected = project_blueprint_understanding(
        reports["affected"],
        affected_surface_ids=("workflow-transition:approve",),
    )
    assert affected.scope == "affected"
    assert affected.affected_surface_ids == ("workflow-transition:approve",)


def _order_models(actual_output: str):
    authority = PortableModel(
        model_id="portable:order-authority",
        states=(PortableState("draft"), PortableState("submitted")),
        transitions=(
            PortableTransition(
                transition_id="authority:submit",
                source_state="draft",
                input_symbol="submit",
                output_symbol="submitted",
                target_state="submitted",
            ),
        ),
        initial_state_ids=("draft",),
        terminal_state_ids=("submitted",),
        guarantees=("order-submit-contract",),
    )
    observed = PortableModel(
        model_id="portable:order-observed",
        states=(PortableState("draft"), PortableState(actual_output)),
        transitions=(
            PortableTransition(
                transition_id="observed:submit",
                source_state="draft",
                input_symbol="submit",
                output_symbol=actual_output,
                target_state=actual_output,
            ),
        ),
        initial_state_ids=("draft",),
        terminal_state_ids=(actual_output,),
        guarantees=("order-submit-contract",),
    )
    binding = RefinementBinding(
        parent_model_id=authority.model_id,
        child_model_id=observed.model_id,
        parent_model_fingerprint=authority.fingerprint,
        child_model_fingerprint=observed.fingerprint,
        state_mapping=(("draft", "draft"), (actual_output, "submitted")),
        transition_mapping=(("observed:submit", "authority:submit"),),
    )
    return observed, authority, binding


def _software_native_members(
    behavior_id: str,
    *,
    label: str,
) -> dict[str, tuple[tuple[str, tuple[str, ...]], ...]]:
    return {
        "behavior": ((behavior_id, (behavior_id,)),),
        "input": ((f"input:{label}", (behavior_id,)),),
        "state": ((f"state:{label}", (behavior_id,)),),
        "output": ((f"output:{label}", (behavior_id,)),),
        "implementation": ((f"src/{label}.py#run", (behavior_id,)),),
        "interface": ((f"interface:{label}", (behavior_id,)),),
        "test": ((f"test:{label}", (behavior_id,)),),
        "resource": ((f"resource:{label}", (behavior_id,)),),
        "intent": ((f"intent:{label}", (behavior_id,)),),
    }


def _receipt_bound_software_fixture(
    *,
    member_id: str,
    detail_binding: Mapping[str, str],
    contract: ValidationOwnerContract | None = None,
    receipt: EvidenceReceipt | None = None,
    verification: ReceiptVerificationResult | None = None,
    extra_test_member_ids: tuple[str, ...] = (),
    extra_detail_bindings: Mapping[str, Mapping[str, str]] | None = None,
):
    target_system_id = "target:native-receipt-verification"
    target_profile = "software"
    subject_revision = "revision:native-receipt-verification"
    behavior_id = "behavior:native-receipt-verification"
    observed, authority, binding = _order_models("submitted")
    members = _software_native_members(behavior_id, label="native-receipt")
    members["test"] = tuple(
        (test_member_id, (behavior_id,))
        for test_member_id in (member_id, *extra_test_member_ids)
    )
    overrides: dict[tuple[str, str], Mapping[str, Any]] = {
        ("test", member_id): dict(detail_binding),
    }
    overrides.update(
        {
            ("test", extra_member_id): dict(extra_binding)
            for extra_member_id, extra_binding in dict(
                extra_detail_bindings or {}
            ).items()
        }
    )
    return _portable_native_fixture(
        target_system_id=target_system_id,
        target_kind="software",
        target_profile=target_profile,
        subject_revision=subject_revision,
        plan=CANONICAL_SOFTWARE_LAYER_PLAN,
        observed_model=observed,
        authority_model=authority,
        refinement_binding=binding,
        members_by_kind=members,
        observed_model_transition_ids={behavior_id: ("observed:submit",)},
        authority_model_transition_ids={behavior_id: ("authority:submit",)},
        observed_detail_overrides=overrides,
        validation_owner_contracts=((contract,) if contract is not None else ()),
        execution_receipts=((receipt,) if receipt is not None else ()),
        receipt_verifications=(
            (verification,) if verification is not None else ()
        ),
    )


def _native_receipt_evidence(member_id: str = "test:native-receipt"):
    return _valid_native_execution_evidence(
        target_system_id="target:native-receipt-verification",
        target_profile="software",
        subject_revision="revision:native-receipt-verification",
        evidence_role="observation",
        member_kind="test",
        member_id=member_id,
    )


def test_native_pass_requires_and_accepts_exact_typed_leaf_receipt_registry(
    tmp_path: Path,
) -> None:
    member_id = "test:native-receipt"
    detail, contract, receipt, verification = _native_receipt_evidence(member_id)
    descriptor, frozen, native = _receipt_bound_software_fixture(
        member_id=member_id,
        detail_binding=detail,
        contract=contract,
        receipt=receipt,
        verification=verification,
    )

    report = qualify_target_system_from_native_reports(descriptor, frozen, native)

    assert report.ok
    assert report.scope == "whole"
    with pytest.raises(TypeError):
        qualify_target_system_from_native_reports(  # type: ignore[call-arg]
            descriptor,
            frozen,
            native,
            scope="affected",
        )
    model_test = next(row for row in report.layers if row.layer == "model_code_test")
    assert model_test.status == "pass"
    assert model_test.executed_evidence_status == "passed"
    path = tmp_path / "typed-native-receipt.json"
    path.write_bytes(serialize_target_blueprint_native_report_set(native))
    loaded = load_target_blueprint_native_report_set(path)
    assert loaded.execution_receipts == (receipt,)
    assert loaded.receipt_verifications == (verification,)
    assert loaded.validation_owner_contracts == (contract,)


def test_native_pass_rejects_opaque_caller_receipt_without_typed_registries() -> None:
    member_id = "test:native-receipt"
    with pytest.raises(
        TargetSystemBlueprintError,
        match="validation owner registry is not the exact passed-member set",
    ):
        _receipt_bound_software_fixture(
            member_id=member_id,
            detail_binding={
                "receipt_id": "receipt:opaque-caller-pass",
                "receipt_fingerprint": fingerprint_value(
                    {"opaque": "caller-authored-pass"}
                ),
                "execution_status": "passed",
            },
        )


def test_native_pass_rejects_parent_or_aggregate_receipt() -> None:
    member_id = "test:native-receipt"
    detail, contract, receipt, verification = _native_receipt_evidence(member_id)
    parent = replace(
        receipt,
        receipt_id=f"receipt:validation-owner:{contract.owner_id}:" + "0" * 32,
        subject_kind="validation_parent",
    )
    parent = _content_address_native_receipt(parent, owner_id=contract.owner_id)
    detail = {
        **detail,
        "receipt_id": parent.receipt_id,
        "receipt_fingerprint": parent.fingerprint,
    }
    parent_verification = replace(
        verification,
        receipt_id=parent.receipt_id,
        receipt_fingerprint=parent.fingerprint,
    )

    with pytest.raises(
        TargetSystemBlueprintError,
        match="parent or aggregate receipt",
    ):
        _receipt_bound_software_fixture(
            member_id=member_id,
            detail_binding=detail,
            contract=contract,
            receipt=parent,
            verification=parent_verification,
        )


def test_native_pass_rejects_cross_owner_receipt() -> None:
    member_id = "test:native-receipt"
    detail, contract, receipt, verification = _native_receipt_evidence(member_id)
    cross_owner = replace(
        receipt,
        receipt_id=f"receipt:validation-owner:{contract.owner_id}:" + "0" * 32,
        producer_id="validation-owner:foreign-owner",
    )
    cross_owner = _content_address_native_receipt(
        cross_owner,
        owner_id=contract.owner_id,
    )
    detail = {
        **detail,
        "receipt_id": cross_owner.receipt_id,
        "receipt_fingerprint": cross_owner.fingerprint,
    }
    cross_verification = replace(
        verification,
        receipt_id=cross_owner.receipt_id,
        receipt_fingerprint=cross_owner.fingerprint,
    )

    with pytest.raises(
        TargetSystemBlueprintError,
        match="verified_receipt_producer_mismatch",
    ):
        _receipt_bound_software_fixture(
            member_id=member_id,
            detail_binding=detail,
            contract=contract,
            receipt=cross_owner,
            verification=cross_verification,
        )


def test_native_pass_rejects_receipt_relabel_to_another_member() -> None:
    original_member_id = "test:native-receipt"
    relabeled_member_id = "test:relabeled-receipt"
    detail, contract, receipt, verification = _native_receipt_evidence(
        original_member_id
    )

    with pytest.raises(
        TargetSystemBlueprintError,
        match="obligation is not bound to the exact target",
    ):
        _receipt_bound_software_fixture(
            member_id=relabeled_member_id,
            detail_binding=detail,
            contract=contract,
            receipt=receipt,
            verification=verification,
        )


def test_native_pass_rejects_receipt_with_omitted_member_coverage() -> None:
    member_id = "test:native-receipt"
    detail, contract, receipt, verification = _native_receipt_evidence(member_id)
    omitted = replace(
        receipt,
        receipt_id=f"receipt:validation-owner:{contract.owner_id}:" + "0" * 32,
        covered_obligations=("target-native-test:unrelated",),
    )
    omitted = _content_address_native_receipt(omitted, owner_id=contract.owner_id)
    detail = {
        **detail,
        "receipt_id": omitted.receipt_id,
        "receipt_fingerprint": omitted.fingerprint,
    }
    omitted_verification = replace(
        verification,
        receipt_id=omitted.receipt_id,
        receipt_fingerprint=omitted.fingerprint,
    )

    with pytest.raises(
        TargetSystemBlueprintError,
        match="verified_receipt_obligation_scope_mismatch",
    ):
        _receipt_bound_software_fixture(
            member_id=member_id,
            detail_binding=detail,
            contract=contract,
            receipt=omitted,
            verification=omitted_verification,
        )


def test_native_pass_rejects_one_receipt_reused_for_two_members() -> None:
    first_member_id = "test:native-receipt"
    second_member_id = "test:second-native-receipt"
    detail, contract, receipt, verification = _native_receipt_evidence(
        first_member_id
    )
    second_binding = {
        **detail,
        "obligation_id": target_native_test_obligation_id(
            target_system_id="target:native-receipt-verification",
            target_profile="software",
            subject_revision="revision:native-receipt-verification",
            evidence_role="observation",
            member_kind="test",
            member_id=second_member_id,
        ),
    }

    with pytest.raises(
        TargetSystemBlueprintError,
        match="receipt cannot be reused for multiple passed members",
    ):
        _receipt_bound_software_fixture(
            member_id=first_member_id,
            detail_binding=detail,
            contract=contract,
            receipt=receipt,
            verification=verification,
            extra_test_member_ids=(second_member_id,),
            extra_detail_bindings={second_member_id: second_binding},
        )


def test_native_typescript_path_detects_logic_mismatch_then_accepts_corrected_target(
    tmp_path: Path,
) -> None:
    target_root = tmp_path / "typescript-native-target"
    (target_root / "src").mkdir(parents=True)
    (target_root / "tests").mkdir()
    source = target_root / "src" / "order-machine.ts"
    test_file = target_root / "tests" / "order-machine.spec.ts"
    package_file = target_root / "package.json"
    package_file.write_text(
        json.dumps({"scripts": {"test": "vitest run"}}, sort_keys=True),
        encoding="utf-8",
    )
    test_file.write_text(
        "test('submit', () => expect(transition('draft', 'submit')).toBe('submitted'));\n",
        encoding="utf-8",
    )
    behavior_id = "behavior:order:submit"
    members = {
        "behavior": ((behavior_id, (behavior_id,)),),
        "input": (("input:order-event", (behavior_id,)),),
        "state": (("state:order-lifecycle", (behavior_id,)),),
        "output": (("output:order-next-state", (behavior_id,)),),
        "implementation": (
            ("typescript:src/order-machine.ts#transition", (behavior_id,)),
        ),
        "interface": (
            ("interface:state,event->next_state", (behavior_id,)),
        ),
        "test": (("typescript:tests/order-machine.spec.ts#submit", (behavior_id,)),),
        "resource": (("resource:package.json#scripts", (behavior_id,)),),
        "intent": (("intent:order-lifecycle", (behavior_id,)),),
    }

    def qualify_source(text: str):
        source.write_text(text, encoding="utf-8")
        actual_output = (
            "submitted" if "return 'submitted'" in source.read_text(encoding="utf-8")
            else "draft:submit"
        )
        observed, authority, binding = _order_models(actual_output)
        descriptor, frozen, native = _portable_native_fixture(
            target_system_id="target:typescript-native-order",
            target_kind="software",
            target_profile="software",
            subject_revision=fingerprint_value(
                {
                    "source": source.read_text(encoding="utf-8"),
                    "test": test_file.read_text(encoding="utf-8"),
                    "package": package_file.read_text(encoding="utf-8"),
                }
            ),
            plan=CANONICAL_SOFTWARE_LAYER_PLAN,
            observed_model=observed,
            authority_model=authority,
            refinement_binding=binding,
            members_by_kind=members,
        )
        before = _tree_state(target_root)
        report = qualify_target_system_from_native_reports(
            descriptor, frozen, native
        )
        assert _tree_state(target_root) == before
        return descriptor, frozen, native, report

    _descriptor, _frozen, _native, wrong = qualify_source(
        "export function transition(state: string, event: string) { "
        "return `${state}:${event}`; }\n"
    )
    assert not wrong.ok
    assert any(
        gap.object_kind == "portable_refinement_finding"
        and gap.object_id == "refinement_step_mismatch"
        for gap in wrong.gaps
    )
    assert wrong.readiness_ledger.first_gap is not None
    assert wrong.readiness_ledger.first_gap.layer == "independent_semantics"

    descriptor, frozen, native, corrected = qualify_source(
        "export function transition(state: string, event: string) { "
        "if (state === 'draft' && event === 'submit') return 'submitted'; "
        "return state; }\n"
    )
    assert corrected.ok
    assert corrected.implementation_admitted
    assert corrected.readiness_ledger.executed_evidence_status == "not_run"

    observed_without_resource = {
        **members,
        "resource": (("resource:missing-package-scripts", (behavior_id,)),),
    }
    observed, authority, binding = _order_models("submitted")
    descriptor, frozen, native = _portable_native_fixture(
        target_system_id="target:typescript-native-resource-negative",
        target_kind="software",
        target_profile="software",
        subject_revision="revision:typescript-resource-negative",
        plan=CANONICAL_SOFTWARE_LAYER_PLAN,
        observed_model=observed,
        authority_model=authority,
        refinement_binding=binding,
        members_by_kind=observed_without_resource,
        authority_members_by_kind=members,
    )
    missing_resource = qualify_target_system_from_native_reports(
        descriptor, frozen, native
    )
    assert not missing_resource.ok
    assert any(
        gap.layer == "resource_oracle"
        and gap.object_kind
        in {"observed_member_undeclared", "declared_member_unobserved"}
        for gap in missing_resource.gaps
    )

    observed_without_test = {
        **members,
        "test": (("typescript:tests/order-machine.spec.ts#wrong-test", (behavior_id,)),),
    }
    descriptor, frozen, native = _portable_native_fixture(
        target_system_id="target:typescript-native-test-negative",
        target_kind="software",
        target_profile="software",
        subject_revision="revision:typescript-test-negative",
        plan=CANONICAL_SOFTWARE_LAYER_PLAN,
        observed_model=observed,
        authority_model=authority,
        refinement_binding=binding,
        members_by_kind=observed_without_test,
        authority_members_by_kind=members,
    )
    missing_test = qualify_target_system_from_native_reports(
        descriptor, frozen, native
    )
    assert not missing_test.ok
    assert any(
        gap.layer == "model_code_test"
        and gap.object_kind
        in {"observed_member_undeclared", "declared_member_unobserved"}
        for gap in missing_test.gaps
    )


def _approval_models(*, actual_actor: str, actual_output: str):
    authority = PortableModel(
        model_id="portable:approval-authority",
        states=(PortableState("pending_review"), PortableState("approved")),
        transitions=(
            PortableTransition(
                transition_id="authority:approve",
                source_state="pending_review",
                input_symbol={"event": "approve", "actor": "finance_reviewer"},
                output_symbol="approved",
                target_state="approved",
            ),
        ),
        initial_state_ids=("pending_review",),
        terminal_state_ids=("approved",),
        guarantees=("policy-bounded-approval",),
    )
    observed = PortableModel(
        model_id="portable:approval-observed",
        states=(PortableState("pending_review"), PortableState(actual_output)),
        transitions=(
            PortableTransition(
                transition_id="observed:approve",
                source_state="pending_review",
                input_symbol={"event": "approve", "actor": actual_actor},
                output_symbol=actual_output,
                target_state=actual_output,
            ),
        ),
        initial_state_ids=("pending_review",),
        terminal_state_ids=(actual_output,),
        guarantees=("policy-bounded-approval",),
    )
    binding = RefinementBinding(
        parent_model_id=authority.model_id,
        child_model_id=observed.model_id,
        parent_model_fingerprint=authority.fingerprint,
        child_model_fingerprint=observed.fingerprint,
        state_mapping=(
            ("pending_review", "pending_review"),
            (actual_output, "approved"),
        ),
        transition_mapping=(("observed:approve", "authority:approve"),),
    )
    return observed, authority, binding


def test_native_non_code_workflow_checks_actor_transition_and_verification() -> None:
    transition_id = "transition:approve"
    authority_members = {
        "boundary": (("boundary:expense-approval", (transition_id,)),),
        "actor": (
            ("actor:finance_reviewer:permission:approve_within_limit", (transition_id,)),
        ),
        "input": (("input:expense_request", (transition_id,)),),
        "state": (
            ("state:pending_review", (transition_id,)),
            ("state:approved", (transition_id,)),
        ),
        "transition": ((transition_id, (transition_id,)),),
        "output": (("output:approval_decision", (transition_id,)),),
        "resource": (("resource:expense-policy", (transition_id,)),),
        "intent": (("intent:attributable-policy-bounded-decision", (transition_id,)),),
        "verification": (("verification:reviewer-approves-valid", (transition_id,)),),
    }
    observed, authority, binding = _approval_models(
        actual_actor="finance_reviewer", actual_output="approved"
    )
    descriptor, frozen, native = _portable_native_fixture(
        target_system_id="target:non-code-expense-approval",
        target_kind="workflow",
        target_profile="non_code_workflow",
        subject_revision="revision:expense-workflow-current",
        plan=CANONICAL_NON_CODE_WORKFLOW_LAYER_PLAN,
        observed_model=observed,
        authority_model=authority,
        refinement_binding=binding,
        members_by_kind=authority_members,
    )
    current = qualify_target_system_from_native_reports(descriptor, frozen, native)
    assert current.ok
    assert current.target_profile == "non_code_workflow"
    assert not current.implementation_admitted

    wrong_actor_members = {
        **authority_members,
        "actor": (("actor:employee:permission:approve_within_limit", (transition_id,)),),
    }
    descriptor, frozen, native = _portable_native_fixture(
        target_system_id="target:non-code-expense-wrong-actor",
        target_kind="workflow",
        target_profile="non_code_workflow",
        subject_revision="revision:expense-wrong-actor",
        plan=CANONICAL_NON_CODE_WORKFLOW_LAYER_PLAN,
        observed_model=observed,
        authority_model=authority,
        refinement_binding=binding,
        members_by_kind=wrong_actor_members,
        authority_members_by_kind=authority_members,
    )
    wrong_actor = qualify_target_system_from_native_reports(
        descriptor, frozen, native
    )
    assert not wrong_actor.ok
    assert any(gap.layer == "workflow_actors" for gap in wrong_actor.gaps)

    wrong_observed, authority, wrong_binding = _approval_models(
        actual_actor="finance_reviewer", actual_output="returned"
    )
    descriptor, frozen, native = _portable_native_fixture(
        target_system_id="target:non-code-expense-wrong-transition",
        target_kind="workflow",
        target_profile="non_code_workflow",
        subject_revision="revision:expense-wrong-transition",
        plan=CANONICAL_NON_CODE_WORKFLOW_LAYER_PLAN,
        observed_model=wrong_observed,
        authority_model=authority,
        refinement_binding=wrong_binding,
        members_by_kind=authority_members,
    )
    wrong_transition = qualify_target_system_from_native_reports(
        descriptor, frozen, native
    )
    assert not wrong_transition.ok
    assert any(
        gap.layer == "workflow_transitions"
        and gap.object_id == "refinement_step_mismatch"
        for gap in wrong_transition.gaps
    )


def test_native_report_set_round_trips_strictly_and_rejects_relation_drift(
    tmp_path: Path,
) -> None:
    behavior_id = "behavior:strict-native"
    members = {
        "behavior": ((behavior_id, (behavior_id,)),),
        "input": (("input:strict-native", (behavior_id,)),),
        "state": (("state:strict-native", (behavior_id,)),),
        "output": (("output:strict-native", (behavior_id,)),),
        "implementation": (("surface:strict-native", (behavior_id,)),),
        "interface": (("interface:strict-native", (behavior_id,)),),
        "test": (("test:strict-native", (behavior_id,)),),
        "resource": (("resource:strict-native", (behavior_id,)),),
        "intent": (("intent:strict-native", (behavior_id,)),),
    }
    observed, authority, binding = _order_models("submitted")
    descriptor, frozen, native = _portable_native_fixture(
        target_system_id="target:strict-native",
        target_kind="software",
        target_profile="software",
        subject_revision="revision:strict-native",
        plan=CANONICAL_SOFTWARE_LAYER_PLAN,
        observed_model=observed,
        authority_model=authority,
        refinement_binding=binding,
        members_by_kind=members,
    )
    path = tmp_path / "native-report-set.json"
    path.write_bytes(serialize_target_blueprint_native_report_set(native))
    loaded = load_target_blueprint_native_report_set(path)
    assert loaded.fingerprint == native.fingerprint
    assert qualify_target_system_from_native_reports(
        descriptor, frozen, loaded
    ).ok

    drifted_authority = {
        **members,
        "test": (("test:strict-native", ()),),
    }
    descriptor, frozen, drifted = _portable_native_fixture(
        target_system_id="target:strict-native-drift",
        target_kind="software",
        target_profile="software",
        subject_revision="revision:strict-native-drift",
        plan=CANONICAL_SOFTWARE_LAYER_PLAN,
        observed_model=observed,
        authority_model=authority,
        refinement_binding=binding,
        members_by_kind=members,
        authority_members_by_kind=drifted_authority,
    )
    report = qualify_target_system_from_native_reports(
        descriptor, frozen, drifted
    )
    assert not report.ok
    assert any(
        gap.layer == "model_code_test"
        and gap.object_kind == "native_member_contract_mismatch"
        for gap in report.gaps
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["fallback_native_report"] = {}
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(
        TargetSystemBlueprintError, match="fields are not exact-current"
    ):
        load_target_blueprint_native_report_set(path)


def test_native_member_requires_typed_details_and_fingerprints_the_full_payload() -> None:
    behavior_id = "behavior:typed-payload"
    members = _software_native_members(behavior_id, label="typed-payload")
    observed, authority, binding = _order_models("submitted")
    _descriptor, _frozen, native = _portable_native_fixture(
        target_system_id="target:typed-payload",
        target_kind="software",
        target_profile="software",
        subject_revision="revision:typed-payload",
        plan=CANONICAL_SOFTWARE_LAYER_PLAN,
        observed_model=observed,
        authority_model=authority,
        refinement_binding=binding,
        members_by_kind=members,
    )

    label_only = json.loads(json.dumps(native.to_dict()))
    del label_only["members"][0]["details"]
    with pytest.raises(
        TargetSystemBlueprintError, match="fields are not exact-current"
    ):
        TargetBlueprintNativeReportSet.from_dict(label_only)

    detail_drift = json.loads(json.dumps(native.to_dict()))
    resource = next(
        row for row in detail_drift["members"] if row["member_kind"] == "resource"
    )
    resource["details"]["lifecycle_status"] = "stale"
    with pytest.raises(
        TargetSystemBlueprintError,
        match="canonical provider payload fingerprint",
    ):
        TargetBlueprintNativeReportSet.from_dict(detail_drift)


def test_native_software_requires_exact_io_and_effect_error_relations() -> None:
    behavior_id = "behavior:typed-relations"
    members = _software_native_members(behavior_id, label="typed-relations")
    observed, authority, binding = _order_models("submitted")

    missing_input_members = {
        kind: rows for kind, rows in members.items() if kind != "input"
    }
    descriptor, frozen, native = _portable_native_fixture(
        target_system_id="target:typed-relations-missing-input",
        target_kind="software",
        target_profile="software",
        subject_revision="revision:typed-relations-missing-input",
        plan=CANONICAL_SOFTWARE_LAYER_PLAN,
        observed_model=observed,
        authority_model=authority,
        refinement_binding=binding,
        members_by_kind=missing_input_members,
    )
    missing_input = qualify_target_system_from_native_reports(
        descriptor, frozen, native
    )
    assert not missing_input.ok
    assert any(
        gap.object_kind
        in {
            "observed_member_kind",
            "declared_member_kind",
            "native_behavior_port_relation",
            "native_model_port_coverage",
        }
        and gap.object_id.endswith("input")
        for gap in missing_input.gaps
    )

    interface_id = members["interface"][0][0]
    descriptor, frozen, native = _portable_native_fixture(
        target_system_id="target:typed-relations-effect-drift",
        target_kind="software",
        target_profile="software",
        subject_revision="revision:typed-relations-effect-drift",
        plan=CANONICAL_SOFTWARE_LAYER_PLAN,
        observed_model=observed,
        authority_model=authority,
        refinement_binding=binding,
        members_by_kind=members,
        observed_detail_overrides={
            ("interface", interface_id): {"effect_ids": ["effect:unexpected"]}
        },
    )
    effect_drift = qualify_target_system_from_native_reports(
        descriptor, frozen, native
    )
    assert not effect_drift.ok
    assert any(
        gap.object_kind == "native_effect_error_relation"
        for gap in effect_drift.gaps
    )

    implementation_id = members["implementation"][0][0]
    descriptor, frozen, native = _portable_native_fixture(
        target_system_id="target:typed-relations-content-drift",
        target_kind="software",
        target_profile="software",
        subject_revision="revision:typed-relations-content-drift",
        plan=CANONICAL_SOFTWARE_LAYER_PLAN,
        observed_model=observed,
        authority_model=authority,
        refinement_binding=binding,
        members_by_kind=members,
        observed_detail_overrides={
            ("implementation", implementation_id): {
                "content_fingerprint": fingerprint_value(
                    {"unexpected": "implementation-content"}
                )
            }
        },
    )
    content_drift = qualify_target_system_from_native_reports(
        descriptor, frozen, native
    )
    assert not content_drift.ok
    assert any(
        gap.layer == "implementation_inventory"
        and gap.object_kind == "native_member_contract_mismatch"
        for gap in content_drift.gaps
    )


@pytest.mark.parametrize(
    "source_kind",
    (
        "user_objective",
        "openspec",
        "spark",
        "openspark",
        "changelog",
        "target_contract",
    ),
)
def test_native_intent_contribution_accepts_each_direct_source_kind(
    source_kind: str,
) -> None:
    behavior_id = f"behavior:intent-source:{source_kind}"
    members = _software_native_members(
        behavior_id, label=f"intent-source-{source_kind}"
    )
    intent_id = members["intent"][0][0]
    observed, authority, binding = _order_models("submitted")
    descriptor, frozen, native = _portable_native_fixture(
        target_system_id=f"target:intent-source:{source_kind}",
        target_kind="software",
        target_profile="software",
        subject_revision=f"revision:intent-source:{source_kind}",
        plan=CANONICAL_SOFTWARE_LAYER_PLAN,
        observed_model=observed,
        authority_model=authority,
        refinement_binding=binding,
        members_by_kind=members,
        observed_detail_overrides={
            ("intent", intent_id): {"source_kind": source_kind}
        },
        authority_detail_overrides={
            ("intent", intent_id): {"source_kind": source_kind}
        },
    )
    loaded = TargetBlueprintNativeReportSet.from_dict(native.to_dict())
    report = qualify_target_system_from_native_reports(
        descriptor, frozen, loaded
    )
    assert report.ok


def test_native_intent_direct_source_kind_inventory_is_exact() -> None:
    assert TARGET_NATIVE_INTENT_SOURCE_KINDS == (
        "user_objective",
        "openspec",
        "spark",
        "openspark",
        "changelog",
        "target_contract",
    )


@pytest.mark.parametrize(
    ("contribution_status", "conflicts"),
    (("stale", ()), ("contradictory", ("contribution:conflicting",))),
)
def test_native_intent_stale_or_contradictory_contribution_forms_gap(
    contribution_status: str,
    conflicts: tuple[str, ...],
) -> None:
    behavior_id = f"behavior:intent-{contribution_status}"
    members = _software_native_members(
        behavior_id, label=f"intent-{contribution_status}"
    )
    intent_id = members["intent"][0][0]
    overrides = {
        "contribution_status": contribution_status,
        "conflicts_with_contribution_ids": list(conflicts),
    }
    observed, authority, binding = _order_models("submitted")
    descriptor, frozen, native = _portable_native_fixture(
        target_system_id=f"target:intent-{contribution_status}",
        target_kind="software",
        target_profile="software",
        subject_revision=f"revision:intent-{contribution_status}",
        plan=CANONICAL_SOFTWARE_LAYER_PLAN,
        observed_model=observed,
        authority_model=authority,
        refinement_binding=binding,
        members_by_kind=members,
        observed_detail_overrides={("intent", intent_id): overrides},
        authority_detail_overrides={("intent", intent_id): overrides},
    )
    report = qualify_target_system_from_native_reports(
        descriptor, frozen, native
    )
    assert not report.ok
    assert any(
        gap.object_kind == "native_intent_contribution_currentness"
        and gap.status == (
            "stale" if contribution_status == "stale" else "blocked"
        )
        for gap in report.gaps
    )


def test_native_intent_contribution_requires_exact_model_and_transition_binding() -> None:
    behavior_id = "behavior:intent-binding"
    members = _software_native_members(behavior_id, label="intent-binding")
    intent_id = members["intent"][0][0]
    observed, authority, binding = _order_models("submitted")
    descriptor, frozen, native = _portable_native_fixture(
        target_system_id="target:intent-binding",
        target_kind="software",
        target_profile="software",
        subject_revision="revision:intent-binding",
        plan=CANONICAL_SOFTWARE_LAYER_PLAN,
        observed_model=observed,
        authority_model=authority,
        refinement_binding=binding,
        members_by_kind=members,
        observed_detail_overrides={
            ("intent", intent_id): {"model_ids": ["portable:unknown"]}
        },
    )
    report = qualify_target_system_from_native_reports(
        descriptor, frozen, native
    )
    assert not report.ok
    assert any(
        gap.object_kind == "native_intent_model_binding"
        for gap in report.gaps
    )


def test_native_intent_source_kind_has_no_alias_or_fallback() -> None:
    behavior_id = "behavior:intent-source-no-fallback"
    members = _software_native_members(
        behavior_id, label="intent-source-no-fallback"
    )
    intent_id = members["intent"][0][0]
    observed, authority, binding = _order_models("submitted")
    with pytest.raises(
        TargetSystemBlueprintError,
        match="not a direct current source kind",
    ):
        _portable_native_fixture(
            target_system_id="target:intent-source-no-fallback",
            target_kind="software",
            target_profile="software",
            subject_revision="revision:intent-source-no-fallback",
            plan=CANONICAL_SOFTWARE_LAYER_PLAN,
            observed_model=observed,
            authority_model=authority,
            refinement_binding=binding,
            members_by_kind=members,
            observed_detail_overrides={
                ("intent", intent_id): {"source_kind": "product_brief"}
            },
        )


@pytest.mark.parametrize(
    "mutation",
    ("wrong_type", "wrong_detail_type", "duplicate_relation"),
)
def test_native_report_loader_rejects_types_and_duplicates_before_normalization(
    tmp_path: Path,
    mutation: str,
) -> None:
    behavior_id = "behavior:strict-loader"
    members = {
        "behavior": ((behavior_id, (behavior_id,)),),
        "input": (("input:strict-loader", (behavior_id,)),),
        "state": (("state:strict-loader", (behavior_id,)),),
        "output": (("output:strict-loader", (behavior_id,)),),
        "implementation": (("surface:strict-loader", (behavior_id,)),),
        "interface": (("interface:strict-loader", (behavior_id,)),),
        "test": (("test:strict-loader", (behavior_id,)),),
        "resource": (("resource:strict-loader", (behavior_id,)),),
        "intent": (("intent:strict-loader", (behavior_id,)),),
    }
    observed, authority, binding = _order_models("submitted")
    _descriptor_value, _frozen_value, native = _portable_native_fixture(
        target_system_id="target:strict-loader",
        target_kind="software",
        target_profile="software",
        subject_revision="revision:strict-loader",
        plan=CANONICAL_SOFTWARE_LAYER_PLAN,
        observed_model=observed,
        authority_model=authority,
        refinement_binding=binding,
        members_by_kind=members,
    )
    payload = native.to_dict()
    if mutation == "wrong_type":
        payload["members"][0]["member_id"] = 123
        expected = "JSON string"
    elif mutation == "wrong_detail_type":
        payload["members"][0]["details"]["input_ids"] = 123
        expected = "must be an array"
    else:
        payload["members"][0]["behavior_ids"] = [behavior_id, behavior_id]
        expected = "duplicate"
    path = tmp_path / f"{mutation}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(TargetSystemBlueprintError, match=expected):
        load_target_blueprint_native_report_set(path)


def test_native_route_blocks_unsafe_models_blank_identity_unbound_and_dangling_edges() -> None:
    behavior_id = "behavior:native-integrity"
    members = {
        "behavior": ((behavior_id, (behavior_id,)),),
        "input": (("input:native-integrity", (behavior_id,)),),
        "state": (("state:native-integrity", (behavior_id,)),),
        "output": (("output:native-integrity", (behavior_id,)),),
        "implementation": (("surface:native-integrity", (behavior_id,)),),
        "interface": (("interface:native-integrity", (behavior_id,)),),
        "test": (("test:native-integrity", (behavior_id,)),),
        "resource": (("resource:native-integrity", (behavior_id,)),),
        "intent": (("intent:native-integrity", (behavior_id,)),),
    }
    observed, authority, binding = _order_models("submitted")

    unsafe_observed = replace(
        observed,
        invariants=(
            PortableInvariant(
                "never-draft",
                ("draft",),
                "The initial draft state is forbidden in this negative fixture.",
            ),
        ),
    )
    unsafe_binding = replace(
        binding,
        child_model_fingerprint=unsafe_observed.fingerprint,
    )
    descriptor, frozen, native = _portable_native_fixture(
        target_system_id="target:native-unsafe",
        target_kind="software",
        target_profile="software",
        subject_revision="revision:native-unsafe",
        plan=CANONICAL_SOFTWARE_LAYER_PLAN,
        observed_model=unsafe_observed,
        authority_model=authority,
        refinement_binding=unsafe_binding,
        members_by_kind=members,
    )
    unsafe = qualify_target_system_from_native_reports(descriptor, frozen, native)
    assert not unsafe.ok
    assert any(
        gap.object_kind == "portable_model_finding"
        and "invariant_forbidden_state_reachable" in gap.object_id
        for gap in unsafe.gaps
    )

    temporal_observed = replace(
        observed,
        states=(*observed.states, PortableState("never_reached")),
        temporal_obligations=(
            PortableTemporalObligation(
                "eventually-never-reached",
                "eventually",
                trigger_state_ids=("draft",),
                target_state_ids=("never_reached",),
            ),
        ),
    )
    temporal_binding = replace(
        binding,
        child_model_fingerprint=temporal_observed.fingerprint,
    )
    descriptor, frozen, native = _portable_native_fixture(
        target_system_id="target:native-temporal-failure",
        target_kind="software",
        target_profile="software",
        subject_revision="revision:native-temporal-failure",
        plan=CANONICAL_SOFTWARE_LAYER_PLAN,
        observed_model=temporal_observed,
        authority_model=authority,
        refinement_binding=temporal_binding,
        members_by_kind=members,
    )
    temporal = qualify_target_system_from_native_reports(
        descriptor, frozen, native
    )
    assert not temporal.ok
    assert any(
        gap.object_kind == "portable_model_finding"
        and "eventual_dead_end" in gap.object_id
        for gap in temporal.gaps
    )

    descriptor, frozen, native = _portable_native_fixture(
        target_system_id="target:native-blank-refinement",
        target_kind="software",
        target_profile="software",
        subject_revision="revision:native-blank-refinement",
        plan=CANONICAL_SOFTWARE_LAYER_PLAN,
        observed_model=observed,
        authority_model=authority,
        refinement_binding=replace(binding, parent_model_fingerprint=""),
        members_by_kind=members,
    )
    blank = qualify_target_system_from_native_reports(descriptor, frozen, native)
    assert not blank.ok
    assert any(
        gap.object_kind == "portable_refinement_binding_identity"
        for gap in blank.gaps
    )

    descriptor, frozen, native = _portable_native_fixture(
        target_system_id="target:native-unbound-transition",
        target_kind="software",
        target_profile="software",
        subject_revision="revision:native-unbound-transition",
        plan=CANONICAL_SOFTWARE_LAYER_PLAN,
        observed_model=observed,
        authority_model=authority,
        refinement_binding=binding,
        members_by_kind=members,
        observed_model_transition_ids={behavior_id: ()},
        authority_model_transition_ids={behavior_id: ()},
    )
    unbound = qualify_target_system_from_native_reports(descriptor, frozen, native)
    assert not unbound.ok
    assert any(
        gap.object_kind
        in {"native_behavior_model_binding", "portable_transition_unbound"}
        for gap in unbound.gaps
    )

    dangling_members = {
        **members,
        "interface": (("interface:native-integrity", ("behavior:unknown",)),),
    }
    descriptor, frozen, native = _portable_native_fixture(
        target_system_id="target:native-dangling-relation",
        target_kind="software",
        target_profile="software",
        subject_revision="revision:native-dangling-relation",
        plan=CANONICAL_SOFTWARE_LAYER_PLAN,
        observed_model=observed,
        authority_model=authority,
        refinement_binding=binding,
        members_by_kind=dangling_members,
    )
    dangling = qualify_target_system_from_native_reports(descriptor, frozen, native)
    assert not dangling.ok
    assert any(
        gap.object_kind == "native_behavior_relation_unknown"
        for gap in dangling.gaps
    )


def test_native_report_replay_is_blocked_and_typed_alternatives_remain_valid() -> None:
    behavior_id = "behavior:external-verification"
    members = {
        "behavior": ((behavior_id, (behavior_id,)),),
        "input": (("input:external-order", (behavior_id,)),),
        "state": (("state:external-order", (behavior_id,)),),
        "output": (("output:external-order", (behavior_id,)),),
        "external_owner": (("external-owner:order-service", (behavior_id,)),),
        "interface": (("interface:order-service", (behavior_id,)),),
        "verification": (("native-check:order-service", (behavior_id,)),),
        "resource": (("resource:service-contract", (behavior_id,)),),
        "intent": (("intent:external-order", (behavior_id,)),),
    }
    observed, authority, binding = _order_models("submitted")
    descriptor, frozen, native = _portable_native_fixture(
        target_system_id="target:external-verification",
        target_kind="software_service",
        target_profile="software",
        subject_revision="revision:external-verification",
        plan=CANONICAL_SOFTWARE_LAYER_PLAN,
        observed_model=observed,
        authority_model=authority,
        refinement_binding=binding,
        members_by_kind=members,
    )
    current = qualify_target_system_from_native_reports(descriptor, frozen, native)
    assert current.ok

    replayed = replace(
        native,
        boundary_fingerprint=fingerprint_value({"other": "boundary"}),
    )
    blocked = qualify_target_system_from_native_reports(
        descriptor, frozen, replayed
    )
    assert not blocked.ok
    assert any(
        gap.object_kind == "native_boundary_identity" for gap in blocked.gaps
    )
