"""Structure refactor mesh governance helpers.

StructureMesh reviews whether a large script or module can be split into
smaller owned modules without losing public entrypoints, duplicating state or
side effects, introducing unsafe dependency cycles, or overclaiming behavior
parity. It does not parse source code or perform the refactor. Project adapters
or agents collect structure evidence and pass it here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .code_structure import CodeStructureRecommendation, review_code_structure_recommendation
from .export import to_jsonable
from .hierarchy import (
    EVIDENCE_ABSTRACT_GREEN,
    EVIDENCE_CANDIDATE_ONLY,
    EVIDENCE_CONFORMANCE_GREEN,
    EVIDENCE_HAZARD_GREEN,
    EVIDENCE_LIVE_CURRENT_GREEN,
    EVIDENCE_MESH_GREEN,
    OWNERSHIP_CHILD,
    OWNERSHIP_PARENT,
    OWNERSHIP_READ_ONLY,
    OWNERSHIP_SHARED_KERNEL,
)


STRUCTURE_SCOPE_ROUTINE = "routine"
STRUCTURE_SCOPE_RELEASE = "release"

STRUCTURE_EVIDENCE_ORDER = {
    EVIDENCE_CANDIDATE_ONLY: 0,
    EVIDENCE_ABSTRACT_GREEN: 1,
    EVIDENCE_HAZARD_GREEN: 2,
    EVIDENCE_LIVE_CURRENT_GREEN: 3,
    EVIDENCE_CONFORMANCE_GREEN: 4,
    EVIDENCE_MESH_GREEN: 5,
}


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


@dataclass(frozen=True)
class StructurePartitionItem:
    """One function, module, state, config, side effect, or contract boundary."""

    item_id: str
    item_type: str = "function"
    owner_module_id: str = ""
    ownership: str = OWNERSHIP_CHILD
    description: str = ""
    public_surface: bool = False
    old_path: str = ""
    new_path: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "item_id", str(self.item_id))
        object.__setattr__(self, "item_type", str(self.item_type))
        object.__setattr__(self, "owner_module_id", str(self.owner_module_id))
        object.__setattr__(self, "ownership", str(self.ownership))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "old_path", str(self.old_path))
        object.__setattr__(self, "new_path", str(self.new_path))

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "item_type": self.item_type,
            "owner_module_id": self.owner_module_id,
            "ownership": self.ownership,
            "description": self.description,
            "public_surface": self.public_surface,
            "old_path": self.old_path,
            "new_path": self.new_path,
        }


@dataclass(frozen=True)
class PublicEntrypointEvidence:
    """Compatibility evidence for one public CLI, API, function, or data shape."""

    entrypoint_id: str
    entrypoint_type: str = "function"
    old_path: str = ""
    new_path: str = ""
    compatibility_preserved: bool = True
    facade_available: bool = True
    parity_evidence_current: bool = True
    parity_evidence_tier: str = EVIDENCE_ABSTRACT_GREEN
    release_required: bool = False
    evidence_path: str = ""
    not_ready_reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "entrypoint_id", str(self.entrypoint_id))
        object.__setattr__(self, "entrypoint_type", str(self.entrypoint_type))
        object.__setattr__(self, "old_path", str(self.old_path))
        object.__setattr__(self, "new_path", str(self.new_path))
        object.__setattr__(self, "parity_evidence_tier", str(self.parity_evidence_tier))
        object.__setattr__(self, "evidence_path", str(self.evidence_path))
        object.__setattr__(self, "not_ready_reason", str(self.not_ready_reason))

    def is_ready(self) -> bool:
        return (
            self.compatibility_preserved
            and self.facade_available
            and self.parity_evidence_current
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "entrypoint_id": self.entrypoint_id,
            "entrypoint_type": self.entrypoint_type,
            "old_path": self.old_path,
            "new_path": self.new_path,
            "compatibility_preserved": self.compatibility_preserved,
            "facade_available": self.facade_available,
            "parity_evidence_current": self.parity_evidence_current,
            "parity_evidence_tier": self.parity_evidence_tier,
            "release_required": self.release_required,
            "evidence_path": self.evidence_path,
            "not_ready_reason": self.not_ready_reason,
        }


@dataclass(frozen=True)
class ModuleStructureEvidence:
    """Structure and parity summary for one parent, facade, or child module."""

    module_id: str
    path: str = ""
    layer: str = "child"
    extracted_from: str = ""
    owns_functions: tuple[str, ...] = ()
    owns_state: tuple[str, ...] = ()
    owns_side_effects: tuple[str, ...] = ()
    owns_config: tuple[str, ...] = ()
    behavior_contracts: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    dependency_cycles: tuple[str, ...] = ()
    facade_retained: bool = True
    behavior_parity_current: bool = True
    behavior_parity_tier: str = EVIDENCE_ABSTRACT_GREEN
    config_defaults_changed: bool = False
    release_required: bool = False
    not_ready_reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "module_id", str(self.module_id))
        object.__setattr__(self, "path", str(self.path))
        object.__setattr__(self, "layer", str(self.layer))
        object.__setattr__(self, "extracted_from", str(self.extracted_from))
        object.__setattr__(self, "owns_functions", _as_tuple(self.owns_functions))
        object.__setattr__(self, "owns_state", _as_tuple(self.owns_state))
        object.__setattr__(self, "owns_side_effects", _as_tuple(self.owns_side_effects))
        object.__setattr__(self, "owns_config", _as_tuple(self.owns_config))
        object.__setattr__(self, "behavior_contracts", _as_tuple(self.behavior_contracts))
        object.__setattr__(self, "dependencies", _as_tuple(self.dependencies))
        object.__setattr__(self, "dependency_cycles", _as_tuple(self.dependency_cycles))
        object.__setattr__(self, "behavior_parity_tier", str(self.behavior_parity_tier))
        object.__setattr__(self, "not_ready_reason", str(self.not_ready_reason))

    def is_release_only(self) -> bool:
        return self.release_required or self.layer == "release"

    def has_current_parity(self) -> bool:
        return self.behavior_parity_current and bool(self.behavior_parity_tier)

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_id": self.module_id,
            "path": self.path,
            "layer": self.layer,
            "extracted_from": self.extracted_from,
            "owns_functions": list(self.owns_functions),
            "owns_state": list(self.owns_state),
            "owns_side_effects": list(self.owns_side_effects),
            "owns_config": list(self.owns_config),
            "behavior_contracts": list(self.behavior_contracts),
            "dependencies": list(self.dependencies),
            "dependency_cycles": list(self.dependency_cycles),
            "facade_retained": self.facade_retained,
            "behavior_parity_current": self.behavior_parity_current,
            "behavior_parity_tier": self.behavior_parity_tier,
            "config_defaults_changed": self.config_defaults_changed,
            "release_required": self.release_required,
            "not_ready_reason": self.not_ready_reason,
        }


@dataclass(frozen=True)
class StructureMeshPlan:
    """A parent structure boundary and the child module evidence used for review."""

    parent_module_id: str
    partition_items: tuple[StructurePartitionItem, ...] = ()
    child_modules: tuple[ModuleStructureEvidence, ...] = ()
    public_entrypoints: tuple[PublicEntrypointEvidence, ...] = ()
    target_structure: CodeStructureRecommendation | None = None
    required_evidence_tier: str = EVIDENCE_ABSTRACT_GREEN
    decision_scope: str = STRUCTURE_SCOPE_ROUTINE
    release_deferred_allowed: bool = True
    allowed_shared_state: tuple[str, ...] = ()
    allowed_shared_side_effects: tuple[str, ...] = ()
    allowed_shared_config: tuple[str, ...] = ()
    allowed_dependency_cycles: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "parent_module_id", str(self.parent_module_id))
        object.__setattr__(self, "partition_items", tuple(self.partition_items))
        object.__setattr__(self, "child_modules", tuple(self.child_modules))
        object.__setattr__(self, "public_entrypoints", tuple(self.public_entrypoints))
        object.__setattr__(self, "required_evidence_tier", str(self.required_evidence_tier))
        object.__setattr__(self, "decision_scope", str(self.decision_scope))
        object.__setattr__(self, "allowed_shared_state", _as_tuple(self.allowed_shared_state))
        object.__setattr__(self, "allowed_shared_side_effects", _as_tuple(self.allowed_shared_side_effects))
        object.__setattr__(self, "allowed_shared_config", _as_tuple(self.allowed_shared_config))
        object.__setattr__(self, "allowed_dependency_cycles", _as_tuple(self.allowed_dependency_cycles))

    def to_dict(self) -> dict[str, Any]:
        return {
            "parent_module_id": self.parent_module_id,
            "partition_items": [item.to_dict() for item in self.partition_items],
            "child_modules": [module.to_dict() for module in self.child_modules],
            "public_entrypoints": [entrypoint.to_dict() for entrypoint in self.public_entrypoints],
            "target_structure": self.target_structure.to_dict() if self.target_structure else None,
            "required_evidence_tier": self.required_evidence_tier,
            "decision_scope": self.decision_scope,
            "release_deferred_allowed": self.release_deferred_allowed,
            "allowed_shared_state": list(self.allowed_shared_state),
            "allowed_shared_side_effects": list(self.allowed_shared_side_effects),
            "allowed_shared_config": list(self.allowed_shared_config),
            "allowed_dependency_cycles": list(self.allowed_dependency_cycles),
        }


@dataclass(frozen=True)
class StructureMeshFinding:
    """One structure, ownership, dependency, entrypoint, or parity finding."""

    code: str
    message: str
    severity: str = "blocker"
    module_id: str = ""
    item_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "module_id", str(self.module_id))
        object.__setattr__(self, "item_id", str(self.item_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "module_id": self.module_id,
            "item_id": self.item_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class StructureMeshReport:
    """Structured outcome of a StructureMesh review."""

    ok: bool
    parent_module_id: str
    decision: str
    decision_scope: str
    findings: tuple[StructureMeshFinding, ...] = ()
    release_obligations: tuple[str, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "parent_module_id", str(self.parent_module_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "decision_scope", str(self.decision_scope))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "release_obligations", _as_tuple(self.release_obligations))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: parent={self.parent_module_id} scope={self.decision_scope} decision={self.decision} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard structure mesh review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"parent: {self.parent_module_id}",
            f"scope: {self.decision_scope}",
            f"decision: {self.decision}",
            f"findings: {len(self.findings)}",
        ]
        if self.release_obligations:
            lines.append("release_obligations:")
            for item_id in self.release_obligations:
                lines.append(f"  - {item_id}")
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"module: {finding.module_id or '(none)'}",
                    f"item: {finding.item_id or '(none)'}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "parent_module_id": self.parent_module_id,
            "decision": self.decision,
            "decision_scope": self.decision_scope,
            "findings": [finding.to_dict() for finding in self.findings],
            "release_obligations": list(self.release_obligations),
            "summary": self.summary,
        }


def _tier_value(tier: str) -> int:
    return STRUCTURE_EVIDENCE_ORDER.get(tier, -1)


def _blocker_findings(findings: Sequence[StructureMeshFinding]) -> tuple[StructureMeshFinding, ...]:
    return tuple(finding for finding in findings if finding.severity == "blocker")


def _decision_for_findings(findings: Sequence[StructureMeshFinding]) -> str:
    blockers = _blocker_findings(findings)
    if not blockers:
        return "structure_mesh_green_can_continue"
    priority = [
        ("missing_target_structure", "target_structure_missing"),
        ("missing_source_model", "target_structure_blocked"),
        ("missing_target_modules", "target_structure_blocked"),
        ("missing_function_block_map", "target_structure_blocked"),
        ("missing_validation_plan", "target_structure_blocked"),
        ("missing_structure_rationale", "target_structure_blocked"),
        ("target_structure_parent_mismatch", "target_structure_blocked"),
        ("target_module_missing", "target_structure_blocked"),
        ("coverage_gap", "coverage_gap_blocked"),
        ("duplicate_partition_owner", "ownership_conflict"),
        ("duplicate_state_owner", "ownership_conflict"),
        ("duplicate_side_effect_owner", "ownership_conflict"),
        ("duplicate_config_owner", "ownership_conflict"),
        ("target_function_owner_mismatch", "target_structure_blocked"),
        ("target_state_owner_mismatch", "target_structure_blocked"),
        ("target_side_effect_owner_mismatch", "target_structure_blocked"),
        ("target_config_owner_mismatch", "target_structure_blocked"),
        ("target_entrypoint_owner_mismatch", "target_structure_blocked"),
        ("target_facade_missing", "target_structure_blocked"),
        ("entrypoint_removed", "entrypoint_compatibility_blocked"),
        ("facade_missing", "facade_compatibility_blocked"),
        ("dependency_cycle", "dependency_cycle_blocked"),
        ("config_drift", "config_drift_blocked"),
        ("missing_behavior_parity", "missing_behavior_parity"),
        ("stale_behavior_parity", "stale_behavior_parity"),
        ("insufficient_evidence_tier", "insufficient_evidence"),
        ("release_parity_not_current", "missing_release_evidence"),
    ]
    codes = {finding.code for finding in blockers}
    for code, decision in priority:
        if code in codes:
            return decision
    return "structure_mesh_blocked"


def _partition_findings(plan: StructureMeshPlan) -> list[StructureMeshFinding]:
    findings: list[StructureMeshFinding] = []
    module_ids = {module.module_id for module in plan.child_modules}
    owners_by_item: dict[str, list[StructurePartitionItem]] = {}
    for item in plan.partition_items:
        if item.ownership not in {
            OWNERSHIP_CHILD,
            OWNERSHIP_PARENT,
            OWNERSHIP_READ_ONLY,
            OWNERSHIP_SHARED_KERNEL,
        }:
            findings.append(
                StructureMeshFinding(
                    "invalid_partition_ownership",
                    f"structure item {item.item_id} has invalid ownership {item.ownership!r}",
                    item_id=item.item_id,
                    metadata=item.to_dict(),
                )
            )
        if item.ownership == OWNERSHIP_CHILD:
            if not item.owner_module_id:
                findings.append(
                    StructureMeshFinding(
                        "coverage_gap",
                        f"structure item {item.item_id} has no owning child module",
                        item_id=item.item_id,
                        metadata=item.to_dict(),
                    )
                )
            elif item.owner_module_id not in module_ids:
                findings.append(
                    StructureMeshFinding(
                        "coverage_gap",
                        f"structure item {item.item_id} owner {item.owner_module_id} is not registered",
                        module_id=item.owner_module_id,
                        item_id=item.item_id,
                        metadata=item.to_dict(),
                    )
                )
        if item.ownership in {OWNERSHIP_CHILD, OWNERSHIP_PARENT, OWNERSHIP_SHARED_KERNEL}:
            owners_by_item.setdefault(item.item_id, []).append(item)

    for item_id, owners in owners_by_item.items():
        owner_keys = {(owner.owner_module_id, owner.ownership) for owner in owners}
        if len(owner_keys) > 1:
            findings.append(
                StructureMeshFinding(
                    "duplicate_partition_owner",
                    f"structure item {item_id} has multiple owning modules",
                    item_id=item_id,
                    metadata={"owners": [owner.to_dict() for owner in owners]},
                )
            )
    return findings


def _target_structure_findings(plan: StructureMeshPlan) -> list[StructureMeshFinding]:
    findings: list[StructureMeshFinding] = []
    recommendation = plan.target_structure
    if recommendation is None:
        return [
            StructureMeshFinding(
                "missing_target_structure",
                "StructureMesh split has no FlowGuard model-derived target code structure",
                metadata={"parent_module_id": plan.parent_module_id},
            )
        ]

    report = review_code_structure_recommendation(recommendation)
    for finding in report.findings:
        findings.append(
            StructureMeshFinding(
                finding.code,
                finding.message,
                severity=finding.severity,
                module_id=finding.module_id,
                item_id=finding.item_id,
                metadata=finding.metadata,
            )
        )

    if recommendation.parent_module_id != plan.parent_module_id:
        findings.append(
            StructureMeshFinding(
                "target_structure_parent_mismatch",
                "target structure recommendation parent does not match StructureMesh parent",
                metadata={
                    "structure_parent": plan.parent_module_id,
                    "recommendation_parent": recommendation.parent_module_id,
                },
            )
        )

    target_modules = set(recommendation.module_ids())
    for module in plan.child_modules:
        if module.is_release_only():
            continue
        if module.module_id not in target_modules:
            findings.append(
                StructureMeshFinding(
                    "target_module_missing",
                    f"child module {module.module_id} is not present in the model-derived target structure",
                    module_id=module.module_id,
                    metadata=module.to_dict(),
                )
            )

    function_owners = recommendation.function_block_owners()
    state_owners = recommendation.state_owners()
    side_effect_owners = recommendation.side_effect_owners()
    config_owners = recommendation.config_owners()
    entrypoint_owners = recommendation.public_entrypoint_owners()

    for item in plan.partition_items:
        if item.ownership != OWNERSHIP_CHILD:
            continue
        if item.item_type == "function":
            owner = function_owners.get(item.item_id)
            if owner != item.owner_module_id:
                findings.append(
                    StructureMeshFinding(
                        "target_function_owner_mismatch",
                        f"function {item.item_id} target owner {owner or '(missing)'} does not match partition owner {item.owner_module_id}",
                        module_id=item.owner_module_id,
                        item_id=item.item_id,
                        metadata=item.to_dict(),
                    )
                )
        elif item.item_type in {"state", "state_field"}:
            owner = state_owners.get(item.item_id)
            if owner != item.owner_module_id:
                findings.append(
                    StructureMeshFinding(
                        "target_state_owner_mismatch",
                        f"state {item.item_id} target owner {owner or '(missing)'} does not match partition owner {item.owner_module_id}",
                        module_id=item.owner_module_id,
                        item_id=item.item_id,
                        metadata=item.to_dict(),
                    )
                )
        elif item.item_type == "side_effect":
            owner = side_effect_owners.get(item.item_id)
            if owner != item.owner_module_id:
                findings.append(
                    StructureMeshFinding(
                        "target_side_effect_owner_mismatch",
                        f"side effect {item.item_id} target owner {owner or '(missing)'} does not match partition owner {item.owner_module_id}",
                        module_id=item.owner_module_id,
                        item_id=item.item_id,
                        metadata=item.to_dict(),
                    )
                )
        elif item.item_type == "config":
            owner = config_owners.get(item.item_id)
            if owner != item.owner_module_id:
                findings.append(
                    StructureMeshFinding(
                        "target_config_owner_mismatch",
                        f"config {item.item_id} target owner {owner or '(missing)'} does not match partition owner {item.owner_module_id}",
                        module_id=item.owner_module_id,
                        item_id=item.item_id,
                        metadata=item.to_dict(),
                    )
                )
        elif item.item_type == "entrypoint":
            owner = entrypoint_owners.get(item.item_id) or recommendation.facade_module_id
            if owner != item.owner_module_id:
                findings.append(
                    StructureMeshFinding(
                        "target_entrypoint_owner_mismatch",
                        f"entrypoint {item.item_id} target owner {owner or '(missing)'} does not match partition owner {item.owner_module_id}",
                        module_id=item.owner_module_id,
                        item_id=item.item_id,
                        metadata=item.to_dict(),
                    )
                )

    for module in plan.child_modules:
        for state_id in module.owns_state:
            owner = state_owners.get(state_id)
            if owner != module.module_id:
                findings.append(
                    StructureMeshFinding(
                        "target_state_owner_mismatch",
                        f"state {state_id} target owner {owner or '(missing)'} does not match module owner {module.module_id}",
                        module_id=module.module_id,
                        item_id=state_id,
                        metadata=module.to_dict(),
                    )
                )
        for side_effect_id in module.owns_side_effects:
            owner = side_effect_owners.get(side_effect_id)
            if owner != module.module_id:
                findings.append(
                    StructureMeshFinding(
                        "target_side_effect_owner_mismatch",
                        f"side effect {side_effect_id} target owner {owner or '(missing)'} does not match module owner {module.module_id}",
                        module_id=module.module_id,
                        item_id=side_effect_id,
                        metadata=module.to_dict(),
                    )
                )
        for config_id in module.owns_config:
            owner = config_owners.get(config_id)
            if owner != module.module_id:
                findings.append(
                    StructureMeshFinding(
                        "target_config_owner_mismatch",
                        f"config {config_id} target owner {owner or '(missing)'} does not match module owner {module.module_id}",
                        module_id=module.module_id,
                        item_id=config_id,
                        metadata=module.to_dict(),
                    )
                )

    if plan.public_entrypoints and not recommendation.facade_module_id:
        findings.append(
            StructureMeshFinding(
                "target_facade_missing",
                "target structure recommendation has no facade module for public entrypoints",
                metadata={"entrypoints": [entrypoint.to_dict() for entrypoint in plan.public_entrypoints]},
            )
        )
    return findings


def _duplicate_value_findings(
    modules: Sequence[ModuleStructureEvidence],
    *,
    attr_name: str,
    allowed: Sequence[str],
    code: str,
    noun: str,
) -> list[StructureMeshFinding]:
    findings: list[StructureMeshFinding] = []
    owners: dict[str, list[str]] = {}
    allowed_set = set(allowed)
    for module in modules:
        for value in getattr(module, attr_name):
            if value in allowed_set:
                continue
            owners.setdefault(value, []).append(module.module_id)
    for value, module_ids in sorted(owners.items()):
        if len(set(module_ids)) > 1:
            findings.append(
                StructureMeshFinding(
                    code,
                    f"{noun} {value} is owned by multiple modules",
                    metadata={noun: value, "modules": sorted(set(module_ids))},
                )
            )
    return findings


def _module_findings(plan: StructureMeshPlan) -> tuple[list[StructureMeshFinding], list[str]]:
    findings: list[StructureMeshFinding] = []
    release_obligations: list[str] = []
    required_tier = _tier_value(plan.required_evidence_tier)
    allowed_cycles = set(plan.allowed_dependency_cycles)
    for module in plan.child_modules:
        release_only = module.is_release_only()
        deferred_release = (
            plan.decision_scope == STRUCTURE_SCOPE_ROUTINE
            and plan.release_deferred_allowed
            and release_only
            and not module.has_current_parity()
        )
        if deferred_release:
            release_obligations.append(module.module_id)
            findings.append(
                StructureMeshFinding(
                    "release_parity_deferred",
                    f"release-only module {module.module_id} is deferred for routine refactor confidence",
                    severity="warning",
                    module_id=module.module_id,
                    metadata=module.to_dict(),
                )
            )
            continue

        if not module.facade_retained:
            findings.append(
                StructureMeshFinding(
                    "facade_missing",
                    f"module {module.module_id} removed or bypassed the compatibility facade",
                    module_id=module.module_id,
                    metadata=module.to_dict(),
                )
            )
        if module.dependency_cycles:
            unsafe_cycles = tuple(cycle for cycle in module.dependency_cycles if cycle not in allowed_cycles)
            if unsafe_cycles:
                findings.append(
                    StructureMeshFinding(
                        "dependency_cycle",
                        f"module {module.module_id} has unsafe dependency cycles",
                        module_id=module.module_id,
                        metadata={"cycles": list(unsafe_cycles), "module": module.to_dict()},
                    )
                )
        if module.config_defaults_changed:
            findings.append(
                StructureMeshFinding(
                    "config_drift",
                    f"module {module.module_id} changed config, environment, path, or default behavior",
                    module_id=module.module_id,
                    metadata=module.to_dict(),
                )
            )
        if not module.behavior_parity_tier:
            findings.append(
                StructureMeshFinding(
                    "missing_behavior_parity",
                    f"module {module.module_id} has no behavior parity evidence tier",
                    module_id=module.module_id,
                    metadata=module.to_dict(),
                )
            )
        elif not module.behavior_parity_current:
            code = "release_parity_not_current" if plan.decision_scope == STRUCTURE_SCOPE_RELEASE and release_only else "stale_behavior_parity"
            findings.append(
                StructureMeshFinding(
                    code,
                    f"module {module.module_id} behavior parity evidence is not current",
                    module_id=module.module_id,
                    metadata=module.to_dict(),
                )
            )
        if _tier_value(module.behavior_parity_tier) < required_tier:
            findings.append(
                StructureMeshFinding(
                    "insufficient_evidence_tier",
                    f"module {module.module_id} evidence tier {module.behavior_parity_tier} is below {plan.required_evidence_tier}",
                    module_id=module.module_id,
                    metadata=module.to_dict(),
                )
            )
    return findings, release_obligations


def _entrypoint_findings(plan: StructureMeshPlan) -> tuple[list[StructureMeshFinding], list[str]]:
    findings: list[StructureMeshFinding] = []
    release_obligations: list[str] = []
    required_tier = _tier_value(plan.required_evidence_tier)
    for entrypoint in plan.public_entrypoints:
        release_only = entrypoint.release_required
        deferred_release = (
            plan.decision_scope == STRUCTURE_SCOPE_ROUTINE
            and plan.release_deferred_allowed
            and release_only
            and not entrypoint.is_ready()
        )
        if deferred_release:
            release_obligations.append(entrypoint.entrypoint_id)
            findings.append(
                StructureMeshFinding(
                    "release_entrypoint_deferred",
                    f"release-only entrypoint {entrypoint.entrypoint_id} is deferred for routine refactor confidence",
                    severity="warning",
                    item_id=entrypoint.entrypoint_id,
                    metadata=entrypoint.to_dict(),
                )
            )
            continue

        if not entrypoint.compatibility_preserved:
            findings.append(
                StructureMeshFinding(
                    "entrypoint_removed",
                    f"public entrypoint {entrypoint.entrypoint_id} is not compatibility-preserved",
                    item_id=entrypoint.entrypoint_id,
                    metadata=entrypoint.to_dict(),
                )
            )
        if not entrypoint.facade_available:
            findings.append(
                StructureMeshFinding(
                    "facade_missing",
                    f"public entrypoint {entrypoint.entrypoint_id} has no available compatibility facade",
                    item_id=entrypoint.entrypoint_id,
                    metadata=entrypoint.to_dict(),
                )
            )
        if not entrypoint.parity_evidence_tier:
            findings.append(
                StructureMeshFinding(
                    "missing_behavior_parity",
                    f"public entrypoint {entrypoint.entrypoint_id} has no behavior parity evidence",
                    item_id=entrypoint.entrypoint_id,
                    metadata=entrypoint.to_dict(),
                )
            )
        elif not entrypoint.parity_evidence_current:
            code = "release_parity_not_current" if plan.decision_scope == STRUCTURE_SCOPE_RELEASE and release_only else "stale_behavior_parity"
            findings.append(
                StructureMeshFinding(
                    code,
                    f"public entrypoint {entrypoint.entrypoint_id} parity evidence is not current",
                    item_id=entrypoint.entrypoint_id,
                    metadata=entrypoint.to_dict(),
                )
            )
        if _tier_value(entrypoint.parity_evidence_tier) < required_tier:
            findings.append(
                StructureMeshFinding(
                    "insufficient_evidence_tier",
                    f"public entrypoint {entrypoint.entrypoint_id} evidence tier {entrypoint.parity_evidence_tier} is below {plan.required_evidence_tier}",
                    item_id=entrypoint.entrypoint_id,
                    metadata=entrypoint.to_dict(),
                )
            )
    return findings, release_obligations


def review_structure_mesh(plan: StructureMeshPlan) -> StructureMeshReport:
    """Review a parent/child structure split plan."""

    findings: list[StructureMeshFinding] = []
    release_obligations: list[str] = []
    findings.extend(_target_structure_findings(plan))
    findings.extend(_partition_findings(plan))
    findings.extend(
        _duplicate_value_findings(
            plan.child_modules,
            attr_name="owns_state",
            allowed=plan.allowed_shared_state,
            code="duplicate_state_owner",
            noun="state",
        )
    )
    findings.extend(
        _duplicate_value_findings(
            plan.child_modules,
            attr_name="owns_side_effects",
            allowed=plan.allowed_shared_side_effects,
            code="duplicate_side_effect_owner",
            noun="side_effect",
        )
    )
    findings.extend(
        _duplicate_value_findings(
            plan.child_modules,
            attr_name="owns_config",
            allowed=plan.allowed_shared_config,
            code="duplicate_config_owner",
            noun="config",
        )
    )
    module_findings, module_release_obligations = _module_findings(plan)
    entrypoint_findings, entrypoint_release_obligations = _entrypoint_findings(plan)
    findings.extend(module_findings)
    findings.extend(entrypoint_findings)
    release_obligations.extend(module_release_obligations)
    release_obligations.extend(entrypoint_release_obligations)
    blockers = _blocker_findings(findings)
    return StructureMeshReport(
        ok=not blockers,
        parent_module_id=plan.parent_module_id,
        decision=_decision_for_findings(findings),
        decision_scope=plan.decision_scope,
        findings=tuple(findings),
        release_obligations=tuple(release_obligations),
    )


__all__ = [
    "STRUCTURE_EVIDENCE_ORDER",
    "STRUCTURE_SCOPE_RELEASE",
    "STRUCTURE_SCOPE_ROUTINE",
    "CodeStructureRecommendation",
    "ModuleStructureEvidence",
    "PublicEntrypointEvidence",
    "StructureMeshFinding",
    "StructureMeshPlan",
    "StructureMeshReport",
    "StructurePartitionItem",
    "review_structure_mesh",
]
