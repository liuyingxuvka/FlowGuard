"""Model-derived code structure recommendation helpers.

Code structure recommendation turns a FlowGuard functional model into an
implementation-structure proposal. It does not write production code and it is
not behavior proof; it is structured design evidence that other helpers, such
as StructureMesh, can review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .export import to_jsonable


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


def _as_pairs(values: Sequence[tuple[str, str]] | None) -> tuple[tuple[str, str], ...]:
    if values is None:
        return ()
    return tuple((str(left), str(right)) for left, right in values)


def _pair_map(pairs: Sequence[tuple[str, str]]) -> dict[str, str]:
    return {str(key): str(value) for key, value in pairs}


@dataclass(frozen=True)
class TargetModuleRecommendation:
    """One target child module proposed by a functional model."""

    module_id: str
    path: str = ""
    layer: str = "child"
    owns_function_blocks: tuple[str, ...] = ()
    owns_state: tuple[str, ...] = ()
    owns_side_effects: tuple[str, ...] = ()
    owns_config: tuple[str, ...] = ()
    public_entrypoints: tuple[str, ...] = ()
    validation_boundaries: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "module_id", str(self.module_id))
        object.__setattr__(self, "path", str(self.path))
        object.__setattr__(self, "layer", str(self.layer))
        object.__setattr__(self, "owns_function_blocks", _as_tuple(self.owns_function_blocks))
        object.__setattr__(self, "owns_state", _as_tuple(self.owns_state))
        object.__setattr__(self, "owns_side_effects", _as_tuple(self.owns_side_effects))
        object.__setattr__(self, "owns_config", _as_tuple(self.owns_config))
        object.__setattr__(self, "public_entrypoints", _as_tuple(self.public_entrypoints))
        object.__setattr__(self, "validation_boundaries", _as_tuple(self.validation_boundaries))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_id": self.module_id,
            "path": self.path,
            "layer": self.layer,
            "owns_function_blocks": list(self.owns_function_blocks),
            "owns_state": list(self.owns_state),
            "owns_side_effects": list(self.owns_side_effects),
            "owns_config": list(self.owns_config),
            "public_entrypoints": list(self.public_entrypoints),
            "validation_boundaries": list(self.validation_boundaries),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class CodeStructureRecommendation:
    """Recommended code structure derived from a FlowGuard functional model."""

    recommendation_id: str
    source_model_id: str
    parent_module_id: str
    target_modules: tuple[TargetModuleRecommendation, ...] = ()
    source_model_path: str = ""
    source_model_evidence_tier: str = "abstract_green"
    function_block_map: tuple[tuple[str, str], ...] = ()
    state_owner_map: tuple[tuple[str, str], ...] = ()
    side_effect_owner_map: tuple[tuple[str, str], ...] = ()
    config_owner_map: tuple[tuple[str, str], ...] = ()
    public_entrypoint_map: tuple[tuple[str, str], ...] = ()
    facade_module_id: str = ""
    similarity_relation_ids: tuple[str, ...] = ()
    similarity_maintenance_group_ids: tuple[str, ...] = ()
    similarity_code_obligation_ids: tuple[str, ...] = ()
    shared_kernel_module_id: str = ""
    variant_adapter_module_ids: tuple[str, ...] = ()
    validation_boundaries: tuple[str, ...] = ()
    rationale: str = ""
    hierarchical_model_used: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "recommendation_id", str(self.recommendation_id))
        object.__setattr__(self, "source_model_id", str(self.source_model_id))
        object.__setattr__(self, "parent_module_id", str(self.parent_module_id))
        object.__setattr__(self, "target_modules", tuple(self.target_modules))
        object.__setattr__(self, "source_model_path", str(self.source_model_path))
        object.__setattr__(self, "source_model_evidence_tier", str(self.source_model_evidence_tier))
        object.__setattr__(self, "function_block_map", _as_pairs(self.function_block_map))
        object.__setattr__(self, "state_owner_map", _as_pairs(self.state_owner_map))
        object.__setattr__(self, "side_effect_owner_map", _as_pairs(self.side_effect_owner_map))
        object.__setattr__(self, "config_owner_map", _as_pairs(self.config_owner_map))
        object.__setattr__(self, "public_entrypoint_map", _as_pairs(self.public_entrypoint_map))
        object.__setattr__(self, "facade_module_id", str(self.facade_module_id))
        object.__setattr__(self, "similarity_relation_ids", _as_tuple(self.similarity_relation_ids))
        object.__setattr__(
            self,
            "similarity_maintenance_group_ids",
            _as_tuple(self.similarity_maintenance_group_ids),
        )
        object.__setattr__(
            self,
            "similarity_code_obligation_ids",
            _as_tuple(self.similarity_code_obligation_ids),
        )
        object.__setattr__(self, "shared_kernel_module_id", str(self.shared_kernel_module_id))
        object.__setattr__(self, "variant_adapter_module_ids", _as_tuple(self.variant_adapter_module_ids))
        object.__setattr__(self, "validation_boundaries", _as_tuple(self.validation_boundaries))
        object.__setattr__(self, "rationale", str(self.rationale))

    def module_ids(self) -> tuple[str, ...]:
        return tuple(module.module_id for module in self.target_modules)

    def function_block_owners(self) -> dict[str, str]:
        return _pair_map(self.function_block_map)

    def state_owners(self) -> dict[str, str]:
        return _pair_map(self.state_owner_map)

    def side_effect_owners(self) -> dict[str, str]:
        return _pair_map(self.side_effect_owner_map)

    def config_owners(self) -> dict[str, str]:
        return _pair_map(self.config_owner_map)

    def public_entrypoint_owners(self) -> dict[str, str]:
        return _pair_map(self.public_entrypoint_map)

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "source_model_id": self.source_model_id,
            "parent_module_id": self.parent_module_id,
            "target_modules": [module.to_dict() for module in self.target_modules],
            "source_model_path": self.source_model_path,
            "source_model_evidence_tier": self.source_model_evidence_tier,
            "function_block_map": [list(pair) for pair in self.function_block_map],
            "state_owner_map": [list(pair) for pair in self.state_owner_map],
            "side_effect_owner_map": [list(pair) for pair in self.side_effect_owner_map],
            "config_owner_map": [list(pair) for pair in self.config_owner_map],
            "public_entrypoint_map": [list(pair) for pair in self.public_entrypoint_map],
            "facade_module_id": self.facade_module_id,
            "similarity_relation_ids": list(self.similarity_relation_ids),
            "similarity_maintenance_group_ids": list(self.similarity_maintenance_group_ids),
            "similarity_code_obligation_ids": list(self.similarity_code_obligation_ids),
            "shared_kernel_module_id": self.shared_kernel_module_id,
            "variant_adapter_module_ids": list(self.variant_adapter_module_ids),
            "validation_boundaries": list(self.validation_boundaries),
            "rationale": self.rationale,
            "hierarchical_model_used": self.hierarchical_model_used,
        }


@dataclass(frozen=True)
class CodeStructureFinding:
    """One finding from reviewing a code structure recommendation."""

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
class CodeStructureRecommendationReport:
    """Structured review result for a code structure recommendation."""

    ok: bool
    recommendation_id: str
    findings: tuple[CodeStructureFinding, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "recommendation_id", str(self.recommendation_id))
        object.__setattr__(self, "findings", tuple(self.findings))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: recommendation={self.recommendation_id} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard code structure recommendation review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"recommendation: {self.recommendation_id}",
            f"findings: {len(self.findings)}",
        ]
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
            "recommendation_id": self.recommendation_id,
            "findings": [finding.to_dict() for finding in self.findings],
            "summary": self.summary,
        }


def _blocker_findings(findings: Sequence[CodeStructureFinding]) -> tuple[CodeStructureFinding, ...]:
    return tuple(finding for finding in findings if finding.severity == "blocker")


def _duplicate_pair_keys(
    pairs: Sequence[tuple[str, str]],
    *,
    code: str,
    noun: str,
) -> list[CodeStructureFinding]:
    findings: list[CodeStructureFinding] = []
    owners: dict[str, list[str]] = {}
    for item_id, module_id in pairs:
        owners.setdefault(item_id, []).append(module_id)
    for item_id, module_ids in sorted(owners.items()):
        if len(set(module_ids)) > 1:
            findings.append(
                CodeStructureFinding(
                    code,
                    f"{noun} {item_id} has multiple recommended owners",
                    item_id=item_id,
                    metadata={"owners": sorted(set(module_ids))},
                )
            )
    return findings


def review_code_structure_recommendation(
    recommendation: CodeStructureRecommendation,
) -> CodeStructureRecommendationReport:
    """Review a model-derived implementation-structure recommendation."""

    findings: list[CodeStructureFinding] = []
    module_ids = set(recommendation.module_ids())
    if not recommendation.source_model_id:
        findings.append(
            CodeStructureFinding(
                "missing_source_model",
                "code structure recommendation has no FlowGuard source model id",
            )
        )
    if not recommendation.parent_module_id:
        findings.append(
            CodeStructureFinding(
                "missing_parent_boundary",
                "code structure recommendation has no parent module boundary",
            )
        )
    if not recommendation.target_modules:
        findings.append(
            CodeStructureFinding(
                "missing_target_modules",
                "code structure recommendation has no target modules",
            )
        )
    if not recommendation.function_block_map:
        findings.append(
            CodeStructureFinding(
                "missing_function_block_map",
                "code structure recommendation maps no FunctionBlocks to target modules",
            )
        )
    if not recommendation.validation_boundaries:
        findings.append(
            CodeStructureFinding(
                "missing_validation_plan",
                "code structure recommendation has no validation boundary plan",
            )
        )
    if not recommendation.rationale:
        findings.append(
            CodeStructureFinding(
                "missing_structure_rationale",
                "code structure recommendation has no rationale for the target split",
            )
        )

    for module in recommendation.target_modules:
        if not module.module_id:
            findings.append(
                CodeStructureFinding(
                    "missing_target_module_id",
                    "target module recommendation has no module id",
                    metadata=module.to_dict(),
                )
            )
        if not module.rationale:
            findings.append(
                CodeStructureFinding(
                    "missing_module_rationale",
                    f"target module {module.module_id} has no grouping rationale",
                    module_id=module.module_id,
                    metadata=module.to_dict(),
                )
            )

    if recommendation.similarity_relation_ids:
        false_friend_relations = tuple(
            relation_id
            for relation_id in recommendation.similarity_relation_ids
            if "false_friend" in relation_id
        )
        if false_friend_relations:
            findings.append(
                CodeStructureFinding(
                    "false_friend_similarity_blocks_shared_structure",
                    "false-friend similarity relations cannot derive a shared module without manual review",
                    metadata={"similarity_relation_ids": false_friend_relations},
                )
            )
        if recommendation.shared_kernel_module_id and recommendation.shared_kernel_module_id not in module_ids:
            findings.append(
                CodeStructureFinding(
                    "shared_kernel_module_not_registered",
                    "similarity-derived shared kernel owner is not a registered target module",
                    module_id=recommendation.shared_kernel_module_id,
                    metadata={"similarity_relation_ids": list(recommendation.similarity_relation_ids)},
                )
            )
        for module_id in recommendation.variant_adapter_module_ids:
            if module_id not in module_ids:
                findings.append(
                    CodeStructureFinding(
                        "variant_adapter_module_not_registered",
                        "similarity-derived variant adapter owner is not a registered target module",
                        module_id=module_id,
                        metadata={"similarity_relation_ids": list(recommendation.similarity_relation_ids)},
                    )
                )
        if (
            recommendation.shared_kernel_module_id
            and recommendation.variant_adapter_module_ids
            and not recommendation.similarity_code_obligation_ids
        ):
            findings.append(
                CodeStructureFinding(
                    "missing_similarity_code_obligation",
                    "similarity-derived shared-kernel structure should cite the code maintenance obligation that named the kernel and adapters",
                    severity="warning",
                    module_id=recommendation.shared_kernel_module_id,
                    metadata={"similarity_relation_ids": list(recommendation.similarity_relation_ids)},
                )
            )
        if recommendation.similarity_maintenance_group_ids and not recommendation.similarity_code_obligation_ids:
            findings.append(
                CodeStructureFinding(
                    "missing_similarity_group_code_obligation",
                    "a similarity maintenance group used for code structure should cite the code obligation that drives shared-kernel or adapter ownership",
                    severity="warning",
                    metadata={"similarity_maintenance_group_ids": list(recommendation.similarity_maintenance_group_ids)},
                )
            )

    all_pairs = (
        ("function_block_owner_not_registered", "FunctionBlock", recommendation.function_block_map),
        ("state_owner_not_registered", "state", recommendation.state_owner_map),
        ("side_effect_owner_not_registered", "side effect", recommendation.side_effect_owner_map),
        ("config_owner_not_registered", "config", recommendation.config_owner_map),
        ("entrypoint_owner_not_registered", "public entrypoint", recommendation.public_entrypoint_map),
    )
    for code, noun, pairs in all_pairs:
        for item_id, module_id in pairs:
            if module_id not in module_ids:
                findings.append(
                    CodeStructureFinding(
                        code,
                        f"{noun} {item_id} is assigned to unregistered target module {module_id}",
                        module_id=module_id,
                        item_id=item_id,
                    )
                )

    findings.extend(
        _duplicate_pair_keys(
            recommendation.function_block_map,
            code="duplicate_function_block_owner",
            noun="FunctionBlock",
        )
    )
    findings.extend(
        _duplicate_pair_keys(
            recommendation.state_owner_map,
            code="duplicate_state_recommendation_owner",
            noun="state",
        )
    )
    findings.extend(
        _duplicate_pair_keys(
            recommendation.side_effect_owner_map,
            code="duplicate_side_effect_recommendation_owner",
            noun="side effect",
        )
    )
    findings.extend(
        _duplicate_pair_keys(
            recommendation.config_owner_map,
            code="duplicate_config_recommendation_owner",
            noun="config",
        )
    )
    blockers = _blocker_findings(findings)
    return CodeStructureRecommendationReport(
        ok=not blockers,
        recommendation_id=recommendation.recommendation_id,
        findings=tuple(findings),
    )


__all__ = [
    "CodeStructureFinding",
    "CodeStructureRecommendation",
    "CodeStructureRecommendationReport",
    "TargetModuleRecommendation",
    "review_code_structure_recommendation",
]
