"""Hierarchical model-mesh governance helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .export import to_jsonable


OWNERSHIP_CHILD = "child"
OWNERSHIP_PARENT = "parent"
OWNERSHIP_READ_ONLY = "read_only"
OWNERSHIP_SHARED_KERNEL = "shared_kernel"
OWNING_MODES = {OWNERSHIP_CHILD, OWNERSHIP_PARENT, OWNERSHIP_SHARED_KERNEL}
ALLOWED_OWNERSHIP = OWNING_MODES | {OWNERSHIP_READ_ONLY}

EVIDENCE_CANDIDATE_ONLY = "candidate_only"
EVIDENCE_ABSTRACT_GREEN = "abstract_green"
EVIDENCE_HAZARD_GREEN = "hazard_green"
EVIDENCE_LIVE_CURRENT_GREEN = "live_current_green"
EVIDENCE_CONFORMANCE_GREEN = "conformance_green"
EVIDENCE_MESH_GREEN = "mesh_green"

DEFAULT_LARGE_MODEL_STATE_THRESHOLD = 10_000


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


@dataclass(frozen=True)
class HierarchyCoverageItem:
    """One parent-space item that must be owned, shared, or explicitly read-only."""

    item_id: str
    item_type: str = "function"
    owner_model_id: str = ""
    ownership: str = OWNERSHIP_CHILD
    description: str = ""
    allowed_shared_with: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "item_id", str(self.item_id))
        object.__setattr__(self, "item_type", str(self.item_type))
        object.__setattr__(self, "owner_model_id", str(self.owner_model_id))
        object.__setattr__(self, "ownership", str(self.ownership))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "allowed_shared_with", _as_tuple(self.allowed_shared_with))

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "item_type": self.item_type,
            "owner_model_id": self.owner_model_id,
            "ownership": self.ownership,
            "description": self.description,
            "allowed_shared_with": list(self.allowed_shared_with),
        }


@dataclass(frozen=True)
class ChildModelEvidence:
    """Contract and evidence summary for one child model."""

    model_id: str
    risk_boundary: str = ""
    state_owned: tuple[str, ...] = ()
    side_effects_owned: tuple[str, ...] = ()
    functional_areas: tuple[str, ...] = ()
    contracts_out: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    evidence_tier: str = EVIDENCE_CANDIDATE_ONLY
    evidence_current: bool = True
    skipped_checks: tuple[str, ...] = ()
    not_run_checks: tuple[str, ...] = ()
    estimated_state_count: int | None = None
    observed_state_count: int | None = None
    budgeted_incomplete: bool = False
    unrelated_functional_areas: bool = False
    structurally_cohesive: bool = True
    is_legacy: bool = False
    has_compatibility_contract: bool = True
    overlaps_existing_model: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "risk_boundary", str(self.risk_boundary))
        object.__setattr__(self, "state_owned", _as_tuple(self.state_owned))
        object.__setattr__(self, "side_effects_owned", _as_tuple(self.side_effects_owned))
        object.__setattr__(self, "functional_areas", _as_tuple(self.functional_areas))
        object.__setattr__(self, "contracts_out", _as_tuple(self.contracts_out))
        object.__setattr__(self, "depends_on", _as_tuple(self.depends_on))
        object.__setattr__(self, "evidence_tier", str(self.evidence_tier))
        object.__setattr__(self, "skipped_checks", _as_tuple(self.skipped_checks))
        object.__setattr__(self, "not_run_checks", _as_tuple(self.not_run_checks))
        object.__setattr__(self, "overlaps_existing_model", str(self.overlaps_existing_model))

    def largest_state_count(self) -> int:
        counts = [
            count
            for count in (self.estimated_state_count, self.observed_state_count)
            if count is not None
        ]
        return max(counts) if counts else 0

    def requires_large_model_review(self, threshold: int = DEFAULT_LARGE_MODEL_STATE_THRESHOLD) -> bool:
        return (
            self.largest_state_count() > threshold
            or self.budgeted_incomplete
            or self.unrelated_functional_areas
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "risk_boundary": self.risk_boundary,
            "state_owned": list(self.state_owned),
            "side_effects_owned": list(self.side_effects_owned),
            "functional_areas": list(self.functional_areas),
            "contracts_out": list(self.contracts_out),
            "depends_on": list(self.depends_on),
            "evidence_tier": self.evidence_tier,
            "evidence_current": self.evidence_current,
            "skipped_checks": list(self.skipped_checks),
            "not_run_checks": list(self.not_run_checks),
            "estimated_state_count": self.estimated_state_count,
            "observed_state_count": self.observed_state_count,
            "budgeted_incomplete": self.budgeted_incomplete,
            "unrelated_functional_areas": self.unrelated_functional_areas,
            "structurally_cohesive": self.structurally_cohesive,
            "is_legacy": self.is_legacy,
            "has_compatibility_contract": self.has_compatibility_contract,
            "overlaps_existing_model": self.overlaps_existing_model,
        }


@dataclass(frozen=True)
class ModelTargetSplitDerivation:
    """Model-derived target child layout for one parent ModelMesh boundary."""

    source_model_id: str
    target_child_model_ids: tuple[str, ...] = ()
    covered_partition_item_ids: tuple[str, ...] = ()
    state_owner_fields: tuple[str, ...] = ()
    side_effect_owner_fields: tuple[str, ...] = ()
    source_model_path: str = ""
    rationale: str = ""
    derived_from_flowguard_model: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_model_id", str(self.source_model_id))
        object.__setattr__(self, "target_child_model_ids", _as_tuple(self.target_child_model_ids))
        object.__setattr__(self, "covered_partition_item_ids", _as_tuple(self.covered_partition_item_ids))
        object.__setattr__(self, "state_owner_fields", _as_tuple(self.state_owner_fields))
        object.__setattr__(self, "side_effect_owner_fields", _as_tuple(self.side_effect_owner_fields))
        object.__setattr__(self, "source_model_path", str(self.source_model_path))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_model_id": self.source_model_id,
            "target_child_model_ids": list(self.target_child_model_ids),
            "covered_partition_item_ids": list(self.covered_partition_item_ids),
            "state_owner_fields": list(self.state_owner_fields),
            "side_effect_owner_fields": list(self.side_effect_owner_fields),
            "source_model_path": self.source_model_path,
            "rationale": self.rationale,
            "derived_from_flowguard_model": self.derived_from_flowguard_model,
        }


@dataclass(frozen=True)
class HierarchyPartitionMap:
    """Partition map for one parent model boundary."""

    parent_model_id: str
    coverage_items: tuple[HierarchyCoverageItem, ...] = ()
    child_models: tuple[ChildModelEvidence, ...] = ()
    target_split_derivation: ModelTargetSplitDerivation | None = None
    required_evidence_tier: str = EVIDENCE_ABSTRACT_GREEN
    allowed_shared_areas: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "parent_model_id", str(self.parent_model_id))
        object.__setattr__(self, "coverage_items", tuple(self.coverage_items))
        object.__setattr__(self, "child_models", tuple(self.child_models))
        object.__setattr__(self, "required_evidence_tier", str(self.required_evidence_tier))
        object.__setattr__(self, "allowed_shared_areas", _as_tuple(self.allowed_shared_areas))

    def to_dict(self) -> dict[str, Any]:
        return {
            "parent_model_id": self.parent_model_id,
            "coverage_items": [item.to_dict() for item in self.coverage_items],
            "child_models": [child.to_dict() for child in self.child_models],
            "target_split_derivation": (
                self.target_split_derivation.to_dict()
                if self.target_split_derivation is not None
                else None
            ),
            "required_evidence_tier": self.required_evidence_tier,
            "allowed_shared_areas": list(self.allowed_shared_areas),
        }


@dataclass(frozen=True)
class HierarchyMeshFinding:
    """One partition, overlap, evidence, or legacy finding from a mesh review."""

    code: str
    message: str
    severity: str = "blocker"
    model_id: str = ""
    item_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "item_id", str(self.item_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "model_id": self.model_id,
            "item_id": self.item_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class HierarchyMeshReport:
    """Structured outcome of a hierarchical mesh review."""

    ok: bool
    parent_model_id: str
    decision: str
    activation_reasons: tuple[str, ...] = ()
    findings: tuple[HierarchyMeshFinding, ...] = ()
    split_decisions: Mapping[str, str] = field(default_factory=dict)
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "parent_model_id", str(self.parent_model_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "activation_reasons", _as_tuple(self.activation_reasons))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "split_decisions", dict(self.split_decisions))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: parent={self.parent_model_id} decision={self.decision} findings={len(self.findings)}",
            )

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard hierarchical mesh review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"parent: {self.parent_model_id}",
            f"decision: {self.decision}",
            f"activation_reasons: {', '.join(self.activation_reasons) if self.activation_reasons else '(none)'}",
            f"findings: {len(self.findings)}",
        ]
        if self.split_decisions:
            lines.append("split_decisions:")
            for model_id, decision in sorted(self.split_decisions.items()):
                lines.append(f"  - {model_id}: {decision}")
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"model: {finding.model_id or '(none)'}",
                    f"item: {finding.item_id or '(none)'}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "parent_model_id": self.parent_model_id,
            "decision": self.decision,
            "activation_reasons": list(self.activation_reasons),
            "findings": [finding.to_dict() for finding in self.findings],
            "split_decisions": to_jsonable(dict(self.split_decisions)),
            "summary": self.summary,
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(to_jsonable(self.to_dict()), indent=indent, sort_keys=True)


@dataclass(frozen=True)
class LegacyModelRecord:
    """Discovery-time facts about an existing FlowGuard model."""

    model_id: str
    model_file: str = ""
    has_compatibility_contract: bool = False
    estimated_state_count: int | None = None
    observed_state_count: int | None = None
    budgeted_incomplete: bool = False
    functional_area_count: int = 1
    evidence_current: bool = True
    skipped_checks: tuple[str, ...] = ()
    not_run_checks: tuple[str, ...] = ()
    overlaps_existing_model: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "model_file", str(self.model_file))
        object.__setattr__(self, "skipped_checks", _as_tuple(self.skipped_checks))
        object.__setattr__(self, "not_run_checks", _as_tuple(self.not_run_checks))
        object.__setattr__(self, "overlaps_existing_model", str(self.overlaps_existing_model))


@dataclass(frozen=True)
class LegacyModelClassification:
    """Compatibility classification for a legacy model."""

    model_id: str
    labels: tuple[str, ...]
    requires_split_review: bool = False
    can_be_strong_evidence: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "labels": list(self.labels),
            "requires_split_review": self.requires_split_review,
            "can_be_strong_evidence": self.can_be_strong_evidence,
            "reason": self.reason,
        }


def _evidence_rank(tier: str) -> int:
    order = {
        EVIDENCE_CANDIDATE_ONLY: 0,
        EVIDENCE_ABSTRACT_GREEN: 1,
        EVIDENCE_HAZARD_GREEN: 2,
        EVIDENCE_LIVE_CURRENT_GREEN: 3,
        EVIDENCE_CONFORMANCE_GREEN: 4,
        EVIDENCE_MESH_GREEN: 5,
    }
    return order.get(str(tier), -1)


def _is_large_child(child: ChildModelEvidence, threshold: int) -> bool:
    return child.requires_large_model_review(threshold)


def _split_decision(child: ChildModelEvidence, threshold: int) -> str:
    if not _is_large_child(child, threshold):
        return "not_large"
    if child.overlaps_existing_model:
        return "merge_with_existing_model"
    if child.unrelated_functional_areas or not child.structurally_cohesive:
        return "split_into_children"
    if child.budgeted_incomplete:
        return "continue_with_budgeted_execution_only"
    return "keep_as_single_model"


def classify_legacy_model(
    record: LegacyModelRecord,
    *,
    large_model_threshold: int = DEFAULT_LARGE_MODEL_STATE_THRESHOLD,
) -> LegacyModelClassification:
    """Classify one discovered legacy model without rewriting it."""

    labels: list[str] = ["standalone_legacy"]
    counts = [
        count
        for count in (record.estimated_state_count, record.observed_state_count)
        if count is not None
    ]
    large = bool(counts and max(counts) > large_model_threshold) or record.budgeted_incomplete
    if large or record.functional_area_count > 1:
        labels.append("legacy_large_review_needed")
    if record.functional_area_count > 1:
        labels.append("legacy_candidate_parent")
    elif record.has_compatibility_contract:
        labels.append("legacy_candidate_child")
    if record.overlaps_existing_model:
        labels.append("legacy_overlaps_existing")
    if not record.evidence_current or record.skipped_checks or record.not_run_checks:
        labels.append("legacy_stale_or_partial")
    if not record.has_compatibility_contract:
        labels.append("legacy_without_contract")

    can_be_strong = (
        record.has_compatibility_contract
        and not large
        and record.evidence_current
        and not record.skipped_checks
        and not record.not_run_checks
    )
    reason = "strong child evidence allowed" if can_be_strong else "compatibility review required"
    return LegacyModelClassification(
        model_id=record.model_id,
        labels=tuple(labels),
        requires_split_review=large or record.functional_area_count > 1,
        can_be_strong_evidence=can_be_strong,
        reason=reason,
    )


def _target_split_derivation_findings(partition_map: HierarchyPartitionMap) -> list[HierarchyMeshFinding]:
    findings: list[HierarchyMeshFinding] = []
    if not partition_map.coverage_items and not partition_map.child_models:
        return findings

    derivation = partition_map.target_split_derivation
    if derivation is None:
        return [
            HierarchyMeshFinding(
                "missing_target_split_derivation",
                "parent model boundary lacks FlowGuard-derived target split structure",
                model_id=partition_map.parent_model_id,
            )
        ]

    if not derivation.derived_from_flowguard_model or not derivation.source_model_id:
        findings.append(
            HierarchyMeshFinding(
                "invalid_target_split_derivation",
                "target model split derivation must name the FlowGuard source model",
                model_id=partition_map.parent_model_id,
                metadata=derivation.to_dict(),
            )
        )

    child_ids = {child.model_id for child in partition_map.child_models}
    target_ids = set(derivation.target_child_model_ids)
    if not target_ids:
        findings.append(
            HierarchyMeshFinding(
                "missing_target_children",
                "target model split derivation has no target child models",
                model_id=partition_map.parent_model_id,
                metadata=derivation.to_dict(),
            )
        )
    else:
        unknown_targets = tuple(sorted(target_ids - child_ids))
        if unknown_targets:
            findings.append(
                HierarchyMeshFinding(
                    "unknown_target_child_model",
                    "target model split derivation names unregistered child models",
                    model_id=partition_map.parent_model_id,
                    metadata={"unknown_targets": unknown_targets, "derivation": derivation.to_dict()},
                )
            )
        missing_targets = tuple(sorted(child_ids - target_ids))
        if missing_targets:
            findings.append(
                HierarchyMeshFinding(
                    "incomplete_target_children",
                    "target model split derivation omits registered child models",
                    model_id=partition_map.parent_model_id,
                    metadata={"missing_targets": missing_targets, "derivation": derivation.to_dict()},
                )
            )

    coverage_ids = {item.item_id for item in partition_map.coverage_items}
    derived_coverage = set(derivation.covered_partition_item_ids)
    missing_coverage = tuple(sorted(coverage_ids - derived_coverage))
    if missing_coverage:
        findings.append(
            HierarchyMeshFinding(
                "incomplete_target_split_coverage",
                "target model split derivation does not cover all parent partition items",
                model_id=partition_map.parent_model_id,
                metadata={"missing_coverage": missing_coverage, "derivation": derivation.to_dict()},
            )
        )

    if not derivation.state_owner_fields and any(child.state_owned for child in partition_map.child_models):
        findings.append(
            HierarchyMeshFinding(
                "missing_target_state_owner_map",
                "target model split derivation omits state owner fields",
                model_id=partition_map.parent_model_id,
                metadata=derivation.to_dict(),
            )
        )
    if not derivation.side_effect_owner_fields and any(child.side_effects_owned for child in partition_map.child_models):
        findings.append(
            HierarchyMeshFinding(
                "missing_target_side_effect_owner_map",
                "target model split derivation omits side-effect owner fields",
                model_id=partition_map.parent_model_id,
                metadata=derivation.to_dict(),
            )
        )
    if not derivation.rationale:
        findings.append(
            HierarchyMeshFinding(
                "missing_target_split_rationale",
                "target model split derivation lacks rationale",
                model_id=partition_map.parent_model_id,
                metadata=derivation.to_dict(),
            )
        )
    return findings


def review_hierarchical_mesh(
    partition_map: HierarchyPartitionMap,
    *,
    model_count: int | None = None,
    large_model_threshold: int = DEFAULT_LARGE_MODEL_STATE_THRESHOLD,
) -> HierarchyMeshReport:
    """Review one parent boundary without expanding child state graphs."""

    findings: list[HierarchyMeshFinding] = []
    activation_reasons: list[str] = []
    child_ids = {child.model_id for child in partition_map.child_models}
    effective_model_count = len(partition_map.child_models) if model_count is None else model_count
    if effective_model_count >= 3:
        activation_reasons.append("model_count")

    for child in partition_map.child_models:
        if _is_large_child(child, large_model_threshold):
            activation_reasons.append(f"large_model:{child.model_id}")

    findings.extend(_target_split_derivation_findings(partition_map))

    owner_by_item: dict[str, list[HierarchyCoverageItem]] = {}
    for item in partition_map.coverage_items:
        if item.ownership not in ALLOWED_OWNERSHIP:
            findings.append(
                HierarchyMeshFinding(
                    "unknown_ownership",
                    f"coverage item uses unknown ownership mode {item.ownership!r}",
                    item_id=item.item_id,
                    metadata={"ownership": item.ownership},
                )
            )
        if item.ownership == OWNERSHIP_PARENT:
            owner = item.owner_model_id or partition_map.parent_model_id
        else:
            owner = item.owner_model_id
        if not owner and item.ownership != OWNERSHIP_READ_ONLY:
            findings.append(
                HierarchyMeshFinding(
                    "coverage_gap",
                    "parent coverage item has no owner",
                    item_id=item.item_id,
                    metadata={"item_type": item.item_type},
                )
            )
        if owner and item.ownership not in {OWNERSHIP_PARENT, OWNERSHIP_SHARED_KERNEL} and owner not in child_ids:
            findings.append(
                HierarchyMeshFinding(
                    "unknown_child_owner",
                    f"coverage item owner {owner!r} is not a registered child",
                    item_id=item.item_id,
                    model_id=owner,
                )
            )
        if item.ownership in OWNING_MODES:
            owner_by_item.setdefault(item.item_id, []).append(item)

    for item_id, owners in sorted(owner_by_item.items()):
        distinct_owners = {
            item.owner_model_id or partition_map.parent_model_id
            for item in owners
        }
        if len(distinct_owners) > 1:
            findings.append(
                HierarchyMeshFinding(
                    "duplicate_coverage_owner",
                    "coverage item has multiple owning models",
                    item_id=item_id,
                    metadata={"owners": sorted(distinct_owners)},
                )
            )

    _add_duplicate_owner_findings(
        findings,
        partition_map.child_models,
        field_name="state_owned",
        code="duplicate_state_owner",
        noun="state field",
    )
    _add_duplicate_owner_findings(
        findings,
        partition_map.child_models,
        field_name="side_effects_owned",
        code="duplicate_side_effect_owner",
        noun="side effect",
    )

    allowed_shared = set(partition_map.allowed_shared_areas)
    for left_index, left in enumerate(partition_map.child_models):
        for right in partition_map.child_models[left_index + 1 :]:
            overlap = set(left.functional_areas) & set(right.functional_areas)
            unsafe = tuple(sorted(overlap - allowed_shared))
            if unsafe:
                findings.append(
                    HierarchyMeshFinding(
                        "excessive_functional_overlap",
                        "sibling child models share functional areas without an allowed shared kernel",
                        severity="refactor",
                        metadata={"models": (left.model_id, right.model_id), "areas": unsafe},
                    )
                )

    split_decisions: dict[str, str] = {}
    for child in partition_map.child_models:
        decision = _split_decision(child, large_model_threshold)
        if decision != "not_large":
            split_decisions[child.model_id] = decision
            if decision in {"split_into_children", "merge_with_existing_model"}:
                findings.append(
                    HierarchyMeshFinding(
                        "large_model_split_review",
                        f"large model requires split review decision {decision}",
                        severity="refactor",
                        model_id=child.model_id,
                        metadata={"decision": decision, "state_count": child.largest_state_count()},
                    )
                )
        if not child.evidence_current:
            findings.append(
                HierarchyMeshFinding(
                    "stale_child_evidence",
                    "child evidence is stale",
                    model_id=child.model_id,
                    metadata={"evidence_tier": child.evidence_tier},
                )
            )
        if child.skipped_checks or child.not_run_checks:
            findings.append(
                HierarchyMeshFinding(
                    "missing_or_skipped_child_check",
                    "child has skipped or not-run checks",
                    model_id=child.model_id,
                    metadata={
                        "skipped_checks": child.skipped_checks,
                        "not_run_checks": child.not_run_checks,
                    },
                )
            )
        if _evidence_rank(child.evidence_tier) < _evidence_rank(partition_map.required_evidence_tier):
            findings.append(
                HierarchyMeshFinding(
                    "insufficient_evidence_tier",
                    "child evidence tier is below the parent requirement",
                    model_id=child.model_id,
                    metadata={
                        "required": partition_map.required_evidence_tier,
                        "actual": child.evidence_tier,
                    },
                )
            )
        if child.is_legacy and not child.has_compatibility_contract:
            findings.append(
                HierarchyMeshFinding(
                    "legacy_without_contract",
                    "legacy model cannot be strong child evidence before compatibility wrapping",
                    model_id=child.model_id,
                )
            )

    blocking = [finding for finding in findings if finding.severity in {"blocker", "refactor"}]
    if not blocking:
        decision = "mesh_green_can_continue"
    elif any(finding.code in {
        "missing_target_split_derivation",
        "invalid_target_split_derivation",
        "missing_target_children",
        "unknown_target_child_model",
        "incomplete_target_children",
        "incomplete_target_split_coverage",
        "missing_target_state_owner_map",
        "missing_target_side_effect_owner_map",
        "missing_target_split_rationale",
    } for finding in blocking):
        decision = "target_split_derivation_required"
    elif any(finding.code == "coverage_gap" for finding in blocking):
        decision = "coverage_gap_blocked"
    elif any(finding.code == "excessive_functional_overlap" for finding in blocking):
        decision = "overlap_too_high_refactor_needed"
    elif any(finding.code in {"duplicate_state_owner", "duplicate_side_effect_owner"} for finding in blocking):
        decision = "ownership_conflict"
    elif any(finding.code == "large_model_split_review" for finding in blocking):
        decision = "large_model_split_review_required"
    elif any(finding.code == "legacy_without_contract" for finding in blocking):
        decision = "legacy_compatibility_required"
    elif any(finding.code == "stale_child_evidence" for finding in blocking):
        decision = "blocked_by_stale_evidence"
    else:
        decision = "mesh_review_blocked"

    unique_activation = tuple(dict.fromkeys(activation_reasons))
    return HierarchyMeshReport(
        ok=not blocking,
        parent_model_id=partition_map.parent_model_id,
        decision=decision,
        activation_reasons=unique_activation,
        findings=tuple(findings),
        split_decisions=split_decisions,
    )


def _add_duplicate_owner_findings(
    findings: list[HierarchyMeshFinding],
    children: Sequence[ChildModelEvidence],
    *,
    field_name: str,
    code: str,
    noun: str,
) -> None:
    owners: dict[str, list[str]] = {}
    for child in children:
        for value in getattr(child, field_name):
            owners.setdefault(value, []).append(child.model_id)
    for value, model_ids in sorted(owners.items()):
        unique = tuple(sorted(set(model_ids)))
        if len(unique) > 1:
            findings.append(
                HierarchyMeshFinding(
                    code,
                    f"{noun} is owned by multiple child models",
                    item_id=value,
                    metadata={"owners": unique},
                )
            )


__all__ = [
    "ALLOWED_OWNERSHIP",
    "DEFAULT_LARGE_MODEL_STATE_THRESHOLD",
    "EVIDENCE_ABSTRACT_GREEN",
    "EVIDENCE_CANDIDATE_ONLY",
    "EVIDENCE_CONFORMANCE_GREEN",
    "EVIDENCE_HAZARD_GREEN",
    "EVIDENCE_LIVE_CURRENT_GREEN",
    "EVIDENCE_MESH_GREEN",
    "HierarchyCoverageItem",
    "HierarchyMeshFinding",
    "HierarchyMeshReport",
    "HierarchyPartitionMap",
    "ChildModelEvidence",
    "LegacyModelClassification",
    "LegacyModelRecord",
    "ModelTargetSplitDerivation",
    "OWNERSHIP_CHILD",
    "OWNERSHIP_PARENT",
    "OWNERSHIP_READ_ONLY",
    "OWNERSHIP_SHARED_KERNEL",
    "classify_legacy_model",
    "review_hierarchical_mesh",
]
