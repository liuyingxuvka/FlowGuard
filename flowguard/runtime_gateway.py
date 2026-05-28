"""Runtime gateway adoption reviews for FlowGuard-backed state writes."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .core import FrozenMetadata, freeze_metadata
from .export import to_jsonable


ADOPTION_LEVEL_DESIGN_MODEL = "design_model"
ADOPTION_LEVEL_TEST_ALIGNED = "test_aligned"
ADOPTION_LEVEL_RUNTIME_GATEWAY = "runtime_gateway"

RUNTIME_GATEWAY_ADOPTION_LEVELS = (
    ADOPTION_LEVEL_DESIGN_MODEL,
    ADOPTION_LEVEL_TEST_ALIGNED,
    ADOPTION_LEVEL_RUNTIME_GATEWAY,
)

RUNTIME_WRITE_DIRECT = "direct"
RUNTIME_WRITE_GATEWAY = "gateway"
RUNTIME_WRITE_READ_ONLY = "read_only"

RUNTIME_WRITE_KINDS = (
    RUNTIME_WRITE_DIRECT,
    RUNTIME_WRITE_GATEWAY,
    RUNTIME_WRITE_READ_ONLY,
)

RUNTIME_GATEWAY_PASSING_STATUSES = ("passed", "pass", "ok")

RUNTIME_GATEWAY_DECISION_GREEN = "runtime_gateway_adoption_green"
RUNTIME_GATEWAY_DECISION_BLOCKED = "runtime_gateway_adoption_blocked"
RUNTIME_GATEWAY_DECISION_SCOPED = "runtime_gateway_adoption_scoped"


def _as_tuple(values: Sequence[str] | str | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        return (values,) if values else ()
    return tuple(str(value) for value in values if str(value))


def _metadata(metadata: Mapping[str, Any] | Iterable[tuple[str, Any]] | None) -> FrozenMetadata:
    return freeze_metadata(metadata)


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


@dataclass(frozen=True)
class RuntimeStateSurface:
    """One state surface whose runtime writes may need gateway protection."""

    surface_id: str
    description: str = ""
    paths: tuple[str, ...] = ()
    critical: bool = True
    owner_gateway_ids: tuple[str, ...] = ()
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        surface_id = str(self.surface_id)
        if not surface_id:
            raise ValueError("surface_id is required")
        object.__setattr__(self, "surface_id", surface_id)
        object.__setattr__(self, "description", str(self.description or ""))
        object.__setattr__(self, "paths", _as_tuple(self.paths))
        object.__setattr__(self, "critical", bool(self.critical))
        object.__setattr__(self, "owner_gateway_ids", _as_tuple(self.owner_gateway_ids))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "surface_id": self.surface_id,
            "description": self.description,
            "paths": list(self.paths),
            "critical": self.critical,
            "owner_gateway_ids": list(self.owner_gateway_ids),
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class RuntimeGatewayContract:
    """Runtime gateway that is allowed to mutate declared state surfaces."""

    gateway_id: str
    managed_surface_ids: tuple[str, ...] = ()
    description: str = ""
    requires_atomic_commit: bool = True
    requires_replay_observation: bool = True
    requires_step_contract_binding: bool = True
    requires_code_boundary_binding: bool = True
    requires_proof_artifact: bool = True
    step_contract_ids: tuple[str, ...] = ()
    code_boundary_ids: tuple[str, ...] = ()
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        gateway_id = str(self.gateway_id)
        if not gateway_id:
            raise ValueError("gateway_id is required")
        object.__setattr__(self, "gateway_id", gateway_id)
        object.__setattr__(self, "managed_surface_ids", _as_tuple(self.managed_surface_ids))
        object.__setattr__(self, "description", str(self.description or ""))
        object.__setattr__(self, "requires_atomic_commit", bool(self.requires_atomic_commit))
        object.__setattr__(
            self,
            "requires_replay_observation",
            bool(self.requires_replay_observation),
        )
        object.__setattr__(
            self,
            "requires_step_contract_binding",
            bool(self.requires_step_contract_binding),
        )
        object.__setattr__(
            self,
            "requires_code_boundary_binding",
            bool(self.requires_code_boundary_binding),
        )
        object.__setattr__(self, "requires_proof_artifact", bool(self.requires_proof_artifact))
        object.__setattr__(self, "step_contract_ids", _as_tuple(self.step_contract_ids))
        object.__setattr__(self, "code_boundary_ids", _as_tuple(self.code_boundary_ids))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "gateway_id": self.gateway_id,
            "managed_surface_ids": list(self.managed_surface_ids),
            "description": self.description,
            "requires_atomic_commit": self.requires_atomic_commit,
            "requires_replay_observation": self.requires_replay_observation,
            "requires_step_contract_binding": self.requires_step_contract_binding,
            "requires_code_boundary_binding": self.requires_code_boundary_binding,
            "requires_proof_artifact": self.requires_proof_artifact,
            "step_contract_ids": list(self.step_contract_ids),
            "code_boundary_ids": list(self.code_boundary_ids),
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class RuntimeWriteObservation:
    """Observed or audited write path for one runtime state surface."""

    observation_id: str
    surface_id: str
    path: str = ""
    symbol: str = ""
    write_kind: str = RUNTIME_WRITE_DIRECT
    gateway_id: str = ""
    action_id: str = ""
    step_contract_ids: tuple[str, ...] = ()
    code_boundary_ids: tuple[str, ...] = ()
    proof_artifact_ids: tuple[str, ...] = ()
    current: bool = True
    result_status: str = "passed"
    legacy_bypass_reason: str = ""
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        observation_id = str(self.observation_id)
        if not observation_id:
            raise ValueError("observation_id is required")
        surface_id = str(self.surface_id)
        if not surface_id:
            raise ValueError("surface_id is required")
        write_kind = str(self.write_kind or RUNTIME_WRITE_DIRECT).lower()
        if write_kind not in RUNTIME_WRITE_KINDS:
            raise ValueError(f"write_kind must be one of {RUNTIME_WRITE_KINDS!r}")
        object.__setattr__(self, "observation_id", observation_id)
        object.__setattr__(self, "surface_id", surface_id)
        object.__setattr__(self, "path", str(self.path or ""))
        object.__setattr__(self, "symbol", str(self.symbol or ""))
        object.__setattr__(self, "write_kind", write_kind)
        object.__setattr__(self, "gateway_id", str(self.gateway_id or ""))
        object.__setattr__(self, "action_id", str(self.action_id or ""))
        object.__setattr__(self, "step_contract_ids", _as_tuple(self.step_contract_ids))
        object.__setattr__(self, "code_boundary_ids", _as_tuple(self.code_boundary_ids))
        object.__setattr__(self, "proof_artifact_ids", _as_tuple(self.proof_artifact_ids))
        object.__setattr__(self, "current", bool(self.current))
        object.__setattr__(self, "result_status", str(self.result_status or "").lower())
        object.__setattr__(self, "legacy_bypass_reason", str(self.legacy_bypass_reason or ""))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "surface_id": self.surface_id,
            "path": self.path,
            "symbol": self.symbol,
            "write_kind": self.write_kind,
            "gateway_id": self.gateway_id,
            "action_id": self.action_id,
            "step_contract_ids": list(self.step_contract_ids),
            "code_boundary_ids": list(self.code_boundary_ids),
            "proof_artifact_ids": list(self.proof_artifact_ids),
            "current": self.current,
            "result_status": self.result_status,
            "legacy_bypass_reason": self.legacy_bypass_reason,
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class RuntimeGatewayAdoptionPlan:
    """Plan for reviewing whether runtime state writes are FlowGuard-gated."""

    project_id: str
    target_level: str = ADOPTION_LEVEL_DESIGN_MODEL
    state_surfaces: tuple[RuntimeStateSurface, ...] = ()
    gateways: tuple[RuntimeGatewayContract, ...] = ()
    write_observations: tuple[RuntimeWriteObservation, ...] = ()
    complete_inventory_evidence_ids: tuple[str, ...] = ()
    require_complete_inventory: bool = True
    require_observed_writer_for_critical_surfaces: bool = True
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        project_id = str(self.project_id)
        if not project_id:
            raise ValueError("project_id is required")
        target_level = str(self.target_level or ADOPTION_LEVEL_DESIGN_MODEL)
        if target_level not in RUNTIME_GATEWAY_ADOPTION_LEVELS:
            raise ValueError(
                "target_level must be one of "
                f"{RUNTIME_GATEWAY_ADOPTION_LEVELS!r}; got {target_level!r}"
            )
        object.__setattr__(self, "project_id", project_id)
        object.__setattr__(self, "target_level", target_level)
        object.__setattr__(
            self,
            "state_surfaces",
            tuple(
                item if isinstance(item, RuntimeStateSurface) else RuntimeStateSurface(**item)
                for item in self.state_surfaces
            ),
        )
        object.__setattr__(
            self,
            "gateways",
            tuple(
                item
                if isinstance(item, RuntimeGatewayContract)
                else RuntimeGatewayContract(**item)
                for item in self.gateways
            ),
        )
        object.__setattr__(
            self,
            "write_observations",
            tuple(
                item
                if isinstance(item, RuntimeWriteObservation)
                else RuntimeWriteObservation(**item)
                for item in self.write_observations
            ),
        )
        object.__setattr__(
            self,
            "complete_inventory_evidence_ids",
            _as_tuple(self.complete_inventory_evidence_ids),
        )
        object.__setattr__(
            self,
            "require_complete_inventory",
            bool(self.require_complete_inventory),
        )
        object.__setattr__(
            self,
            "require_observed_writer_for_critical_surfaces",
            bool(self.require_observed_writer_for_critical_surfaces),
        )
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    @property
    def requires_runtime_gateway(self) -> bool:
        return self.target_level == ADOPTION_LEVEL_RUNTIME_GATEWAY

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "target_level": self.target_level,
            "state_surfaces": [surface.to_dict() for surface in self.state_surfaces],
            "gateways": [gateway.to_dict() for gateway in self.gateways],
            "write_observations": [
                observation.to_dict() for observation in self.write_observations
            ],
            "complete_inventory_evidence_ids": list(self.complete_inventory_evidence_ids),
            "require_complete_inventory": self.require_complete_inventory,
            "require_observed_writer_for_critical_surfaces": (
                self.require_observed_writer_for_critical_surfaces
            ),
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class RuntimeGatewayFinding:
    """One runtime gateway adoption gap."""

    code: str
    message: str
    severity: str = "error"
    surface_id: str = ""
    gateway_id: str = ""
    observation_id: str = ""
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        severity = str(self.severity or "error").lower()
        if severity not in ("error", "warning"):
            raise ValueError("severity must be 'error' or 'warning'")
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "surface_id", str(self.surface_id or ""))
        object.__setattr__(self, "gateway_id", str(self.gateway_id or ""))
        object.__setattr__(self, "observation_id", str(self.observation_id or ""))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    @property
    def blocks_runtime_gateway(self) -> bool:
        return self.severity == "error"

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "surface_id": self.surface_id,
            "gateway_id": self.gateway_id,
            "observation_id": self.observation_id,
            "blocks_runtime_gateway": self.blocks_runtime_gateway,
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class RuntimeGatewayAdoptionReport:
    """Structured runtime gateway adoption review result."""

    plan: RuntimeGatewayAdoptionPlan
    findings: tuple[RuntimeGatewayFinding, ...] = ()
    decision: str = ""
    summary: str = ""

    def __post_init__(self) -> None:
        findings = tuple(self.findings)
        object.__setattr__(self, "findings", findings)
        if not self.decision:
            object.__setattr__(self, "decision", _decision(self.plan, findings))
        if not self.summary:
            object.__setattr__(self, "summary", _summary(self.plan, findings, self.decision))

    @property
    def ok(self) -> bool:
        return not any(finding.blocks_runtime_gateway for finding in self.findings)

    def format_text(self, max_findings: int = 8) -> str:
        lines = [
            "=== runtime gateway adoption ===",
            f"project: {self.plan.project_id}",
            f"target_level: {self.plan.target_level}",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"decision: {self.decision}",
            self.summary,
        ]
        for finding in self.findings[:max_findings]:
            lines.append(f"- {finding.severity.upper()} {finding.code}: {finding.message}")
        if len(self.findings) > max_findings:
            lines.append(f"- ... {len(self.findings) - max_findings} more")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "runtime_gateway_adoption_report",
            "ok": self.ok,
            "decision": self.decision,
            "summary": self.summary,
            "plan": self.plan.to_dict(),
            "findings": [finding.to_dict() for finding in self.findings],
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def review_runtime_gateway_adoption(
    plan: RuntimeGatewayAdoptionPlan,
) -> RuntimeGatewayAdoptionReport:
    """Review whether critical runtime writes are mediated by FlowGuard gateways."""

    plan = plan if isinstance(plan, RuntimeGatewayAdoptionPlan) else RuntimeGatewayAdoptionPlan(**plan)
    runtime_required = plan.requires_runtime_gateway
    findings: list[RuntimeGatewayFinding] = []

    severity = "error" if runtime_required else "warning"
    surfaces = {surface.surface_id: surface for surface in plan.state_surfaces}
    gateways = {gateway.gateway_id: gateway for gateway in plan.gateways}
    managed_by_gateway: dict[str, set[str]] = {}
    for gateway in plan.gateways:
        for surface_id in gateway.managed_surface_ids:
            managed_by_gateway.setdefault(surface_id, set()).add(gateway.gateway_id)

    if runtime_required and plan.require_complete_inventory and not plan.complete_inventory_evidence_ids:
        findings.append(
            RuntimeGatewayFinding(
                "missing_complete_writer_inventory",
                "runtime-gateway adoption requires current evidence that all critical writer paths were inventoried",
                "error",
            )
        )

    for surface in plan.state_surfaces:
        owner_gateway_ids = _surface_owner_gateway_ids(surface, managed_by_gateway)
        if surface.critical and not owner_gateway_ids:
            findings.append(
                RuntimeGatewayFinding(
                    "critical_surface_missing_gateway_owner",
                    f"critical surface {surface.surface_id!r} has no gateway owner",
                    severity,
                    surface_id=surface.surface_id,
                )
            )
        for gateway_id in owner_gateway_ids:
            if gateway_id not in gateways:
                findings.append(
                    RuntimeGatewayFinding(
                        "surface_unknown_gateway_owner",
                        f"surface {surface.surface_id!r} references unknown gateway {gateway_id!r}",
                        severity,
                        surface_id=surface.surface_id,
                        gateway_id=gateway_id,
                    )
                )

    for gateway in plan.gateways:
        if not gateway.managed_surface_ids:
            findings.append(
                RuntimeGatewayFinding(
                    "gateway_manages_no_surfaces",
                    f"gateway {gateway.gateway_id!r} does not manage any state surfaces",
                    severity,
                    gateway_id=gateway.gateway_id,
                )
            )
        if runtime_required and not gateway.requires_atomic_commit:
            findings.append(
                RuntimeGatewayFinding(
                    "gateway_missing_atomic_commit_requirement",
                    f"gateway {gateway.gateway_id!r} does not require atomic commit",
                    "error",
                    gateway_id=gateway.gateway_id,
                )
            )
        if runtime_required and not gateway.requires_replay_observation:
            findings.append(
                RuntimeGatewayFinding(
                    "gateway_missing_replay_observation_requirement",
                    f"gateway {gateway.gateway_id!r} does not require replay observation",
                    "error",
                    gateway_id=gateway.gateway_id,
                )
            )

    observations_by_surface: dict[str, list[RuntimeWriteObservation]] = {}
    for observation in plan.write_observations:
        observations_by_surface.setdefault(observation.surface_id, []).append(observation)
        surface = surfaces.get(observation.surface_id)
        if surface is None:
            findings.append(
                RuntimeGatewayFinding(
                    "writer_observation_unknown_surface",
                    f"writer observation {observation.observation_id!r} targets unknown surface {observation.surface_id!r}",
                    severity,
                    surface_id=observation.surface_id,
                    observation_id=observation.observation_id,
                )
            )
            continue
        _review_observation(
            observation,
            surface,
            gateways,
            findings,
            severity=severity,
            runtime_required=runtime_required,
        )

    if runtime_required and plan.require_observed_writer_for_critical_surfaces:
        for surface in plan.state_surfaces:
            if not surface.critical:
                continue
            current_observations = [
                observation
                for observation in observations_by_surface.get(surface.surface_id, ())
                if observation.current
            ]
            if not current_observations:
                findings.append(
                    RuntimeGatewayFinding(
                        "critical_surface_missing_writer_observation",
                        f"critical surface {surface.surface_id!r} has no current writer observation",
                        "error",
                        surface_id=surface.surface_id,
                    )
                )

    return RuntimeGatewayAdoptionReport(plan=plan, findings=tuple(findings))


def _surface_owner_gateway_ids(
    surface: RuntimeStateSurface,
    managed_by_gateway: Mapping[str, set[str]],
) -> tuple[str, ...]:
    return _unique(surface.owner_gateway_ids + tuple(sorted(managed_by_gateway.get(surface.surface_id, ()))))


def _review_observation(
    observation: RuntimeWriteObservation,
    surface: RuntimeStateSurface,
    gateways: Mapping[str, RuntimeGatewayContract],
    findings: list[RuntimeGatewayFinding],
    *,
    severity: str,
    runtime_required: bool,
) -> None:
    if not observation.current:
        findings.append(
            RuntimeGatewayFinding(
                "writer_observation_stale",
                f"writer observation {observation.observation_id!r} is not current",
                severity,
                surface_id=surface.surface_id,
                gateway_id=observation.gateway_id,
                observation_id=observation.observation_id,
            )
        )
    if observation.result_status not in RUNTIME_GATEWAY_PASSING_STATUSES:
        findings.append(
            RuntimeGatewayFinding(
                "writer_observation_not_passing",
                f"writer observation {observation.observation_id!r} has non-passing status {observation.result_status!r}",
                severity,
                surface_id=surface.surface_id,
                gateway_id=observation.gateway_id,
                observation_id=observation.observation_id,
            )
        )

    if not surface.critical or not runtime_required or observation.write_kind == RUNTIME_WRITE_READ_ONLY:
        return

    if observation.legacy_bypass_reason:
        findings.append(
            RuntimeGatewayFinding(
                "declared_legacy_gateway_bypass",
                f"writer observation {observation.observation_id!r} declares a legacy bypass: {observation.legacy_bypass_reason}",
                "error",
                surface_id=surface.surface_id,
                gateway_id=observation.gateway_id,
                observation_id=observation.observation_id,
            )
        )

    if observation.write_kind != RUNTIME_WRITE_GATEWAY or not observation.gateway_id:
        findings.append(
            RuntimeGatewayFinding(
                "direct_state_write_bypasses_gateway",
                f"writer observation {observation.observation_id!r} writes critical surface {surface.surface_id!r} without a gateway",
                "error",
                surface_id=surface.surface_id,
                observation_id=observation.observation_id,
            )
        )
        return

    gateway = gateways.get(observation.gateway_id)
    if gateway is None:
        findings.append(
            RuntimeGatewayFinding(
                "writer_observation_unknown_gateway",
                f"writer observation {observation.observation_id!r} references unknown gateway {observation.gateway_id!r}",
                "error",
                surface_id=surface.surface_id,
                gateway_id=observation.gateway_id,
                observation_id=observation.observation_id,
            )
        )
        return
    if surface.surface_id not in gateway.managed_surface_ids:
        findings.append(
            RuntimeGatewayFinding(
                "gateway_surface_mismatch",
                f"gateway {gateway.gateway_id!r} does not manage surface {surface.surface_id!r}",
                "error",
                surface_id=surface.surface_id,
                gateway_id=gateway.gateway_id,
                observation_id=observation.observation_id,
            )
        )
    if gateway.requires_step_contract_binding and not observation.step_contract_ids:
        findings.append(
            RuntimeGatewayFinding(
                "missing_step_contract_evidence",
                f"gateway write {observation.observation_id!r} has no workflow step contract id",
                "error",
                surface_id=surface.surface_id,
                gateway_id=gateway.gateway_id,
                observation_id=observation.observation_id,
            )
        )
    if gateway.requires_code_boundary_binding and not observation.code_boundary_ids:
        findings.append(
            RuntimeGatewayFinding(
                "missing_code_boundary_evidence",
                f"gateway write {observation.observation_id!r} has no code-boundary id",
                "error",
                surface_id=surface.surface_id,
                gateway_id=gateway.gateway_id,
                observation_id=observation.observation_id,
            )
        )
    if gateway.requires_proof_artifact and not observation.proof_artifact_ids:
        findings.append(
            RuntimeGatewayFinding(
                "missing_proof_artifact_evidence",
                f"gateway write {observation.observation_id!r} has no proof artifact id",
                "error",
                surface_id=surface.surface_id,
                gateway_id=gateway.gateway_id,
                observation_id=observation.observation_id,
            )
        )


def _decision(
    plan: RuntimeGatewayAdoptionPlan,
    findings: tuple[RuntimeGatewayFinding, ...],
) -> str:
    blocked = any(finding.blocks_runtime_gateway for finding in findings)
    if plan.target_level == ADOPTION_LEVEL_RUNTIME_GATEWAY:
        return RUNTIME_GATEWAY_DECISION_BLOCKED if blocked else RUNTIME_GATEWAY_DECISION_GREEN
    if findings:
        return RUNTIME_GATEWAY_DECISION_SCOPED
    return plan.target_level


def _summary(
    plan: RuntimeGatewayAdoptionPlan,
    findings: tuple[RuntimeGatewayFinding, ...],
    decision: str,
) -> str:
    errors = sum(1 for finding in findings if finding.blocks_runtime_gateway)
    warnings = len(findings) - errors
    return (
        f"{decision}: surfaces={len(plan.state_surfaces)} "
        f"gateways={len(plan.gateways)} observations={len(plan.write_observations)} "
        f"errors={errors} warnings={warnings}"
    )


__all__ = [
    "ADOPTION_LEVEL_DESIGN_MODEL",
    "ADOPTION_LEVEL_RUNTIME_GATEWAY",
    "ADOPTION_LEVEL_TEST_ALIGNED",
    "RUNTIME_GATEWAY_ADOPTION_LEVELS",
    "RUNTIME_GATEWAY_DECISION_BLOCKED",
    "RUNTIME_GATEWAY_DECISION_GREEN",
    "RUNTIME_GATEWAY_DECISION_SCOPED",
    "RUNTIME_GATEWAY_PASSING_STATUSES",
    "RUNTIME_WRITE_DIRECT",
    "RUNTIME_WRITE_GATEWAY",
    "RUNTIME_WRITE_KINDS",
    "RUNTIME_WRITE_READ_ONLY",
    "RuntimeGatewayAdoptionPlan",
    "RuntimeGatewayAdoptionReport",
    "RuntimeGatewayContract",
    "RuntimeGatewayFinding",
    "RuntimeStateSurface",
    "RuntimeWriteObservation",
    "review_runtime_gateway_adoption",
]
