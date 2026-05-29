"""Model similarity and consolidation review helpers.

This helper compares structured FlowGuard model signatures and returns typed,
evidence-gated relation advice. It does not merge models or rewrite production
code; downstream FlowGuard routes own those implementation and confidence
claims.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Any, Mapping, Sequence

from .export import to_jsonable


MODEL_SIMILARITY_ROUTE = "model_similarity_consolidation"

RELATION_SAME_WORKFLOW = "same_workflow"
RELATION_SAME_FAMILY_VARIANT = "same_family_variant"
RELATION_SYMMETRIC_FLOW = "symmetric_flow"
RELATION_SHARED_KERNEL = "shared_kernel_candidate"
RELATION_DUPLICATE_BOUNDARY = "duplicate_boundary"
RELATION_OVERLAPPING_OWNERSHIP = "overlapping_ownership"
RELATION_PARENT_CHILD = "parent_child_candidate"
RELATION_SIBLING_OVERLAP = "sibling_overlap"
RELATION_ADAPTER_ONLY = "adapter_only_difference"
RELATION_EVIDENCE_DUPLICATE = "evidence_duplicate"
RELATION_FALSE_FRIEND = "false_friend"
RELATION_UNRELATED = "unrelated"
RELATION_MANUAL_REVIEW = "manual_review"

MODEL_SIMILARITY_RELATION_TYPES = {
    RELATION_SAME_WORKFLOW,
    RELATION_SAME_FAMILY_VARIANT,
    RELATION_SYMMETRIC_FLOW,
    RELATION_SHARED_KERNEL,
    RELATION_DUPLICATE_BOUNDARY,
    RELATION_OVERLAPPING_OWNERSHIP,
    RELATION_PARENT_CHILD,
    RELATION_SIBLING_OVERLAP,
    RELATION_ADAPTER_ONLY,
    RELATION_EVIDENCE_DUPLICATE,
    RELATION_FALSE_FRIEND,
    RELATION_UNRELATED,
    RELATION_MANUAL_REVIEW,
}

CONFIDENCE_FULL = "full"
CONFIDENCE_SCOPED = "scoped"
CONFIDENCE_BLOCKED = "blocked"

EVIDENCE_STATUS_PASSED = "passed"
EVIDENCE_STATUS_FAILED = "failed"
EVIDENCE_STATUS_STALE = "stale"
EVIDENCE_STATUS_SKIPPED = "skipped"
EVIDENCE_STATUS_NOT_RUN = "not_run"
EVIDENCE_STATUS_RUNNING = "running"
EVIDENCE_STATUS_PROGRESS_ONLY = "progress_only"
EVIDENCE_STATUS_ERROR = "error"

PASSING_EVIDENCE_STATUSES = {EVIDENCE_STATUS_PASSED}

RECOMMEND_REUSE_OR_EXTEND = "reuse_or_extend_existing"
RECOMMEND_CREATE_FAMILY_VARIANT = "create_family_variant"
RECOMMEND_EXTRACT_SHARED_KERNEL = "extract_shared_kernel"
RECOMMEND_ROUTE_ARCHITECTURE_REDUCTION = "route_architecture_reduction"
RECOMMEND_ROUTE_MODEL_MESH = "route_model_mesh"
RECOMMEND_ROUTE_MODEL_TEST_ALIGNMENT = "route_model_test_alignment"
RECOMMEND_KEEP_SEPARATE = "keep_separate"
RECOMMEND_MANUAL_REVIEW = "manual_review"
RECOMMEND_NO_ACTION = "no_action"

ROUTE_EXISTING_MODEL_PREFLIGHT = "existing_model_preflight"
ROUTE_MODEL_MESH = "model_mesh"
ROUTE_ARCHITECTURE_REDUCTION = "architecture_reduction"
ROUTE_CODE_STRUCTURE_RECOMMENDATION = "code_structure_recommendation"
ROUTE_STRUCTURE_MESH = "structure_mesh"
ROUTE_MODEL_TEST_ALIGNMENT = "model_test_alignment"
ROUTE_MANUAL_REVIEW = "manual_review"


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return tuple(result)


def _tokens(value: str) -> set[str]:
    return {token for token in value.replace("-", "_").split("_") if token}


def _intersection(left: Sequence[str], right: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(set(left).intersection(right)))


@dataclass(frozen=True)
class ModelSignature:
    """Comparable summary of one FlowGuard model boundary."""

    model_id: str
    model_path: str = ""
    workflow_family: str = ""
    variant_id: str = ""
    function_blocks: tuple[str, ...] = ()
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    state_owned: tuple[str, ...] = ()
    state_read: tuple[str, ...] = ()
    side_effects_owned: tuple[str, ...] = ()
    invariants: tuple[str, ...] = ()
    failure_modes: tuple[str, ...] = ()
    contracts_in: tuple[str, ...] = ()
    contracts_out: tuple[str, ...] = ()
    public_entrypoints: tuple[str, ...] = ()
    parent_model_id: str = ""
    child_model_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    evidence_current: bool = True
    known_blindspots: tuple[str, ...] = ()
    false_friend_model_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "model_path", str(self.model_path))
        object.__setattr__(self, "workflow_family", str(self.workflow_family))
        object.__setattr__(self, "variant_id", str(self.variant_id))
        object.__setattr__(self, "function_blocks", _as_tuple(self.function_blocks))
        object.__setattr__(self, "inputs", _as_tuple(self.inputs))
        object.__setattr__(self, "outputs", _as_tuple(self.outputs))
        object.__setattr__(self, "state_owned", _as_tuple(self.state_owned))
        object.__setattr__(self, "state_read", _as_tuple(self.state_read))
        object.__setattr__(self, "side_effects_owned", _as_tuple(self.side_effects_owned))
        object.__setattr__(self, "invariants", _as_tuple(self.invariants))
        object.__setattr__(self, "failure_modes", _as_tuple(self.failure_modes))
        object.__setattr__(self, "contracts_in", _as_tuple(self.contracts_in))
        object.__setattr__(self, "contracts_out", _as_tuple(self.contracts_out))
        object.__setattr__(self, "public_entrypoints", _as_tuple(self.public_entrypoints))
        object.__setattr__(self, "parent_model_id", str(self.parent_model_id))
        object.__setattr__(self, "child_model_ids", _as_tuple(self.child_model_ids))
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))
        object.__setattr__(self, "known_blindspots", _as_tuple(self.known_blindspots))
        object.__setattr__(self, "false_friend_model_ids", _as_tuple(self.false_friend_model_ids))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def comparable_elements(self) -> tuple[str, ...]:
        return _unique(
            self.function_blocks
            + self.inputs
            + self.outputs
            + self.state_owned
            + self.state_read
            + self.side_effects_owned
            + self.invariants
            + self.failure_modes
            + self.contracts_in
            + self.contracts_out
            + self.public_entrypoints
        )

    def has_behavior_elements(self) -> bool:
        return bool(self.comparable_elements())

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_path": self.model_path,
            "workflow_family": self.workflow_family,
            "variant_id": self.variant_id,
            "function_blocks": list(self.function_blocks),
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "state_owned": list(self.state_owned),
            "state_read": list(self.state_read),
            "side_effects_owned": list(self.side_effects_owned),
            "invariants": list(self.invariants),
            "failure_modes": list(self.failure_modes),
            "contracts_in": list(self.contracts_in),
            "contracts_out": list(self.contracts_out),
            "public_entrypoints": list(self.public_entrypoints),
            "parent_model_id": self.parent_model_id,
            "child_model_ids": list(self.child_model_ids),
            "evidence_ids": list(self.evidence_ids),
            "evidence_current": self.evidence_current,
            "known_blindspots": list(self.known_blindspots),
            "false_friend_model_ids": list(self.false_friend_model_ids),
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ModelSimilarityEvidence:
    """Evidence attached to a model relation."""

    evidence_id: str
    relation_id: str = ""
    evidence_type: str = "similarity_review"
    result_status: str = EVIDENCE_STATUS_PASSED
    current: bool = True
    summary: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "relation_id", str(self.relation_id))
        object.__setattr__(self, "evidence_type", str(self.evidence_type))
        object.__setattr__(self, "result_status", str(self.result_status))
        object.__setattr__(self, "summary", str(self.summary))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def is_current_pass(self) -> bool:
        return self.current and self.result_status in PASSING_EVIDENCE_STATUSES

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "relation_id": self.relation_id,
            "evidence_type": self.evidence_type,
            "result_status": self.result_status,
            "current": self.current,
            "summary": self.summary,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ModelSimilarityRelation:
    """One typed relation between two model signatures."""

    relation_id: str
    left_model_id: str
    right_model_id: str
    relation_type: str
    confidence: str = CONFIDENCE_SCOPED
    matched_elements: tuple[str, ...] = ()
    different_elements: tuple[str, ...] = ()
    risk_if_merged: str = ""
    risk_if_kept_separate: str = ""
    recommendation: str = RECOMMEND_MANUAL_REVIEW
    required_next_routes: tuple[str, ...] = ()
    required_evidence: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    rationale: str = ""
    manual_review_required: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "relation_id", str(self.relation_id))
        object.__setattr__(self, "left_model_id", str(self.left_model_id))
        object.__setattr__(self, "right_model_id", str(self.right_model_id))
        object.__setattr__(self, "relation_type", str(self.relation_type))
        object.__setattr__(self, "confidence", str(self.confidence))
        object.__setattr__(self, "matched_elements", _as_tuple(self.matched_elements))
        object.__setattr__(self, "different_elements", _as_tuple(self.different_elements))
        object.__setattr__(self, "risk_if_merged", str(self.risk_if_merged))
        object.__setattr__(self, "risk_if_kept_separate", str(self.risk_if_kept_separate))
        object.__setattr__(self, "recommendation", str(self.recommendation))
        object.__setattr__(self, "required_next_routes", _as_tuple(self.required_next_routes))
        object.__setattr__(self, "required_evidence", _as_tuple(self.required_evidence))
        object.__setattr__(self, "evidence_refs", _as_tuple(self.evidence_refs))
        object.__setattr__(self, "rationale", str(self.rationale))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def is_consolidation_candidate(self) -> bool:
        return self.relation_type not in {
            RELATION_FALSE_FRIEND,
            RELATION_UNRELATED,
            RELATION_MANUAL_REVIEW,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation_id": self.relation_id,
            "left_model_id": self.left_model_id,
            "right_model_id": self.right_model_id,
            "relation_type": self.relation_type,
            "confidence": self.confidence,
            "matched_elements": list(self.matched_elements),
            "different_elements": list(self.different_elements),
            "risk_if_merged": self.risk_if_merged,
            "risk_if_kept_separate": self.risk_if_kept_separate,
            "recommendation": self.recommendation,
            "required_next_routes": list(self.required_next_routes),
            "required_evidence": list(self.required_evidence),
            "evidence_refs": list(self.evidence_refs),
            "rationale": self.rationale,
            "manual_review_required": self.manual_review_required,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ModelSimilarityPlan:
    """Review plan for pairwise model similarity consolidation."""

    plan_id: str
    signatures: tuple[ModelSignature, ...] = ()
    comparison_pairs: tuple[tuple[str, str], ...] = ()
    evidence: tuple[ModelSimilarityEvidence, ...] = ()
    required_relation_ids: tuple[str, ...] = ()
    require_current_evidence: bool = False
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "signatures", tuple(self.signatures))
        object.__setattr__(
            self,
            "comparison_pairs",
            tuple((str(left), str(right)) for left, right in self.comparison_pairs),
        )
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "required_relation_ids", _as_tuple(self.required_relation_ids))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "signatures": [signature.to_dict() for signature in self.signatures],
            "comparison_pairs": [list(pair) for pair in self.comparison_pairs],
            "evidence": [evidence.to_dict() for evidence in self.evidence],
            "required_relation_ids": list(self.required_relation_ids),
            "require_current_evidence": self.require_current_evidence,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class ModelSimilarityFinding:
    """One model similarity diagnostic."""

    code: str
    message: str
    severity: str = "blocker"
    relation_id: str = ""
    model_id: str = ""
    item_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "relation_id", str(self.relation_id))
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "item_id", str(self.item_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "relation_id": self.relation_id,
            "model_id": self.model_id,
            "item_id": self.item_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ModelSimilarityReport:
    """Structured model-similarity consolidation review result."""

    ok: bool
    plan_id: str
    decision: str
    relations: tuple[ModelSimilarityRelation, ...] = ()
    findings: tuple[ModelSimilarityFinding, ...] = ()
    recommended_next_routes: tuple[str, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "relations", tuple(self.relations))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "recommended_next_routes", _as_tuple(self.recommended_next_routes))
        if not self.summary:
            object.__setattr__(
                self,
                "summary",
                f"{'OK' if self.ok else 'BLOCKED'}: plan={self.plan_id} decision={self.decision} relations={len(self.relations)} findings={len(self.findings)}",
            )

    def format_text(self, max_relations: int = 12, max_findings: int = 12) -> str:
        lines = [
            "=== flowguard model similarity consolidation review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"plan: {self.plan_id}",
            f"decision: {self.decision}",
            f"relations: {len(self.relations)}",
            f"findings: {len(self.findings)}",
            f"recommended_next_routes: {', '.join(self.recommended_next_routes) or '(none)'}",
        ]
        for relation in self.relations[:max_relations]:
            lines.extend(
                [
                    "",
                    f"relation: {relation.relation_id}",
                    f"type: {relation.relation_type}",
                    f"models: {relation.left_model_id} <-> {relation.right_model_id}",
                    f"confidence: {relation.confidence}",
                    f"recommendation: {relation.recommendation}",
                    f"routes: {', '.join(relation.required_next_routes) or '(none)'}",
                    f"matched: {', '.join(relation.matched_elements) or '(none)'}",
                    f"different: {', '.join(relation.different_elements) or '(none)'}",
                    f"rationale: {relation.rationale}",
                ]
            )
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"relation: {finding.relation_id or '(none)'}",
                    f"model: {finding.model_id or '(none)'}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "plan_id": self.plan_id,
            "decision": self.decision,
            "relations": [relation.to_dict() for relation in self.relations],
            "findings": [finding.to_dict() for finding in self.findings],
            "recommended_next_routes": list(self.recommended_next_routes),
            "summary": self.summary,
        }


def _relation_id(left: ModelSignature, right: ModelSignature, relation_type: str) -> str:
    return f"{left.model_id}:{right.model_id}:{relation_type}"


def _matching_elements(left: ModelSignature, right: ModelSignature) -> tuple[str, ...]:
    matches: list[str] = []
    for label, left_values, right_values in (
        ("function", left.function_blocks, right.function_blocks),
        ("input", left.inputs, right.inputs),
        ("output", left.outputs, right.outputs),
        ("state", left.state_owned, right.state_owned),
        ("state_read", left.state_read, right.state_read),
        ("side_effect", left.side_effects_owned, right.side_effects_owned),
        ("invariant", left.invariants, right.invariants),
        ("failure", left.failure_modes, right.failure_modes),
        ("contract_in", left.contracts_in, right.contracts_in),
        ("contract_out", left.contracts_out, right.contracts_out),
        ("entrypoint", left.public_entrypoints, right.public_entrypoints),
        ("evidence", left.evidence_ids, right.evidence_ids),
    ):
        matches.extend(f"{label}:{item}" for item in _intersection(left_values, right_values))
    if left.workflow_family and left.workflow_family == right.workflow_family:
        matches.append(f"workflow_family:{left.workflow_family}")
    return tuple(matches)


def _different_elements(left: ModelSignature, right: ModelSignature) -> tuple[str, ...]:
    differences: list[str] = []
    if left.variant_id and right.variant_id and left.variant_id != right.variant_id:
        differences.append(f"variant:{left.variant_id}!={right.variant_id}")
    for label, left_values, right_values in (
        ("function", left.function_blocks, right.function_blocks),
        ("input", left.inputs, right.inputs),
        ("output", left.outputs, right.outputs),
        ("state", left.state_owned, right.state_owned),
        ("side_effect", left.side_effects_owned, right.side_effects_owned),
        ("invariant", left.invariants, right.invariants),
        ("failure", left.failure_modes, right.failure_modes),
        ("entrypoint", left.public_entrypoints, right.public_entrypoints),
    ):
        left_only = sorted(set(left_values) - set(right_values))
        right_only = sorted(set(right_values) - set(left_values))
        if left_only:
            differences.append(f"{label}:{left.model_id}_only={','.join(left_only)}")
        if right_only:
            differences.append(f"{label}:{right.model_id}_only={','.join(right_only)}")
    return tuple(differences)


def _has_name_overlap(left: ModelSignature, right: ModelSignature) -> bool:
    return bool(_tokens(left.model_id).intersection(_tokens(right.model_id)))


def _material_conflict(left: ModelSignature, right: ModelSignature) -> bool:
    shared_behavior = (
        set(left.function_blocks)
        | set(left.state_owned)
        | set(left.side_effects_owned)
        | set(left.failure_modes)
        | set(left.invariants)
        | set(left.contracts_in)
        | set(left.contracts_out)
    ).intersection(
        set(right.function_blocks)
        | set(right.state_owned)
        | set(right.side_effects_owned)
        | set(right.failure_modes)
        | set(right.invariants)
        | set(right.contracts_in)
        | set(right.contracts_out)
    )
    return not shared_behavior and (
        bool(left.state_owned or left.side_effects_owned or left.failure_modes)
        and bool(right.state_owned or right.side_effects_owned or right.failure_modes)
    )


def _relation_policy(relation_type: str) -> tuple[str, tuple[str, ...], str, str]:
    if relation_type == RELATION_SAME_WORKFLOW:
        return (
            RECOMMEND_REUSE_OR_EXTEND,
            (ROUTE_EXISTING_MODEL_PREFLIGHT,),
            "parallel model boundary may duplicate existing workflow ownership",
            "separate implementations may drift for the same workflow",
        )
    if relation_type == RELATION_SAME_FAMILY_VARIANT:
        return (
            RECOMMEND_CREATE_FAMILY_VARIANT,
            (ROUTE_MODEL_MESH, ROUTE_MODEL_TEST_ALIGNMENT),
            "merging all variants may erase policy-specific behavior",
            "variants may miss shared family evidence",
        )
    if relation_type in {RELATION_SYMMETRIC_FLOW, RELATION_SHARED_KERNEL}:
        return (
            RECOMMEND_EXTRACT_SHARED_KERNEL,
            (ROUTE_CODE_STRUCTURE_RECOMMENDATION, ROUTE_MODEL_MESH),
            "shared kernel extraction can hide directional or variant obligations",
            "duplicate kernels can drift across similar workflows",
        )
    if relation_type in {RELATION_DUPLICATE_BOUNDARY, RELATION_ADAPTER_ONLY}:
        return (
            RECOMMEND_ROUTE_ARCHITECTURE_REDUCTION,
            (ROUTE_ARCHITECTURE_REDUCTION,),
            "code contraction can break public entrypoints or side effects",
            "duplicate boundaries increase maintenance and validation cost",
        )
    if relation_type in {RELATION_OVERLAPPING_OWNERSHIP, RELATION_SIBLING_OVERLAP, RELATION_PARENT_CHILD}:
        return (
            RECOMMEND_ROUTE_MODEL_MESH,
            (ROUTE_MODEL_MESH,),
            "unsafe overlap can break parent, child, or sibling proof",
            "unreviewed overlap can duplicate state or side-effect ownership",
        )
    if relation_type == RELATION_EVIDENCE_DUPLICATE:
        return (
            RECOMMEND_ROUTE_MODEL_TEST_ALIGNMENT,
            (ROUTE_MODEL_TEST_ALIGNMENT,),
            "shared evidence may not prove both external contracts",
            "duplicated evidence rows can overclaim family coverage",
        )
    if relation_type == RELATION_FALSE_FRIEND:
        return (
            RECOMMEND_KEEP_SEPARATE,
            (ROUTE_MANUAL_REVIEW,),
            "merging false friends can collapse distinct responsibilities",
            "keeping separate is expected when rationale is visible",
        )
    if relation_type == RELATION_UNRELATED:
        return (RECOMMEND_NO_ACTION, (), "none", "none")
    return (
        RECOMMEND_MANUAL_REVIEW,
        (ROUTE_MANUAL_REVIEW,),
        "manual relation needs human or route-specific review",
        "unreviewed relation may hide consolidation or split work",
    )


def _classify_pair(left: ModelSignature, right: ModelSignature) -> str:
    matches = _matching_elements(left, right)
    state_overlap = bool(_intersection(left.state_owned, right.state_owned))
    side_effect_overlap = bool(_intersection(left.side_effects_owned, right.side_effects_owned))
    function_overlap = bool(_intersection(left.function_blocks, right.function_blocks))
    failure_overlap = bool(_intersection(left.failure_modes, right.failure_modes))
    invariant_overlap = bool(_intersection(left.invariants, right.invariants))
    evidence_overlap = bool(_intersection(left.evidence_ids, right.evidence_ids))
    same_family = bool(left.workflow_family and left.workflow_family == right.workflow_family)
    different_variants = bool(left.variant_id and right.variant_id and left.variant_id != right.variant_id)
    parent_child = left.model_id in right.child_model_ids or right.model_id in left.child_model_ids
    parent_child = parent_child or left.parent_model_id == right.model_id or right.parent_model_id == left.model_id
    same_parent = bool(left.parent_model_id and left.parent_model_id == right.parent_model_id)
    symmetric = bool(set(left.inputs).intersection(right.outputs) and set(left.outputs).intersection(right.inputs))
    false_friend_declared = right.model_id in left.false_friend_model_ids or left.model_id in right.false_friend_model_ids

    if false_friend_declared or ((_has_name_overlap(left, right) or same_family) and _material_conflict(left, right)):
        return RELATION_FALSE_FRIEND
    if parent_child:
        return RELATION_PARENT_CHILD
    if same_parent and (state_overlap or side_effect_overlap):
        return RELATION_SIBLING_OVERLAP
    if same_family and different_variants and (function_overlap or failure_overlap or invariant_overlap):
        return RELATION_SAME_FAMILY_VARIANT
    if same_family and (function_overlap or failure_overlap) and not different_variants:
        return RELATION_SAME_WORKFLOW
    if function_overlap and (state_overlap or side_effect_overlap) and (same_family or failure_overlap):
        return RELATION_DUPLICATE_BOUNDARY
    if state_overlap or side_effect_overlap:
        return RELATION_OVERLAPPING_OWNERSHIP
    if symmetric:
        return RELATION_SYMMETRIC_FLOW
    if function_overlap and (failure_overlap or invariant_overlap):
        if set(left.public_entrypoints) != set(right.public_entrypoints) or set(left.inputs) != set(right.inputs):
            return RELATION_ADAPTER_ONLY
        return RELATION_SHARED_KERNEL
    shared_categories = sum(
        1
        for shared in (
            function_overlap,
            failure_overlap,
            invariant_overlap,
            bool(_intersection(left.contracts_in, right.contracts_in)),
            bool(_intersection(left.contracts_out, right.contracts_out)),
        )
        if shared
    )
    if shared_categories >= 2:
        return RELATION_SHARED_KERNEL
    if evidence_overlap:
        return RELATION_EVIDENCE_DUPLICATE
    if matches:
        return RELATION_MANUAL_REVIEW
    return RELATION_UNRELATED


def _evidence_for_relation(
    relation_id: str,
    left: ModelSignature,
    right: ModelSignature,
    evidence: Sequence[ModelSimilarityEvidence],
) -> tuple[ModelSimilarityEvidence, ...]:
    direct = [item for item in evidence if item.relation_id == relation_id]
    shared_ids = set(left.evidence_ids).intersection(right.evidence_ids)
    shared = [
        item
        for item in evidence
        if item.evidence_id in shared_ids and not item.relation_id
    ]
    return tuple(direct + shared)


def _build_relation(
    left: ModelSignature,
    right: ModelSignature,
    *,
    evidence: Sequence[ModelSimilarityEvidence],
    require_current_evidence: bool,
) -> tuple[ModelSimilarityRelation, tuple[ModelSimilarityFinding, ...]]:
    relation_type = _classify_pair(left, right)
    relation_id = _relation_id(left, right, relation_type)
    recommendation, routes, risk_if_merged, risk_if_kept_separate = _relation_policy(relation_type)
    matched = _matching_elements(left, right)
    different = _different_elements(left, right)
    relation_evidence = _evidence_for_relation(relation_id, left, right, evidence)
    evidence_refs = tuple(item.evidence_id for item in relation_evidence if item.is_current_pass())
    required_evidence: list[str] = []
    findings: list[ModelSimilarityFinding] = []
    current_signature_evidence = left.evidence_current and right.evidence_current

    if relation_type not in {RELATION_UNRELATED, RELATION_FALSE_FRIEND, RELATION_MANUAL_REVIEW}:
        required_evidence.append("current_similarity_evidence")
        if not current_signature_evidence:
            findings.append(
                ModelSimilarityFinding(
                    "stale_model_signature_evidence",
                    "relation uses one or more model signatures with stale evidence",
                    severity="blocker" if require_current_evidence else "warning",
                    relation_id=relation_id,
                    metadata={"left": left.model_id, "right": right.model_id},
                )
            )
        if require_current_evidence and not evidence_refs:
            findings.append(
                ModelSimilarityFinding(
                    "missing_current_similarity_evidence",
                    "relation recommends consolidation but has no current passing similarity evidence",
                    relation_id=relation_id,
                )
            )

    blocked_relation = relation_type in {RELATION_FALSE_FRIEND, RELATION_MANUAL_REVIEW}
    confidence = CONFIDENCE_FULL
    if blocked_relation:
        confidence = CONFIDENCE_BLOCKED
    elif findings or (required_evidence and not evidence_refs):
        confidence = CONFIDENCE_SCOPED
    if relation_type == RELATION_UNRELATED:
        confidence = CONFIDENCE_FULL

    relation = ModelSimilarityRelation(
        relation_id=relation_id,
        left_model_id=left.model_id,
        right_model_id=right.model_id,
        relation_type=relation_type,
        confidence=confidence,
        matched_elements=matched,
        different_elements=different,
        risk_if_merged=risk_if_merged,
        risk_if_kept_separate=risk_if_kept_separate,
        recommendation=recommendation,
        required_next_routes=routes,
        required_evidence=tuple(required_evidence),
        evidence_refs=evidence_refs,
        rationale=_rationale_for_relation(relation_type, matched, different),
        manual_review_required=relation_type in {RELATION_FALSE_FRIEND, RELATION_MANUAL_REVIEW},
    )
    return relation, tuple(findings)


def _rationale_for_relation(
    relation_type: str,
    matched: Sequence[str],
    different: Sequence[str],
) -> str:
    if relation_type == RELATION_UNRELATED:
        return "No shared behavior elements were found."
    if relation_type == RELATION_FALSE_FRIEND:
        return "Names or families look related, but material ownership differs."
    if relation_type == RELATION_SAME_FAMILY_VARIANT:
        return "The models share a workflow family while preserving variant-specific differences."
    if relation_type == RELATION_SAME_WORKFLOW:
        return "The models share workflow and behavior elements."
    if relation_type == RELATION_DUPLICATE_BOUNDARY:
        return "The models share function and ownership elements that look duplicative."
    if relation_type == RELATION_ADAPTER_ONLY:
        return "The models share core behavior while differing mainly at adapter or entrypoint edges."
    if relation_type == RELATION_SHARED_KERNEL:
        return "The models share enough core behavior to consider a shared kernel."
    if relation_type == RELATION_SYMMETRIC_FLOW:
        return "The models exchange compatible input and output shapes."
    if relation_type in {RELATION_OVERLAPPING_OWNERSHIP, RELATION_SIBLING_OVERLAP}:
        return "The models overlap state or side-effect ownership."
    if relation_type == RELATION_PARENT_CHILD:
        return "The models already declare parent/child relation signals."
    if relation_type == RELATION_EVIDENCE_DUPLICATE:
        return "The models cite shared evidence and need scope review."
    if matched or different:
        return "The relation needs manual review because shared and different elements are mixed."
    return "Manual review required."


def _blocker_findings(findings: Sequence[ModelSimilarityFinding]) -> tuple[ModelSimilarityFinding, ...]:
    return tuple(finding for finding in findings if finding.severity == "blocker")


def _decision_for(
    relations: Sequence[ModelSimilarityRelation],
    findings: Sequence[ModelSimilarityFinding],
) -> str:
    if _blocker_findings(findings):
        return "model_similarity_blocked"
    if any(relation.confidence == CONFIDENCE_SCOPED for relation in relations):
        return "model_similarity_scoped"
    return "model_similarity_ready"


def review_model_similarity_consolidation(plan: ModelSimilarityPlan) -> ModelSimilarityReport:
    """Review pairwise model relations and produce consolidation handoffs."""

    findings: list[ModelSimilarityFinding] = []
    if not plan.plan_id:
        findings.append(
            ModelSimilarityFinding(
                "missing_plan_id",
                "model similarity consolidation plan has no id",
            )
        )
    if not plan.signatures:
        findings.append(
            ModelSimilarityFinding(
                "missing_model_signatures",
                "model similarity consolidation plan has no model signatures",
            )
        )

    signatures_by_id: dict[str, ModelSignature] = {}
    for signature in plan.signatures:
        if not signature.model_id:
            findings.append(
                ModelSimilarityFinding(
                    "missing_model_id",
                    "model signature has no model id",
                    metadata=signature.to_dict(),
                )
            )
            continue
        if signature.model_id in signatures_by_id:
            findings.append(
                ModelSimilarityFinding(
                    "duplicate_model_signature",
                    "model signature id is duplicated",
                    model_id=signature.model_id,
                )
            )
        signatures_by_id[signature.model_id] = signature
        if not signature.has_behavior_elements():
            findings.append(
                ModelSimilarityFinding(
                    "incomplete_model_signature",
                    "model signature has no comparable behavior elements",
                    model_id=signature.model_id,
                    metadata=signature.to_dict(),
                )
            )

    pairs = plan.comparison_pairs
    if not pairs and len(signatures_by_id) >= 2:
        pairs = tuple(combinations(sorted(signatures_by_id), 2))
    relations: list[ModelSimilarityRelation] = []
    for left_id, right_id in pairs:
        left = signatures_by_id.get(left_id)
        right = signatures_by_id.get(right_id)
        if left is None or right is None:
            findings.append(
                ModelSimilarityFinding(
                    "unknown_comparison_model",
                    "comparison pair references a model id that is not registered",
                    item_id=f"{left_id}:{right_id}",
                    metadata={"left_model_id": left_id, "right_model_id": right_id},
                )
            )
            continue
        relation, relation_findings = _build_relation(
            left,
            right,
            evidence=plan.evidence,
            require_current_evidence=plan.require_current_evidence,
        )
        relations.append(relation)
        findings.extend(relation_findings)

    relation_ids = {relation.relation_id for relation in relations}
    for relation_id in plan.required_relation_ids:
        if relation_id not in relation_ids:
            findings.append(
                ModelSimilarityFinding(
                    "missing_required_relation",
                    "required model-similarity relation was not produced",
                    relation_id=relation_id,
                )
            )

    recommended_routes = tuple(
        sorted(
            {
                route
                for relation in relations
                if relation.confidence != CONFIDENCE_BLOCKED
                for route in relation.required_next_routes
            }
        )
    )
    decision = _decision_for(relations, findings)
    blockers = _blocker_findings(findings)
    return ModelSimilarityReport(
        ok=not blockers,
        plan_id=plan.plan_id,
        decision=decision,
        relations=tuple(relations),
        findings=tuple(findings),
        recommended_next_routes=recommended_routes,
    )


__all__ = [
    "CONFIDENCE_BLOCKED",
    "CONFIDENCE_FULL",
    "CONFIDENCE_SCOPED",
    "EVIDENCE_STATUS_ERROR",
    "EVIDENCE_STATUS_FAILED",
    "EVIDENCE_STATUS_NOT_RUN",
    "EVIDENCE_STATUS_PASSED",
    "EVIDENCE_STATUS_PROGRESS_ONLY",
    "EVIDENCE_STATUS_RUNNING",
    "EVIDENCE_STATUS_SKIPPED",
    "EVIDENCE_STATUS_STALE",
    "MODEL_SIMILARITY_RELATION_TYPES",
    "MODEL_SIMILARITY_ROUTE",
    "PASSING_EVIDENCE_STATUSES",
    "RECOMMEND_CREATE_FAMILY_VARIANT",
    "RECOMMEND_EXTRACT_SHARED_KERNEL",
    "RECOMMEND_KEEP_SEPARATE",
    "RECOMMEND_MANUAL_REVIEW",
    "RECOMMEND_NO_ACTION",
    "RECOMMEND_REUSE_OR_EXTEND",
    "RECOMMEND_ROUTE_ARCHITECTURE_REDUCTION",
    "RECOMMEND_ROUTE_MODEL_MESH",
    "RECOMMEND_ROUTE_MODEL_TEST_ALIGNMENT",
    "RELATION_ADAPTER_ONLY",
    "RELATION_DUPLICATE_BOUNDARY",
    "RELATION_EVIDENCE_DUPLICATE",
    "RELATION_FALSE_FRIEND",
    "RELATION_MANUAL_REVIEW",
    "RELATION_OVERLAPPING_OWNERSHIP",
    "RELATION_PARENT_CHILD",
    "RELATION_SAME_FAMILY_VARIANT",
    "RELATION_SAME_WORKFLOW",
    "RELATION_SHARED_KERNEL",
    "RELATION_SIBLING_OVERLAP",
    "RELATION_SYMMETRIC_FLOW",
    "RELATION_UNRELATED",
    "ROUTE_ARCHITECTURE_REDUCTION",
    "ROUTE_CODE_STRUCTURE_RECOMMENDATION",
    "ROUTE_EXISTING_MODEL_PREFLIGHT",
    "ROUTE_MANUAL_REVIEW",
    "ROUTE_MODEL_MESH",
    "ROUTE_MODEL_TEST_ALIGNMENT",
    "ROUTE_STRUCTURE_MESH",
    "ModelSignature",
    "ModelSimilarityEvidence",
    "ModelSimilarityFinding",
    "ModelSimilarityPlan",
    "ModelSimilarityRelation",
    "ModelSimilarityReport",
    "review_model_similarity_consolidation",
]
