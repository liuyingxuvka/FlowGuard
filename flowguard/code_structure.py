"""Model-derived code structure recommendation helpers.

Code structure recommendation turns a FlowGuard functional model into an
implementation-structure proposal. It does not write production code and it is
not behavior proof; it is structured design evidence that other helpers, such
as StructureMesh, can review.

Model kit: ``add_target_module`` and ``move_responsibility`` are plan edits,
``code_structure_explorer`` explores them with the existing reviews as
invariants, and ``code_structure_code_facts`` compares the target plan with the
real code and the project map.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

from ._normalization import string_sequence as _as_tuple
from .export import to_jsonable
from .canonical_relation import (
    RELATION_FALSE_FRIEND,
    CanonicalRelationHandoff,
    normalize_canonical_relation_handoff,
)


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
    owns_fields: tuple[str, ...] = ()
    reads_fields: tuple[str, ...] = ()
    writes_fields: tuple[str, ...] = ()
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
        object.__setattr__(self, "owns_fields", _as_tuple(self.owns_fields))
        object.__setattr__(self, "reads_fields", _as_tuple(self.reads_fields))
        object.__setattr__(self, "writes_fields", _as_tuple(self.writes_fields))
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
            "owns_fields": list(self.owns_fields),
            "reads_fields": list(self.reads_fields),
            "writes_fields": list(self.writes_fields),
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
    function_block_map: tuple[tuple[str, str], ...] = ()
    state_owner_map: tuple[tuple[str, str], ...] = ()
    side_effect_owner_map: tuple[tuple[str, str], ...] = ()
    config_owner_map: tuple[tuple[str, str], ...] = ()
    field_owner_map: tuple[tuple[str, str], ...] = ()
    field_reader_map: tuple[tuple[str, str], ...] = ()
    field_writer_map: tuple[tuple[str, str], ...] = ()
    public_entrypoint_map: tuple[tuple[str, str], ...] = ()
    facade_module_id: str = ""
    canonical_relation_handoff: CanonicalRelationHandoff | Mapping[str, Any] | None = None
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
        object.__setattr__(self, "function_block_map", _as_pairs(self.function_block_map))
        object.__setattr__(self, "state_owner_map", _as_pairs(self.state_owner_map))
        object.__setattr__(self, "side_effect_owner_map", _as_pairs(self.side_effect_owner_map))
        object.__setattr__(self, "config_owner_map", _as_pairs(self.config_owner_map))
        object.__setattr__(self, "field_owner_map", _as_pairs(self.field_owner_map))
        object.__setattr__(self, "field_reader_map", _as_pairs(self.field_reader_map))
        object.__setattr__(self, "field_writer_map", _as_pairs(self.field_writer_map))
        object.__setattr__(self, "public_entrypoint_map", _as_pairs(self.public_entrypoint_map))
        object.__setattr__(self, "facade_module_id", str(self.facade_module_id))
        object.__setattr__(
            self,
            "canonical_relation_handoff",
            normalize_canonical_relation_handoff(self.canonical_relation_handoff),
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

    def field_owners(self) -> dict[str, str]:
        return _pair_map(self.field_owner_map)

    def field_readers(self) -> dict[str, str]:
        return _pair_map(self.field_reader_map)

    def field_writers(self) -> dict[str, str]:
        return _pair_map(self.field_writer_map)

    def public_entrypoint_owners(self) -> dict[str, str]:
        return _pair_map(self.public_entrypoint_map)

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "source_model_id": self.source_model_id,
            "parent_module_id": self.parent_module_id,
            "target_modules": [module.to_dict() for module in self.target_modules],
            "source_model_path": self.source_model_path,
            "function_block_map": [list(pair) for pair in self.function_block_map],
            "state_owner_map": [list(pair) for pair in self.state_owner_map],
            "side_effect_owner_map": [list(pair) for pair in self.side_effect_owner_map],
            "config_owner_map": [list(pair) for pair in self.config_owner_map],
            "field_owner_map": [list(pair) for pair in self.field_owner_map],
            "field_reader_map": [list(pair) for pair in self.field_reader_map],
            "field_writer_map": [list(pair) for pair in self.field_writer_map],
            "public_entrypoint_map": [list(pair) for pair in self.public_entrypoint_map],
            "facade_module_id": self.facade_module_id,
            "canonical_relation_handoff": self.canonical_relation_handoff.to_dict()
            if self.canonical_relation_handoff
            else None,
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

    canonical_relation_handoff = recommendation.canonical_relation_handoff
    relation_ids = canonical_relation_handoff.relation_ids if canonical_relation_handoff else ()
    relation_code_obligation_ids = canonical_relation_handoff.code_obligation_ids if canonical_relation_handoff else ()
    relation_group_ids = canonical_relation_handoff.relation_group_ids if canonical_relation_handoff else ()

    for gap_id in canonical_relation_handoff.gap_ids if canonical_relation_handoff else ():
        findings.append(
            CodeStructureFinding(
                "canonical_relation_gap_unresolved",
                "code structure cannot derive ownership while an affected relation gap remains",
                item_id=gap_id,
                metadata=canonical_relation_handoff.to_dict(),
            )
        )

    if relation_ids:
        false_friend_relations = canonical_relation_handoff.relation_ids_of_type(
            RELATION_FALSE_FRIEND
        )
        if false_friend_relations:
            findings.append(
                CodeStructureFinding(
                    "false_friend_relation_blocks_shared_structure",
                    "false-friend canonical relations cannot derive a shared module without manual review",
                    metadata={"relation_ids": false_friend_relations},
                )
            )
        if recommendation.shared_kernel_module_id and recommendation.shared_kernel_module_id not in module_ids:
            findings.append(
                CodeStructureFinding(
                    "shared_kernel_module_not_registered",
                    "canonical-relation-derived shared kernel owner is not a registered target module",
                    module_id=recommendation.shared_kernel_module_id,
                    metadata={"relation_ids": list(relation_ids)},
                )
            )
        for module_id in recommendation.variant_adapter_module_ids:
            if module_id not in module_ids:
                findings.append(
                    CodeStructureFinding(
                        "variant_adapter_module_not_registered",
                        "canonical-relation-derived variant adapter owner is not a registered target module",
                        module_id=module_id,
                        metadata={"relation_ids": list(relation_ids)},
                    )
                )
        if (
            recommendation.shared_kernel_module_id
            and recommendation.variant_adapter_module_ids
            and not relation_code_obligation_ids
        ):
            findings.append(
                CodeStructureFinding(
                    "missing_relation_code_obligation",
                    "canonical-relation-derived shared-kernel structure should cite the code maintenance obligation that named the kernel and adapters",
                    severity="warning",
                    module_id=recommendation.shared_kernel_module_id,
                    metadata={"relation_ids": list(relation_ids)},
                )
            )
        if relation_group_ids and not relation_code_obligation_ids:
            findings.append(
                CodeStructureFinding(
                    "missing_relation_group_code_obligation",
                    "a canonical relation group used for code structure should cite the code obligation that drives shared-kernel or adapter ownership",
                    severity="warning",
                    metadata={"relation_group_ids": list(relation_group_ids)},
                )
            )

    all_pairs = (
        ("function_block_owner_not_registered", "FunctionBlock", recommendation.function_block_map),
        ("state_owner_not_registered", "state", recommendation.state_owner_map),
        ("side_effect_owner_not_registered", "side effect", recommendation.side_effect_owner_map),
        ("config_owner_not_registered", "config", recommendation.config_owner_map),
        ("field_owner_not_registered", "field owner", recommendation.field_owner_map),
        ("field_reader_not_registered", "field reader", recommendation.field_reader_map),
        ("field_writer_not_registered", "field writer", recommendation.field_writer_map),
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

    owned_fields = {field_id for field_id, _module_id in recommendation.field_owner_map}
    accessed_fields = {
        field_id
        for field_id, _module_id in (*recommendation.field_reader_map, *recommendation.field_writer_map)
    }
    for field_id in sorted(accessed_fields - owned_fields):
        findings.append(
            CodeStructureFinding(
                "field_access_without_owner",
                f"field {field_id} is read or written but has no recommended owner module",
                item_id=field_id,
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
    findings.extend(
        _duplicate_pair_keys(
            recommendation.field_owner_map,
            code="duplicate_field_recommendation_owner",
            noun="field",
        )
    )
    blockers = _blocker_findings(findings)
    return CodeStructureRecommendationReport(
        ok=not blockers,
        recommendation_id=recommendation.recommendation_id,
        findings=tuple(findings),
    )


# Model kit: plan edits, the reviews as invariants, code facts.  The plan is a CodeStructureRecommendation
# or, for a split of an existing module, a StructureMeshPlan whose target_structure is the recommendation.
_OWNERSHIP = {   # kind -> (recommendation map, target-module list, split-child list, partition item type)
    "function_block": ("function_block_map", "owns_function_blocks", "owns_functions", "function"),
    "state": ("state_owner_map", "owns_state", "owns_state", "state"),
    "side_effect": ("side_effect_owner_map", "owns_side_effects", "owns_side_effects", "side_effect"),
    "config": ("config_owner_map", "owns_config", "owns_config", "config"),
    "field": ("field_owner_map", "owns_fields", "", ""),
    "entrypoint": ("public_entrypoint_map", "public_entrypoints", "", "entrypoint"),
}
_CODE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}


def _recommendation_of(plan: Any) -> CodeStructureRecommendation | None:
    return plan if isinstance(plan, CodeStructureRecommendation) else plan.target_structure


def _with_recommendation(plan: Any, recommendation: CodeStructureRecommendation) -> Any:
    return recommendation if isinstance(plan, CodeStructureRecommendation) else replace(plan, target_structure=recommendation)


def _moved(values: tuple[str, ...], item_id: str, here: bool) -> tuple[str, ...]:
    return tuple(value for value in values if value != item_id) + ((item_id,) if here else ())


def add_target_module(plan: Any, module: TargetModuleRecommendation) -> Any:
    """Plan edit for a code-structure model: a new target module (in a split also a new child module)."""
    from .structuremesh import ModuleStructureEvidence

    recommendation = _recommendation_of(plan)
    if module.module_id not in recommendation.module_ids():
        plan = _with_recommendation(plan, replace(recommendation,
                                                  target_modules=recommendation.target_modules + (module,)))
    if not isinstance(plan, CodeStructureRecommendation) and \
            module.module_id not in {child.module_id for child in plan.child_modules}:
        plan = replace(plan, child_modules=plan.child_modules + (ModuleStructureEvidence(module.module_id, path=module.path),))
    return plan


def move_responsibility(plan: Any, item_id: str, module_id: str, kind: str = "function_block") -> Any:
    """Plan edit for a code-structure model: ``module_id`` becomes the one owner of ``item_id``.

    ``kind`` is function_block, state, side_effect, config, field or entrypoint.  The owner map, the target
    modules' ``owns_*`` lists and, in a split, the partition item and the child modules move together.
    """
    from .structuremesh import StructurePartitionItem

    pair_map, owns, child_owns, item_type = _OWNERSHIP[kind]
    recommendation = _recommendation_of(plan)
    pairs = tuple(pair for pair in getattr(recommendation, pair_map) if pair[0] != item_id) + ((item_id, module_id),)
    modules = tuple(replace(module, **{owns: _moved(getattr(module, owns), item_id, module.module_id == module_id)})
                    for module in recommendation.target_modules)
    plan = _with_recommendation(plan, replace(recommendation, **{pair_map: pairs, "target_modules": modules}))
    if isinstance(plan, CodeStructureRecommendation):
        return plan
    if item_type:
        items = plan.partition_items
        if any(item.item_id == item_id for item in items):
            items = tuple(replace(item, owner_module_id=module_id) if item.item_id == item_id else item for item in items)
        else:
            items += (StructurePartitionItem(item_id, item_type=item_type, owner_module_id=module_id),)
        plan = replace(plan, partition_items=items)
    if child_owns:
        plan = replace(plan, child_modules=tuple(
            replace(child, **{child_owns: _moved(getattr(child, child_owns), item_id, child.module_id == module_id)})
            for child in plan.child_modules))
    return plan


def _review_plan_recommendation(plan: Any) -> CodeStructureRecommendationReport:
    recommendation = _recommendation_of(plan)
    if recommendation is None:
        return CodeStructureRecommendationReport(False, "", (CodeStructureFinding(
            "missing_target_structure", "the split has no model-derived target code structure"),))
    return review_code_structure_recommendation(recommendation)


def code_structure_explorer(initial, edits, *, explore=None, max_sequence_length: int = 2):
    """Code-structure model: named edits change the module plan; the existing reviews must accept every plan.

    Invariants: ``code_structure_review_accepts`` (``review_code_structure_recommendation``) and, when the
    plan is a split (``StructureMeshPlan``), ``structure_mesh_review_accepts`` (``review_structure_mesh``).
    """
    from .kit import plan_explorer
    from .structuremesh import review_structure_mesh

    split = not isinstance(initial(), CodeStructureRecommendation)
    return plan_explorer(initial, edits, _review_plan_recommendation, explore=explore,
                         invariant_name="code_structure_review_accepts", max_sequence_length=max_sequence_length,
                         extra_reviews={"structure_mesh_review_accepts": review_structure_mesh} if split else None)


def _code_entrypoint_problems(root: Path, targets: Sequence[str]) -> dict[str, str | None]:
    """For each target that names code ('path:Symbol' or a source file): None when it exists, else the problem.

    Commands, routes and dotted import paths are left out; tests check them.
    """
    from .map.check import anchor_problems

    problems = anchor_problems(root, [target for target in targets if ":" in target])
    found: dict[str, str | None] = {}
    for target in targets:
        if ":" in target:
            found[target] = problems.get(target)
        elif Path(target).suffix in _CODE_SUFFIXES:
            found[target] = None if (Path(root) / target).is_file() else f"entrypoint file missing: {target}"
    return found


def code_structure_code_facts(plan: Any, *, anchors=(), root=None, planned: bool = False):
    """Compare a module plan with the real code and the project map (static code facts, nothing is executed).

    * every target module path, split child path and source model path exists, and every public entrypoint
      that names code ('path:Symbol' or a source file) resolves;
    * with ``.flowguard/map.json``: the file of each responsibility's owner module belongs to the map
      component with that module id (or, when the map has no such component, to the plan's parent component);
    * every anchor exists.
    """
    from .map.common import matches_any
    from .map.facts import CodeFacts
    from .map.mapfile import MapError, load_map, map_path

    facts = CodeFacts(root, planned=planned)
    if anchors:
        facts.anchors_exist(anchors)
    recommendation = _recommendation_of(plan)
    split = None if isinstance(plan, CodeStructureRecommendation) else plan
    modules = [(m.module_id, m.path) for m in (recommendation.target_modules if recommendation else ())]
    modules += [(child.module_id, child.path) for child in (split.child_modules if split else ())]
    paths: dict[str, str] = {}
    for module_id, path in modules:
        if path and module_id not in paths:
            paths[module_id] = path
            facts.check(f"module {module_id} exists at {path}", (facts.root / path).exists(), f"{path} does not exist")
    if recommendation and recommendation.source_model_path:
        facts.check(f"source model {recommendation.source_model_path} exists",
                    (facts.root / recommendation.source_model_path).is_file(),
                    f"{recommendation.source_model_path} does not exist")
    targets = [item for item, _module in (recommendation.public_entrypoint_map if recommendation else ())]
    targets += [entry for module in (recommendation.target_modules if recommendation else ())
                for entry in module.public_entrypoints]
    targets += [entry.new_path for entry in (split.public_entrypoints if split else ())]
    for target, problem in _code_entrypoint_problems(facts.root, list(dict.fromkeys(targets))).items():
        facts.check(f"entrypoint {target} exists", problem is None, problem or "")
    if map_path(facts.root).is_file():
        try:
            components = {c["id"]: c.get("files", []) for c in load_map(facts.root)["components"]}
        except MapError as exc:
            facts.check("the project map is readable", False, str(exc))
            return facts.report()
        parent = (recommendation.parent_module_id if recommendation else "") or (split.parent_module_id if split else "")
        owned = [pair for kind in _OWNERSHIP for pair in getattr(recommendation, _OWNERSHIP[kind][0])] if recommendation else []
        for item_id, module_id in dict.fromkeys(owned):
            path = paths.get(module_id)
            if not path:
                continue
            expected = module_id if module_id in components else parent
            owners = sorted(cid for cid, patterns in components.items() if matches_any(path, patterns))
            facts.check(f"{item_id}: owner file {path} belongs to map component {expected}", expected in owners,
                        f"{path} belongs to {', '.join(owners) or 'no component'}")
    return facts.report()


__all__ = [
    "CodeStructureFinding",
    "CodeStructureRecommendation",
    "CodeStructureRecommendationReport",
    "TargetModuleRecommendation",
    "add_target_module",
    "code_structure_code_facts",
    "code_structure_explorer",
    "move_responsibility",
    "review_code_structure_recommendation",
]
