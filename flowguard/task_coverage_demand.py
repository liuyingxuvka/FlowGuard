"""Task-derived coverage demand for model-first FlowGuard work.

The compiler owns the minimum denominator. Callers may add coverage but cannot
remove built-in rows or declare them satisfied during compilation.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .evidence_receipts import fingerprint_value
from .route_topology import RETIRED_PUBLIC_ROUTE_IDS, public_owner_descriptor


COVERAGE_DEMAND_SCHEMA_VERSION = "flowguard.task_coverage_demand.v1"

COVERAGE_DISPOSITION_SATISFIED = "satisfied"
COVERAGE_DISPOSITION_NOT_TRIGGERED = "not_triggered"
COVERAGE_DISPOSITION_UNRESOLVED = "unresolved"
COVERAGE_DISPOSITION_BLOCKED = "blocked"
COVERAGE_DISPOSITIONS = frozenset(
    {
        COVERAGE_DISPOSITION_SATISFIED,
        COVERAGE_DISPOSITION_NOT_TRIGGERED,
        COVERAGE_DISPOSITION_UNRESOLVED,
        COVERAGE_DISPOSITION_BLOCKED,
    }
)

COVERAGE_TIER_ORDINARY = "ordinary"
COVERAGE_TIER_STANDARD = "standard"
COVERAGE_TIER_DEEP = "deep"
COVERAGE_TIER_RELEASE = "release"
COVERAGE_TIERS = (
    COVERAGE_TIER_ORDINARY,
    COVERAGE_TIER_STANDARD,
    COVERAGE_TIER_DEEP,
    COVERAGE_TIER_RELEASE,
)
_TIER_RANK = {value: index for index, value in enumerate(COVERAGE_TIERS)}

MODEL_MESH_TOPOLOGY_TRIGGERS = frozenset(
    {
        "affected_related_models",
        "parent_child_change",
        "stale_child_evidence",
        "oversized_model",
        "cross_model_refinement",
        "whole_flow_claim",
    }
)

TASK_FACT_SOURCE_REQUEST = "request"
TASK_FACT_SOURCE_CURRENT_MODEL = "current_model"
TASK_FACT_SOURCE_PUBLIC_SURFACE = "public_surface"
TASK_FACT_SOURCE_LIFECYCLE = "lifecycle"
TASK_FACT_SOURCE_PLANES = frozenset(
    {
        TASK_FACT_SOURCE_REQUEST,
        TASK_FACT_SOURCE_CURRENT_MODEL,
        TASK_FACT_SOURCE_PUBLIC_SURFACE,
        TASK_FACT_SOURCE_LIFECYCLE,
    }
)

TASK_FACT_SOURCE_STATUS_COMPLETE = "complete"
TASK_FACT_SOURCE_STATUS_NOT_APPLICABLE = "not_applicable"
TASK_FACT_SOURCE_STATUS_BLOCKED = "blocked"
TASK_FACT_SOURCE_STATUSES = frozenset(
    {
        TASK_FACT_SOURCE_STATUS_COMPLETE,
        TASK_FACT_SOURCE_STATUS_NOT_APPLICABLE,
        TASK_FACT_SOURCE_STATUS_BLOCKED,
    }
)

TASK_FACT_DISPOSITION_DECLARED = "declared"
TASK_FACT_DISPOSITION_UNKNOWN = "unknown"
TASK_FACT_DISPOSITION_OMITTED = "omitted"
TASK_FACT_DISPOSITION_SCOPED_OUT = "scoped_out"
TASK_FACT_DISPOSITION_CONTRADICTORY = "contradictory"
TASK_FACT_DISPOSITION_UNMAPPED = "unmapped"
TASK_FACT_DISPOSITIONS = frozenset(
    {
        TASK_FACT_DISPOSITION_DECLARED,
        TASK_FACT_DISPOSITION_UNKNOWN,
        TASK_FACT_DISPOSITION_OMITTED,
        TASK_FACT_DISPOSITION_SCOPED_OUT,
        TASK_FACT_DISPOSITION_CONTRADICTORY,
        TASK_FACT_DISPOSITION_UNMAPPED,
    }
)
_UNRESOLVED_TASK_FACT_DISPOSITIONS = frozenset(
    {
        TASK_FACT_DISPOSITION_UNKNOWN,
        TASK_FACT_DISPOSITION_OMITTED,
        TASK_FACT_DISPOSITION_CONTRADICTORY,
        TASK_FACT_DISPOSITION_UNMAPPED,
    }
)


def _tuple(values: Sequence[str] | str | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        values = (values,)
    return tuple(sorted({str(value) for value in values if str(value)}))


@dataclass(frozen=True)
class TaskFactObservation:
    """One provenance-bound member of the task-understanding denominator."""

    fact_id: str
    source_plane: str
    disposition: str = TASK_FACT_DISPOSITION_DECLARED
    owner_route: str = ""
    reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "fact_id", str(self.fact_id))
        object.__setattr__(self, "source_plane", str(self.source_plane))
        object.__setattr__(self, "disposition", str(self.disposition))
        object.__setattr__(self, "owner_route", str(self.owner_route))
        object.__setattr__(self, "reason", str(self.reason))
        if not self.fact_id:
            raise ValueError("task fact observations require a fact id")
        if self.source_plane not in TASK_FACT_SOURCE_PLANES:
            raise ValueError(f"unknown task fact source plane: {self.source_plane}")
        if self.disposition not in TASK_FACT_DISPOSITIONS:
            raise ValueError(f"unknown task fact disposition: {self.disposition}")
        if self.owner_route in RETIRED_PUBLIC_ROUTE_IDS:
            raise ValueError(f"retired public route identity: {self.owner_route}")

    @classmethod
    def from_value(cls, value: TaskFactObservation | Mapping[str, Any]) -> TaskFactObservation:
        if isinstance(value, cls):
            return value
        if not isinstance(value, Mapping):
            raise TypeError("fact observations must be TaskFactObservation values or mappings")
        return cls(**dict(value))

    def to_dict(self) -> dict[str, str]:
        return {
            "fact_id": self.fact_id,
            "source_plane": self.source_plane,
            "disposition": self.disposition,
            "owner_route": self.owner_route,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class TaskFactSourceSnapshot:
    """One independently inspected task-fact plane and its current identity."""

    source_plane: str
    source_ref: str
    source_fingerprint: str
    status: str = TASK_FACT_SOURCE_STATUS_COMPLETE
    observations: tuple[TaskFactObservation, ...] = ()
    reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_plane", str(self.source_plane))
        object.__setattr__(self, "source_ref", str(self.source_ref))
        object.__setattr__(self, "source_fingerprint", str(self.source_fingerprint))
        object.__setattr__(self, "status", str(self.status))
        object.__setattr__(self, "reason", str(self.reason))
        if self.source_plane not in TASK_FACT_SOURCE_PLANES:
            raise ValueError(f"unknown task fact source plane: {self.source_plane}")
        if not self.source_ref:
            raise ValueError("task fact source snapshots require a source reference")
        if not self.source_fingerprint.startswith("sha256:"):
            raise ValueError("task fact source snapshots require a sha256 fingerprint")
        if self.status not in TASK_FACT_SOURCE_STATUSES:
            raise ValueError(f"unknown task fact source status: {self.status}")
        observations = tuple(
            sorted(
                (TaskFactObservation.from_value(value) for value in self.observations),
                key=lambda value: (value.fact_id, value.disposition),
            )
        )
        if any(value.source_plane != self.source_plane for value in observations):
            raise ValueError("task fact observations must match their source snapshot plane")
        if len({value.fact_id for value in observations}) != len(observations):
            raise ValueError("source snapshot observations must be unique by fact id")
        if self.status != TASK_FACT_SOURCE_STATUS_COMPLETE and observations:
            raise ValueError("non-complete source snapshots cannot carry observations")
        if self.status != TASK_FACT_SOURCE_STATUS_COMPLETE and not self.reason:
            raise ValueError("non-complete source snapshots require a reason")
        object.__setattr__(self, "observations", observations)

    @classmethod
    def from_value(
        cls, value: TaskFactSourceSnapshot | Mapping[str, Any]
    ) -> TaskFactSourceSnapshot:
        if isinstance(value, cls):
            return value
        if not isinstance(value, Mapping):
            raise TypeError(
                "source snapshots must be TaskFactSourceSnapshot values or mappings"
            )
        return cls(**dict(value))

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_plane": self.source_plane,
            "source_ref": self.source_ref,
            "source_fingerprint": self.source_fingerprint,
            "status": self.status,
            "observations": [value.to_dict() for value in self.observations],
            "reason": self.reason,
        }


@dataclass(frozen=True)
class TaskFacts:
    """Frozen facts used to derive coverage; target-product roles stay external."""

    task_id: str
    task_purpose: str
    requested_outcome_ids: tuple[str, ...] = ()
    affected_surface_ids: tuple[str, ...] = ()
    change_kinds: tuple[str, ...] = ()
    risk_signal_ids: tuple[str, ...] = ()
    related_model_ids: tuple[str, ...] = ()
    topology_signal_ids: tuple[str, ...] = ()
    caller_requested_owner_ids: tuple[str, ...] = ()
    fact_observations: tuple[TaskFactObservation, ...] = ()
    source_snapshots: tuple[TaskFactSourceSnapshot, ...] = ()
    implementation_requested: bool = False
    release_requested: bool = False
    read_only: bool = False
    non_trivial: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict, compare=False)
    schema_version: str = COVERAGE_DEMAND_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not str(self.task_id):
            raise ValueError("task_id is required")
        if self.schema_version != COVERAGE_DEMAND_SCHEMA_VERSION:
            raise ValueError(f"task facts must use {COVERAGE_DEMAND_SCHEMA_VERSION}")
        object.__setattr__(self, "task_id", str(self.task_id))
        object.__setattr__(self, "task_purpose", str(self.task_purpose))
        for name in (
            "requested_outcome_ids",
            "affected_surface_ids",
            "change_kinds",
            "risk_signal_ids",
            "related_model_ids",
            "topology_signal_ids",
            "caller_requested_owner_ids",
        ):
            object.__setattr__(self, name, _tuple(getattr(self, name)))
        source_snapshots = tuple(
            sorted(
                (
                    TaskFactSourceSnapshot.from_value(value)
                    for value in self.source_snapshots
                ),
                key=lambda value: value.source_plane,
            )
        )
        if len({value.source_plane for value in source_snapshots}) != len(
            source_snapshots
        ):
            raise ValueError("task fact source snapshots must be unique by source plane")
        object.__setattr__(self, "source_snapshots", source_snapshots)
        observations = tuple(
            sorted(
                (
                    TaskFactObservation.from_value(value)
                    for value in (
                        tuple(self.fact_observations)
                        + tuple(
                            observation
                            for snapshot in source_snapshots
                            for observation in snapshot.observations
                        )
                    )
                ),
                key=lambda value: (value.fact_id, value.source_plane, value.disposition),
            )
        )
        observation_keys = [(value.fact_id, value.source_plane) for value in observations]
        if len(observation_keys) != len(set(observation_keys)):
            raise ValueError("task fact observations must be unique by fact and source plane")
        object.__setattr__(self, "fact_observations", observations)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "task_purpose": self.task_purpose,
            "requested_outcome_ids": list(self.requested_outcome_ids),
            "affected_surface_ids": list(self.affected_surface_ids),
            "change_kinds": list(self.change_kinds),
            "risk_signal_ids": list(self.risk_signal_ids),
            "related_model_ids": list(self.related_model_ids),
            "topology_signal_ids": list(self.topology_signal_ids),
            "caller_requested_owner_ids": list(self.caller_requested_owner_ids),
            "fact_observations": [value.to_dict() for value in self.fact_observations],
            "source_snapshots": [value.to_dict() for value in self.source_snapshots],
            "implementation_requested": self.implementation_requested,
            "release_requested": self.release_requested,
            "read_only": self.read_only,
            "non_trivial": self.non_trivial,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class CoverageRule:
    rule_id: str
    owner_route: str
    coverage_ids: tuple[str, ...]
    reason: str
    minimum_tier: str = COVERAGE_TIER_ORDINARY
    always_for_non_trivial: bool = False
    implementation_trigger: bool = False
    release_trigger: bool = False
    change_kind_triggers: tuple[str, ...] = ()
    surface_prefix_triggers: tuple[str, ...] = ()
    risk_triggers: tuple[str, ...] = ()
    topology_triggers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.rule_id or not self.owner_route or not self.coverage_ids:
            raise ValueError("coverage rules require identity, owner, and coverage")
        if self.minimum_tier not in _TIER_RANK:
            raise ValueError(f"unknown coverage tier: {self.minimum_tier}")
        for name in (
            "coverage_ids",
            "change_kind_triggers",
            "surface_prefix_triggers",
            "risk_triggers",
            "topology_triggers",
        ):
            object.__setattr__(self, name, _tuple(getattr(self, name)))

    def matches(self, facts: TaskFacts) -> bool:
        return bool(
            (self.always_for_non_trivial and facts.non_trivial)
            or (self.implementation_trigger and facts.implementation_requested)
            or (self.release_trigger and facts.release_requested)
            or set(self.change_kind_triggers).intersection(facts.change_kinds)
            or set(self.risk_triggers).intersection(facts.risk_signal_ids)
            or set(self.topology_triggers).intersection(facts.topology_signal_ids)
            or any(
                surface.startswith(prefix)
                for surface in facts.affected_surface_ids
                for prefix in self.surface_prefix_triggers
            )
        )


@dataclass(frozen=True)
class CoverageDemandRow:
    demand_id: str
    rule_id: str
    owner_route: str
    coverage_ids: tuple[str, ...]
    triggered: bool
    disposition: str
    reason: str
    evidence_ids: tuple[str, ...] = ()
    evidence_fingerprints: tuple[str, ...] = ()
    blocker_codes: tuple[str, ...] = ()
    minimum_tier: str = COVERAGE_TIER_ORDINARY
    caller_added: bool = False

    def __post_init__(self) -> None:
        if self.disposition not in COVERAGE_DISPOSITIONS:
            raise ValueError(f"unknown coverage disposition: {self.disposition}")
        if self.minimum_tier not in _TIER_RANK:
            raise ValueError(f"unknown coverage tier: {self.minimum_tier}")
        if self.triggered and self.disposition == COVERAGE_DISPOSITION_NOT_TRIGGERED:
            raise ValueError("triggered coverage cannot be marked not_triggered")
        if not self.triggered and self.disposition != COVERAGE_DISPOSITION_NOT_TRIGGERED:
            raise ValueError("untriggered coverage must remain visibly not_triggered")
        if self.disposition == COVERAGE_DISPOSITION_SATISFIED and (
            not self.evidence_ids or not self.evidence_fingerprints
        ):
            raise ValueError("satisfied coverage requires evidence identity and fingerprint")
        if self.disposition == COVERAGE_DISPOSITION_BLOCKED and not self.blocker_codes:
            raise ValueError("blocked coverage requires blocker codes")
        for name in (
            "coverage_ids",
            "evidence_ids",
            "evidence_fingerprints",
            "blocker_codes",
        ):
            object.__setattr__(self, name, _tuple(getattr(self, name)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "demand_id": self.demand_id,
            "rule_id": self.rule_id,
            "owner_route": self.owner_route,
            "coverage_ids": list(self.coverage_ids),
            "triggered": self.triggered,
            "disposition": self.disposition,
            "reason": self.reason,
            "evidence_ids": list(self.evidence_ids),
            "evidence_fingerprints": list(self.evidence_fingerprints),
            "blocker_codes": list(self.blocker_codes),
            "minimum_tier": self.minimum_tier,
            "caller_added": self.caller_added,
        }


@dataclass(frozen=True)
class OwnerCoverageResolution:
    """The sole identity-bearing result returned by one demanded owner."""

    resolution_id: str
    task_id: str
    demand_id: str
    demand_fingerprint: str
    owner_route: str
    disposition: str
    obligation_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...] = ()
    evidence_fingerprints: tuple[str, ...] = ()
    blocker_codes: tuple[str, ...] = ()
    scoped: bool = False
    schema_version: str = COVERAGE_DEMAND_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "resolution_id",
            "task_id",
            "demand_id",
            "demand_fingerprint",
            "owner_route",
            "disposition",
        ):
            object.__setattr__(self, name, str(getattr(self, name)))
        if not all(
            (
                self.resolution_id,
                self.task_id,
                self.demand_id,
                self.owner_route,
            )
        ):
            raise ValueError("owner resolution requires exact identity")
        if not self.demand_fingerprint.startswith("sha256:"):
            raise ValueError("owner resolution requires an exact demand fingerprint")
        if self.owner_route in RETIRED_PUBLIC_ROUTE_IDS:
            raise ValueError(f"retired public route identity: {self.owner_route}")
        if self.disposition not in {
            COVERAGE_DISPOSITION_SATISFIED,
            COVERAGE_DISPOSITION_BLOCKED,
        }:
            raise ValueError("owner resolution must be satisfied or blocked")
        for name in (
            "obligation_ids",
            "evidence_ids",
            "evidence_fingerprints",
            "blocker_codes",
        ):
            object.__setattr__(self, name, _tuple(getattr(self, name)))
        object.__setattr__(self, "scoped", bool(self.scoped))
        if not self.obligation_ids:
            raise ValueError("owner resolution requires covered obligations")
        if self.disposition == COVERAGE_DISPOSITION_SATISFIED:
            if not self.evidence_ids or not self.evidence_fingerprints:
                raise ValueError("satisfied owner resolution requires evidence material")
            if not all(value.startswith("sha256:") for value in self.evidence_fingerprints):
                raise ValueError("owner resolution evidence fingerprints must be sha256 values")
        if self.disposition == COVERAGE_DISPOSITION_BLOCKED and not self.blocker_codes:
            raise ValueError("blocked owner resolution requires blocker codes")

    @property
    def resolution_fingerprint(self) -> str:
        return fingerprint_value(self.to_dict())

    @property
    def fingerprint(self) -> str:
        return self.resolution_fingerprint

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "resolution_id": self.resolution_id,
            "task_id": self.task_id,
            "demand_id": self.demand_id,
            "demand_fingerprint": self.demand_fingerprint,
            "owner_route": self.owner_route,
            "disposition": self.disposition,
            "obligation_ids": list(self.obligation_ids),
            "evidence_ids": list(self.evidence_ids),
            "evidence_fingerprints": list(self.evidence_fingerprints),
            "blocker_codes": list(self.blocker_codes),
            "scoped": self.scoped,
        }


@dataclass(frozen=True)
class TaskCoverageDemand:
    demand_id: str
    task_id: str
    task_fingerprint: str
    presentation_tier: str
    rows: tuple[CoverageDemandRow, ...]
    fact_observations: tuple[TaskFactObservation, ...] = ()
    source_snapshots: tuple[TaskFactSourceSnapshot, ...] = ()
    fact_diagnostic_codes: tuple[str, ...] = ()
    resolution_basis_fingerprint: str = ""
    compiler_version: str = COVERAGE_DEMAND_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.demand_id or not self.task_id or not self.task_fingerprint:
            raise ValueError("coverage demand requires exact identity")
        if self.presentation_tier not in _TIER_RANK:
            raise ValueError(f"unknown coverage tier: {self.presentation_tier}")
        rows = tuple(self.rows)
        ids = [row.demand_id for row in rows]
        if len(ids) != len(set(ids)):
            raise ValueError("coverage demand row identities must be unique")
        object.__setattr__(self, "rows", rows)
        object.__setattr__(
            self,
            "fact_observations",
            tuple(TaskFactObservation.from_value(value) for value in self.fact_observations),
        )
        object.__setattr__(
            self,
            "source_snapshots",
            tuple(
                TaskFactSourceSnapshot.from_value(value)
                for value in self.source_snapshots
            ),
        )
        object.__setattr__(self, "fact_diagnostic_codes", _tuple(self.fact_diagnostic_codes))
        object.__setattr__(
            self, "resolution_basis_fingerprint", str(self.resolution_basis_fingerprint)
        )
        if self.resolution_basis_fingerprint and not self.resolution_basis_fingerprint.startswith(
            "sha256:"
        ):
            raise ValueError("resolution basis fingerprint must be a sha256 value")

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict())

    @property
    def required_owner_ids(self) -> tuple[str, ...]:
        return _tuple(row.owner_route for row in self.rows if row.triggered)

    @property
    def unresolved_owner_ids(self) -> tuple[str, ...]:
        return _tuple(
            row.owner_route
            for row in self.rows
            if row.triggered and row.disposition == COVERAGE_DISPOSITION_UNRESOLVED
        )

    @property
    def blocked_owner_ids(self) -> tuple[str, ...]:
        return _tuple(
            row.owner_route
            for row in self.rows
            if row.triggered and row.disposition == COVERAGE_DISPOSITION_BLOCKED
        )

    @property
    def closed(self) -> bool:
        return all(
            not row.triggered or row.disposition == COVERAGE_DISPOSITION_SATISFIED
            for row in self.rows
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "compiler_version": self.compiler_version,
            "demand_id": self.demand_id,
            "task_id": self.task_id,
            "task_fingerprint": self.task_fingerprint,
            "presentation_tier": self.presentation_tier,
            "rows": [row.to_dict() for row in self.rows],
            "fact_observations": [value.to_dict() for value in self.fact_observations],
            "source_snapshots": [value.to_dict() for value in self.source_snapshots],
            "fact_diagnostic_codes": list(self.fact_diagnostic_codes),
            "resolution_basis_fingerprint": self.resolution_basis_fingerprint,
        }


def _coverage_owner(route_id: str) -> str:
    return public_owner_descriptor(route_id).coverage_owner_id


def _default_rules() -> tuple[CoverageRule, ...]:
    return (
        CoverageRule("existing-model-owner", _coverage_owner("existing_model_preflight"), ("existing-model-owner",), "reuse and ownership must be grounded", always_for_non_trivial=True),
        CoverageRule("maturation-owner", _coverage_owner("model_first_function_flow"), ("task-model-maturation",), "non-trivial work requires an explicit maturity decision", always_for_non_trivial=True),
        CoverageRule("process-owner", _coverage_owner("development_process_flow"), ("implementation-admission",), "implementation and release require a separate admission owner", implementation_trigger=True, release_trigger=True, minimum_tier=COVERAGE_TIER_STANDARD),
        CoverageRule("behavior-owner", _coverage_owner("behavior_commitment_ledger"), ("external-behavior-ownership",), "external behavior needs one primary owner", change_kind_triggers=("external_behavior", "public_api", "command", "prompt", "skill"), minimum_tier=COVERAGE_TIER_STANDARD),
        CoverageRule("ui-owner", _coverage_owner("ui_flow_structure"), ("ui-journey", "ui-operability"), "affected UI needs journey and operability coverage", change_kind_triggers=("ui",), surface_prefix_triggers=("ui:", "screen:", "view:"), minimum_tier=COVERAGE_TIER_DEEP),
        CoverageRule("field-owner", _coverage_owner("field_lifecycle_mesh"), ("field-lifecycle",), "persisted or renamed fields need lifecycle coverage", change_kind_triggers=("field_add", "field_remove", "field_rename", "field_migration", "persistence"), minimum_tier=COVERAGE_TIER_DEEP),
        CoverageRule("mesh-owner", _coverage_owner("model_mesh_maintenance"), ("affected-model-topology",), "affected model relationships need mesh governance", topology_triggers=tuple(MODEL_MESH_TOPOLOGY_TRIGGERS), minimum_tier=COVERAGE_TIER_DEEP),
        CoverageRule("test-owner", _coverage_owner("model_test_alignment"), ("model-test-alignment",), "changed behavior needs explicit evidence ownership", implementation_trigger=True, change_kind_triggers=("behavior", "test", "contract", "public_api"), minimum_tier=COVERAGE_TIER_STANDARD),
        CoverageRule("release-owner", _coverage_owner("development_process_flow"), ("release-identity", "distribution-parity", "full-validation"), "release needs frozen validation and distribution evidence", release_trigger=True, minimum_tier=COVERAGE_TIER_RELEASE),
    )


DEFAULT_COVERAGE_RULES = _default_rules()


def compile_task_coverage_demand(
    facts: TaskFacts,
    *,
    rules: Sequence[CoverageRule] = DEFAULT_COVERAGE_RULES,
) -> TaskCoverageDemand:
    """Compile deterministic built-in minimum plus monotonic caller additions."""

    if not isinstance(facts, TaskFacts):
        raise TypeError("facts must be TaskFacts")
    rows: list[CoverageDemandRow] = []
    fact_diagnostics: list[str] = []
    triggered_tiers = [COVERAGE_TIER_ORDINARY]
    built_in_owners: set[str] = set()
    for rule in sorted(rules, key=lambda item: item.rule_id):
        if rule.owner_route in RETIRED_PUBLIC_ROUTE_IDS:
            raise ValueError(f"retired public route identity: {rule.owner_route}")
        triggered = rule.matches(facts)
        built_in_owners.add(rule.owner_route)
        if triggered:
            triggered_tiers.append(rule.minimum_tier)
        rows.append(
            CoverageDemandRow(
                demand_id=f"demand:{rule.rule_id}",
                rule_id=rule.rule_id,
                owner_route=rule.owner_route,
                coverage_ids=rule.coverage_ids,
                triggered=triggered,
                disposition=(COVERAGE_DISPOSITION_UNRESOLVED if triggered else COVERAGE_DISPOSITION_NOT_TRIGGERED),
                reason=rule.reason if triggered else f"not triggered by task facts: {rule.reason}",
                minimum_tier=rule.minimum_tier,
            )
        )
    for owner in facts.caller_requested_owner_ids:
        if owner in RETIRED_PUBLIC_ROUTE_IDS:
            raise ValueError(f"retired public route identity: {owner}")
        if owner in built_in_owners:
            continue
        rows.append(
            CoverageDemandRow(
                demand_id=f"demand:caller:{owner}",
                rule_id=f"caller:{owner}",
                owner_route=owner,
                coverage_ids=(f"caller-coverage:{owner}",),
                triggered=True,
                disposition=COVERAGE_DISPOSITION_UNRESOLVED,
                reason="caller requested additional coverage",
                caller_added=True,
            )
        )
    coverage_trigger_count = sum(1 for row in rows if row.triggered)
    source_snapshots_by_plane = {
        snapshot.source_plane: snapshot for snapshot in facts.source_snapshots
    }
    if facts.non_trivial:
        for source_plane in sorted(TASK_FACT_SOURCE_PLANES):
            snapshot = source_snapshots_by_plane.get(source_plane)
            if snapshot is None:
                diagnostic_code = f"task_fact_source_not_observed:{source_plane}"
                reason = f"{source_plane} task-fact source was not independently inspected"
            elif snapshot.status == TASK_FACT_SOURCE_STATUS_BLOCKED:
                diagnostic_code = f"task_fact_source_blocked:{source_plane}"
                reason = snapshot.reason
            else:
                continue
            fact_diagnostics.append(diagnostic_code)
            rows.append(
                CoverageDemandRow(
                    demand_id=f"demand:task-fact-source:{source_plane}",
                    rule_id=f"task-fact-source:{source_plane}",
                    owner_route="unresolved_task_fact",
                    coverage_ids=(f"task-fact-source:{source_plane}",),
                    triggered=True,
                    disposition=COVERAGE_DISPOSITION_BLOCKED,
                    reason=reason,
                    blocker_codes=(diagnostic_code,),
                )
            )
    for observation in facts.fact_observations:
        if observation.disposition not in _UNRESOLVED_TASK_FACT_DISPOSITIONS:
            continue
        diagnostic_code = f"task_fact_{observation.disposition}:{observation.fact_id}"
        fact_diagnostics.append(diagnostic_code)
        owner_route = observation.owner_route
        blocker_codes: tuple[str, ...] = ()
        disposition = COVERAGE_DISPOSITION_UNRESOLVED
        if observation.disposition == TASK_FACT_DISPOSITION_UNMAPPED or not owner_route:
            owner_route = "unresolved_task_fact"
            disposition = COVERAGE_DISPOSITION_BLOCKED
            blocker_codes = (f"unresolved_fact_owner:{observation.fact_id}",)
        rows.append(
            CoverageDemandRow(
                demand_id=(
                    f"demand:task-fact:{observation.source_plane}:"
                    f"{observation.fact_id}"
                ),
                rule_id=f"task-fact:{observation.disposition}",
                owner_route=owner_route,
                coverage_ids=(f"task-fact:{observation.fact_id}",),
                triggered=True,
                disposition=disposition,
                reason=(
                    observation.reason
                    or f"{observation.source_plane} fact is {observation.disposition}"
                ),
                blocker_codes=blocker_codes,
                minimum_tier=COVERAGE_TIER_STANDARD,
            )
        )
    if facts.release_requested:
        triggered_tiers.append(COVERAGE_TIER_RELEASE)
    elif facts.risk_signal_ids or facts.related_model_ids or set(facts.topology_signal_ids) & MODEL_MESH_TOPOLOGY_TRIGGERS:
        triggered_tiers.append(COVERAGE_TIER_DEEP)
    elif facts.implementation_requested or coverage_trigger_count > 2:
        triggered_tiers.append(COVERAGE_TIER_STANDARD)
    tier = max(triggered_tiers, key=lambda value: _TIER_RANK[value])
    task_fingerprint = facts.fingerprint
    demand_id = f"task-coverage:{facts.task_id}:{task_fingerprint.split(':', 1)[-1][:16]}"
    return TaskCoverageDemand(
        demand_id,
        facts.task_id,
        task_fingerprint,
        tier,
        tuple(rows),
        fact_observations=facts.fact_observations,
        source_snapshots=facts.source_snapshots,
        fact_diagnostic_codes=tuple(fact_diagnostics),
    )


def resolve_coverage_demand_row(
    demand: TaskCoverageDemand,
    demand_id: str,
    disposition: str,
    *,
    reason: str,
    evidence_ids: Sequence[str] = (),
    evidence_fingerprints: Sequence[str] = (),
    blocker_codes: Sequence[str] = (),
) -> TaskCoverageDemand:
    """Return a new demand with exactly one compiler row independently resolved."""

    if disposition not in {COVERAGE_DISPOSITION_SATISFIED, COVERAGE_DISPOSITION_BLOCKED}:
        raise ValueError("triggered demand rows resolve only to satisfied or blocked")
    changed = False
    rows: list[CoverageDemandRow] = []
    for row in demand.rows:
        if row.demand_id != demand_id:
            rows.append(row)
            continue
        if not row.triggered:
            raise ValueError("not-triggered compiler rows cannot be caller-resolved")
        if (
            disposition == COVERAGE_DISPOSITION_SATISFIED
            and row.owner_route == "unresolved_task_fact"
        ):
            raise ValueError(
                "unresolved task-fact rows require refreshed source facts and demand recompilation"
            )
        rows.append(
            replace(
                row,
                disposition=disposition,
                reason=str(reason),
                evidence_ids=_tuple(evidence_ids),
                evidence_fingerprints=_tuple(evidence_fingerprints),
                blocker_codes=_tuple(blocker_codes),
            )
        )
        changed = True
    if not changed:
        raise ValueError(f"unknown coverage demand row: {demand_id}")
    return replace(demand, rows=tuple(rows))


def project_owner_resolution_to_demand(
    demand: TaskCoverageDemand,
    resolution: OwnerCoverageResolution,
) -> TaskCoverageDemand:
    """Project one canonical owner result onto every row owned by that route."""

    if not isinstance(demand, TaskCoverageDemand):
        raise TypeError("demand must be TaskCoverageDemand")
    if not isinstance(resolution, OwnerCoverageResolution):
        raise TypeError("resolution must be OwnerCoverageResolution")
    if resolution.task_id != demand.task_id:
        raise ValueError("owner resolution task identity is stale")
    if resolution.demand_id != demand.demand_id:
        raise ValueError("owner resolution demand identity is stale")
    basis_fingerprint = demand.resolution_basis_fingerprint or demand.fingerprint
    if resolution.demand_fingerprint != basis_fingerprint:
        raise ValueError("owner resolution demand fingerprint is stale")
    owned_rows = tuple(
        row
        for row in demand.rows
        if row.triggered and row.owner_route == resolution.owner_route
    )
    if not owned_rows:
        raise ValueError(f"owner has no triggered demand: {resolution.owner_route}")
    required_obligations = {
        coverage_id for row in owned_rows for coverage_id in row.coverage_ids
    }
    if not required_obligations.issubset(set(resolution.obligation_ids)):
        raise ValueError("owner resolution does not cover every demanded obligation")
    projected = replace(demand, resolution_basis_fingerprint=basis_fingerprint)
    for row in owned_rows:
        projected = resolve_coverage_demand_row(
            projected,
            row.demand_id,
            resolution.disposition,
            reason=f"canonical owner resolution {resolution.resolution_id}",
            evidence_ids=resolution.evidence_ids,
            evidence_fingerprints=resolution.evidence_fingerprints,
            blocker_codes=resolution.blocker_codes,
        )
    return projected


__all__ = [
    "COVERAGE_DEMAND_SCHEMA_VERSION",
    "COVERAGE_DISPOSITION_BLOCKED",
    "COVERAGE_DISPOSITION_NOT_TRIGGERED",
    "COVERAGE_DISPOSITION_SATISFIED",
    "COVERAGE_DISPOSITION_UNRESOLVED",
    "COVERAGE_TIER_DEEP",
    "COVERAGE_TIER_ORDINARY",
    "COVERAGE_TIER_RELEASE",
    "COVERAGE_TIER_STANDARD",
    "CoverageDemandRow",
    "CoverageRule",
    "DEFAULT_COVERAGE_RULES",
    "MODEL_MESH_TOPOLOGY_TRIGGERS",
    "OwnerCoverageResolution",
    "TASK_FACT_DISPOSITION_CONTRADICTORY",
    "TASK_FACT_DISPOSITION_DECLARED",
    "TASK_FACT_DISPOSITION_OMITTED",
    "TASK_FACT_DISPOSITION_SCOPED_OUT",
    "TASK_FACT_DISPOSITION_UNKNOWN",
    "TASK_FACT_DISPOSITION_UNMAPPED",
    "TASK_FACT_DISPOSITIONS",
    "TASK_FACT_SOURCE_CURRENT_MODEL",
    "TASK_FACT_SOURCE_LIFECYCLE",
    "TASK_FACT_SOURCE_PLANES",
    "TASK_FACT_SOURCE_PUBLIC_SURFACE",
    "TASK_FACT_SOURCE_REQUEST",
    "TASK_FACT_SOURCE_STATUS_BLOCKED",
    "TASK_FACT_SOURCE_STATUS_COMPLETE",
    "TASK_FACT_SOURCE_STATUS_NOT_APPLICABLE",
    "TASK_FACT_SOURCE_STATUSES",
    "TaskFactSourceSnapshot",
    "TaskCoverageDemand",
    "TaskFactObservation",
    "TaskFacts",
    "compile_task_coverage_demand",
    "project_owner_resolution_to_demand",
    "resolve_coverage_demand_row",
]
