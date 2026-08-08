"""Executable model for FlowGuard's permanent skill-suite topology owner.

The model derives the current public skill suite from one canonical suite-map
snapshot and one current route-registry snapshot.  It owns membership,
member-role/owner parity, required-file presence, and public-versus-internal
route separation.  It deliberately does not certify contracts, projections,
installation, package identity, Git, tags, or release readiness.

Function blocks use the FlowGuard shape ``Input x State -> Set(Output x State)``.
Run with ``python .flowguard/codex_skill_satellites/run_checks.py``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


MODEL_ID = "codex_skill_satellites"
FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"

KERNEL_ROLE = "kernel_router"
SATELLITE_ROLE = "public_satellite"
PUBLIC_ROUTE_ROLE = "public_owner"
PUBLIC_ENTRY_POLICY = "direct"

TOPOLOGY_NOT_RUN = "not_run"
TOPOLOGY_CURRENT = "current"
TOPOLOGY_BLOCKED = "blocked"
TOPOLOGY_STALE = "stale"

TOPOLOGY_CLAIM_SCOPE = "current_skill_suite_topology_only"
CLAIM_BOUNDARY = (
    "This model proves only the exact current suite-map membership, member roles, "
    "route owners, required-file presence, and public/internal route separation "
    "for one source fingerprint. Contract execution, repository projections, "
    "consumer cleanliness, installation, package, Git, tag, and release evidence "
    "remain independent and are not release-ready because topology is current."
)

# These are evidence-domain names, not a pipeline and not a combined gate.
EVIDENCE_DOMAIN_IDS = (
    "source_code",
    "generated_contracts",
    "formal_repository_projection",
    "shadow_projection",
    "clean_consumer_distribution",
    "installed_projection",
    "package_version",
    "git_identity",
    "tag_identity",
    "release_identity",
)
DOWNSTREAM_EVIDENCE_DOMAIN_IDS = EVIDENCE_DOMAIN_IDS[1:]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _is_fingerprint(value: str) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != 71:
        return False
    try:
        int(value[7:], 16)
    except ValueError:
        return False
    return True


def _unique_sorted(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


@dataclass(frozen=True)
class TopologyInputIdentity:
    """Every source family that can stale this topology evidence."""

    suite_map_fingerprint: str
    route_registry_fingerprint: str
    skill_inputs_fingerprint: str
    contract_inputs_fingerprint: str
    suite_scripts_fingerprint: str
    suite_tests_fingerprint: str
    model_fingerprint: str
    runner_fingerprint: str

    def valid(self) -> bool:
        return all(_is_fingerprint(value) for value in self.to_dict().values())

    def to_dict(self) -> dict[str, str]:
        return {
            "suite_map_fingerprint": self.suite_map_fingerprint,
            "route_registry_fingerprint": self.route_registry_fingerprint,
            "skill_inputs_fingerprint": self.skill_inputs_fingerprint,
            "contract_inputs_fingerprint": self.contract_inputs_fingerprint,
            "suite_scripts_fingerprint": self.suite_scripts_fingerprint,
            "suite_tests_fingerprint": self.suite_tests_fingerprint,
            "model_fingerprint": self.model_fingerprint,
            "runner_fingerprint": self.runner_fingerprint,
        }


@dataclass(frozen=True)
class CanonicalMember:
    """One member row derived from the current canonical suite map."""

    member_id: str
    role: str
    owner_route_id: str
    declared_path: str
    required: bool
    required_files: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "member_id", str(self.member_id))
        object.__setattr__(self, "role", str(self.role))
        object.__setattr__(self, "owner_route_id", str(self.owner_route_id))
        object.__setattr__(self, "declared_path", str(self.declared_path).replace("\\", "/"))
        object.__setattr__(self, "required", bool(self.required))
        object.__setattr__(self, "required_files", _unique_sorted(self.required_files))

    def to_dict(self) -> dict[str, Any]:
        return {
            "member_id": self.member_id,
            "role": self.role,
            "owner_route_id": self.owner_route_id,
            "declared_path": self.declared_path,
            "required": self.required,
            "required_files": list(self.required_files),
        }


@dataclass(frozen=True)
class RouteRegistryEntry:
    """One current route-registry row, public or internal/delegated."""

    route_id: str
    route_role: str
    entry_policy: str
    owner_route_id: str
    skill_id: str = ""
    member_role: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "route_id", str(self.route_id))
        object.__setattr__(self, "route_role", str(self.route_role))
        object.__setattr__(self, "entry_policy", str(self.entry_policy))
        object.__setattr__(self, "owner_route_id", str(self.owner_route_id))
        object.__setattr__(self, "skill_id", str(self.skill_id))
        object.__setattr__(self, "member_role", str(self.member_role))

    @property
    def is_public(self) -> bool:
        return self.route_role == PUBLIC_ROUTE_ROLE and self.entry_policy == PUBLIC_ENTRY_POLICY

    def to_dict(self) -> dict[str, str]:
        return {
            "route_id": self.route_id,
            "route_role": self.route_role,
            "entry_policy": self.entry_policy,
            "owner_route_id": self.owner_route_id,
            "skill_id": self.skill_id,
            "member_role": self.member_role,
        }


@dataclass(frozen=True)
class DiscoveredMember:
    """One independently discovered public-skill surface."""

    member_id: str
    role: str
    owner_route_id: str
    route_id: str
    discovered_path: str
    present_files: tuple[str, ...]
    reserved_identity: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "member_id", str(self.member_id))
        object.__setattr__(self, "role", str(self.role))
        object.__setattr__(self, "owner_route_id", str(self.owner_route_id))
        object.__setattr__(self, "route_id", str(self.route_id))
        object.__setattr__(self, "discovered_path", str(self.discovered_path).replace("\\", "/"))
        object.__setattr__(self, "present_files", _unique_sorted(self.present_files))
        object.__setattr__(self, "reserved_identity", bool(self.reserved_identity))

    def to_dict(self) -> dict[str, Any]:
        return {
            "member_id": self.member_id,
            "role": self.role,
            "owner_route_id": self.owner_route_id,
            "route_id": self.route_id,
            "discovered_path": self.discovered_path,
            "present_files": list(self.present_files),
            "reserved_identity": self.reserved_identity,
        }


@dataclass(frozen=True)
class FixedCountAssertion:
    """A count mention supplied only so stale parallel authority can be rejected."""

    surface_id: str
    literal_count: int
    claims_authority: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "surface_id": str(self.surface_id),
            "literal_count": int(self.literal_count),
            "claims_authority": bool(self.claims_authority),
        }


@dataclass(frozen=True)
class EvidenceDomain:
    domain_id: str
    status: str
    fingerprint: str

    def to_dict(self) -> dict[str, str]:
        return {
            "domain_id": str(self.domain_id),
            "status": str(self.status),
            "fingerprint": str(self.fingerprint),
        }


@dataclass(frozen=True)
class SuiteTopologySource:
    """Frozen inputs from the suite map, route registry, and live discovery."""

    suite_name: str
    suite_schema: str
    identity: TopologyInputIdentity
    canonical_members: tuple[CanonicalMember, ...]
    route_registry: tuple[RouteRegistryEntry, ...]
    helper_api_ids: tuple[str, ...]
    discovered_members: tuple[DiscoveredMember, ...]
    evidence_domains: tuple[EvidenceDomain, ...]
    fixed_count_assertions: tuple[FixedCountAssertion, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "suite_name", str(self.suite_name))
        object.__setattr__(self, "suite_schema", str(self.suite_schema))
        object.__setattr__(self, "canonical_members", tuple(self.canonical_members))
        object.__setattr__(self, "route_registry", tuple(self.route_registry))
        object.__setattr__(self, "helper_api_ids", _unique_sorted(self.helper_api_ids))
        object.__setattr__(self, "discovered_members", tuple(self.discovered_members))
        object.__setattr__(self, "evidence_domains", tuple(self.evidence_domains))
        object.__setattr__(self, "fixed_count_assertions", tuple(self.fixed_count_assertions))

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite_name": self.suite_name,
            "suite_schema": self.suite_schema,
            "identity": self.identity.to_dict(),
            "canonical_members": [
                member.to_dict()
                for member in sorted(
                    self.canonical_members,
                    key=lambda item: (item.member_id, item.role, item.owner_route_id),
                )
            ],
            "route_registry": [
                route.to_dict()
                for route in sorted(
                    self.route_registry,
                    key=lambda item: (item.route_id, item.skill_id, item.route_role),
                )
            ],
            "helper_api_ids": list(self.helper_api_ids),
            "discovered_members": [
                member.to_dict()
                for member in sorted(
                    self.discovered_members,
                    key=lambda item: (item.member_id, item.discovered_path, item.route_id),
                )
            ],
            "fixed_count_assertions": [
                assertion.to_dict()
                for assertion in sorted(
                    self.fixed_count_assertions,
                    key=lambda item: str(item.surface_id),
                )
            ],
        }


def source_fingerprint(source: SuiteTopologySource) -> str:
    """Bind every topology-affecting input without collapsing evidence domains."""

    return _fingerprint(source.to_dict())


@dataclass(frozen=True)
class TopologyFinding:
    code: str
    message: str
    member_id: str = ""
    route_id: str = ""
    file_path: str = ""
    surface_id: str = ""
    metadata: Mapping[str, Any] | None = None

    def __hash__(self) -> int:
        """Keep model states hashable while retaining structured diagnostics."""

        return hash(
            (
                self.code,
                self.message,
                self.member_id,
                self.route_id,
                self.file_path,
                self.surface_id,
                _canonical_json(dict(self.metadata or {})),
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "member_id": self.member_id,
            "route_id": self.route_id,
            "file_path": self.file_path,
            "surface_id": self.surface_id,
            "metadata": dict(self.metadata or {}),
        }


@dataclass(frozen=True)
class MemberProjection:
    member_id: str
    role: str
    owner_route_id: str
    route_id: str
    declared_path: str
    required_files: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "member_id": self.member_id,
            "role": self.role,
            "owner_route_id": self.owner_route_id,
            "route_id": self.route_id,
            "declared_path": self.declared_path,
            "required_files": list(self.required_files),
        }


@dataclass(frozen=True)
class RouteProjection:
    route_id: str
    route_role: str
    entry_policy: str
    owner_route_id: str

    def to_dict(self) -> dict[str, str]:
        return {
            "route_id": self.route_id,
            "route_role": self.route_role,
            "entry_policy": self.entry_policy,
            "owner_route_id": self.owner_route_id,
        }


@dataclass(frozen=True)
class TopologyReport:
    status: str
    input_fingerprint: str
    topology_fingerprint: str
    members: tuple[MemberProjection, ...]
    internal_routes: tuple[RouteProjection, ...]
    helper_api_ids: tuple[str, ...]
    reported_count: int
    reported_role_counts: tuple[tuple[str, int], ...]
    findings: tuple[TopologyFinding, ...]
    claim_boundary: str = CLAIM_BOUNDARY

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "input_fingerprint": self.input_fingerprint,
            "topology_fingerprint": self.topology_fingerprint,
            "members": [member.to_dict() for member in self.members],
            "internal_routes": [route.to_dict() for route in self.internal_routes],
            "helper_api_ids": list(self.helper_api_ids),
            "reported_count": self.reported_count,
            "reported_role_counts": dict(self.reported_role_counts),
            "findings": [finding.to_dict() for finding in self.findings],
            "claim_boundary": self.claim_boundary,
        }


@dataclass(frozen=True)
class TopologyAction:
    action_type: str
    source: SuiteTopologySource | None = None


@dataclass(frozen=True)
class TopologyOutput:
    status: str
    reported_count: int
    finding_ids: tuple[str, ...]
    claim_scope: str = TOPOLOGY_CLAIM_SCOPE
    release_readiness: str = "not_owned"


@dataclass(frozen=True)
class TopologyState:
    source: SuiteTopologySource | None = None
    input_fingerprint: str = ""
    reviewed_input_fingerprint: str = ""
    topology_status: str = TOPOLOGY_NOT_RUN
    report: TopologyReport | None = None
    evidence_domains: tuple[EvidenceDomain, ...] = ()
    stale_domain_ids: tuple[str, ...] = ()
    topology_claim: str = "none"
    release_readiness: str = "not_owned"


def _finding_sort_key(finding: TopologyFinding) -> tuple[Any, ...]:
    return (
        finding.code,
        finding.member_id,
        finding.route_id,
        finding.file_path,
        finding.surface_id,
        _canonical_json(dict(finding.metadata or {})),
    )


def _add_finding(
    findings: list[TopologyFinding],
    code: str,
    message: str,
    *,
    member_id: str = "",
    route_id: str = "",
    file_path: str = "",
    surface_id: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> None:
    findings.append(
        TopologyFinding(
            code,
            message,
            member_id=member_id,
            route_id=route_id,
            file_path=file_path,
            surface_id=surface_id,
            metadata=metadata,
        )
    )


def derive_topology_report(source: SuiteTopologySource) -> TopologyReport:
    """Derive topology and deterministic exact findings from current inputs."""

    findings: list[TopologyFinding] = []
    if not source.identity.valid():
        _add_finding(
            findings,
            "invalid_topology_input_identity",
            "suite topology inputs require exact fingerprints for map, registry, skills, contracts, scripts, tests, model, and runner",
        )

    domain_ids = tuple(domain.domain_id for domain in source.evidence_domains)
    if len(domain_ids) != len(set(domain_ids)):
        _add_finding(
            findings,
            "duplicate_evidence_domain",
            "evidence domains must remain independently identified",
            metadata={"domain_ids": domain_ids},
        )
    if set(domain_ids) != set(EVIDENCE_DOMAIN_IDS):
        _add_finding(
            findings,
            "evidence_domain_inventory_mismatch",
            "topology cannot collapse or omit source, projection, installation, package, Git, tag, or release domains",
            metadata={"actual": domain_ids, "expected": EVIDENCE_DOMAIN_IDS},
        )

    canonical_by_id: dict[str, list[CanonicalMember]] = {}
    for member in source.canonical_members:
        canonical_by_id.setdefault(member.member_id, []).append(member)
    for member_id, rows in sorted(canonical_by_id.items()):
        if len(rows) > 1:
            _add_finding(
                findings,
                "duplicate_member_id",
                "canonical suite map declares the member more than once",
                member_id=member_id,
                metadata={"occurrences": len(rows)},
            )

    public_routes = tuple(route for route in source.route_registry if route.is_public)
    internal_routes = tuple(route for route in source.route_registry if not route.is_public)
    public_by_skill: dict[str, list[RouteRegistryEntry]] = {}
    route_rows: dict[str, list[RouteRegistryEntry]] = {}
    for route in source.route_registry:
        route_rows.setdefault(route.route_id, []).append(route)
        if route.is_public:
            public_by_skill.setdefault(route.skill_id, []).append(route)
            if not route.skill_id:
                _add_finding(
                    findings,
                    "public_route_missing_member_id",
                    "a public route has no skill member identity",
                    route_id=route.route_id,
                )
    for route_id, rows in sorted(route_rows.items()):
        if len(rows) > 1:
            _add_finding(
                findings,
                "duplicate_route_id",
                "route registry declares the route more than once",
                route_id=route_id,
                metadata={"occurrences": len(rows)},
            )

    discovered_by_id: dict[str, list[DiscoveredMember]] = {}
    for member in source.discovered_members:
        discovered_by_id.setdefault(member.member_id, []).append(member)
    for member_id, rows in sorted(discovered_by_id.items()):
        if len(rows) > 1:
            _add_finding(
                findings,
                "duplicate_discovered_member",
                "public discovery found the same member identity more than once",
                member_id=member_id,
                metadata={"paths": sorted(row.discovered_path for row in rows)},
            )

    canonical_ids = set(canonical_by_id)
    internal_route_ids = {route.route_id for route in internal_routes}
    helper_api_ids = set(source.helper_api_ids)

    for member_id, rows in sorted(canonical_by_id.items()):
        canonical = rows[0]
        if not member_id:
            _add_finding(findings, "member_id_missing", "suite member id is empty")
            continue
        if canonical.role not in {KERNEL_ROLE, SATELLITE_ROLE}:
            _add_finding(
                findings,
                "member_role_invalid",
                "suite member role is neither kernel_router nor public_satellite",
                member_id=member_id,
                metadata={"actual": canonical.role},
            )
        if canonical.required and not canonical.required_files:
            _add_finding(
                findings,
                "required_file_policy_missing",
                "required suite member has no current required-file inventory",
                member_id=member_id,
            )

        registry_rows = public_by_skill.get(member_id, [])
        if not registry_rows:
            _add_finding(
                findings,
                "route_registry_member_missing",
                "canonical suite member has no current direct public route",
                member_id=member_id,
            )
            route = None
        elif len(registry_rows) > 1:
            _add_finding(
                findings,
                "duplicate_public_member_owner",
                "more than one public route claims the member",
                member_id=member_id,
                metadata={"route_ids": sorted(row.route_id for row in registry_rows)},
            )
            route = registry_rows[0]
        else:
            route = registry_rows[0]
        if route is not None:
            if route.member_role != canonical.role:
                _add_finding(
                    findings,
                    "member_role_mismatch",
                    "suite-map role differs from the current route-registry role",
                    member_id=member_id,
                    route_id=route.route_id,
                    metadata={"suite_map": canonical.role, "route_registry": route.member_role},
                )
            if route.owner_route_id != canonical.owner_route_id or route.route_id != canonical.owner_route_id:
                _add_finding(
                    findings,
                    "member_owner_mismatch",
                    "suite-map owner differs from the current public route owner",
                    member_id=member_id,
                    route_id=route.route_id,
                    metadata={
                        "suite_map": canonical.owner_route_id,
                        "route_registry": route.owner_route_id,
                    },
                )

        discovered_rows = discovered_by_id.get(member_id, [])
        if canonical.required and not discovered_rows:
            _add_finding(
                findings,
                "missing_declared_member",
                "required canonical member is absent from public discovery",
                member_id=member_id,
            )
        if not discovered_rows:
            continue
        discovered = discovered_rows[0]
        if discovered.role != canonical.role:
            _add_finding(
                findings,
                "discovered_member_role_mismatch",
                "discovered member role differs from the canonical suite-map role",
                member_id=member_id,
                route_id=discovered.route_id,
                metadata={"canonical": canonical.role, "discovered": discovered.role},
            )
        if discovered.owner_route_id != canonical.owner_route_id:
            _add_finding(
                findings,
                "discovered_member_owner_mismatch",
                "discovered member owner differs from the canonical suite-map owner",
                member_id=member_id,
                route_id=discovered.route_id,
                metadata={
                    "canonical": canonical.owner_route_id,
                    "discovered": discovered.owner_route_id,
                },
            )
        if route is not None and discovered.route_id != route.route_id:
            _add_finding(
                findings,
                "discovered_member_route_mismatch",
                "discovered member route differs from the current route registry",
                member_id=member_id,
                route_id=discovered.route_id,
                metadata={"expected": route.route_id},
            )
        if discovered.discovered_path != canonical.declared_path:
            _add_finding(
                findings,
                "member_path_mismatch",
                "discovered member path differs from the canonical suite-map path",
                member_id=member_id,
                file_path=discovered.discovered_path,
                metadata={"expected": canonical.declared_path},
            )
        present = set(discovered.present_files)
        for relative_path in canonical.required_files:
            if relative_path not in present:
                _add_finding(
                    findings,
                    "required_member_file_missing",
                    "required member file is absent",
                    member_id=member_id,
                    file_path=f"{canonical.declared_path}/{relative_path}",
                )

    for route in sorted(public_routes, key=lambda item: (item.skill_id, item.route_id)):
        if route.skill_id not in canonical_ids:
            _add_finding(
                findings,
                "extra_route_registry_member",
                "current public route has no canonical suite-map member",
                member_id=route.skill_id,
                route_id=route.route_id,
            )

    for member in sorted(
        source.discovered_members,
        key=lambda item: (item.member_id, item.discovered_path, item.route_id),
    ):
        if member.reserved_identity and member.member_id not in canonical_ids:
            _add_finding(
                findings,
                "extra_reserved_member",
                "FlowGuard-reserved public skill is absent from the canonical suite map",
                member_id=member.member_id,
                route_id=member.route_id,
            )
        if member.route_id in internal_route_ids or member.route_id in helper_api_ids:
            _add_finding(
                findings,
                "internal_helper_exposed_public",
                "an internal/delegated route or helper API was exposed as a public skill",
                member_id=member.member_id,
                route_id=member.route_id,
            )

    public_owner_ids = {route.route_id for route in public_routes}
    for route in sorted(internal_routes, key=lambda item: item.route_id):
        if not route.owner_route_id or route.owner_route_id not in public_owner_ids:
            _add_finding(
                findings,
                "internal_route_owner_missing",
                "internal/delegated route has no current public owner",
                route_id=route.route_id,
                metadata={"owner_route_id": route.owner_route_id},
            )

    derived_count = len(canonical_ids)
    for assertion in source.fixed_count_assertions:
        if assertion.literal_count != derived_count:
            _add_finding(
                findings,
                "fixed_count_mismatch",
                "literal member count differs from the current canonical suite map",
                surface_id=assertion.surface_id,
                metadata={"literal": assertion.literal_count, "derived": derived_count},
            )
        if assertion.claims_authority:
            _add_finding(
                findings,
                "fixed_count_parallel_authority",
                "a literal count cannot own current suite topology",
                surface_id=assertion.surface_id,
                metadata={"literal": assertion.literal_count, "derived": derived_count},
            )

    public_route_by_skill = {
        route.skill_id: route
        for route in public_routes
        if route.skill_id and len(public_by_skill.get(route.skill_id, ())) == 1
    }
    member_projections = tuple(
        MemberProjection(
            member.member_id,
            member.role,
            member.owner_route_id,
            public_route_by_skill.get(member.member_id).route_id
            if member.member_id in public_route_by_skill
            else "",
            member.declared_path,
            member.required_files,
        )
        for member in sorted(
            (rows[0] for rows in canonical_by_id.values()),
            key=lambda item: item.member_id,
        )
    )
    internal_projections = tuple(
        RouteProjection(
            route.route_id,
            route.route_role,
            route.entry_policy,
            route.owner_route_id,
        )
        for route in sorted(internal_routes, key=lambda item: item.route_id)
    )
    role_counts: dict[str, int] = {}
    for member in member_projections:
        role_counts[member.role] = role_counts.get(member.role, 0) + 1
    topology_payload = {
        "members": [member.to_dict() for member in member_projections],
        "internal_routes": [route.to_dict() for route in internal_projections],
        "helper_api_ids": list(source.helper_api_ids),
        "reported_count": derived_count,
        "reported_role_counts": role_counts,
    }
    ordered_findings = tuple(sorted(findings, key=_finding_sort_key))
    return TopologyReport(
        status="pass" if not ordered_findings else "blocked",
        input_fingerprint=source_fingerprint(source),
        topology_fingerprint=_fingerprint(topology_payload),
        members=member_projections,
        internal_routes=internal_projections,
        helper_api_ids=source.helper_api_ids,
        reported_count=derived_count,
        reported_role_counts=tuple(sorted(role_counts.items())),
        findings=ordered_findings,
    )


def _compact_output(state: TopologyState, status: str) -> TopologyOutput:
    report = state.report
    return TopologyOutput(
        status=status,
        reported_count=report.reported_count if report is not None else 0,
        finding_ids=tuple(
            f"{finding.code}:{finding.member_id or finding.route_id or finding.surface_id}"
            for finding in (report.findings if report is not None else ())
        ),
        release_readiness=state.release_readiness,
    )


class SuiteTopologyFlow:
    """Load, review, and claim one current topology snapshot."""

    name = "SuiteTopologyFlow"
    reads = (
        "source",
        "input_fingerprint",
        "reviewed_input_fingerprint",
        "topology_status",
        "report",
        "evidence_domains",
        "stale_domain_ids",
        "topology_claim",
        "release_readiness",
    )
    writes = reads
    accepted_input_type = TopologyAction
    input_description = "current suite-map, route-registry, discovery, or topology claim action"
    output_description = "current or blocked suite topology without release overclaim"
    idempotency = "the same frozen source derives the same topology and exact findings"

    def _load_source(self, source: SuiteTopologySource, state: TopologyState) -> TopologyState:
        current_fingerprint = source_fingerprint(source)
        changed = bool(state.input_fingerprint and state.input_fingerprint != current_fingerprint)
        domains = source.evidence_domains
        stale_domain_ids: tuple[str, ...] = ()
        if changed:
            stale_domain_ids = DOWNSTREAM_EVIDENCE_DOMAIN_IDS
            domains = tuple(
                replace(domain, status="stale")
                if domain.domain_id in DOWNSTREAM_EVIDENCE_DOMAIN_IDS
                else domain
                for domain in domains
            )
        return replace(
            state,
            source=source,
            input_fingerprint=current_fingerprint,
            topology_status=TOPOLOGY_STALE if changed else TOPOLOGY_NOT_RUN,
            evidence_domains=domains,
            stale_domain_ids=stale_domain_ids,
            topology_claim="none",
            release_readiness="not_owned",
        )

    def _review(self, state: TopologyState) -> TopologyState:
        if state.source is None:
            return replace(state, topology_status=TOPOLOGY_BLOCKED, topology_claim="none")
        report = derive_topology_report(state.source)
        return replace(
            state,
            reviewed_input_fingerprint=state.input_fingerprint,
            topology_status=TOPOLOGY_CURRENT if report.status == "pass" else TOPOLOGY_BLOCKED,
            report=report,
            topology_claim="none",
            release_readiness="not_owned",
        )

    def _claimable(self, state: TopologyState) -> bool:
        return (
            state.source is not None
            and state.report is not None
            and state.topology_status == TOPOLOGY_CURRENT
            and state.report.status == "pass"
            and not state.report.findings
            and state.reviewed_input_fingerprint == state.input_fingerprint
            and state.report.input_fingerprint == state.input_fingerprint
        )

    def _claim(self, state: TopologyState) -> TopologyState:
        return replace(
            state,
            topology_claim="accepted" if self._claimable(state) else "rejected",
            release_readiness="not_owned",
        )

    def apply(self, input_obj: TopologyAction, state: TopologyState) -> Iterable[FunctionResult]:
        action = str(input_obj.action_type)
        if action == "load_source":
            if input_obj.source is None:
                next_state = replace(state, topology_status=TOPOLOGY_BLOCKED, topology_claim="none")
                label = "topology_source_missing"
            else:
                next_state = self._load_source(input_obj.source, state)
                label = "topology_source_changed" if next_state.topology_status == TOPOLOGY_STALE else "topology_source_loaded"
            yield FunctionResult(
                _compact_output(next_state, next_state.topology_status),
                next_state,
                label=label,
                reason="loaded one suite-map and route-registry source identity",
            )
            return
        if action == "review_topology":
            next_state = self._review(state)
            yield FunctionResult(
                _compact_output(next_state, next_state.topology_status),
                next_state,
                label="topology_current" if next_state.topology_status == TOPOLOGY_CURRENT else "topology_blocked",
                reason=CLAIM_BOUNDARY,
            )
            return
        if action == "claim_topology":
            next_state = self._claim(state)
            yield FunctionResult(
                _compact_output(next_state, next_state.topology_claim),
                next_state,
                label=f"topology_claim_{next_state.topology_claim}",
                reason=CLAIM_BOUNDARY,
            )
            return
        if action == "claim_release":
            next_state = replace(state, release_readiness="not_owned")
            yield FunctionResult(
                _compact_output(next_state, "release_not_owned"),
                next_state,
                label="release_claim_not_owned",
                reason="DevelopmentProcessFlow and independent evidence owners decide release readiness",
            )


class BrokenAcceptMemberFindings(SuiteTopologyFlow):
    """Known-bad path that accepts missing/extra/duplicate/misclassified members."""

    name = "BrokenAcceptMemberFindings"

    def _claimable(self, state: TopologyState) -> bool:
        return state.source is not None and state.report is not None


class BrokenFixedCountAuthority(SuiteTopologyFlow):
    """Known-bad path that lets a literal count replace the suite map."""

    name = "BrokenFixedCountAuthority"

    def _review(self, state: TopologyState) -> TopologyState:
        reviewed = super()._review(state)
        if reviewed.report is None or reviewed.source is None or not reviewed.source.fixed_count_assertions:
            return reviewed
        assertion = reviewed.source.fixed_count_assertions[0]
        findings = tuple(
            finding
            for finding in reviewed.report.findings
            if not finding.code.startswith("fixed_count_")
        )
        report = replace(
            reviewed.report,
            status="pass" if not findings else "blocked",
            reported_count=assertion.literal_count,
            findings=findings,
        )
        return replace(
            reviewed,
            report=report,
            topology_status=TOPOLOGY_CURRENT if report.status == "pass" else TOPOLOGY_BLOCKED,
        )


class BrokenStaleTopologyReuse(SuiteTopologyFlow):
    """Known-bad path that reuses an old report after any watched input changes."""

    name = "BrokenStaleTopologyReuse"

    def _load_source(self, source: SuiteTopologySource, state: TopologyState) -> TopologyState:
        loaded = super()._load_source(source, state)
        if state.report is not None and state.topology_status == TOPOLOGY_CURRENT:
            return replace(
                loaded,
                reviewed_input_fingerprint=state.reviewed_input_fingerprint,
                topology_status=TOPOLOGY_CURRENT,
                report=state.report,
            )
        return loaded

    def _claimable(self, state: TopologyState) -> bool:
        return state.report is not None and state.topology_status == TOPOLOGY_CURRENT


class BrokenCollapsedEvidenceDomains(SuiteTopologyFlow):
    """Known-bad path that compresses independent evidence into one green bit."""

    name = "BrokenCollapsedEvidenceDomains"

    def _review(self, state: TopologyState) -> TopologyState:
        reviewed = super()._review(state)
        return replace(
            reviewed,
            evidence_domains=(EvidenceDomain("source_to_release", "pass", _fingerprint("collapsed")),),
        )


class BrokenTopologyOverclaim(SuiteTopologyFlow):
    """Known-bad path that promotes a topology claim into release readiness."""

    name = "BrokenTopologyOverclaim"

    def _claim(self, state: TopologyState) -> TopologyState:
        claimed = super()._claim(state)
        if claimed.topology_claim == "accepted":
            return replace(claimed, release_readiness="accepted")
        return claimed


def accepted_topology_matches_current_source(
    state: TopologyState,
    trace,
) -> InvariantResult:
    del trace
    if state.topology_claim != "accepted":
        return InvariantResult.pass_()
    if state.source is None or state.report is None:
        return InvariantResult.fail("accepted topology has no frozen source and report")
    expected = derive_topology_report(state.source)
    if expected.status != "pass" or expected.findings:
        return InvariantResult.fail("accepted topology contains exact current topology findings")
    if state.report != expected:
        return InvariantResult.fail("accepted topology differs from the current suite-map and route-registry derivation")
    if state.report.reported_count != len({member.member_id for member in state.source.canonical_members}):
        return InvariantResult.fail("accepted reported count is not dynamically derived from canonical members")
    return InvariantResult.pass_()


def accepted_topology_evidence_is_current(
    state: TopologyState,
    trace,
) -> InvariantResult:
    del trace
    if state.topology_claim != "accepted":
        return InvariantResult.pass_()
    if (
        state.topology_status != TOPOLOGY_CURRENT
        or state.reviewed_input_fingerprint != state.input_fingerprint
        or state.report is None
        or state.report.input_fingerprint != state.input_fingerprint
    ):
        return InvariantResult.fail("accepted topology reused stale map, skill, contract, script, test, model, or runner evidence")
    return InvariantResult.pass_()


def evidence_domains_are_not_collapsed(
    state: TopologyState,
    trace,
) -> InvariantResult:
    del trace
    if state.source is None:
        return InvariantResult.pass_()
    domain_ids = tuple(domain.domain_id for domain in state.evidence_domains)
    if len(domain_ids) != len(set(domain_ids)) or set(domain_ids) != set(EVIDENCE_DOMAIN_IDS):
        return InvariantResult.fail("source, projections, installation, package, Git, tag, and release evidence were collapsed or omitted")
    return InvariantResult.pass_()


def topology_never_becomes_release_readiness(
    state: TopologyState,
    trace,
) -> InvariantResult:
    del trace
    if state.release_readiness != "not_owned":
        return InvariantResult.fail("suite topology was promoted beyond its owner into release readiness")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "accepted_topology_matches_current_source",
        "Accepted topology is exactly derived from the current suite map, route registry, discovery, and required files.",
        accepted_topology_matches_current_source,
    ),
    Invariant(
        "accepted_topology_evidence_is_current",
        "Every watched suite input change invalidates the prior topology review.",
        accepted_topology_evidence_is_current,
    ),
    Invariant(
        "evidence_domains_are_not_collapsed",
        "Topology, projections, installation, package, Git, tag, and release retain independent evidence identities.",
        evidence_domains_are_not_collapsed,
    ),
    Invariant(
        "topology_never_becomes_release_readiness",
        "A current topology claim cannot directly authorize release.",
        topology_never_becomes_release_readiness,
    ),
)


def initial_state() -> TopologyState:
    return TopologyState()


def build_correct_workflow() -> Workflow:
    return Workflow((SuiteTopologyFlow(),), name="dynamic_skill_suite_topology")


def build_broken_member_findings_workflow() -> Workflow:
    return Workflow((BrokenAcceptMemberFindings(),), name="broken_accept_member_findings")


def build_broken_fixed_count_workflow() -> Workflow:
    return Workflow((BrokenFixedCountAuthority(),), name="broken_fixed_count_authority")


def build_broken_stale_reuse_workflow() -> Workflow:
    return Workflow((BrokenStaleTopologyReuse(),), name="broken_stale_topology_reuse")


def build_broken_collapsed_domains_workflow() -> Workflow:
    return Workflow((BrokenCollapsedEvidenceDomains(),), name="broken_collapsed_evidence_domains")


def build_broken_topology_overclaim_workflow() -> Workflow:
    return Workflow((BrokenTopologyOverclaim(),), name="broken_topology_overclaim")


__all__ = [
    "CLAIM_BOUNDARY",
    "DOWNSTREAM_EVIDENCE_DOMAIN_IDS",
    "EVIDENCE_DOMAIN_IDS",
    "INVARIANTS",
    "KERNEL_ROLE",
    "PUBLIC_ENTRY_POLICY",
    "PUBLIC_ROUTE_ROLE",
    "SATELLITE_ROLE",
    "TOPOLOGY_BLOCKED",
    "TOPOLOGY_CURRENT",
    "TOPOLOGY_NOT_RUN",
    "TOPOLOGY_STALE",
    "CanonicalMember",
    "DiscoveredMember",
    "EvidenceDomain",
    "FixedCountAssertion",
    "RouteRegistryEntry",
    "SuiteTopologySource",
    "TopologyAction",
    "TopologyInputIdentity",
    "TopologyOutput",
    "TopologyReport",
    "TopologyState",
    "build_broken_collapsed_domains_workflow",
    "build_broken_fixed_count_workflow",
    "build_broken_member_findings_workflow",
    "build_broken_stale_reuse_workflow",
    "build_broken_topology_overclaim_workflow",
    "build_correct_workflow",
    "derive_topology_report",
    "initial_state",
    "source_fingerprint",
]
