"""Canonical typed route topology and ownership checks for FlowGuard.

The registry in this module is deliberately about routing topology only.  It
does not execute a target skill, helper, or external action.  Bare strings are
not accepted as handoffs: callers must state what kind of target they mean so
the topology can resolve it without guessing from naming conventions.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


TARGET_KIND_SKILL = "skill"
TARGET_KIND_INTERNAL_ROUTE = "internal_route"
TARGET_KIND_HELPER_API = "helper_api"
TARGET_KIND_EXTERNAL_ACTION = "external_action"
TARGET_KINDS = (
    TARGET_KIND_SKILL,
    TARGET_KIND_INTERNAL_ROUTE,
    TARGET_KIND_HELPER_API,
    TARGET_KIND_EXTERNAL_ACTION,
)

ROUTE_ROLE_PUBLIC_OWNER = "public_owner"
ENTRY_POLICY_DIRECT = "direct"

TOPOLOGY_STATUS_PASS = "pass"
TOPOLOGY_STATUS_BLOCKED = "blocked"

LOOP_DECISION_CONTINUE = "continue"
LOOP_DECISION_SUCCESS = "success"
LOOP_DECISION_BLOCKED_UNCHANGED = "blocked_unchanged_progress"
LOOP_DECISION_BLOCKED_BOUND = "blocked_reentry_bound"


# This is the machine route-owner projection.  Skill ids are derived from
# stable route ids so this module does not become a second literal suite
# inventory.  The suite map remains the declared membership authority and is
# checked against this projection.
PUBLIC_ROUTE_IDS = (
    "model_first_function_flow",
    "existing_model_preflight",
    "behavior_commitment_ledger",
    "architecture_reduction",
    "code_structure_recommendation",
    "contract_exhaustion_mesh",
    "development_process_flow",
    "field_lifecycle_mesh",
    "model_mesh_maintenance",
    "model_miss_review",
    "model_test_alignment",
    "model_topology_hazard_review",
    "structure_mesh_maintenance",
    "test_mesh_maintenance",
    "ui_flow_structure",
)


def _skill_id_for_public_route(route_id: str) -> str:
    if route_id == "model_first_function_flow":
        return route_id.replace("_", "-")
    route_stem = {
        "model_mesh_maintenance": "model_mesh",
        "structure_mesh_maintenance": "structure_mesh",
        "test_mesh_maintenance": "test_mesh",
    }.get(route_id, route_id)
    return f"flowguard-{route_stem.replace('_', '-')}"


PUBLIC_ROUTE_SKILL_OWNERS: Mapping[str, str] = {
    route_id: _skill_id_for_public_route(route_id)
    for route_id in PUBLIC_ROUTE_IDS
}

# Internal and delegated routes resolve through exactly one public owner.
INTERNAL_ROUTE_OWNERS: Mapping[str, str] = {
    "flowguard_self_maintenance": "model_first_function_flow",
    "template_structure": "model_first_function_flow",
    "evidence_field_structure": "development_process_flow",
    "primary_path_authority": "behavior_commitment_ledger",
    "model_angle_deliberation": "existing_model_preflight",
    "model_similarity_consolidation": "existing_model_preflight",
    "model_maturation_loop": "model_first_function_flow",
    "risk_template_library": "model_first_function_flow",
    "maintenance_scan_router": "development_process_flow",
    "maintenance_obligation_memory": "model_first_function_flow",
    "development_process_simulator": "development_process_flow",
    "agent_workflow_rehearsal": "development_process_flow",
    "plan_detailing_compiler": "development_process_flow",
    "risk_evidence_ledger": "model_first_function_flow",
    "flowguard_closure_contract": "model_first_function_flow",
    "state_closure": "contract_exhaustion_mesh",
}

HELPER_API_TARGETS = frozenset(
    {
        "write_template_files",
        "summarize_evidence_gates",
    }
)
EXTERNAL_ACTION_TARGETS = frozenset(
    {
        "publish_release",
        "install_distribution",
    }
)


class LegacyRouteHandoffError(ValueError):
    """Raised when a historical bare-string handoff reaches the typed API."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest().upper()


@dataclass(frozen=True)
class RouteHandoff:
    """One discriminated handoff from a route to an owned target."""

    target_kind: str
    target_id: str
    condition: str
    claim_scope: str

    def __post_init__(self) -> None:
        target_kind = str(self.target_kind)
        target_id = str(self.target_id)
        condition = str(self.condition)
        claim_scope = str(self.claim_scope)
        if target_kind not in TARGET_KINDS:
            raise ValueError(f"unknown route handoff target kind: {target_kind}")
        if not target_id:
            raise ValueError("route handoff target_id is required")
        if not condition:
            raise ValueError("route handoff condition is required")
        if not claim_scope:
            raise ValueError("route handoff claim_scope is required")
        object.__setattr__(self, "target_kind", target_kind)
        object.__setattr__(self, "target_id", target_id)
        object.__setattr__(self, "condition", condition)
        object.__setattr__(self, "claim_scope", claim_scope)

    def to_dict(self) -> dict[str, str]:
        return {
            "target_kind": self.target_kind,
            "target_id": self.target_id,
            "condition": self.condition,
            "claim_scope": self.claim_scope,
        }


def require_typed_handoff(value: RouteHandoff | Mapping[str, Any] | str) -> RouteHandoff:
    """Return a typed handoff or a deterministic migration error.

    A mapping is a serialized typed handoff and is accepted.  A bare string is
    never followed as a compatibility success path.
    """

    if isinstance(value, RouteHandoff):
        return value
    if isinstance(value, str):
        raise LegacyRouteHandoffError(
            f"legacy route handoff {value!r} is not executable; supply target_kind, "
            "target_id, condition, and claim_scope"
        )
    if isinstance(value, Mapping):
        return RouteHandoff(
            target_kind=str(value.get("target_kind", "")),
            target_id=str(value.get("target_id", "")),
            condition=str(value.get("condition", "")),
            claim_scope=str(value.get("claim_scope", "")),
        )
    raise TypeError(f"cannot coerce {type(value).__name__} to RouteHandoff")


def route_handoff(
    route_id: str,
    *,
    condition: str = "when the source route emits an owned downstream obligation",
    claim_scope: str = "target-route evidence only",
) -> RouteHandoff:
    """Create a typed handoff for a registered public or internal route id."""

    route_id = str(route_id)
    if route_id in PUBLIC_ROUTE_SKILL_OWNERS:
        return RouteHandoff(
            TARGET_KIND_SKILL,
            PUBLIC_ROUTE_SKILL_OWNERS[route_id],
            condition,
            claim_scope,
        )
    if route_id in INTERNAL_ROUTE_OWNERS:
        return RouteHandoff(TARGET_KIND_INTERNAL_ROUTE, route_id, condition, claim_scope)
    raise ValueError(f"route id is not registered for a typed handoff: {route_id}")


def helper_handoff(
    helper_id: str,
    *,
    condition: str,
    claim_scope: str = "helper output only",
) -> RouteHandoff:
    return RouteHandoff(TARGET_KIND_HELPER_API, helper_id, condition, claim_scope)


def external_action_handoff(
    action_id: str,
    *,
    condition: str,
    claim_scope: str,
) -> RouteHandoff:
    return RouteHandoff(TARGET_KIND_EXTERNAL_ACTION, action_id, condition, claim_scope)


def route_handoffs(*route_ids: str) -> tuple[RouteHandoff, ...]:
    return tuple(route_handoff(route_id) for route_id in route_ids)


@dataclass(frozen=True)
class RouteCycleLiveness:
    """Executable liveness contract for one strongly connected component."""

    component_id: str
    route_ids: tuple[str, ...]
    progress_measure: str
    allowed_delta: str
    success_terminal: str
    blocked_terminal: str
    max_reentries: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "component_id", str(self.component_id))
        object.__setattr__(self, "route_ids", tuple(sorted(str(item) for item in self.route_ids)))
        object.__setattr__(self, "progress_measure", str(self.progress_measure))
        object.__setattr__(self, "allowed_delta", str(self.allowed_delta))
        object.__setattr__(self, "success_terminal", str(self.success_terminal))
        object.__setattr__(self, "blocked_terminal", str(self.blocked_terminal))
        object.__setattr__(self, "max_reentries", int(self.max_reentries))

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "route_ids": list(self.route_ids),
            "progress_measure": self.progress_measure,
            "allowed_delta": self.allowed_delta,
            "success_terminal": self.success_terminal,
            "blocked_terminal": self.blocked_terminal,
            "max_reentries": self.max_reentries,
        }


DEFAULT_ROUTE_CYCLE_LIVENESS = (
    RouteCycleLiveness(
        "development_closure_rework",
        (
            "development_process_flow",
            "flowguard_closure_contract",
            "maintenance_scan_router",
            "model_test_alignment",
            "risk_evidence_ledger",
            "structure_mesh_maintenance",
            "test_mesh_maintenance",
        ),
        "accepted evidence receipt ids and resolved obligation ids",
        "at least one new accepted receipt or one resolved route-owned obligation",
        "closure_accepted",
        "blocked_no_evidence_delta",
        3,
    ),
    RouteCycleLiveness(
        "existing_model_similarity_rework",
        ("existing_model_preflight", "model_similarity_consolidation"),
        "reviewed model signatures and recorded disposition ids",
        "a new signature review or a changed reuse/split/consolidate disposition",
        "model_owner_selected",
        "blocked_unchanged_model_evidence",
        2,
    ),
)


@dataclass(frozen=True)
class RouteLoopProbe:
    component_id: str
    decision: str
    reentries: int
    progress_changed: bool
    terminal: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "decision": self.decision,
            "reentries": self.reentries,
            "progress_changed": self.progress_changed,
            "terminal": self.terminal,
        }


def probe_cycle_liveness(
    policy: RouteCycleLiveness,
    *,
    previous_progress: Iterable[str] = (),
    current_progress: Iterable[str] = (),
    reentries: int = 0,
    success: bool = False,
) -> RouteLoopProbe:
    """Probe one re-entry with an explicit progress delta and finite bound."""

    if success:
        return RouteLoopProbe(
            policy.component_id,
            LOOP_DECISION_SUCCESS,
            int(reentries),
            True,
            policy.success_terminal,
        )
    previous = frozenset(str(item) for item in previous_progress)
    current = frozenset(str(item) for item in current_progress)
    changed = current != previous and bool(current - previous)
    if not changed:
        return RouteLoopProbe(
            policy.component_id,
            LOOP_DECISION_BLOCKED_UNCHANGED,
            int(reentries),
            False,
            policy.blocked_terminal,
        )
    if int(reentries) >= policy.max_reentries:
        return RouteLoopProbe(
            policy.component_id,
            LOOP_DECISION_BLOCKED_BOUND,
            int(reentries),
            True,
            policy.blocked_terminal,
        )
    return RouteLoopProbe(policy.component_id, LOOP_DECISION_CONTINUE, int(reentries), True, "")


@dataclass(frozen=True)
class RouteTopologyFinding:
    code: str
    message: str
    source_route_id: str = ""
    target_kind: str = ""
    target_id: str = ""
    affected_route_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "affected_route_ids", tuple(sorted(str(item) for item in self.affected_route_ids)))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "source_route_id": self.source_route_id,
            "target_kind": self.target_kind,
            "target_id": self.target_id,
            "affected_route_ids": list(self.affected_route_ids),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class SuiteRoutingSnapshot:
    skill_ids: tuple[str, ...]
    route_owner_by_skill: Mapping[str, str]
    inventory_hash: str


@dataclass(frozen=True)
class RouteTopologyReport:
    inventory_hash: str
    registry_hash: str
    route_ids: tuple[str, ...]
    edge_count: int
    cycle_components: tuple[tuple[str, ...], ...]
    cycle_probes: tuple[RouteLoopProbe, ...]
    findings: tuple[RouteTopologyFinding, ...]

    @property
    def ok(self) -> bool:
        return not self.findings

    @property
    def status(self) -> str:
        return TOPOLOGY_STATUS_PASS if self.ok else TOPOLOGY_STATUS_BLOCKED

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "flowguard_route_topology_report",
            "ok": self.ok,
            "status": self.status,
            "inventory_hash": self.inventory_hash,
            "registry_hash": self.registry_hash,
            "route_count": len(self.route_ids),
            "edge_count": self.edge_count,
            "route_ids": list(self.route_ids),
            "cycle_components": [list(item) for item in self.cycle_components],
            "cycle_probes": [probe.to_dict() for probe in self.cycle_probes],
            "findings": [finding.to_dict() for finding in self.findings],
            "claim_boundary": (
                "This report proves typed target resolution, canonical ownership, and declared "
                "cycle liveness for the inspected registry. It does not execute target routes or "
                "prove their evidence freshness."
            ),
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, sort_keys=True)

    def format_text(self) -> str:
        lines = [
            "=== flowguard route topology ===",
            f"status: {self.status}",
            f"routes: {len(self.route_ids)}",
            f"edges: {self.edge_count}",
            f"cycles: {len(self.cycle_components)}",
            f"registry_hash: {self.registry_hash}",
        ]
        for finding in self.findings:
            subject = finding.source_route_id or ",".join(finding.affected_route_ids)
            lines.append(f"- {finding.code}: {subject}: {finding.message}")
        return "\n".join(lines)


@dataclass(frozen=True)
class RouteParityReport:
    inventory_hash: str
    registry_hash: str
    findings: tuple[RouteTopologyFinding, ...]

    @property
    def ok(self) -> bool:
        return not self.findings

    @property
    def status(self) -> str:
        return TOPOLOGY_STATUS_PASS if self.ok else TOPOLOGY_STATUS_BLOCKED

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "flowguard_route_parity_report",
            "ok": self.ok,
            "status": self.status,
            "inventory_hash": self.inventory_hash,
            "registry_hash": self.registry_hash,
            "findings": [finding.to_dict() for finding in self.findings],
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, sort_keys=True)

    def format_text(self) -> str:
        lines = ["=== flowguard route parity ===", f"status: {self.status}"]
        lines.extend(f"- {item.code}: {item.message}" for item in self.findings)
        return "\n".join(lines)


def load_suite_routing_snapshot(root: str | Path = ".") -> SuiteRoutingSnapshot:
    root_path = Path(root).resolve()
    path = root_path / ".skillguard" / "flowguard-suite" / "suite-map.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    members = data.get("included_skills", ())
    skill_ids: list[str] = []
    owners: dict[str, str] = {}
    for raw in members:
        if not isinstance(raw, Mapping):
            continue
        skill_id = str(raw.get("name", ""))
        if not skill_id:
            continue
        skill_ids.append(skill_id)
        owners[skill_id] = str(raw.get("owner", ""))
    return SuiteRoutingSnapshot(tuple(sorted(skill_ids)), owners, _sha256(data))


def _finding_sort_key(finding: RouteTopologyFinding) -> tuple[Any, ...]:
    return (
        finding.code,
        finding.source_route_id,
        finding.target_kind,
        finding.target_id,
        finding.affected_route_ids,
        _canonical_json(dict(finding.metadata)),
    )


def _profile_dict(profile: Any) -> dict[str, Any]:
    if hasattr(profile, "to_dict"):
        return profile.to_dict()
    return {
        "route_id": str(getattr(profile, "route_id", "")),
        "route_role": str(getattr(profile, "route_role", "")),
        "entry_policy": str(getattr(profile, "entry_policy", "")),
        "skill_name": str(getattr(profile, "skill_name", "")),
        "canonical_owner_route": str(getattr(profile, "canonical_owner_route", "")),
        "next_actions": [
            require_typed_handoff(item).to_dict()
            for item in getattr(profile, "next_actions", ())
        ],
    }


def route_registry_hash(
    route_profiles: Sequence[Any],
    cycle_policies: Sequence[RouteCycleLiveness] = DEFAULT_ROUTE_CYCLE_LIVENESS,
) -> str:
    return _sha256(
        {
            "profiles": [_profile_dict(profile) for profile in sorted(route_profiles, key=lambda item: item.route_id)],
            "cycle_policies": [policy.to_dict() for policy in sorted(cycle_policies, key=lambda item: item.component_id)],
        }
    )


def _strongly_connected_components(graph: Mapping[str, Sequence[str]]) -> tuple[tuple[str, ...], ...]:
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    components: list[tuple[str, ...]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for target in sorted(graph.get(node, ())):
            if target not in indices:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[target])
        if lowlinks[node] != indices[node]:
            return
        component: list[str] = []
        while stack:
            target = stack.pop()
            on_stack.remove(target)
            component.append(target)
            if target == node:
                break
        component_tuple = tuple(sorted(component))
        if len(component_tuple) > 1 or node in graph.get(node, ()):
            components.append(component_tuple)

    for node in sorted(graph):
        if node not in indices:
            visit(node)
    return tuple(sorted(components))


def _target_kind_for_id(target_id: str, suite_skill_ids: set[str], route_ids: set[str]) -> str:
    if target_id in suite_skill_ids:
        return TARGET_KIND_SKILL
    if target_id in route_ids:
        return TARGET_KIND_INTERNAL_ROUTE
    if target_id in HELPER_API_TARGETS:
        return TARGET_KIND_HELPER_API
    if target_id in EXTERNAL_ACTION_TARGETS:
        return TARGET_KIND_EXTERNAL_ACTION
    return ""


def validate_route_topology(
    route_profiles: Sequence[Any],
    suite_snapshot: SuiteRoutingSnapshot,
    *,
    cycle_policies: Sequence[RouteCycleLiveness] = DEFAULT_ROUTE_CYCLE_LIVENESS,
) -> RouteTopologyReport:
    """Validate typed targets, ownership, and bounded SCC liveness."""

    findings: list[RouteTopologyFinding] = []
    profiles_by_id: dict[str, list[Any]] = {}
    for profile in route_profiles:
        profiles_by_id.setdefault(str(profile.route_id), []).append(profile)
    for route_id, claims in sorted(profiles_by_id.items()):
        if len(claims) > 1:
            findings.append(
                RouteTopologyFinding(
                    "duplicate_route_owner",
                    "route id has more than one ownership declaration",
                    affected_route_ids=(route_id,),
                    metadata={"claimants": [str(getattr(item, "skill_name", "")) for item in claims]},
                )
            )
    profiles = {route_id: claims[0] for route_id, claims in profiles_by_id.items()}
    route_ids = set(profiles)
    suite_skill_ids = set(suite_snapshot.skill_ids)
    public_skill_to_route: dict[str, str] = {}

    for route_id, profile in sorted(profiles.items()):
        role = str(getattr(profile, "route_role", ""))
        entry_policy = str(getattr(profile, "entry_policy", ""))
        skill_name = str(getattr(profile, "skill_name", ""))
        owner_route = str(getattr(profile, "canonical_owner_route", ""))
        if route_id in PUBLIC_ROUTE_SKILL_OWNERS:
            expected_skill = PUBLIC_ROUTE_SKILL_OWNERS[route_id]
            if role != ROUTE_ROLE_PUBLIC_OWNER or entry_policy != ENTRY_POLICY_DIRECT:
                findings.append(
                    RouteTopologyFinding(
                        "public_route_classification_mismatch",
                        "canonical public route must be direct and public_owner",
                        source_route_id=route_id,
                    )
                )
            if not skill_name:
                findings.append(
                    RouteTopologyFinding(
                        "missing_public_owner",
                        "public route is missing its canonical skill owner",
                        source_route_id=route_id,
                    )
                )
            elif skill_name != expected_skill:
                findings.append(
                    RouteTopologyFinding(
                        "public_owner_mismatch",
                        "public route owner differs from canonical registry",
                        source_route_id=route_id,
                        metadata={"actual": skill_name, "expected": expected_skill},
                    )
                )
            if skill_name and skill_name not in suite_skill_ids:
                findings.append(
                    RouteTopologyFinding(
                        "public_owner_not_in_suite",
                        "public route owner is absent from canonical suite inventory",
                        source_route_id=route_id,
                        target_kind=TARGET_KIND_SKILL,
                        target_id=skill_name,
                    )
                )
            if skill_name:
                prior = public_skill_to_route.get(skill_name)
                if prior and prior != route_id:
                    findings.append(
                        RouteTopologyFinding(
                            "duplicate_public_skill_owner",
                            "one skill is primary owner for more than one public route",
                            affected_route_ids=(prior, route_id),
                            target_kind=TARGET_KIND_SKILL,
                            target_id=skill_name,
                        )
                    )
                public_skill_to_route[skill_name] = route_id
        elif route_id in INTERNAL_ROUTE_OWNERS:
            expected_owner = INTERNAL_ROUTE_OWNERS[route_id]
            if role == ROUTE_ROLE_PUBLIC_OWNER or entry_policy == ENTRY_POLICY_DIRECT:
                findings.append(
                    RouteTopologyFinding(
                        "internal_route_exposed_as_public",
                        "canonical internal/delegated route cannot be a direct public owner",
                        source_route_id=route_id,
                    )
                )
            if not owner_route:
                findings.append(
                    RouteTopologyFinding(
                        "missing_internal_owner",
                        "internal route is missing its canonical public owner route",
                        source_route_id=route_id,
                    )
                )
            elif owner_route != expected_owner:
                findings.append(
                    RouteTopologyFinding(
                        "internal_owner_mismatch",
                        "internal route owner differs from canonical registry",
                        source_route_id=route_id,
                        metadata={"actual": owner_route, "expected": expected_owner},
                    )
                )
            if owner_route and owner_route not in PUBLIC_ROUTE_SKILL_OWNERS:
                findings.append(
                    RouteTopologyFinding(
                        "internal_owner_not_public_route",
                        "internal route owner does not resolve to a canonical public route",
                        source_route_id=route_id,
                        target_id=owner_route,
                    )
                )
        else:
            findings.append(
                RouteTopologyFinding(
                    "unregistered_route",
                    "route profile is absent from the canonical ownership registry",
                    source_route_id=route_id,
                )
            )

    for route_id in sorted((set(PUBLIC_ROUTE_SKILL_OWNERS) | set(INTERNAL_ROUTE_OWNERS)) - route_ids):
        if route_id not in route_ids:
            findings.append(
                RouteTopologyFinding(
                    "registered_route_missing_profile",
                    "canonical route registry entry has no route profile",
                    source_route_id=route_id,
                )
            )

    graph: dict[str, list[str]] = {route_id: [] for route_id in route_ids}
    edge_count = 0
    for source_route_id, profile in sorted(profiles.items()):
        for raw in getattr(profile, "next_actions", ()):
            edge_count += 1
            if isinstance(raw, str):
                findings.append(
                    RouteTopologyFinding(
                        "legacy_handoff_not_typed",
                        "bare-string handoff is a migration error and cannot be followed",
                        source_route_id=source_route_id,
                        target_id=raw,
                    )
                )
                continue
            try:
                handoff = require_typed_handoff(raw)
            except (TypeError, ValueError) as exc:
                findings.append(
                    RouteTopologyFinding(
                        "invalid_typed_handoff",
                        str(exc),
                        source_route_id=source_route_id,
                    )
                )
                continue
            resolved_route = ""
            valid = False
            if handoff.target_kind == TARGET_KIND_SKILL:
                valid = handoff.target_id in suite_skill_ids and handoff.target_id in public_skill_to_route
                resolved_route = public_skill_to_route.get(handoff.target_id, "")
            elif handoff.target_kind == TARGET_KIND_INTERNAL_ROUTE:
                valid = handoff.target_id in INTERNAL_ROUTE_OWNERS and handoff.target_id in route_ids
                resolved_route = handoff.target_id if valid else ""
            elif handoff.target_kind == TARGET_KIND_HELPER_API:
                valid = handoff.target_id in HELPER_API_TARGETS
            elif handoff.target_kind == TARGET_KIND_EXTERNAL_ACTION:
                valid = handoff.target_id in EXTERNAL_ACTION_TARGETS
            if not valid:
                actual_kind = _target_kind_for_id(handoff.target_id, suite_skill_ids, route_ids)
                code = "target_kind_mismatch" if actual_kind and actual_kind != handoff.target_kind else "dangling_target"
                findings.append(
                    RouteTopologyFinding(
                        code,
                        "handoff target does not resolve under its declared target kind",
                        source_route_id=source_route_id,
                        target_kind=handoff.target_kind,
                        target_id=handoff.target_id,
                        metadata={"actual_kind": actual_kind},
                    )
                )
            elif resolved_route:
                graph[source_route_id].append(resolved_route)

    components = _strongly_connected_components(graph)
    policies_by_routes = {policy.route_ids: policy for policy in cycle_policies}
    probes: list[RouteLoopProbe] = []
    for component in components:
        policy = policies_by_routes.get(component)
        if policy is None:
            findings.append(
                RouteTopologyFinding(
                    "unbounded_cycle",
                    "strongly connected route component has no liveness policy",
                    affected_route_ids=component,
                )
            )
            continue
        missing_fields = [
            name
            for name, value in (
                ("progress_measure", policy.progress_measure),
                ("allowed_delta", policy.allowed_delta),
                ("success_terminal", policy.success_terminal),
                ("blocked_terminal", policy.blocked_terminal),
            )
            if not value
        ]
        if missing_fields:
            findings.append(
                RouteTopologyFinding(
                    "cycle_liveness_metadata_missing",
                    "cycle liveness policy is missing required fields",
                    affected_route_ids=component,
                    metadata={"missing_fields": missing_fields},
                )
            )
        if policy.max_reentries <= 0 or not math.isfinite(policy.max_reentries):
            findings.append(
                RouteTopologyFinding(
                    "unbounded_cycle",
                    "cycle liveness policy has no positive finite re-entry bound",
                    affected_route_ids=component,
                    metadata={"max_reentries": policy.max_reentries},
                )
            )
        unchanged = probe_cycle_liveness(
            policy,
            previous_progress=("receipt-a",),
            current_progress=("receipt-a",),
            reentries=policy.max_reentries,
        )
        changed = probe_cycle_liveness(
            policy,
            previous_progress=("receipt-a",),
            current_progress=("receipt-a", "receipt-b"),
            reentries=0,
        )
        probes.extend((unchanged, changed))
        if unchanged.decision != LOOP_DECISION_BLOCKED_UNCHANGED:
            findings.append(
                RouteTopologyFinding(
                    "unchanged_loop_progress",
                    "unchanged cycle input did not terminate at the blocked terminal",
                    affected_route_ids=component,
                )
            )
        if changed.decision != LOOP_DECISION_CONTINUE:
            findings.append(
                RouteTopologyFinding(
                    "changed_loop_cannot_progress",
                    "cycle with an allowed evidence delta cannot continue within its bound",
                    affected_route_ids=component,
                )
            )

    for policy in cycle_policies:
        if policy.route_ids not in components:
            findings.append(
                RouteTopologyFinding(
                    "stale_cycle_policy",
                    "cycle liveness policy does not match a current strongly connected component",
                    affected_route_ids=policy.route_ids,
                    metadata={"component_id": policy.component_id},
                )
            )

    ordered_findings = tuple(sorted(findings, key=_finding_sort_key))
    return RouteTopologyReport(
        inventory_hash=suite_snapshot.inventory_hash,
        registry_hash=route_registry_hash(route_profiles, cycle_policies),
        route_ids=tuple(sorted(route_ids)),
        edge_count=edge_count,
        cycle_components=components,
        cycle_probes=tuple(probes),
        findings=ordered_findings,
    )


def validate_route_parity(
    root: str | Path,
    route_profiles: Sequence[Any],
    suite_snapshot: SuiteRoutingSnapshot,
    *,
    public_route_ids: Sequence[str],
    internal_route_ids: Sequence[str],
) -> RouteParityReport:
    """Compare registry, suite ownership, route API projections, and prompt ids."""

    root_path = Path(root).resolve()
    findings: list[RouteTopologyFinding] = []
    profiles = {str(profile.route_id): profile for profile in route_profiles}
    expected_public = set(PUBLIC_ROUTE_SKILL_OWNERS)
    expected_internal = set(INTERNAL_ROUTE_OWNERS)
    actual_public = set(str(item) for item in public_route_ids)
    actual_internal = set(str(item) for item in internal_route_ids)
    if actual_public != expected_public:
        findings.append(
            RouteTopologyFinding(
                "public_route_projection_mismatch",
                "public route API projection differs from canonical route registry",
                affected_route_ids=tuple(sorted(actual_public ^ expected_public)),
                metadata={"actual": sorted(actual_public), "expected": sorted(expected_public)},
            )
        )
    if actual_internal != expected_internal:
        findings.append(
            RouteTopologyFinding(
                "internal_route_projection_mismatch",
                "internal route API projection differs from canonical route registry",
                affected_route_ids=tuple(sorted(actual_internal ^ expected_internal)),
                metadata={"actual": sorted(actual_internal), "expected": sorted(expected_internal)},
            )
        )

    delegated_by_skill = {
        str(getattr(profile, "skill_name", "")): str(getattr(profile, "canonical_owner_route", ""))
        for profile in route_profiles
        if str(getattr(profile, "skill_name", ""))
        and str(getattr(profile, "canonical_owner_route", ""))
        and str(getattr(profile, "route_role", "")) == "delegated_mode"
    }
    for skill_id in suite_snapshot.skill_ids:
        owner_route = str(suite_snapshot.route_owner_by_skill.get(skill_id, ""))
        direct_match = PUBLIC_ROUTE_SKILL_OWNERS.get(owner_route) == skill_id
        delegated_match = delegated_by_skill.get(skill_id) == owner_route
        if not (direct_match or delegated_match):
            findings.append(
                RouteTopologyFinding(
                    "suite_owner_projection_mismatch",
                    "suite member owner does not match a public or delegated route projection",
                    target_kind=TARGET_KIND_SKILL,
                    target_id=skill_id,
                    metadata={"suite_owner": owner_route},
                )
            )

    route_pattern = re.compile(r"(?:Route id|Route):\s*`([^`]+)`")
    skill_root = root_path / ".agents" / "skills"
    for skill_id in suite_snapshot.skill_ids:
        skill_file = skill_root / skill_id / "SKILL.md"
        if not skill_file.is_file():
            continue
        declared = tuple(sorted(set(route_pattern.findall(skill_file.read_text(encoding="utf-8", errors="replace")))))
        for route_id in declared:
            profile = profiles.get(route_id)
            if profile is None:
                findings.append(
                    RouteTopologyFinding(
                        "prompt_route_id_stale",
                        "skill prompt declares a route id absent from the canonical registry",
                        source_route_id=route_id,
                        target_kind=TARGET_KIND_SKILL,
                        target_id=skill_id,
                    )
                )
                continue
            actual_skill = str(getattr(profile, "skill_name", ""))
            if actual_skill != skill_id:
                findings.append(
                    RouteTopologyFinding(
                        "prompt_route_owner_mismatch",
                        "skill prompt route id is owned by a different skill",
                        source_route_id=route_id,
                        target_kind=TARGET_KIND_SKILL,
                        target_id=skill_id,
                        metadata={"registry_skill": actual_skill},
                    )
                )

    return RouteParityReport(
        inventory_hash=suite_snapshot.inventory_hash,
        registry_hash=route_registry_hash(route_profiles),
        findings=tuple(sorted(findings, key=_finding_sort_key)),
    )


def validate_default_route_topology(root: str | Path = ".") -> RouteTopologyReport:
    from .self_maintenance import default_flowguard_route_profiles

    return validate_route_topology(default_flowguard_route_profiles(), load_suite_routing_snapshot(root))


__all__ = [
    "DEFAULT_ROUTE_CYCLE_LIVENESS",
    "EXTERNAL_ACTION_TARGETS",
    "HELPER_API_TARGETS",
    "INTERNAL_ROUTE_OWNERS",
    "LOOP_DECISION_BLOCKED_BOUND",
    "LOOP_DECISION_BLOCKED_UNCHANGED",
    "LOOP_DECISION_CONTINUE",
    "LOOP_DECISION_SUCCESS",
    "LegacyRouteHandoffError",
    "PUBLIC_ROUTE_SKILL_OWNERS",
    "PUBLIC_ROUTE_IDS",
    "RouteCycleLiveness",
    "RouteHandoff",
    "RouteLoopProbe",
    "RouteParityReport",
    "RouteTopologyFinding",
    "RouteTopologyReport",
    "SuiteRoutingSnapshot",
    "TARGET_KIND_EXTERNAL_ACTION",
    "TARGET_KIND_HELPER_API",
    "TARGET_KIND_INTERNAL_ROUTE",
    "TARGET_KIND_SKILL",
    "TARGET_KINDS",
    "external_action_handoff",
    "helper_handoff",
    "load_suite_routing_snapshot",
    "probe_cycle_liveness",
    "require_typed_handoff",
    "route_handoff",
    "route_handoffs",
    "route_registry_hash",
    "validate_default_route_topology",
    "validate_route_parity",
    "validate_route_topology",
]
