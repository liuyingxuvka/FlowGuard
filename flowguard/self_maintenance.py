"""Route-first self-maintenance helpers for FlowGuard.

This module makes FlowGuard's own maintenance path easier for AI agents to
follow. It describes route profiles, thin AI entry profiles, field layers, and
child closure reports. It does not replace the owning specialist routes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .export import to_jsonable


SELF_MAINTENANCE_ROUTE = "flowguard_self_maintenance"

FIELD_LAYER_CORE = "core"
FIELD_LAYER_ROUTE_OWNED = "route_owned"
FIELD_LAYER_SHARED_EVIDENCE = "shared_evidence"
FIELD_LAYER_METADATA_DISPLAY = "metadata_display"
FIELD_LAYER_COMPATIBILITY = "compatibility_disposition"
FIELD_LAYERS = (
    FIELD_LAYER_CORE,
    FIELD_LAYER_ROUTE_OWNED,
    FIELD_LAYER_SHARED_EVIDENCE,
    FIELD_LAYER_METADATA_DISPLAY,
    FIELD_LAYER_COMPATIBILITY,
)

SELF_MAINTENANCE_STATUS_PASS = "pass"
SELF_MAINTENANCE_STATUS_SCOPED = "scoped"
SELF_MAINTENANCE_STATUS_BLOCKED = "blocked"
SELF_MAINTENANCE_STATUS_STALE = "stale"
SELF_MAINTENANCE_STATUS_SKIPPED = "skipped"
SELF_MAINTENANCE_STATUSES = (
    SELF_MAINTENANCE_STATUS_PASS,
    SELF_MAINTENANCE_STATUS_SCOPED,
    SELF_MAINTENANCE_STATUS_BLOCKED,
    SELF_MAINTENANCE_STATUS_STALE,
    SELF_MAINTENANCE_STATUS_SKIPPED,
)

SELF_MAINTENANCE_DECISION_FULL = "self_maintenance_full"
SELF_MAINTENANCE_DECISION_SCOPED = "self_maintenance_scoped"
SELF_MAINTENANCE_DECISION_BLOCKED = "self_maintenance_blocked"

SELF_MAINTENANCE_FINDING_INFO = "info"
SELF_MAINTENANCE_FINDING_GAP = "gap"
SELF_MAINTENANCE_FINDING_BLOCKER = "blocker"

ROUTE_ROLE_PUBLIC_OWNER = "public_owner"
ROUTE_ROLE_DELEGATED_MODE = "delegated_mode"
ROUTE_ROLE_INTERNAL_FEEDER = "internal_feeder"
ROUTE_ROLE_DATA_HELPER = "data_helper"
ROUTE_ROLE_ARCHIVE_ONLY = "archive_only"
ROUTE_ROLES = (
    ROUTE_ROLE_PUBLIC_OWNER,
    ROUTE_ROLE_DELEGATED_MODE,
    ROUTE_ROLE_INTERNAL_FEEDER,
    ROUTE_ROLE_DATA_HELPER,
    ROUTE_ROLE_ARCHIVE_ONLY,
)

ENTRY_POLICY_DIRECT = "direct"
ENTRY_POLICY_VIA_OWNER = "via_owner"
ENTRY_POLICY_INTERNAL_ONLY = "internal_only"
ENTRY_POLICIES = (
    ENTRY_POLICY_DIRECT,
    ENTRY_POLICY_VIA_OWNER,
    ENTRY_POLICY_INTERNAL_ONLY,
)

CLEANUP_DISPOSITION_KEEP = "keep"
CLEANUP_DISPOSITION_ABSORB = "absorb"
CLEANUP_DISPOSITION_DELETE = "delete"
CLEANUP_DISPOSITION_FACADE_REVIEW = "facade_review"
CLEANUP_DISPOSITIONS = (
    CLEANUP_DISPOSITION_KEEP,
    CLEANUP_DISPOSITION_ABSORB,
    CLEANUP_DISPOSITION_DELETE,
    CLEANUP_DISPOSITION_FACADE_REVIEW,
)


def _as_tuple(values: Sequence[str] | str | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        return (values,) if values else ()
    return tuple(str(value) for value in values if str(value))


def _coerce_child_report(value: Any) -> "SelfMaintenanceChildReport":
    if isinstance(value, SelfMaintenanceChildReport):
        return value
    if isinstance(value, Mapping):
        return SelfMaintenanceChildReport(**dict(value))
    raise TypeError(f"cannot coerce {type(value).__name__} to SelfMaintenanceChildReport")


@dataclass(frozen=True)
class RouteProfile:
    """Compact AI-facing profile for one FlowGuard maintenance route."""

    route_id: str
    trigger: str
    minimal_inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    evidence_owner: str = ""
    next_actions: tuple[str, ...] = ()
    api_group: str = ""
    template_factory: str = ""
    skill_name: str = ""
    summary: str = ""
    route_role: str = ROUTE_ROLE_PUBLIC_OWNER
    entry_policy: str = ENTRY_POLICY_DIRECT
    canonical_owner_route: str = ""
    absorbed_by_route: str = ""
    cleanup_disposition: str = CLEANUP_DISPOSITION_KEEP
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "route_id", str(self.route_id))
        object.__setattr__(self, "trigger", str(self.trigger))
        object.__setattr__(self, "minimal_inputs", _as_tuple(self.minimal_inputs))
        object.__setattr__(self, "outputs", _as_tuple(self.outputs))
        object.__setattr__(self, "evidence_owner", str(self.evidence_owner or self.route_id))
        object.__setattr__(self, "next_actions", _as_tuple(self.next_actions))
        object.__setattr__(self, "api_group", str(self.api_group or self.route_id))
        object.__setattr__(self, "template_factory", str(self.template_factory))
        object.__setattr__(self, "skill_name", str(self.skill_name))
        object.__setattr__(self, "summary", str(self.summary))
        route_role = str(self.route_role or ROUTE_ROLE_PUBLIC_OWNER)
        if route_role not in ROUTE_ROLES:
            raise ValueError(f"unknown route role: {route_role}")
        entry_policy = str(self.entry_policy or ENTRY_POLICY_DIRECT)
        if entry_policy not in ENTRY_POLICIES:
            raise ValueError(f"unknown entry policy: {entry_policy}")
        cleanup_disposition = str(self.cleanup_disposition or CLEANUP_DISPOSITION_KEEP)
        if cleanup_disposition not in CLEANUP_DISPOSITIONS:
            raise ValueError(f"unknown cleanup disposition: {cleanup_disposition}")
        object.__setattr__(self, "route_role", route_role)
        object.__setattr__(self, "entry_policy", entry_policy)
        object.__setattr__(self, "canonical_owner_route", str(self.canonical_owner_route))
        object.__setattr__(self, "absorbed_by_route", str(self.absorbed_by_route))
        object.__setattr__(self, "cleanup_disposition", cleanup_disposition)
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "trigger": self.trigger,
            "minimal_inputs": list(self.minimal_inputs),
            "outputs": list(self.outputs),
            "evidence_owner": self.evidence_owner,
            "next_actions": list(self.next_actions),
            "api_group": self.api_group,
            "template_factory": self.template_factory,
            "skill_name": self.skill_name,
            "summary": self.summary,
            "route_role": self.route_role,
            "entry_policy": self.entry_policy,
            "canonical_owner_route": self.canonical_owner_route,
            "absorbed_by_route": self.absorbed_by_route,
            "cleanup_disposition": self.cleanup_disposition,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class AIMaintenanceProfile:
    """Thin entry profile for common AI self-maintenance tasks."""

    profile_id: str
    intent: str
    first_route: str
    minimal_inputs: tuple[str, ...] = ()
    expansion_routes: tuple[str, ...] = ()
    broad_claim_requires: tuple[str, ...] = ()
    flat_surface_warning: str = "Do not start from __all__ or the full helper API."

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", str(self.profile_id))
        object.__setattr__(self, "intent", str(self.intent))
        object.__setattr__(self, "first_route", str(self.first_route))
        object.__setattr__(self, "minimal_inputs", _as_tuple(self.minimal_inputs))
        object.__setattr__(self, "expansion_routes", _as_tuple(self.expansion_routes))
        object.__setattr__(self, "broad_claim_requires", _as_tuple(self.broad_claim_requires))
        object.__setattr__(self, "flat_surface_warning", str(self.flat_surface_warning))

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "intent": self.intent,
            "first_route": self.first_route,
            "minimal_inputs": list(self.minimal_inputs),
            "expansion_routes": list(self.expansion_routes),
            "broad_claim_requires": list(self.broad_claim_requires),
            "flat_surface_warning": self.flat_surface_warning,
        }


@dataclass(frozen=True)
class FieldLayerProfile:
    """Grouped field exposure profile for AI-facing prompts and reports."""

    layer_id: str
    field_kinds: tuple[str, ...] = ()
    first_read_exposure: str = ""
    owner_route: str = ""
    expansion_required_for: tuple[str, ...] = ()
    disposition_required: bool = False
    summary: str = ""

    def __post_init__(self) -> None:
        if self.layer_id not in FIELD_LAYERS:
            raise ValueError(f"unknown field layer: {self.layer_id}")
        object.__setattr__(self, "field_kinds", _as_tuple(self.field_kinds))
        object.__setattr__(self, "first_read_exposure", str(self.first_read_exposure))
        object.__setattr__(self, "owner_route", str(self.owner_route))
        object.__setattr__(self, "expansion_required_for", _as_tuple(self.expansion_required_for))
        object.__setattr__(self, "disposition_required", bool(self.disposition_required))
        object.__setattr__(self, "summary", str(self.summary))

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer_id": self.layer_id,
            "field_kinds": list(self.field_kinds),
            "first_read_exposure": self.first_read_exposure,
            "owner_route": self.owner_route,
            "expansion_required_for": list(self.expansion_required_for),
            "disposition_required": self.disposition_required,
            "summary": self.summary,
        }


@dataclass(frozen=True)
class SelfMaintenanceChildReport:
    """Closure report from one self-maintenance child route."""

    child_id: str
    owner_guard: str
    artifact_kind: str
    closure_status: str = SELF_MAINTENANCE_STATUS_SKIPPED
    findings: tuple[str, ...] = ()
    missing_inputs: tuple[str, ...] = ()
    stale_evidence: tuple[str, ...] = ()
    skipped_checks: tuple[str, ...] = ()
    next_actions: tuple[str, ...] = ()
    safe_claim: str = ""
    unsafe_claim_boundary: str = ""
    current: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "child_id", str(self.child_id))
        object.__setattr__(self, "owner_guard", str(self.owner_guard))
        object.__setattr__(self, "artifact_kind", str(self.artifact_kind))
        status = str(self.closure_status or SELF_MAINTENANCE_STATUS_SKIPPED)
        if status not in SELF_MAINTENANCE_STATUSES:
            raise ValueError(f"unknown self-maintenance status: {status}")
        object.__setattr__(self, "closure_status", status)
        object.__setattr__(self, "findings", _as_tuple(self.findings))
        object.__setattr__(self, "missing_inputs", _as_tuple(self.missing_inputs))
        object.__setattr__(self, "stale_evidence", _as_tuple(self.stale_evidence))
        object.__setattr__(self, "skipped_checks", _as_tuple(self.skipped_checks))
        object.__setattr__(self, "next_actions", _as_tuple(self.next_actions))
        object.__setattr__(self, "safe_claim", str(self.safe_claim))
        object.__setattr__(self, "unsafe_claim_boundary", str(self.unsafe_claim_boundary))
        object.__setattr__(self, "current", bool(self.current))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def is_current_pass(self) -> bool:
        return self.current and self.closure_status == SELF_MAINTENANCE_STATUS_PASS

    def is_scoped_or_pass(self) -> bool:
        return self.current and self.closure_status in {
            SELF_MAINTENANCE_STATUS_PASS,
            SELF_MAINTENANCE_STATUS_SCOPED,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "child_id": self.child_id,
            "owner_guard": self.owner_guard,
            "artifact_kind": self.artifact_kind,
            "closure_status": self.closure_status,
            "findings": list(self.findings),
            "missing_inputs": list(self.missing_inputs),
            "stale_evidence": list(self.stale_evidence),
            "skipped_checks": list(self.skipped_checks),
            "next_actions": list(self.next_actions),
            "safe_claim": self.safe_claim,
            "unsafe_claim_boundary": self.unsafe_claim_boundary,
            "current": self.current,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class SelfMaintenanceFinding:
    """One self-maintenance mesh finding."""

    code: str
    message: str
    severity: str = SELF_MAINTENANCE_FINDING_GAP
    owner_route: str = ""
    child_id: str = ""
    next_action: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity or SELF_MAINTENANCE_FINDING_GAP))
        object.__setattr__(self, "owner_route", str(self.owner_route))
        object.__setattr__(self, "child_id", str(self.child_id))
        object.__setattr__(self, "next_action", str(self.next_action))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def blocks_full_confidence(self) -> bool:
        return self.severity == SELF_MAINTENANCE_FINDING_BLOCKER

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "owner_route": self.owner_route,
            "child_id": self.child_id,
            "next_action": self.next_action,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class SelfMaintenancePlan:
    """Parent plan for FlowGuard self-maintenance review."""

    plan_id: str
    route_profiles: tuple[RouteProfile, ...] = ()
    api_route_group_ids: tuple[str, ...] = ()
    ai_profiles: tuple[AIMaintenanceProfile, ...] = ()
    field_layers: tuple[FieldLayerProfile, ...] = ()
    child_reports: tuple[SelfMaintenanceChildReport, ...] = ()
    broad_claim: bool = False
    allow_scoped_confidence: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "route_profiles", tuple(self.route_profiles))
        object.__setattr__(self, "api_route_group_ids", _as_tuple(self.api_route_group_ids))
        object.__setattr__(self, "ai_profiles", tuple(self.ai_profiles))
        object.__setattr__(self, "field_layers", tuple(self.field_layers))
        object.__setattr__(
            self,
            "child_reports",
            tuple(_coerce_child_report(report) for report in self.child_reports),
        )
        object.__setattr__(self, "broad_claim", bool(self.broad_claim))
        object.__setattr__(self, "allow_scoped_confidence", bool(self.allow_scoped_confidence))

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "route_profiles": [profile.to_dict() for profile in self.route_profiles],
            "api_route_group_ids": list(self.api_route_group_ids),
            "ai_profiles": [profile.to_dict() for profile in self.ai_profiles],
            "field_layers": [layer.to_dict() for layer in self.field_layers],
            "child_reports": [report.to_dict() for report in self.child_reports],
            "broad_claim": self.broad_claim,
            "allow_scoped_confidence": self.allow_scoped_confidence,
        }


@dataclass(frozen=True)
class SelfMaintenanceReport:
    """Review result for FlowGuard self-maintenance."""

    ok: bool
    plan_id: str
    decision: str
    confidence: str
    findings: tuple[SelfMaintenanceFinding, ...] = ()
    route_profiles: tuple[RouteProfile, ...] = ()
    child_reports: tuple[SelfMaintenanceChildReport, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "route_profiles", tuple(self.route_profiles))
        object.__setattr__(self, "child_reports", tuple(self.child_reports))
        object.__setattr__(self, "summary", str(self.summary))

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "flowguard_self_maintenance_report",
            "ok": self.ok,
            "plan_id": self.plan_id,
            "decision": self.decision,
            "confidence": self.confidence,
            "findings": [finding.to_dict() for finding in self.findings],
            "route_profiles": [profile.to_dict() for profile in self.route_profiles],
            "child_reports": [report.to_dict() for report in self.child_reports],
            "summary": self.summary,
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    def format_text(self) -> str:
        lines = [
            "=== flowguard self-maintenance mesh ===",
            f"status: {'pass' if self.ok else 'blocked'}",
            f"plan_id: {self.plan_id}",
            f"decision: {self.decision}",
            f"confidence: {self.confidence}",
            f"routes: {len(self.route_profiles)}",
            f"child_reports: {len(self.child_reports)}",
            f"summary: {self.summary}",
        ]
        if self.findings:
            lines.append("findings:")
            for finding in self.findings:
                route = f" route={finding.owner_route}" if finding.owner_route else ""
                child = f" child={finding.child_id}" if finding.child_id else ""
                action = f" action={finding.next_action}" if finding.next_action else ""
                lines.append(f"- {finding.severity}: {finding.code}:{route}{child}: {finding.message}{action}")
        return "\n".join(lines)


def default_flowguard_route_profiles() -> tuple[RouteProfile, ...]:
    """Return compact route profiles for installed FlowGuard maintenance paths."""

    return (
        RouteProfile(
            "template_structure",
            "Project, route, or evidence templates need route-scoped public facade discovery.",
            ("template purpose", "target root"),
            ("template files", "write target", "route-owned template text"),
            "template_structure",
            ("development_process_flow", "flowguard-codex-skill-satellites"),
            "template_structure",
            "write_template_files",
            route_role=ROUTE_ROLE_DATA_HELPER,
            entry_policy=ENTRY_POLICY_INTERNAL_ONLY,
            canonical_owner_route=SELF_MAINTENANCE_ROUTE,
            absorbed_by_route=SELF_MAINTENANCE_ROUTE,
            cleanup_disposition=CLEANUP_DISPOSITION_ABSORB,
        ),
        RouteProfile(
            "evidence_field_structure",
            "Evidence fields need compact status/detail grouping without hiding skipped or stale states.",
            ("process-like evidence", "gate statuses"),
            ("evidence gates", "background detail", "mesh split detail"),
            "evidence_field_structure",
            ("development_process_flow", "risk_evidence_ledger"),
            "evidence_field_structure",
            route_role=ROUTE_ROLE_DATA_HELPER,
            entry_policy=ENTRY_POLICY_INTERNAL_ONLY,
            canonical_owner_route="development_process_flow",
            absorbed_by_route="development_process_flow",
            cleanup_disposition=CLEANUP_DISPOSITION_ABSORB,
        ),
        RouteProfile(
            "existing_model_preflight",
            "Existing modeled system needs ownership lookup before new work.",
            ("project root", "candidate change boundary"),
            ("reuse decision", "duplicate-boundary risks", "affected commitment ids", "downstream route"),
            "existing_model_preflight",
            ("behavior_commitment_ledger", "model_similarity_consolidation", "architecture_reduction", "field_lifecycle_mesh"),
            "existing_model_preflight",
            "existing_model_preflight_template_files",
            "flowguard-existing-model-preflight",
        ),
        RouteProfile(
            "behavior_commitment_ledger",
            "Project or work-package needs a complete external behavior inventory before broad FlowGuard confidence.",
            ("source surfaces", "behavior commitments", "owner models", "path sensitivity"),
            ("coverage decision", "missing behavior gaps", "extra behavior gaps", "PPA handoff ids", "risk gate ids"),
            "behavior_commitment_ledger",
            ("primary_path_authority", "contract_exhaustion_mesh", "test_mesh_maintenance", "risk_evidence_ledger"),
            "behavior_commitment_ledger",
            "behavior_commitment_ledger_template_files",
            "flowguard-behavior-commitment-ledger",
            metadata={
                "checklist": (
                    "register external behavior promises, not every helper function",
                    "map every source surface to commitments and every commitment back to source evidence",
                    "select exactly one primary owner model per commitment",
                    "route path_sensitive=true commitments through Primary Path Authority",
                )
            },
        ),
        RouteProfile(
            "primary_path_authority",
            "Path-sensitive work needs one primary runtime authority and no automatic alternate success after primary failure.",
            ("business intent", "primary path", "fallback candidates", "coverage receipts"),
            ("authority decision", "fallback disposition gaps", "coverage gate ids", "risk gate ids"),
            "primary_path_authority",
            ("contract_exhaustion_mesh", "test_mesh_maintenance", "risk_evidence_ledger"),
            "primary_path_authority",
            "primary_path_authority_template_files",
            "flowguard-development-process-flow",
            metadata={
                "checklist": (
                    "enumerate runtime paths, aliases, wrappers, helper routes, old fields, recovery paths, and migrations",
                    "select exactly one primary runtime authority per business intent",
                    "reject primary_failure -> fallback_success masking",
                    "require ContractExhaustionMesh axes, TestMesh shards, and RiskLedger gates for broad claims",
                )
            },
        ),
        RouteProfile(
            "model_angle_deliberation",
            "Open-ended model boundary question needs recorded reuse, split, defer, or review decision.",
            ("candidate angle rows", "current model coverage", "miss risk"),
            ("model angle decision", "owner route", "unresolved angle ids"),
            "model_angle_deliberation",
            ("existing_model_preflight", "model_maturation_loop", "model_mesh_maintenance"),
            "model_angle_deliberation",
            "model_angle_deliberation_template_files",
            route_role=ROUTE_ROLE_INTERNAL_FEEDER,
            entry_policy=ENTRY_POLICY_VIA_OWNER,
            canonical_owner_route="existing_model_preflight",
            absorbed_by_route="existing_model_preflight",
            cleanup_disposition=CLEANUP_DISPOSITION_ABSORB,
        ),
        RouteProfile(
            "risk_template_library",
            "New or deepened models need reusable public/local risk templates and local harvest candidates.",
            ("risk query", "public templates", "local template root"),
            ("template matches", "reuse review", "candidate harvest report"),
            "risk_template_library",
            ("model_maturation_loop", "model_similarity_consolidation", "development_process_flow"),
            "risk_template_library",
            "risk_template_library_template_files",
        ),
        RouteProfile(
            "maintenance_scan_router",
            "Changed artifacts, skipped routes, stale evidence, or summary gaps need owner-route actions.",
            ("changed artifacts", "signals", "prior obligations"),
            ("maintenance actions", "owner routes", "reopened obligations"),
            "maintenance_scan_router",
            ("development_process_flow", "model_test_alignment", "structure_mesh_maintenance"),
            "maintenance_scan_router",
            "maintenance_scan_template_files",
            route_role=ROUTE_ROLE_INTERNAL_FEEDER,
            entry_policy=ENTRY_POLICY_VIA_OWNER,
            canonical_owner_route="development_process_flow",
            absorbed_by_route="development_process_flow",
            cleanup_disposition=CLEANUP_DISPOSITION_ABSORB,
        ),
        RouteProfile(
            "maintenance_obligation_memory",
            "Open route-owned gaps need to stay visible across summary, scan, maturation, and ledger.",
            ("obligation rows", "owner route", "artifact anchors"),
            ("obligation report", "active obligations", "handoff inputs"),
            "maintenance_obligation_memory",
            ("maintenance_scan_router", "risk_evidence_ledger"),
            "maintenance_obligation_memory",
            route_role=ROUTE_ROLE_DATA_HELPER,
            entry_policy=ENTRY_POLICY_INTERNAL_ONLY,
            canonical_owner_route="risk_evidence_ledger",
            absorbed_by_route="risk_evidence_ledger",
            cleanup_disposition=CLEANUP_DISPOSITION_ABSORB,
        ),
        RouteProfile(
            "field_lifecycle_mesh",
            "Fields are added, removed, replaced, folded, migrated, or audited.",
            ("field boundary", "field rows", "field groups"),
            ("field projections", "old-field dispositions", "downstream obligations"),
            "field_lifecycle_mesh",
            ("model_test_alignment", "development_process_flow", "architecture_reduction"),
            "field_lifecycle_mesh",
            "field_lifecycle_template_files",
            "flowguard-field-lifecycle-mesh",
        ),
        RouteProfile(
            "contract_exhaustion_mesh",
            "Declared finite model boundaries need canonical bad-case ids, Cartesian combinations, universe coverage, or oracle handoffs.",
            ("contract dimensions", "coverage universe", "seed cases", "oracles", "model axes", "interaction groups"),
            ("mutation cases", "combination cases", "coverage shards", "coverage receipts", "fault profiles", "backfeed report", "route case ids"),
            "contract_exhaustion_mesh",
            (
                "model_test_alignment",
                "test_mesh_maintenance",
                "model_mesh_maintenance",
                "risk_evidence_ledger",
                "development_process_flow",
            ),
            "contract_exhaustion_mesh",
            "",
            "flowguard-contract-exhaustion-mesh",
            metadata={
                "checklist": (
                    "declare model_id before Cartesian coverage",
                    "declare the coverage universe before broad/full claims",
                    "generate only from declared finite axes or dimensions",
                    "require actionable oracle feedback fields for reject/block/reissue cases",
                    "map observed real misses back to generated and same-class case ids",
                    "project combination obligations to Model-Test Alignment",
                    "project case and shard ids to TestMesh",
                    "require ModelMesh coverage receipts for parent/child closure",
                    "add Risk Evidence Ledger gates for model_cartesian_coverage, contract_coverage_shard, and parent_consumed_child_coverage",
                ),
                "starter_helpers": (
                    "ContractAxis",
                    "ContractInteractionGroup",
                    "ContractCoverageUniverse",
                    "ContractFaultProfile",
                    "ObservedProblemBackfeed",
                    "ModelContractCoverageReceipt",
                    "contract_exhaustion_to_test_mesh_shard_ids",
                    "contract_exhaustion_to_coverage_receipt_ids",
                ),
            },
        ),
        RouteProfile(
            "model_similarity_consolidation",
            "Similar models or workflows may share kernels, adapters, tests, or false-friend boundaries.",
            ("model signatures", "relation evidence", "changed member"),
            ("similarity handoff", "maintenance group", "shared/variant obligations"),
            "model_similarity_consolidation",
            ("existing_model_preflight", "architecture_reduction", "model_test_alignment"),
            "model_similarity_consolidation",
            "model_similarity_consolidation_template_files",
            route_role=ROUTE_ROLE_INTERNAL_FEEDER,
            entry_policy=ENTRY_POLICY_VIA_OWNER,
            canonical_owner_route="existing_model_preflight",
            absorbed_by_route="existing_model_preflight",
            cleanup_disposition=CLEANUP_DISPOSITION_ABSORB,
        ),
        RouteProfile(
            "architecture_reduction",
            "Existing modeled implementation may be contracted without behavior change.",
            ("observable contract", "candidate reductions"),
            ("proof status", "target action", "required next route"),
            "architecture_reduction",
            ("code_structure_recommendation", "structure_mesh_maintenance", "development_process_flow"),
            "architecture_reduction",
            "",
            "flowguard-architecture-reduction",
        ),
        RouteProfile(
            "code_structure_recommendation",
            "Target implementation ownership needs model-derived structure before code edits.",
            ("FunctionBlocks", "state owners", "field owners"),
            ("target module recommendations", "facade map", "validation boundary"),
            "code_structure_recommendation",
            ("structure_mesh_maintenance", "model_test_alignment"),
            "code_structure_recommendation",
            "code_structure_recommendation_template_files",
            "flowguard-code-structure-recommendation",
        ),
        RouteProfile(
            "structure_mesh_maintenance",
            "Large modules, public APIs, facades, or package splits need parity evidence.",
            ("parent module", "partition items", "public entrypoints"),
            ("module ownership", "facade parity", "dependency/config gaps"),
            "structure_mesh_maintenance",
            ("development_process_flow", "model_test_alignment", "risk_evidence_ledger"),
            "structure_mesh_maintenance",
            "structure_mesh_template_files",
            "flowguard-structure-mesh",
        ),
        RouteProfile(
            "model_test_alignment",
            "Model obligations, including generated combination obligations, need direct binding to owner code contracts and tests.",
            ("model obligations", "code contracts", "test evidence", "contract-exhaustion obligation ids"),
            ("binding rows", "coverage gaps", "boundary observations", "combination obligation coverage"),
            "model_test_alignment",
            ("test_mesh_maintenance", "risk_evidence_ledger", "flowguard_closure_contract"),
            "model_test_alignment",
            "model_test_alignment_template_files",
            "flowguard-model-test-alignment",
        ),
        RouteProfile(
            "test_mesh_maintenance",
            "Large, slow, stale, background, release-only, or combination-shard validation needs child evidence.",
            ("parent suite", "child suites", "freshness evidence", "required case ids", "required shard ids"),
            ("parent/child test mesh", "result artifacts", "case evidence", "shard evidence", "scoped gaps"),
            "test_mesh_maintenance",
            ("model_test_alignment", "development_process_flow", "risk_evidence_ledger"),
            "test_mesh_maintenance",
            "test_mesh_template_files",
            "flowguard-test-mesh",
        ),
        RouteProfile(
            "model_mesh_maintenance",
            "Three or more models, large models, stale child evidence, or coverage receipt handoffs need parent/child governance.",
            ("parent model", "child models", "partition items", "coverage receipts", "required child receipt ids"),
            ("mesh evidence", "reattachment status", "coverage receipt status", "affected siblings"),
            "model_mesh_maintenance",
            ("model_test_alignment", "test_mesh_maintenance", "flowguard_closure_contract"),
            "model_mesh_maintenance",
            "",
            "flowguard-model-mesh",
        ),
        RouteProfile(
            "development_process_simulator",
            "Non-trivial rough plan, multi-skill workflow, or lifecycle claim needs one process front door with internal modes.",
            ("task intent", "risk flags", "candidate modes"),
            ("selected modes", "delegated mode owners", "claim boundary"),
            "development_process_flow",
            ("plan_detailing_compiler", "agent_workflow_rehearsal", "development_process_flow"),
            "development_process_simulator",
            "",
            "flowguard-development-process-flow",
            metadata={
                "modes": ("plan_detailing", "agent_workflow", "execution_freshness"),
                "front_door": "development_process_flow",
            },
            route_role=ROUTE_ROLE_INTERNAL_FEEDER,
            entry_policy=ENTRY_POLICY_VIA_OWNER,
            canonical_owner_route="development_process_flow",
            absorbed_by_route="development_process_flow",
            cleanup_disposition=CLEANUP_DISPOSITION_ABSORB,
        ),
        RouteProfile(
            "development_process_flow",
            "Development-process simulator front door and execution-freshness owner for staged edits, validation freshness, install sync, shadow sync, or peer writes.",
            ("process actions", "artifacts", "evidence"),
            ("minimum revalidation", "freshness gaps", "blocked claims"),
            "development_process_flow",
            ("maintenance_scan_router", "risk_evidence_ledger", "flowguard_closure_contract"),
            "development_process_flow",
            "development_process_flow_template_files",
            "flowguard-development-process-flow",
        ),
        RouteProfile(
            "risk_evidence_ledger",
            "Final done/release/production confidence needs risk-to-proof and route-gate accounting.",
            ("risk rows", "proof refs", "route evidence", "cartesian coverage gates"),
            ("confidence decision", "unsupported claims", "proof gaps", "coverage gate gaps"),
            "risk_evidence_ledger",
            ("flowguard_closure_contract", "development_process_flow"),
            "risk_evidence_ledger",
            "risk_evidence_ledger_template_files",
        ),
        RouteProfile(
            "flowguard_closure_contract",
            "Broad done/release/publish confidence needs guard-family child closure reports.",
            ("child reports", "runtime mappings", "ledger support"),
            ("safe claim", "unsafe claim boundary", "closure decision"),
            "flowguard_closure_contract",
            ("maintenance_scan_router", "development_process_flow"),
            "flowguard_closure_contract",
            "closure_contract_template_files",
            route_role=ROUTE_ROLE_INTERNAL_FEEDER,
            entry_policy=ENTRY_POLICY_VIA_OWNER,
            canonical_owner_route="risk_evidence_ledger",
            absorbed_by_route="risk_evidence_ledger",
            cleanup_disposition=CLEANUP_DISPOSITION_ABSORB,
        ),
        RouteProfile(
            "agent_workflow_rehearsal",
            "Delegated agent_workflow simulator mode needs skill/tool ordering, skipped-skill consequences, and rework gates.",
            ("candidate skills", "tool actions", "claim boundary"),
            ("workflow findings", "required rework", "final claim scope"),
            "agent_workflow_rehearsal",
            ("development_process_flow", "maintenance_scan_router"),
            "agent_workflow_rehearsal",
            "",
            "flowguard-agent-workflow-rehearsal",
            route_role=ROUTE_ROLE_DELEGATED_MODE,
            entry_policy=ENTRY_POLICY_VIA_OWNER,
            canonical_owner_route="development_process_flow",
            absorbed_by_route="development_process_flow",
            cleanup_disposition=CLEANUP_DISPOSITION_KEEP,
        ),
        RouteProfile(
            "ui_flow_structure",
            "UI interactions, journeys, visible controls, hierarchy, or runnable validation need UI route ownership.",
            ("UI states", "controls", "journeys"),
            ("transition coverage", "blindspots", "structure/text handoff"),
            "ui_flow_structure",
            ("model_test_alignment", "test_mesh_maintenance"),
            "ui_flow_structure",
            "ui_flow_structure_template_files",
            "flowguard-ui-flow-structure",
        ),
        RouteProfile(
            "model_miss_review",
            "A bug, runtime failure, combination miss, or post-green miss needs generalized repair evidence.",
            ("observed miss", "root cause", "same-class bad case", "combination case id"),
            ("defect family gate", "analogous defect scan", "interaction group upgrade", "coverage receipt", "closure evidence"),
            "model_miss_review",
            ("model_test_alignment", "risk_evidence_ledger", "flowguard_closure_contract"),
            "model_miss_review",
            "model_miss_review_template_files",
            "flowguard-model-miss-review",
        ),
        RouteProfile(
            "plan_detailing_compiler",
            "Delegated plan_detailing simulator mode needs checkable PlanDetail rows.",
            ("rough plan", "sources", "state surfaces"),
            ("plan detail rows", "step contracts", "validation requirements"),
            "plan_detailing_compiler",
            ("development_process_flow", "agent_workflow_rehearsal"),
            "plan_detailing_compiler",
            "plan_detailing_template_files",
            "flowguard-plan-detailing-compiler",
            route_role=ROUTE_ROLE_DELEGATED_MODE,
            entry_policy=ENTRY_POLICY_VIA_OWNER,
            canonical_owner_route="development_process_flow",
            absorbed_by_route="development_process_flow",
            cleanup_disposition=CLEANUP_DISPOSITION_KEEP,
        ),
        RouteProfile(
            "state_closure",
            "Finite state/input boundaries need unknown, malformed, missing, old-schema, or terminal cases visible.",
            ("state dimensions", "input dimensions", "closure policy"),
            ("closure cases", "handling policy", "blocked unknowns"),
            "state_closure",
            ("model_maturation_loop", "model_test_alignment"),
            "state_closure",
            route_role=ROUTE_ROLE_INTERNAL_FEEDER,
            entry_policy=ENTRY_POLICY_VIA_OWNER,
            canonical_owner_route="contract_exhaustion_mesh",
            absorbed_by_route="contract_exhaustion_mesh",
            cleanup_disposition=CLEANUP_DISPOSITION_ABSORB,
        ),
        RouteProfile(
            "model_topology_hazard_review",
            "Locally green model topology needs future-use hazard review before broad confidence.",
            ("usage intent", "topology digest", "hazard candidates"),
            ("hazard report", "unresolved hazards", "claim boundary"),
            "model_topology_hazard_review",
            ("risk_evidence_ledger", "flowguard_closure_contract"),
            "model_topology_hazard_review",
            "topology_hazard_template_files",
            "flowguard-model-topology-hazard-review",
        ),
        RouteProfile(
            SELF_MAINTENANCE_ROUTE,
            "FlowGuard itself needs route graph, field, structure, validation, install, and closure governance.",
            ("route profiles", "AI profiles", "field layers", "child reports"),
            ("self-maintenance decision", "route graph gaps", "next route actions"),
            SELF_MAINTENANCE_ROUTE,
            ("maintenance_scan_router", "development_process_flow", "flowguard_closure_contract"),
            SELF_MAINTENANCE_ROUTE,
        ),
    )


def default_ai_maintenance_profiles() -> tuple[AIMaintenanceProfile, ...]:
    """Return thin entry profiles for common AI maintenance intents."""

    return (
        AIMaintenanceProfile(
            "fields",
            "Audit or reduce fields without hiding behavior-bearing evidence.",
            "field_lifecycle_mesh",
            ("field boundary", "candidate field ids"),
            ("model_test_alignment", "development_process_flow", "risk_evidence_ledger"),
            ("field projections", "old-field dispositions", "current tests"),
        ),
        AIMaintenanceProfile(
            "route_graph",
            "Connect scattered capabilities into a route chain.",
            SELF_MAINTENANCE_ROUTE,
            ("installed route ids", "public route groups"),
            ("maintenance_scan_router", "flowguard-codex-skill-satellites"),
            ("route profiles", "skill/docs sync", "route completeness check"),
        ),
        AIMaintenanceProfile(
            "primary_path_authority",
            "Prevent fallback maintenance debt by fixing the primary path instead of adding alternate success paths.",
            "primary_path_authority",
            ("business intent", "primary path id", "fallback candidates"),
            ("contract_exhaustion_mesh", "test_mesh_maintenance", "risk_evidence_ledger"),
            ("no silent fallback", "compatibility disposition", "coverage receipts"),
        ),
        AIMaintenanceProfile(
            "structure",
            "Split or fold oversized modules behind stable facades.",
            "structure_mesh_maintenance",
            ("parent module", "public entrypoints"),
            ("code_structure_recommendation", "development_process_flow", "model_test_alignment"),
            ("facade parity", "owner contracts", "focused tests"),
        ),
        AIMaintenanceProfile(
            "validation",
            "Handle slow, stale, broad, or background validation honestly.",
            "test_mesh_maintenance",
            ("parent claim", "child tests", "result artifacts"),
            ("model_test_alignment", "risk_evidence_ledger", "flowguard_closure_contract"),
            ("current child evidence", "result status", "proof refs"),
        ),
    )


def default_field_layer_profiles() -> tuple[FieldLayerProfile, ...]:
    """Return first-read field layers for route prompts and reports."""

    return (
        FieldLayerProfile(
            FIELD_LAYER_CORE,
            ("id", "status", "decision", "current", "owner_route"),
            "first_read",
            SELF_MAINTENANCE_ROUTE,
            ("route selection", "summary decision"),
            False,
            "Small identity and decision fields stay visible.",
        ),
        FieldLayerProfile(
            FIELD_LAYER_ROUTE_OWNED,
            ("route-specific obligations", "transition cells", "owner contracts"),
            "expand_when_route_runs",
            "field_lifecycle_mesh",
            ("model_test_alignment", "structure_mesh_maintenance"),
            False,
            "Specialist fields expand only when their owner route runs.",
        ),
        FieldLayerProfile(
            FIELD_LAYER_SHARED_EVIDENCE,
            ("proof refs", "freshness refs", "scope refs", "test reuse tickets"),
            "summarized_first_read",
            "risk_evidence_ledger",
            ("broad claim", "release confidence"),
            False,
            "Shared proof concepts use compact references before full evidence expansion.",
        ),
        FieldLayerProfile(
            FIELD_LAYER_METADATA_DISPLAY,
            ("metadata", "display labels", "formatting notes"),
            "scoped_summary_only",
            SELF_MAINTENANCE_ROUTE,
            ("documentation", "display-only prompts"),
            False,
            "Display and metadata fields stay accounted but out of high-level behavior models.",
        ),
        FieldLayerProfile(
            FIELD_LAYER_COMPATIBILITY,
            ("old fields", "aliases", "fallbacks", "wrappers"),
            "show_disposition",
            "architecture_reduction",
            ("field_lifecycle_mesh", "development_process_flow"),
            True,
            "Compatibility-like fields need delete, migrate, block, delegate, repair, preserve, or scope evidence.",
        ),
    )


def route_graph_completeness_findings(
    route_profiles: Sequence[RouteProfile],
    api_route_group_ids: Sequence[str],
) -> tuple[SelfMaintenanceFinding, ...]:
    """Compare route profiles with public route discovery groups."""

    public_profile_ids = {
        profile.route_id
        for profile in route_profiles
        if profile.route_role == ROUTE_ROLE_PUBLIC_OWNER and profile.entry_policy == ENTRY_POLICY_DIRECT
    }
    api_ids = set(_as_tuple(api_route_group_ids))
    findings: list[SelfMaintenanceFinding] = []
    for profile in route_profiles:
        if profile.route_role == ROUTE_ROLE_PUBLIC_OWNER and profile.entry_policy != ENTRY_POLICY_DIRECT:
            findings.append(
                SelfMaintenanceFinding(
                    "public_owner_not_direct",
                    "public owner route must use direct entry policy",
                    SELF_MAINTENANCE_FINDING_BLOCKER,
                    owner_route=profile.route_id,
                    next_action="set entry_policy=direct or classify the profile as delegated/internal/data",
                    metadata=profile.to_dict(),
                )
            )
        if profile.route_role != ROUTE_ROLE_PUBLIC_OWNER and profile.entry_policy == ENTRY_POLICY_DIRECT:
            findings.append(
                SelfMaintenanceFinding(
                    "non_public_route_direct_entry",
                    "non-public route profile cannot use direct entry policy",
                    SELF_MAINTENANCE_FINDING_BLOCKER,
                    owner_route=profile.route_id,
                    next_action="set entry_policy=via_owner or internal_only",
                    metadata=profile.to_dict(),
                )
            )
        if profile.route_role in {ROUTE_ROLE_INTERNAL_FEEDER, ROUTE_ROLE_DATA_HELPER, ROUTE_ROLE_DELEGATED_MODE} and not (
            profile.canonical_owner_route or profile.absorbed_by_route
        ):
            findings.append(
                SelfMaintenanceFinding(
                    "helper_route_missing_owner",
                    "delegated, feeder, or data-helper route must name the owner that consumes it",
                    SELF_MAINTENANCE_FINDING_BLOCKER,
                    owner_route=profile.route_id,
                    next_action="set canonical_owner_route or absorbed_by_route",
                    metadata=profile.to_dict(),
                )
            )
        if profile.route_role == ROUTE_ROLE_PUBLIC_OWNER and profile.api_group not in api_ids:
            findings.append(
                SelfMaintenanceFinding(
                    "route_profile_missing_api_group",
                    "route profile is not reachable through FLOWGUARD_ROUTE_API",
                    SELF_MAINTENANCE_FINDING_BLOCKER,
                    owner_route=profile.route_id,
                    next_action="add the route group or explicitly scope out the route",
                    metadata=profile.to_dict(),
                )
            )
        if profile.route_role != ROUTE_ROLE_PUBLIC_OWNER and profile.api_group in api_ids:
            findings.append(
                SelfMaintenanceFinding(
                    "internal_route_exposed_publicly",
                    "internal, delegated, or data-helper route is exposed through the public route API",
                    SELF_MAINTENANCE_FINDING_BLOCKER,
                    owner_route=profile.route_id,
                    next_action="remove the route from FLOWGUARD_ROUTE_API and expose it only through advanced/helper inventories",
                    metadata=profile.to_dict(),
                )
            )
    for group_id in sorted(api_ids - public_profile_ids):
        findings.append(
            SelfMaintenanceFinding(
                "api_group_missing_route_profile",
                "FLOWGUARD_ROUTE_API group has no direct public-owner route profile",
                SELF_MAINTENANCE_FINDING_GAP,
                owner_route=group_id,
                next_action="add a public-owner RouteProfile or remove the group from public route discovery",
            )
        )
    return tuple(findings)


def review_flowguard_self_maintenance(plan: SelfMaintenancePlan) -> SelfMaintenanceReport:
    """Review the parent FlowGuard self-maintenance mesh."""

    findings = list(route_graph_completeness_findings(plan.route_profiles, plan.api_route_group_ids))

    if not plan.ai_profiles:
        findings.append(
            SelfMaintenanceFinding(
                "missing_ai_entry_profiles",
                "self-maintenance plan has no lightweight AI entry profiles",
                SELF_MAINTENANCE_FINDING_BLOCKER if plan.broad_claim else SELF_MAINTENANCE_FINDING_GAP,
                owner_route=SELF_MAINTENANCE_ROUTE,
                next_action="add default_ai_maintenance_profiles() or an equivalent bounded profile set",
            )
        )
    if not plan.field_layers:
        findings.append(
            SelfMaintenanceFinding(
                "missing_field_layer_profiles",
                "self-maintenance plan has no field layer profiles",
                SELF_MAINTENANCE_FINDING_BLOCKER,
                owner_route="field_lifecycle_mesh",
                next_action="add default_field_layer_profiles() or equivalent field lifecycle rows",
            )
        )

    seen_layers = {layer.layer_id for layer in plan.field_layers}
    for required_layer in FIELD_LAYERS:
        if required_layer not in seen_layers:
            findings.append(
                SelfMaintenanceFinding(
                    "field_layer_missing",
                    "required field layer is missing",
                    SELF_MAINTENANCE_FINDING_BLOCKER if required_layer == FIELD_LAYER_COMPATIBILITY else SELF_MAINTENANCE_FINDING_GAP,
                    owner_route="field_lifecycle_mesh",
                    next_action=f"add field layer {required_layer}",
                    metadata={"layer_id": required_layer},
                )
            )

    for report in plan.child_reports:
        if report.is_current_pass():
            continue
        severity = (
            SELF_MAINTENANCE_FINDING_BLOCKER
            if plan.broad_claim or report.closure_status == SELF_MAINTENANCE_STATUS_BLOCKED
            else SELF_MAINTENANCE_FINDING_GAP
        )
        findings.append(
            SelfMaintenanceFinding(
                "child_report_not_current_pass",
                "self-maintenance child report is not current pass evidence",
                severity,
                owner_route=report.owner_guard,
                child_id=report.child_id,
                next_action=", ".join(report.next_actions) or "refresh the child route evidence",
                metadata=report.to_dict(),
            )
        )

    blockers = tuple(finding for finding in findings if finding.blocks_full_confidence())
    gaps = tuple(finding for finding in findings if finding.severity == SELF_MAINTENANCE_FINDING_GAP)
    if blockers:
        decision = SELF_MAINTENANCE_DECISION_BLOCKED
        confidence = SELF_MAINTENANCE_STATUS_BLOCKED
        ok = False
        summary = "Self-maintenance has blockers before broad confidence."
    elif gaps:
        decision = SELF_MAINTENANCE_DECISION_SCOPED
        confidence = SELF_MAINTENANCE_STATUS_SCOPED
        ok = plan.allow_scoped_confidence
        summary = "Self-maintenance has scoped route or evidence gaps."
    else:
        decision = SELF_MAINTENANCE_DECISION_FULL
        confidence = SELF_MAINTENANCE_STATUS_PASS
        ok = True
        summary = "Route graph, field layers, AI profiles, and child reports are current."

    return SelfMaintenanceReport(
        ok=ok,
        plan_id=plan.plan_id,
        decision=decision,
        confidence=confidence,
        findings=tuple(findings),
        route_profiles=tuple(plan.route_profiles),
        child_reports=tuple(plan.child_reports),
        summary=summary,
    )


__all__ = [
    "AIMaintenanceProfile",
    "CLEANUP_DISPOSITION_ABSORB",
    "CLEANUP_DISPOSITION_DELETE",
    "CLEANUP_DISPOSITION_FACADE_REVIEW",
    "CLEANUP_DISPOSITION_KEEP",
    "CLEANUP_DISPOSITIONS",
    "ENTRY_POLICIES",
    "ENTRY_POLICY_DIRECT",
    "ENTRY_POLICY_INTERNAL_ONLY",
    "ENTRY_POLICY_VIA_OWNER",
    "FIELD_LAYER_COMPATIBILITY",
    "FIELD_LAYER_CORE",
    "FIELD_LAYER_METADATA_DISPLAY",
    "FIELD_LAYER_ROUTE_OWNED",
    "FIELD_LAYER_SHARED_EVIDENCE",
    "FIELD_LAYERS",
    "ROUTE_ROLE_ARCHIVE_ONLY",
    "ROUTE_ROLE_DATA_HELPER",
    "ROUTE_ROLE_DELEGATED_MODE",
    "ROUTE_ROLE_INTERNAL_FEEDER",
    "ROUTE_ROLE_PUBLIC_OWNER",
    "ROUTE_ROLES",
    "SELF_MAINTENANCE_DECISION_BLOCKED",
    "SELF_MAINTENANCE_DECISION_FULL",
    "SELF_MAINTENANCE_DECISION_SCOPED",
    "SELF_MAINTENANCE_FINDING_BLOCKER",
    "SELF_MAINTENANCE_FINDING_GAP",
    "SELF_MAINTENANCE_FINDING_INFO",
    "SELF_MAINTENANCE_ROUTE",
    "SELF_MAINTENANCE_STATUS_BLOCKED",
    "SELF_MAINTENANCE_STATUS_PASS",
    "SELF_MAINTENANCE_STATUS_SCOPED",
    "SELF_MAINTENANCE_STATUS_SKIPPED",
    "SELF_MAINTENANCE_STATUS_STALE",
    "SELF_MAINTENANCE_STATUSES",
    "FieldLayerProfile",
    "RouteProfile",
    "SelfMaintenanceChildReport",
    "SelfMaintenanceFinding",
    "SelfMaintenancePlan",
    "SelfMaintenanceReport",
    "default_ai_maintenance_profiles",
    "default_field_layer_profiles",
    "default_flowguard_route_profiles",
    "review_flowguard_self_maintenance",
    "route_graph_completeness_findings",
]
