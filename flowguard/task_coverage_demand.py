"""Task-derived coverage demand for model-first FlowGuard work.

The compiler owns the minimum denominator. Callers may add coverage but cannot
remove built-in rows or declare them satisfied during compilation.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .evidence_receipts import fingerprint_value


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


def _tuple(values: Sequence[str] | str | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        values = (values,)
    return tuple(sorted({str(value) for value in values if str(value)}))


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
class TaskCoverageDemand:
    demand_id: str
    task_id: str
    task_fingerprint: str
    presentation_tier: str
    rows: tuple[CoverageDemandRow, ...]
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
        }


def _default_rules() -> tuple[CoverageRule, ...]:
    return (
        CoverageRule("existing-model-owner", "existing_model_preflight", ("existing-model-owner",), "reuse and ownership must be grounded", always_for_non_trivial=True),
        CoverageRule("maturation-owner", "model_first_function_flow", ("task-model-maturation",), "non-trivial work requires an explicit maturity decision", always_for_non_trivial=True),
        CoverageRule("process-owner", "development_process_flow", ("implementation-admission",), "implementation and release require a separate admission owner", implementation_trigger=True, release_trigger=True, minimum_tier=COVERAGE_TIER_STANDARD),
        CoverageRule("behavior-owner", "behavior_commitment_ledger", ("external-behavior-ownership",), "external behavior needs one primary owner", change_kind_triggers=("external_behavior", "public_api", "command", "prompt", "skill"), minimum_tier=COVERAGE_TIER_STANDARD),
        CoverageRule("ui-owner", "ui_flow_structure", ("ui-journey", "ui-operability"), "affected UI needs journey and operability coverage", change_kind_triggers=("ui",), surface_prefix_triggers=("ui:", "screen:", "view:"), minimum_tier=COVERAGE_TIER_DEEP),
        CoverageRule("field-owner", "field_lifecycle_mesh", ("field-lifecycle",), "persisted or renamed fields need lifecycle coverage", change_kind_triggers=("field_add", "field_remove", "field_rename", "field_migration", "persistence"), minimum_tier=COVERAGE_TIER_DEEP),
        CoverageRule("mesh-owner", "model_mesh", ("affected-model-topology",), "affected model relationships need mesh governance", topology_triggers=tuple(MODEL_MESH_TOPOLOGY_TRIGGERS), minimum_tier=COVERAGE_TIER_DEEP),
        CoverageRule("test-owner", "model_test_alignment", ("model-test-alignment",), "changed behavior needs explicit evidence ownership", implementation_trigger=True, change_kind_triggers=("behavior", "test", "contract", "public_api"), minimum_tier=COVERAGE_TIER_STANDARD),
        CoverageRule("release-owner", "development_process_flow", ("release-identity", "distribution-parity", "full-validation"), "release needs frozen validation and distribution evidence", release_trigger=True, minimum_tier=COVERAGE_TIER_RELEASE),
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
    triggered_tiers = [COVERAGE_TIER_ORDINARY]
    built_in_owners: set[str] = set()
    for rule in sorted(rules, key=lambda item: item.rule_id):
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
    if facts.release_requested:
        triggered_tiers.append(COVERAGE_TIER_RELEASE)
    elif facts.risk_signal_ids or facts.related_model_ids or set(facts.topology_signal_ids) & MODEL_MESH_TOPOLOGY_TRIGGERS:
        triggered_tiers.append(COVERAGE_TIER_DEEP)
    elif facts.implementation_requested or len([row for row in rows if row.triggered]) > 2:
        triggered_tiers.append(COVERAGE_TIER_STANDARD)
    tier = max(triggered_tiers, key=lambda value: _TIER_RANK[value])
    task_fingerprint = facts.fingerprint
    demand_id = f"task-coverage:{facts.task_id}:{task_fingerprint.split(':', 1)[-1][:16]}"
    return TaskCoverageDemand(demand_id, facts.task_id, task_fingerprint, tier, tuple(rows))


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
    "TaskCoverageDemand",
    "TaskFacts",
    "compile_task_coverage_demand",
    "resolve_coverage_demand_row",
]
