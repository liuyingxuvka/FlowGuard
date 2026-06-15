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
    code_paths: tuple[str, ...] = ()
    test_paths: tuple[str, ...] = ()
    owned_public_behaviors: tuple[str, ...] = ()
    business_path_ids: tuple[str, ...] = ()
    business_intents: tuple[str, ...] = ()
    path_terminals: tuple[str, ...] = ()
    shared_kernel_id: str = ""
    adapter_ids: tuple[str, ...] = ()
    maintenance_tags: tuple[str, ...] = ()
    changed_refs: tuple[str, ...] = ()
    parent_model_id: str = ""
    child_model_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    evidence_current: bool = True
    risk_template_ids: tuple[str, ...] = ()
    known_bad_case_ids: tuple[str, ...] = ()
    evidence_gate_ids: tuple[str, ...] = ()
    maturity_level: str = ""
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
        object.__setattr__(self, "code_paths", _as_tuple(self.code_paths))
        object.__setattr__(self, "test_paths", _as_tuple(self.test_paths))
        object.__setattr__(self, "owned_public_behaviors", _as_tuple(self.owned_public_behaviors))
        object.__setattr__(self, "business_path_ids", _as_tuple(self.business_path_ids))
        object.__setattr__(self, "business_intents", _as_tuple(self.business_intents))
        object.__setattr__(self, "path_terminals", _as_tuple(self.path_terminals))
        object.__setattr__(self, "shared_kernel_id", str(self.shared_kernel_id))
        object.__setattr__(self, "adapter_ids", _as_tuple(self.adapter_ids))
        object.__setattr__(self, "maintenance_tags", _as_tuple(self.maintenance_tags))
        object.__setattr__(self, "changed_refs", _as_tuple(self.changed_refs))
        object.__setattr__(self, "parent_model_id", str(self.parent_model_id))
        object.__setattr__(self, "child_model_ids", _as_tuple(self.child_model_ids))
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))
        object.__setattr__(self, "risk_template_ids", _as_tuple(self.risk_template_ids))
        object.__setattr__(self, "known_bad_case_ids", _as_tuple(self.known_bad_case_ids))
        object.__setattr__(self, "evidence_gate_ids", _as_tuple(self.evidence_gate_ids))
        object.__setattr__(self, "maturity_level", str(self.maturity_level))
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
            + self.risk_template_ids
            + self.known_bad_case_ids
            + self.evidence_gate_ids
            + self.public_entrypoints
            + self.owned_public_behaviors
            + self.business_path_ids
            + self.business_intents
            + self.path_terminals
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
            "code_paths": list(self.code_paths),
            "test_paths": list(self.test_paths),
            "owned_public_behaviors": list(self.owned_public_behaviors),
            "business_path_ids": list(self.business_path_ids),
            "business_intents": list(self.business_intents),
            "path_terminals": list(self.path_terminals),
            "shared_kernel_id": self.shared_kernel_id,
            "adapter_ids": list(self.adapter_ids),
            "maintenance_tags": list(self.maintenance_tags),
            "changed_refs": list(self.changed_refs),
            "parent_model_id": self.parent_model_id,
            "child_model_ids": list(self.child_model_ids),
            "evidence_ids": list(self.evidence_ids),
            "evidence_current": self.evidence_current,
            "risk_template_ids": list(self.risk_template_ids),
            "known_bad_case_ids": list(self.known_bad_case_ids),
            "evidence_gate_ids": list(self.evidence_gate_ids),
            "maturity_level": self.maturity_level,
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
    changed_model_ids: tuple[str, ...] = ()
    changed_code_paths: tuple[str, ...] = ()
    require_current_evidence: bool = False
    require_maintenance_test_paths: bool = False
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
        object.__setattr__(self, "changed_model_ids", _as_tuple(self.changed_model_ids))
        object.__setattr__(self, "changed_code_paths", _as_tuple(self.changed_code_paths))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "signatures": [signature.to_dict() for signature in self.signatures],
            "comparison_pairs": [list(pair) for pair in self.comparison_pairs],
            "evidence": [evidence.to_dict() for evidence in self.evidence],
            "required_relation_ids": list(self.required_relation_ids),
            "changed_model_ids": list(self.changed_model_ids),
            "changed_code_paths": list(self.changed_code_paths),
            "require_current_evidence": self.require_current_evidence,
            "require_maintenance_test_paths": self.require_maintenance_test_paths,
            "rationale": self.rationale,
        }


def model_signature_minimal(
    model_id: str,
    *,
    workflow_family: str = "",
    variant_id: str = "",
    function_blocks: Sequence[str] = (),
    inputs: Sequence[str] = (),
    outputs: Sequence[str] = (),
    state_owned: Sequence[str] = (),
    side_effects_owned: Sequence[str] = (),
    invariants: Sequence[str] = (),
    failure_modes: Sequence[str] = (),
    evidence_ids: Sequence[str] = (),
    risk_template_ids: Sequence[str] = (),
    known_bad_case_ids: Sequence[str] = (),
    evidence_gate_ids: Sequence[str] = (),
    business_path_ids: Sequence[str] = (),
    business_intents: Sequence[str] = (),
    path_terminals: Sequence[str] = (),
    maturity_level: str = "",
    model_path: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> ModelSignature:
    """Build the common small model signature used in route-first examples."""

    return ModelSignature(
        model_id,
        model_path=model_path,
        workflow_family=workflow_family,
        variant_id=variant_id,
        function_blocks=tuple(function_blocks),
        inputs=tuple(inputs),
        outputs=tuple(outputs),
        state_owned=tuple(state_owned),
        side_effects_owned=tuple(side_effects_owned),
        invariants=tuple(invariants),
        failure_modes=tuple(failure_modes),
        evidence_ids=tuple(evidence_ids),
        risk_template_ids=tuple(risk_template_ids),
        known_bad_case_ids=tuple(known_bad_case_ids),
        evidence_gate_ids=tuple(evidence_gate_ids),
        business_path_ids=tuple(business_path_ids),
        business_intents=tuple(business_intents),
        path_terminals=tuple(path_terminals),
        maturity_level=maturity_level,
        metadata=dict(metadata or {}),
    )


def model_signature_maintenance(
    model_id: str,
    *,
    workflow_family: str,
    variant_id: str = "",
    function_blocks: Sequence[str] = (),
    state_owned: Sequence[str] = (),
    side_effects_owned: Sequence[str] = (),
    code_paths: Sequence[str] = (),
    test_paths: Sequence[str] = (),
    owned_public_behaviors: Sequence[str] = (),
    business_path_ids: Sequence[str] = (),
    business_intents: Sequence[str] = (),
    path_terminals: Sequence[str] = (),
    shared_kernel_id: str = "",
    adapter_ids: Sequence[str] = (),
    maintenance_tags: Sequence[str] = (),
    changed_refs: Sequence[str] = (),
    evidence_ids: Sequence[str] = (),
    risk_template_ids: Sequence[str] = (),
    known_bad_case_ids: Sequence[str] = (),
    evidence_gate_ids: Sequence[str] = (),
    maturity_level: str = "",
    false_friend_model_ids: Sequence[str] = (),
    metadata: Mapping[str, Any] | None = None,
) -> ModelSignature:
    """Build a maintenance-oriented signature without exposing every field."""

    return ModelSignature(
        model_id,
        workflow_family=workflow_family,
        variant_id=variant_id,
        function_blocks=tuple(function_blocks),
        state_owned=tuple(state_owned),
        side_effects_owned=tuple(side_effects_owned),
        code_paths=tuple(code_paths),
        test_paths=tuple(test_paths),
        owned_public_behaviors=tuple(owned_public_behaviors),
        business_path_ids=tuple(business_path_ids),
        business_intents=tuple(business_intents),
        path_terminals=tuple(path_terminals),
        shared_kernel_id=shared_kernel_id,
        adapter_ids=tuple(adapter_ids),
        maintenance_tags=tuple(maintenance_tags),
        changed_refs=tuple(changed_refs),
        evidence_ids=tuple(evidence_ids),
        risk_template_ids=tuple(risk_template_ids),
        known_bad_case_ids=tuple(known_bad_case_ids),
        evidence_gate_ids=tuple(evidence_gate_ids),
        maturity_level=maturity_level,
        false_friend_model_ids=tuple(false_friend_model_ids),
        metadata=dict(metadata or {}),
    )


def model_similarity_plan_for_changed_member(
    plan_id: str,
    signatures: Sequence[ModelSignature],
    *,
    changed_model_id: str = "",
    changed_model_ids: Sequence[str] = (),
    changed_code_paths: Sequence[str] = (),
    evidence: Sequence[ModelSimilarityEvidence] = (),
    comparison_pairs: Sequence[tuple[str, str]] = (),
    required_relation_ids: Sequence[str] = (),
    require_current_evidence: bool = False,
    require_maintenance_test_paths: bool = True,
    rationale: str = "",
) -> ModelSimilarityPlan:
    """Build the ordinary "changed one family member" maintenance plan."""

    changed = (changed_model_id,) if changed_model_id else ()
    return ModelSimilarityPlan(
        plan_id,
        signatures=tuple(signatures),
        comparison_pairs=tuple(comparison_pairs),
        evidence=tuple(evidence),
        required_relation_ids=tuple(required_relation_ids),
        changed_model_ids=_unique(changed + tuple(changed_model_ids)),
        changed_code_paths=tuple(changed_code_paths),
        require_current_evidence=require_current_evidence,
        require_maintenance_test_paths=require_maintenance_test_paths,
        rationale=rationale,
    )


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
class ModelSimilarityMaintenanceGroup:
    """Connected model set that should be maintained as one similarity family."""

    group_id: str
    member_model_ids: tuple[str, ...] = ()
    relation_ids: tuple[str, ...] = ()
    relation_types: tuple[str, ...] = ()
    shared_elements: tuple[str, ...] = ()
    variant_elements: tuple[str, ...] = ()
    code_paths: tuple[str, ...] = ()
    test_paths: tuple[str, ...] = ()
    shared_kernel_ids: tuple[str, ...] = ()
    adapter_ids: tuple[str, ...] = ()
    maintenance_tags: tuple[str, ...] = ()
    required_next_routes: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "group_id", str(self.group_id))
        object.__setattr__(self, "member_model_ids", _as_tuple(self.member_model_ids))
        object.__setattr__(self, "relation_ids", _as_tuple(self.relation_ids))
        object.__setattr__(self, "relation_types", _as_tuple(self.relation_types))
        object.__setattr__(self, "shared_elements", _as_tuple(self.shared_elements))
        object.__setattr__(self, "variant_elements", _as_tuple(self.variant_elements))
        object.__setattr__(self, "code_paths", _as_tuple(self.code_paths))
        object.__setattr__(self, "test_paths", _as_tuple(self.test_paths))
        object.__setattr__(self, "shared_kernel_ids", _as_tuple(self.shared_kernel_ids))
        object.__setattr__(self, "adapter_ids", _as_tuple(self.adapter_ids))
        object.__setattr__(self, "maintenance_tags", _as_tuple(self.maintenance_tags))
        object.__setattr__(self, "required_next_routes", _as_tuple(self.required_next_routes))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "member_model_ids": list(self.member_model_ids),
            "relation_ids": list(self.relation_ids),
            "relation_types": list(self.relation_types),
            "shared_elements": list(self.shared_elements),
            "variant_elements": list(self.variant_elements),
            "code_paths": list(self.code_paths),
            "test_paths": list(self.test_paths),
            "shared_kernel_ids": list(self.shared_kernel_ids),
            "adapter_ids": list(self.adapter_ids),
            "maintenance_tags": list(self.maintenance_tags),
            "required_next_routes": list(self.required_next_routes),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class ModelSimilarityChangeImpact:
    """Sibling review obligation when a model or code path in a group changes."""

    impact_id: str
    changed_model_id: str
    maintenance_group_id: str
    impacted_model_ids: tuple[str, ...] = ()
    impacted_code_paths: tuple[str, ...] = ()
    impacted_test_paths: tuple[str, ...] = ()
    relation_ids: tuple[str, ...] = ()
    shared_elements: tuple[str, ...] = ()
    variant_elements: tuple[str, ...] = ()
    required_next_routes: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "impact_id", str(self.impact_id))
        object.__setattr__(self, "changed_model_id", str(self.changed_model_id))
        object.__setattr__(self, "maintenance_group_id", str(self.maintenance_group_id))
        object.__setattr__(self, "impacted_model_ids", _as_tuple(self.impacted_model_ids))
        object.__setattr__(self, "impacted_code_paths", _as_tuple(self.impacted_code_paths))
        object.__setattr__(self, "impacted_test_paths", _as_tuple(self.impacted_test_paths))
        object.__setattr__(self, "relation_ids", _as_tuple(self.relation_ids))
        object.__setattr__(self, "shared_elements", _as_tuple(self.shared_elements))
        object.__setattr__(self, "variant_elements", _as_tuple(self.variant_elements))
        object.__setattr__(self, "required_next_routes", _as_tuple(self.required_next_routes))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "impact_id": self.impact_id,
            "changed_model_id": self.changed_model_id,
            "maintenance_group_id": self.maintenance_group_id,
            "impacted_model_ids": list(self.impacted_model_ids),
            "impacted_code_paths": list(self.impacted_code_paths),
            "impacted_test_paths": list(self.impacted_test_paths),
            "relation_ids": list(self.relation_ids),
            "shared_elements": list(self.shared_elements),
            "variant_elements": list(self.variant_elements),
            "required_next_routes": list(self.required_next_routes),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class ModelSimilarityTestObligation:
    """Shared or variant test coverage expected for a maintenance group."""

    obligation_id: str
    maintenance_group_id: str
    obligation_type: str
    model_ids: tuple[str, ...] = ()
    behaviors: tuple[str, ...] = ()
    test_paths: tuple[str, ...] = ()
    relation_ids: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "obligation_id", str(self.obligation_id))
        object.__setattr__(self, "maintenance_group_id", str(self.maintenance_group_id))
        object.__setattr__(self, "obligation_type", str(self.obligation_type))
        object.__setattr__(self, "model_ids", _as_tuple(self.model_ids))
        object.__setattr__(self, "behaviors", _as_tuple(self.behaviors))
        object.__setattr__(self, "test_paths", _as_tuple(self.test_paths))
        object.__setattr__(self, "relation_ids", _as_tuple(self.relation_ids))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "obligation_id": self.obligation_id,
            "maintenance_group_id": self.maintenance_group_id,
            "obligation_type": self.obligation_type,
            "model_ids": list(self.model_ids),
            "behaviors": list(self.behaviors),
            "test_paths": list(self.test_paths),
            "relation_ids": list(self.relation_ids),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class ModelSimilarityCodeObligation:
    """Code-structure or contraction obligation derived from similarity."""

    obligation_id: str
    maintenance_group_id: str = ""
    obligation_type: str = ""
    model_ids: tuple[str, ...] = ()
    relation_ids: tuple[str, ...] = ()
    shared_kernel_owner: str = ""
    adapter_owners: tuple[str, ...] = ()
    code_paths: tuple[str, ...] = ()
    required_next_routes: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "obligation_id", str(self.obligation_id))
        object.__setattr__(self, "maintenance_group_id", str(self.maintenance_group_id))
        object.__setattr__(self, "obligation_type", str(self.obligation_type))
        object.__setattr__(self, "model_ids", _as_tuple(self.model_ids))
        object.__setattr__(self, "relation_ids", _as_tuple(self.relation_ids))
        object.__setattr__(self, "shared_kernel_owner", str(self.shared_kernel_owner))
        object.__setattr__(self, "adapter_owners", _as_tuple(self.adapter_owners))
        object.__setattr__(self, "code_paths", _as_tuple(self.code_paths))
        object.__setattr__(self, "required_next_routes", _as_tuple(self.required_next_routes))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "obligation_id": self.obligation_id,
            "maintenance_group_id": self.maintenance_group_id,
            "obligation_type": self.obligation_type,
            "model_ids": list(self.model_ids),
            "relation_ids": list(self.relation_ids),
            "shared_kernel_owner": self.shared_kernel_owner,
            "adapter_owners": list(self.adapter_owners),
            "code_paths": list(self.code_paths),
            "required_next_routes": list(self.required_next_routes),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class SimilarityHandoff:
    """Compact downstream handoff produced by Model Similarity Consolidation."""

    relation_ids: tuple[str, ...] = ()
    maintenance_group_ids: tuple[str, ...] = ()
    change_impact_ids: tuple[str, ...] = ()
    impacted_model_ids: tuple[str, ...] = ()
    test_obligation_ids: tuple[str, ...] = ()
    code_obligation_ids: tuple[str, ...] = ()
    risk_template_ids: tuple[str, ...] = ()
    known_bad_case_ids: tuple[str, ...] = ()
    evidence_gate_ids: tuple[str, ...] = ()
    same_family_relation_ids: tuple[str, ...] = ()
    evidence_duplicate_relation_ids: tuple[str, ...] = ()
    false_friend_rationales: tuple[str, ...] = ()
    unresolved_gaps: tuple[str, ...] = ()
    recommended_next_routes: tuple[str, ...] = ()
    evidence_current: bool = True
    source_report_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        relation_ids = _as_tuple(self.relation_ids)
        same_family = _as_tuple(self.same_family_relation_ids) or tuple(
            relation_id for relation_id in relation_ids if RELATION_SAME_FAMILY_VARIANT in relation_id
        )
        evidence_duplicate = _as_tuple(self.evidence_duplicate_relation_ids) or tuple(
            relation_id for relation_id in relation_ids if RELATION_EVIDENCE_DUPLICATE in relation_id
        )
        false_friend = _as_tuple(self.false_friend_rationales) or tuple(
            relation_id for relation_id in relation_ids if RELATION_FALSE_FRIEND in relation_id
        )
        object.__setattr__(self, "relation_ids", relation_ids)
        object.__setattr__(self, "maintenance_group_ids", _as_tuple(self.maintenance_group_ids))
        object.__setattr__(self, "change_impact_ids", _as_tuple(self.change_impact_ids))
        object.__setattr__(self, "impacted_model_ids", _as_tuple(self.impacted_model_ids))
        object.__setattr__(self, "test_obligation_ids", _as_tuple(self.test_obligation_ids))
        object.__setattr__(self, "code_obligation_ids", _as_tuple(self.code_obligation_ids))
        object.__setattr__(self, "risk_template_ids", _as_tuple(self.risk_template_ids))
        object.__setattr__(self, "known_bad_case_ids", _as_tuple(self.known_bad_case_ids))
        object.__setattr__(self, "evidence_gate_ids", _as_tuple(self.evidence_gate_ids))
        object.__setattr__(self, "same_family_relation_ids", _unique(same_family))
        object.__setattr__(self, "evidence_duplicate_relation_ids", _unique(evidence_duplicate))
        object.__setattr__(self, "false_friend_rationales", _unique(false_friend))
        object.__setattr__(self, "unresolved_gaps", _as_tuple(self.unresolved_gaps))
        object.__setattr__(self, "recommended_next_routes", _as_tuple(self.recommended_next_routes))
        object.__setattr__(self, "source_report_id", str(self.source_report_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def has_similarity_evidence(self) -> bool:
        return bool(self.relation_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation_ids": list(self.relation_ids),
            "maintenance_group_ids": list(self.maintenance_group_ids),
            "change_impact_ids": list(self.change_impact_ids),
            "impacted_model_ids": list(self.impacted_model_ids),
            "test_obligation_ids": list(self.test_obligation_ids),
            "code_obligation_ids": list(self.code_obligation_ids),
            "risk_template_ids": list(self.risk_template_ids),
            "known_bad_case_ids": list(self.known_bad_case_ids),
            "evidence_gate_ids": list(self.evidence_gate_ids),
            "same_family_relation_ids": list(self.same_family_relation_ids),
            "evidence_duplicate_relation_ids": list(self.evidence_duplicate_relation_ids),
            "false_friend_rationales": list(self.false_friend_rationales),
            "unresolved_gaps": list(self.unresolved_gaps),
            "recommended_next_routes": list(self.recommended_next_routes),
            "evidence_current": self.evidence_current,
            "source_report_id": self.source_report_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


def normalize_similarity_handoff(
    value: SimilarityHandoff | Mapping[str, Any] | None,
) -> SimilarityHandoff | None:
    """Normalize mapping input to the single clean downstream handoff type."""

    if value is None:
        return None
    if isinstance(value, SimilarityHandoff):
        return value
    return SimilarityHandoff(**dict(value))


@dataclass(frozen=True)
class ModelSimilarityReport:
    """Structured model-similarity consolidation review result."""

    ok: bool
    plan_id: str
    decision: str
    relations: tuple[ModelSimilarityRelation, ...] = ()
    maintenance_groups: tuple[ModelSimilarityMaintenanceGroup, ...] = ()
    change_impacts: tuple[ModelSimilarityChangeImpact, ...] = ()
    test_obligations: tuple[ModelSimilarityTestObligation, ...] = ()
    code_obligations: tuple[ModelSimilarityCodeObligation, ...] = ()
    findings: tuple[ModelSimilarityFinding, ...] = ()
    recommended_next_routes: tuple[str, ...] = ()
    risk_template_ids: tuple[str, ...] = ()
    known_bad_case_ids: tuple[str, ...] = ()
    evidence_gate_ids: tuple[str, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "relations", tuple(self.relations))
        object.__setattr__(self, "maintenance_groups", tuple(self.maintenance_groups))
        object.__setattr__(self, "change_impacts", tuple(self.change_impacts))
        object.__setattr__(self, "test_obligations", tuple(self.test_obligations))
        object.__setattr__(self, "code_obligations", tuple(self.code_obligations))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "recommended_next_routes", _as_tuple(self.recommended_next_routes))
        object.__setattr__(self, "risk_template_ids", _as_tuple(self.risk_template_ids))
        object.__setattr__(self, "known_bad_case_ids", _as_tuple(self.known_bad_case_ids))
        object.__setattr__(self, "evidence_gate_ids", _as_tuple(self.evidence_gate_ids))
        if not self.summary:
            object.__setattr__(
                self,
                "summary",
                f"{'OK' if self.ok else 'BLOCKED'}: plan={self.plan_id} decision={self.decision} relations={len(self.relations)} groups={len(self.maintenance_groups)} findings={len(self.findings)}",
            )

    def format_text(self, max_relations: int = 12, max_findings: int = 12) -> str:
        lines = [
            "=== flowguard model similarity consolidation review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"plan: {self.plan_id}",
            f"decision: {self.decision}",
            f"relations: {len(self.relations)}",
            f"maintenance_groups: {len(self.maintenance_groups)}",
            f"change_impacts: {len(self.change_impacts)}",
            f"test_obligations: {len(self.test_obligations)}",
            f"code_obligations: {len(self.code_obligations)}",
            f"findings: {len(self.findings)}",
            f"recommended_next_routes: {', '.join(self.recommended_next_routes) or '(none)'}",
        ]
        for group in self.maintenance_groups[:max_relations]:
            lines.extend(
                [
                    "",
                    f"maintenance_group: {group.group_id}",
                    f"members: {', '.join(group.member_model_ids)}",
                    f"relations: {', '.join(group.relation_ids) or '(none)'}",
                    f"shared: {', '.join(group.shared_elements) or '(none)'}",
                    f"variant: {', '.join(group.variant_elements) or '(none)'}",
                    f"code_paths: {', '.join(group.code_paths) or '(none)'}",
                    f"test_paths: {', '.join(group.test_paths) or '(none)'}",
                ]
            )
        for impact in self.change_impacts[:max_relations]:
            lines.extend(
                [
                    "",
                    f"change_impact: {impact.impact_id}",
                    f"changed_model: {impact.changed_model_id}",
                    f"group: {impact.maintenance_group_id}",
                    f"impacted_models: {', '.join(impact.impacted_model_ids) or '(none)'}",
                    f"impacted_code_paths: {', '.join(impact.impacted_code_paths) or '(none)'}",
                    f"impacted_test_paths: {', '.join(impact.impacted_test_paths) or '(none)'}",
                ]
            )
        for obligation in self.test_obligations[:max_relations]:
            lines.extend(
                [
                    "",
                    f"test_obligation: {obligation.obligation_id}",
                    f"type: {obligation.obligation_type}",
                    f"group: {obligation.maintenance_group_id}",
                    f"models: {', '.join(obligation.model_ids) or '(none)'}",
                    f"behaviors: {', '.join(obligation.behaviors) or '(none)'}",
                    f"test_paths: {', '.join(obligation.test_paths) or '(none)'}",
                ]
            )
        for obligation in self.code_obligations[:max_relations]:
            lines.extend(
                [
                    "",
                    f"code_obligation: {obligation.obligation_id}",
                    f"type: {obligation.obligation_type}",
                    f"group: {obligation.maintenance_group_id or '(none)'}",
                    f"models: {', '.join(obligation.model_ids) or '(none)'}",
                    f"shared_kernel_owner: {obligation.shared_kernel_owner or '(none)'}",
                    f"adapter_owners: {', '.join(obligation.adapter_owners) or '(none)'}",
                    f"code_paths: {', '.join(obligation.code_paths) or '(none)'}",
                ]
            )
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
            "maintenance_groups": [group.to_dict() for group in self.maintenance_groups],
            "change_impacts": [impact.to_dict() for impact in self.change_impacts],
            "test_obligations": [obligation.to_dict() for obligation in self.test_obligations],
            "code_obligations": [obligation.to_dict() for obligation in self.code_obligations],
            "findings": [finding.to_dict() for finding in self.findings],
            "recommended_next_routes": list(self.recommended_next_routes),
            "risk_template_ids": list(self.risk_template_ids),
            "known_bad_case_ids": list(self.known_bad_case_ids),
            "evidence_gate_ids": list(self.evidence_gate_ids),
            "summary": self.summary,
        }

    def to_handoff(self) -> SimilarityHandoff:
        blocker_gaps = tuple(
            f"{finding.code}:{finding.relation_id or finding.model_id or finding.item_id}"
            for finding in self.findings
            if finding.severity == "blocker"
        )
        stale_or_missing_evidence = any(
            finding.code in {"missing_current_similarity_evidence", "stale_similarity_evidence"}
            for finding in self.findings
        )
        return SimilarityHandoff(
            relation_ids=tuple(relation.relation_id for relation in self.relations),
            maintenance_group_ids=tuple(group.group_id for group in self.maintenance_groups),
            change_impact_ids=tuple(impact.impact_id for impact in self.change_impacts),
            impacted_model_ids=_unique(
                tuple(
                    model_id
                    for impact in self.change_impacts
                    for model_id in impact.impacted_model_ids
                )
            ),
            test_obligation_ids=tuple(obligation.obligation_id for obligation in self.test_obligations),
            code_obligation_ids=tuple(obligation.obligation_id for obligation in self.code_obligations),
            risk_template_ids=self.risk_template_ids,
            known_bad_case_ids=self.known_bad_case_ids,
            evidence_gate_ids=self.evidence_gate_ids,
            same_family_relation_ids=tuple(
                relation.relation_id
                for relation in self.relations
                if relation.relation_type == RELATION_SAME_FAMILY_VARIANT
            ),
            evidence_duplicate_relation_ids=tuple(
                relation.relation_id
                for relation in self.relations
                if relation.relation_type == RELATION_EVIDENCE_DUPLICATE
            ),
            false_friend_rationales=tuple(
                relation.rationale or relation.relation_id
                for relation in self.relations
                if relation.relation_type == RELATION_FALSE_FRIEND
            ),
            unresolved_gaps=blocker_gaps,
            recommended_next_routes=self.recommended_next_routes,
            evidence_current=not stale_or_missing_evidence,
            source_report_id=self.plan_id,
        )


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
        ("public_behavior", left.owned_public_behaviors, right.owned_public_behaviors),
        ("business_path", left.business_path_ids, right.business_path_ids),
        ("business_intent", left.business_intents, right.business_intents),
        ("business_terminal", left.path_terminals, right.path_terminals),
        ("maintenance_tag", left.maintenance_tags, right.maintenance_tags),
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
        ("public_behavior", left.owned_public_behaviors, right.owned_public_behaviors),
        ("business_path", left.business_path_ids, right.business_path_ids),
        ("business_intent", left.business_intents, right.business_intents),
        ("business_terminal", left.path_terminals, right.path_terminals),
        ("adapter", left.adapter_ids, right.adapter_ids),
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
        | set(left.owned_public_behaviors)
        | set(left.business_path_ids)
        | set(left.business_intents)
    ).intersection(
        set(right.function_blocks)
        | set(right.state_owned)
        | set(right.side_effects_owned)
        | set(right.failure_modes)
        | set(right.invariants)
        | set(right.contracts_in)
        | set(right.contracts_out)
        | set(right.owned_public_behaviors)
        | set(right.business_path_ids)
        | set(right.business_intents)
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
    business_path_overlap = bool(_intersection(left.business_path_ids, right.business_path_ids))
    business_intent_overlap = bool(_intersection(left.business_intents, right.business_intents))
    business_terminal_overlap = bool(_intersection(left.path_terminals, right.path_terminals))
    business_terminal_divergence = bool(
        (business_path_overlap or business_intent_overlap)
        and left.path_terminals
        and right.path_terminals
        and not business_terminal_overlap
    )
    same_family = bool(left.workflow_family and left.workflow_family == right.workflow_family)
    different_variants = bool(left.variant_id and right.variant_id and left.variant_id != right.variant_id)
    parent_child = left.model_id in right.child_model_ids or right.model_id in left.child_model_ids
    parent_child = parent_child or left.parent_model_id == right.model_id or right.parent_model_id == left.model_id
    same_parent = bool(left.parent_model_id and left.parent_model_id == right.parent_model_id)
    symmetric = bool(set(left.inputs).intersection(right.outputs) and set(left.outputs).intersection(right.inputs))
    false_friend_declared = right.model_id in left.false_friend_model_ids or left.model_id in right.false_friend_model_ids
    same_shared_kernel = bool(left.shared_kernel_id and left.shared_kernel_id == right.shared_kernel_id)

    if business_terminal_divergence:
        return RELATION_FALSE_FRIEND
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
    if business_path_overlap and (state_overlap or side_effect_overlap or function_overlap):
        return RELATION_DUPLICATE_BOUNDARY
    if business_intent_overlap and business_terminal_overlap and (state_overlap or side_effect_overlap or function_overlap):
        return RELATION_DUPLICATE_BOUNDARY
    if business_path_overlap or (business_intent_overlap and business_terminal_overlap):
        return RELATION_SAME_WORKFLOW
    if function_overlap and (state_overlap or side_effect_overlap) and (same_family or failure_overlap):
        return RELATION_DUPLICATE_BOUNDARY
    if state_overlap or side_effect_overlap:
        return RELATION_OVERLAPPING_OWNERSHIP
    if symmetric:
        return RELATION_SYMMETRIC_FLOW
    if same_shared_kernel and (function_overlap or failure_overlap or invariant_overlap):
        return RELATION_SHARED_KERNEL
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
            bool(_intersection(left.owned_public_behaviors, right.owned_public_behaviors)),
            business_path_overlap,
            business_intent_overlap and business_terminal_overlap,
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


GROUPING_RELATION_TYPES = {
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
}


def _group_id(member_model_ids: Sequence[str]) -> str:
    return "maintenance:" + "+".join(sorted(member_model_ids))


def _model_by_code_path(
    signatures_by_id: Mapping[str, ModelSignature],
    changed_code_paths: Sequence[str],
) -> tuple[str, ...]:
    changed = set(changed_code_paths)
    if not changed:
        return ()
    model_ids: list[str] = []
    for model_id, signature in signatures_by_id.items():
        if changed.intersection(signature.code_paths):
            model_ids.append(model_id)
    return tuple(sorted(model_ids))


def _signature_shared_elements(signatures: Sequence[ModelSignature]) -> tuple[str, ...]:
    if not signatures:
        return ()
    shared_sets = [set(signature.comparable_elements()) for signature in signatures]
    shared = set.intersection(*shared_sets) if shared_sets else set()
    return tuple(sorted(shared))


def _signature_variant_elements(signatures: Sequence[ModelSignature], shared: Sequence[str]) -> tuple[str, ...]:
    shared_set = set(shared)
    variants: list[str] = []
    for signature in signatures:
        for item in sorted(set(signature.comparable_elements()) - shared_set):
            variants.append(f"{signature.model_id}:{item}")
        if signature.variant_id:
            variants.append(f"{signature.model_id}:variant:{signature.variant_id}")
        for adapter_id in signature.adapter_ids:
            variants.append(f"{signature.model_id}:adapter:{adapter_id}")
    return _unique(variants)


def _relations_for_members(
    relations: Sequence[ModelSimilarityRelation],
    member_ids: Sequence[str],
) -> tuple[ModelSimilarityRelation, ...]:
    members = set(member_ids)
    return tuple(
        relation
        for relation in relations
        if relation.left_model_id in members and relation.right_model_id in members
    )


def _derive_maintenance_groups(
    signatures_by_id: Mapping[str, ModelSignature],
    relations: Sequence[ModelSimilarityRelation],
) -> tuple[ModelSimilarityMaintenanceGroup, ...]:
    parents: dict[str, str] = {model_id: model_id for model_id in signatures_by_id}

    def find(model_id: str) -> str:
        parent = parents[model_id]
        if parent != model_id:
            parents[model_id] = find(parent)
        return parents[model_id]

    def union(left_id: str, right_id: str) -> None:
        left_root = find(left_id)
        right_root = find(right_id)
        if left_root != right_root:
            parents[right_root] = left_root

    for relation in relations:
        if relation.relation_type in GROUPING_RELATION_TYPES and relation.confidence != CONFIDENCE_BLOCKED:
            if relation.left_model_id in parents and relation.right_model_id in parents:
                union(relation.left_model_id, relation.right_model_id)

    components: dict[str, list[str]] = {}
    for model_id in sorted(signatures_by_id):
        components.setdefault(find(model_id), []).append(model_id)

    groups: list[ModelSimilarityMaintenanceGroup] = []
    for member_ids in sorted((tuple(sorted(ids)) for ids in components.values()), key=lambda item: item[0]):
        if len(member_ids) < 2:
            continue
        signatures = tuple(signatures_by_id[model_id] for model_id in member_ids)
        group_relations = _relations_for_members(relations, member_ids)
        shared = _signature_shared_elements(signatures)
        variants = _signature_variant_elements(signatures, shared)
        groups.append(
            ModelSimilarityMaintenanceGroup(
                group_id=_group_id(member_ids),
                member_model_ids=member_ids,
                relation_ids=_unique([relation.relation_id for relation in group_relations]),
                relation_types=_unique([relation.relation_type for relation in group_relations]),
                shared_elements=shared,
                variant_elements=variants,
                code_paths=_unique([path for signature in signatures for path in signature.code_paths]),
                test_paths=_unique([path for signature in signatures for path in signature.test_paths]),
                shared_kernel_ids=_unique(
                    [signature.shared_kernel_id for signature in signatures if signature.shared_kernel_id]
                ),
                adapter_ids=_unique([adapter for signature in signatures for adapter in signature.adapter_ids]),
                maintenance_tags=_unique([tag for signature in signatures for tag in signature.maintenance_tags]),
                required_next_routes=_unique(
                    [route for relation in group_relations for route in relation.required_next_routes]
                ),
                rationale="Connected model-similarity relations require these models to be maintained together.",
            )
        )
    return tuple(groups)


def _derive_change_impacts(
    plan: ModelSimilarityPlan,
    signatures_by_id: Mapping[str, ModelSignature],
    groups: Sequence[ModelSimilarityMaintenanceGroup],
) -> tuple[ModelSimilarityChangeImpact, tuple[ModelSimilarityFinding, ...]]:
    findings: list[ModelSimilarityFinding] = []
    changed_model_ids = set(plan.changed_model_ids)
    changed_model_ids.update(_model_by_code_path(signatures_by_id, plan.changed_code_paths))
    for model_id in plan.changed_model_ids:
        if model_id not in signatures_by_id:
            findings.append(
                ModelSimilarityFinding(
                    "unknown_changed_model",
                    "changed model id is not registered in the similarity plan",
                    model_id=model_id,
                )
            )

    impacts: list[ModelSimilarityChangeImpact] = []
    for group in groups:
        group_members = set(group.member_model_ids)
        for changed_model_id in sorted(group_members.intersection(changed_model_ids)):
            impacted = tuple(model_id for model_id in group.member_model_ids if model_id != changed_model_id)
            impacted_signatures = [signatures_by_id[model_id] for model_id in impacted]
            impacts.append(
                ModelSimilarityChangeImpact(
                    impact_id=f"{group.group_id}:{changed_model_id}:change-impact",
                    changed_model_id=changed_model_id,
                    maintenance_group_id=group.group_id,
                    impacted_model_ids=impacted,
                    impacted_code_paths=_unique(
                        [path for signature in impacted_signatures for path in signature.code_paths]
                    ),
                    impacted_test_paths=_unique(
                        [path for signature in impacted_signatures for path in signature.test_paths]
                    ),
                    relation_ids=group.relation_ids,
                    shared_elements=group.shared_elements,
                    variant_elements=group.variant_elements,
                    required_next_routes=group.required_next_routes,
                    rationale="A changed member of a similarity maintenance group requires sibling code and test review.",
                )
            )
    return tuple(impacts), tuple(findings)


def _derive_test_obligations(
    plan: ModelSimilarityPlan,
    signatures_by_id: Mapping[str, ModelSignature],
    groups: Sequence[ModelSimilarityMaintenanceGroup],
) -> tuple[tuple[ModelSimilarityTestObligation, ...], tuple[ModelSimilarityFinding, ...]]:
    obligations: list[ModelSimilarityTestObligation] = []
    findings: list[ModelSimilarityFinding] = []
    for group in groups:
        if group.shared_elements:
            obligations.append(
                ModelSimilarityTestObligation(
                    obligation_id=f"{group.group_id}:shared-tests",
                    maintenance_group_id=group.group_id,
                    obligation_type="shared_behavior_tests",
                    model_ids=group.member_model_ids,
                    behaviors=group.shared_elements,
                    test_paths=group.test_paths,
                    relation_ids=group.relation_ids,
                    rationale="Shared behavior in a maintenance group needs tests that prove the family, not only one member.",
                )
            )
        if group.variant_elements:
            obligations.append(
                ModelSimilarityTestObligation(
                    obligation_id=f"{group.group_id}:variant-tests",
                    maintenance_group_id=group.group_id,
                    obligation_type="variant_behavior_tests",
                    model_ids=group.member_model_ids,
                    behaviors=group.variant_elements,
                    test_paths=group.test_paths,
                    relation_ids=group.relation_ids,
                    rationale="Variant-specific behavior needs per-member tests so shared-kernel work does not erase differences.",
                )
            )
        for model_id in group.member_model_ids:
            signature = signatures_by_id[model_id]
            if not signature.test_paths:
                findings.append(
                    ModelSimilarityFinding(
                        "missing_maintenance_test_path",
                        "model is in a similarity maintenance group but declares no test paths",
                        severity="blocker" if plan.require_maintenance_test_paths else "warning",
                        model_id=model_id,
                        item_id=group.group_id,
                    )
                )
    return tuple(obligations), tuple(findings)


def _group_for_relation(
    groups: Sequence[ModelSimilarityMaintenanceGroup],
    relation: ModelSimilarityRelation,
) -> str:
    for group in groups:
        if relation.relation_id in group.relation_ids:
            return group.group_id
    return ""


def _shared_kernel_owner(
    signatures: Sequence[ModelSignature],
    group_id: str,
) -> str:
    kernels = _unique([signature.shared_kernel_id for signature in signatures if signature.shared_kernel_id])
    if kernels:
        return kernels[0]
    families = _unique([signature.workflow_family for signature in signatures if signature.workflow_family])
    if families:
        return f"{families[0]}_shared_kernel"
    return f"{group_id}:shared_kernel"


def _derive_code_obligations(
    signatures_by_id: Mapping[str, ModelSignature],
    relations: Sequence[ModelSimilarityRelation],
    groups: Sequence[ModelSimilarityMaintenanceGroup],
) -> tuple[ModelSimilarityCodeObligation, ...]:
    obligations: list[ModelSimilarityCodeObligation] = []
    for group in groups:
        if group.shared_kernel_ids or group.adapter_ids:
            obligations.append(
                ModelSimilarityCodeObligation(
                    obligation_id=f"{group.group_id}:shared-kernel",
                    maintenance_group_id=group.group_id,
                    obligation_type="shared_kernel_or_adapter",
                    model_ids=group.member_model_ids,
                    relation_ids=group.relation_ids,
                    shared_kernel_owner=group.shared_kernel_ids[0]
                    if group.shared_kernel_ids
                    else _shared_kernel_owner(
                        [signatures_by_id[model_id] for model_id in group.member_model_ids],
                        group.group_id,
                    ),
                    adapter_owners=group.adapter_ids,
                    code_paths=group.code_paths,
                    required_next_routes=group.required_next_routes,
                    rationale="The maintenance group declares shared-kernel or adapter metadata that should drive code structure review.",
                )
            )
    for relation in relations:
        model_ids = (relation.left_model_id, relation.right_model_id)
        signatures = tuple(signatures_by_id[model_id] for model_id in model_ids if model_id in signatures_by_id)
        group_id = _group_for_relation(groups, relation)
        code_paths = _unique([path for signature in signatures for path in signature.code_paths])
        adapter_owners = _unique(
            [
                owner
                for signature in signatures
                for owner in (signature.adapter_ids or ((f"{signature.model_id}:{signature.variant_id}",) if signature.variant_id else ()))
            ]
        )
        if relation.relation_type in {RELATION_SHARED_KERNEL, RELATION_SYMMETRIC_FLOW, RELATION_ADAPTER_ONLY}:
            obligations.append(
                ModelSimilarityCodeObligation(
                    obligation_id=f"{relation.relation_id}:shared-kernel",
                    maintenance_group_id=group_id,
                    obligation_type="shared_kernel_or_adapter",
                    model_ids=model_ids,
                    relation_ids=(relation.relation_id,),
                    shared_kernel_owner=_shared_kernel_owner(signatures, group_id or relation.relation_id),
                    adapter_owners=adapter_owners,
                    code_paths=code_paths,
                    required_next_routes=relation.required_next_routes,
                    rationale="Similarity suggests a shared kernel with variant or adapter owners, subject to downstream structure evidence.",
                )
            )
        if relation.relation_type in {RELATION_DUPLICATE_BOUNDARY, RELATION_ADAPTER_ONLY}:
            obligations.append(
                ModelSimilarityCodeObligation(
                    obligation_id=f"{relation.relation_id}:duplicate-boundary",
                    maintenance_group_id=group_id,
                    obligation_type="duplicate_boundary_contraction",
                    model_ids=model_ids,
                    relation_ids=(relation.relation_id,),
                    adapter_owners=adapter_owners,
                    code_paths=code_paths,
                    required_next_routes=relation.required_next_routes,
                    rationale="Duplicate or adapter-only boundaries are maintenance debt until Architecture Reduction evidence proves contraction is safe.",
                )
            )
        if relation.relation_type in {RELATION_OVERLAPPING_OWNERSHIP, RELATION_SIBLING_OVERLAP, RELATION_PARENT_CHILD}:
            obligations.append(
                ModelSimilarityCodeObligation(
                    obligation_id=f"{relation.relation_id}:ownership-overlap",
                    maintenance_group_id=group_id,
                    obligation_type="ownership_overlap_review",
                    model_ids=model_ids,
                    relation_ids=(relation.relation_id,),
                    code_paths=code_paths,
                    required_next_routes=relation.required_next_routes,
                    rationale="Overlapping ownership needs model-mesh review before one side is treated as safely maintained.",
                )
            )
        if relation.relation_type == RELATION_FALSE_FRIEND:
            obligations.append(
                ModelSimilarityCodeObligation(
                    obligation_id=f"{relation.relation_id}:false-friend-quarantine",
                    obligation_type="false_friend_quarantine",
                    model_ids=model_ids,
                    relation_ids=(relation.relation_id,),
                    code_paths=code_paths,
                    required_next_routes=relation.required_next_routes,
                    rationale="False-friend similarity keeps code and test maintenance separate unless manual review proves otherwise.",
                )
            )
    return tuple(obligations)


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

    maintenance_groups = _derive_maintenance_groups(signatures_by_id, relations)
    change_impacts, impact_findings = _derive_change_impacts(plan, signatures_by_id, maintenance_groups)
    test_obligations, test_findings = _derive_test_obligations(plan, signatures_by_id, maintenance_groups)
    code_obligations = _derive_code_obligations(signatures_by_id, relations, maintenance_groups)
    findings.extend(impact_findings)
    findings.extend(test_findings)

    recommended_routes = tuple(
        sorted(
            {
                route
                for relation in relations
                if relation.confidence != CONFIDENCE_BLOCKED
                for route in relation.required_next_routes
            }
            | {route for group in maintenance_groups for route in group.required_next_routes}
            | {route for impact in change_impacts for route in impact.required_next_routes}
            | {route for obligation in code_obligations for route in obligation.required_next_routes}
        )
    )
    decision = _decision_for(relations, findings)
    blockers = _blocker_findings(findings)
    risk_template_ids = _unique(
        item
        for signature in signatures_by_id.values()
        for item in signature.risk_template_ids
    )
    known_bad_case_ids = _unique(
        item
        for signature in signatures_by_id.values()
        for item in signature.known_bad_case_ids
    )
    evidence_gate_ids = _unique(
        item
        for signature in signatures_by_id.values()
        for item in signature.evidence_gate_ids
    )
    return ModelSimilarityReport(
        ok=not blockers,
        plan_id=plan.plan_id,
        decision=decision,
        relations=tuple(relations),
        maintenance_groups=maintenance_groups,
        change_impacts=change_impacts,
        test_obligations=test_obligations,
        code_obligations=code_obligations,
        findings=tuple(findings),
        recommended_next_routes=recommended_routes,
        risk_template_ids=risk_template_ids,
        known_bad_case_ids=known_bad_case_ids,
        evidence_gate_ids=evidence_gate_ids,
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
    "ModelSimilarityChangeImpact",
    "ModelSimilarityCodeObligation",
    "ModelSimilarityEvidence",
    "ModelSimilarityFinding",
    "ModelSimilarityMaintenanceGroup",
    "ModelSimilarityPlan",
    "ModelSimilarityRelation",
    "ModelSimilarityReport",
    "ModelSimilarityTestObligation",
    "SimilarityHandoff",
    "model_signature_maintenance",
    "model_signature_minimal",
    "model_similarity_plan_for_changed_member",
    "normalize_similarity_handoff",
    "review_model_similarity_consolidation",
]
