"""Compile FlowGuard's own current models into path-quality material.

This is a private self-maintenance adapter, not a route, CLI, authority
pointer, or reconstruction workflow.  It projects existing executable model
structures (``Workflow`` objects or explicit contract exports) and, only when
neither exists, the native runner's actual evidence-owner calls into the
provider-neutral facts consumed by :mod:`flowguard.model_path_quality`.

The compact subjects/results can be embedded in the same ModelRevisionSet as
the candidate model snapshot.  Detailed facts and element-local removal
witnesses remain in the returned audit object and do not become a second
current authority.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, replace
import importlib.util
import inspect
import json
from pathlib import Path
import re
import sys
from types import ModuleType
from typing import Any, Iterable, Mapping, Sequence

from .core import Invariant, block_name
from .model_authority import (
    LIFECYCLE_ACTIVE,
    SUBJECT_OBSERVED_IMPLEMENTATION,
    ModelInstanceRef,
    ModelSystemSnapshot,
    file_fingerprint,
)
from .model_path_quality import (
    NecessityWitness,
    PATH_COST_DIMENSIONS,
    PathQualityMaterialReview,
    PathQualityResult,
    PathQualitySubject,
    canonical_fingerprint,
    collect_deep_review_triggers,
    derive_retained_elements,
    find_lightweight_findings,
    lightweight_path_review,
    normalize_path_quality_material,
    normalized_model_facts_fingerprint,
    path_quality_result_set_fingerprint,
    review_path_quality_material,
    validate_necessity_witnesses,
)
from .model_regressions import ModelRegressionEntry, ModelRegressionManifest
from .model_system_inventory import build_manifest_model_system_snapshot
from .scenario import Scenario
from .workflow import Workflow


SELF_PATH_QUALITY_SCHEMA_VERSION = "flowguard.self-path-quality-material.v3"
SELF_PATH_QUALITY_PRODUCER_ID = "flowguard-self-path-quality"

# These are deliberately provider-neutral structural thresholds.  They are
# admission signals, not a license to delete a route: a triggered model still
# needs the finite deep proof owned by ModelMaturation.
SELF_PATH_COST_THRESHOLDS: dict[str, float] = {
    "steps": 64.0,
    "states": 32.0,
    "transitions": 64.0,
    "branches": 16.0,
    "validations": 24.0,
    "payload_bytes": 50_000.0,
}


class SelfPathQualityError(ValueError):
    """Raised when the self adapter cannot bind one exact current input."""


@dataclass(frozen=True)
class SelfModelDeepTriggerCensusEntry:
    """Typed trigger inputs and matching result projection for one model."""

    model_id: str
    explicit_deep_request: bool
    declared_candidate_count: int
    path_design_model_miss: bool
    high_cost_boundary: bool
    release_critical_boundary: bool
    finding_ids: tuple[str, ...]
    trigger_ids: tuple[str, ...]
    conclusion: str
    currentness_id: str
    current: bool
    result_available: bool = True
    measured_costs: tuple[tuple[str, float], ...] = ()
    optimization_depth: str = ""
    cost_detail_evidence_fingerprint: str = ""
    trigger_evidence_fingerprint: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.model_id, str) or not self.model_id:
            raise SelfPathQualityError("deep-trigger census model_id must be non-empty")
        for name in (
            "explicit_deep_request",
            "path_design_model_miss",
            "high_cost_boundary",
            "release_critical_boundary",
            "current",
            "result_available",
        ):
            if not isinstance(getattr(self, name), bool):
                raise SelfPathQualityError(f"deep-trigger census {name} must be boolean")
        if (
            isinstance(self.declared_candidate_count, bool)
            or not isinstance(self.declared_candidate_count, int)
            or self.declared_candidate_count < 0
        ):
            raise SelfPathQualityError(
                "deep-trigger census declared_candidate_count must be a non-negative integer"
            )
        for name in ("finding_ids", "trigger_ids"):
            values = getattr(self, name)
            if not isinstance(values, tuple) or values != tuple(sorted(set(values))):
                raise SelfPathQualityError(
                    f"deep-trigger census {name} must be a canonical tuple"
                )
        costs = tuple(self.measured_costs)
        if costs != tuple(sorted(costs)) or len({key for key, _value in costs}) != len(costs):
            raise SelfPathQualityError("deep-trigger census measured costs must be canonical")
        for dimension, value in costs:
            if dimension not in PATH_COST_DIMENSIONS:
                raise SelfPathQualityError(
                    f"deep-trigger census measured cost has unknown dimension: {dimension}"
                )
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise SelfPathQualityError(
                    f"deep-trigger census measured cost must be numeric: {dimension}"
                )
        object.__setattr__(self, "measured_costs", costs)
        if self.optimization_depth and self.optimization_depth not in {
            "lightweight",
            "deep_required",
            "deep_closed",
        }:
            raise SelfPathQualityError("deep-trigger census optimization depth is invalid")
        for name in (
            "cost_detail_evidence_fingerprint",
            "trigger_evidence_fingerprint",
        ):
            value = str(getattr(self, name))
            if value and not value.startswith("sha256:"):
                raise SelfPathQualityError(
                    f"deep-trigger census {name} must be a fingerprint"
                )
            object.__setattr__(self, name, value)
            if any(not isinstance(value, str) or not value for value in values):
                raise SelfPathQualityError(
                    f"deep-trigger census {name} must contain non-empty strings"
                )
        if self.result_available:
            if not self.conclusion or not self.currentness_id:
                raise SelfPathQualityError(
                    "available deep-trigger census result requires conclusion/currentness"
                )
        elif any(
            (
                self.finding_ids,
                self.trigger_ids,
                self.conclusion,
                self.currentness_id,
                self.current,
                self.measured_costs,
                self.optimization_depth,
                self.cost_detail_evidence_fingerprint,
                self.trigger_evidence_fingerprint,
            )
        ):
            raise SelfPathQualityError(
                "unavailable deep-trigger census result cannot project result fields"
            )

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.identity_payload())

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": SELF_PATH_QUALITY_SCHEMA_VERSION,
            "model_id": self.model_id,
            "explicit_deep_request": self.explicit_deep_request,
            "declared_candidate_count": self.declared_candidate_count,
            "path_design_model_miss": self.path_design_model_miss,
            "high_cost_boundary": self.high_cost_boundary,
            "release_critical_boundary": self.release_critical_boundary,
            "finding_ids": list(self.finding_ids),
            "trigger_ids": list(self.trigger_ids),
            "conclusion": self.conclusion,
            "currentness_id": self.currentness_id,
            "current": self.current,
            "result_available": self.result_available,
            "measured_costs": {
                dimension: value for dimension, value in self.measured_costs
            },
            "optimization_depth": self.optimization_depth,
            "cost_detail_evidence_fingerprint": self.cost_detail_evidence_fingerprint,
            "trigger_evidence_fingerprint": self.trigger_evidence_fingerprint,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "fingerprint": self.fingerprint}


@dataclass(frozen=True)
class SelfModelPathQualityDetail:
    """Deep material for one current self model; never a current pointer."""

    model_id: str
    provider_kind: str
    provider_fingerprint: str
    model_facts: Mapping[str, Any]
    retained_elements: tuple[tuple[str, str], ...]
    active_obligation_ids: tuple[str, ...]
    necessity_witnesses: tuple[NecessityWitness, ...]
    subject: PathQualitySubject
    result: PathQualityResult
    source_refs: tuple[str, ...]
    provider_gaps: tuple[str, ...] = ()

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.identity_payload())

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": SELF_PATH_QUALITY_SCHEMA_VERSION,
            "model_id": self.model_id,
            "provider_kind": self.provider_kind,
            "provider_fingerprint": self.provider_fingerprint,
            "model_facts": dict(self.model_facts),
            "retained_elements": dict(self.retained_elements),
            "active_obligation_ids": list(self.active_obligation_ids),
            "necessity_witnesses": [item.to_dict() for item in self.necessity_witnesses],
            "subject": self.subject.to_dict(),
            "result": self.result.to_dict(),
            "source_refs": list(self.source_refs),
            "provider_gaps": list(self.provider_gaps),
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "fingerprint": self.fingerprint}


@dataclass(frozen=True)
class FlowGuardSelfPathQualityMaterial:
    """One candidate-snapshot-bound self path-quality audit."""

    candidate_snapshot_fingerprint: str
    required_model_ids: tuple[str, ...]
    details: tuple[SelfModelPathQualityDetail, ...]
    deep_trigger_census: tuple[SelfModelDeepTriggerCensusEntry, ...]
    review: PathQualityMaterialReview
    global_gaps: tuple[str, ...] = ()
    schema_version: str = SELF_PATH_QUALITY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SELF_PATH_QUALITY_SCHEMA_VERSION:
            raise SelfPathQualityError(
                "self path-quality material requires the direct-current schema"
            )
        if (
            not isinstance(self.candidate_snapshot_fingerprint, str)
            or not self.candidate_snapshot_fingerprint
        ):
            raise SelfPathQualityError(
                "self path-quality material requires a candidate snapshot fingerprint"
            )
        if self.required_model_ids != tuple(sorted(set(self.required_model_ids))):
            raise SelfPathQualityError(
                "self path-quality required model ids must be canonical"
            )
        detail_ids = tuple(item.model_id for item in self.details)
        if detail_ids != tuple(sorted(set(detail_ids))):
            raise SelfPathQualityError("self path-quality details must be canonical")
        census_ids = tuple(item.model_id for item in self.deep_trigger_census)
        if census_ids != self.required_model_ids:
            raise SelfPathQualityError(
                "deep-trigger census must exactly cover the required denominator"
            )
        available_ids = tuple(
            item.model_id for item in self.deep_trigger_census if item.result_available
        )
        if available_ids != detail_ids:
            raise SelfPathQualityError(
                "deep-trigger census available results must exactly match details"
            )
        details_by_id = {item.model_id: item for item in self.details}
        for entry in self.deep_trigger_census:
            if not entry.result_available:
                continue
            result = details_by_id[entry.model_id].result
            if (
                entry.finding_ids != result.finding_ids
                or entry.trigger_ids != result.trigger_ids
                or entry.conclusion != result.conclusion
                or entry.currentness_id != result.currentness_id
                or entry.current != result.current
                or entry.measured_costs != result.cost_measurements
                or entry.optimization_depth != result.optimization_depth
                or entry.cost_detail_evidence_fingerprint
                != result.cost_detail_evidence_fingerprint
                or entry.trigger_evidence_fingerprint
                != result.trigger_evidence_fingerprint
            ):
                raise SelfPathQualityError(
                    "deep-trigger census result projection drifted: " + entry.model_id
                )

    @property
    def subjects(self) -> tuple[PathQualitySubject, ...]:
        return tuple(item.subject for item in self.details)

    @property
    def results(self) -> tuple[PathQualityResult, ...]:
        return tuple(item.result for item in self.details)

    @property
    def deep_required_model_ids(self) -> tuple[str, ...]:
        return tuple(
            item.model_id
            for item in self.details
            if item.result.trigger_ids or item.result.conclusion == "unresolved"
        )

    @property
    def triggered_model_ids(self) -> tuple[str, ...]:
        return tuple(
            item.model_id
            for item in self.deep_trigger_census
            if item.result_available and item.trigger_ids
        )

    @property
    def untriggered_model_ids(self) -> tuple[str, ...]:
        return tuple(
            item.model_id
            for item in self.deep_trigger_census
            if item.result_available and not item.trigger_ids
        )

    @property
    def trigger_census_blocked_model_ids(self) -> tuple[str, ...]:
        return tuple(
            item.model_id
            for item in self.deep_trigger_census
            if not item.result_available
        )

    @property
    def ok(self) -> bool:
        return self.review.ok and not self.global_gaps

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(
            {
                "schema_version": self.schema_version,
                "candidate_snapshot_fingerprint": self.candidate_snapshot_fingerprint,
                "required_model_ids": list(self.required_model_ids),
                "detail_fingerprints": [item.fingerprint for item in self.details],
                "deep_trigger_census_fingerprints": [
                    item.fingerprint for item in self.deep_trigger_census
                ],
                "result_set_fingerprint": self.review.result_set_fingerprint,
                "global_gaps": list(self.global_gaps),
            }
        )

    def to_revision_material(self) -> dict[str, Any]:
        """Return the exact compact wire shape consumed by the revision CLI."""

        return {
            "subjects": [item.to_dict() for item in self.subjects],
            "results": [item.to_dict() for item in self.results],
        }

    def to_audit_dict(self) -> dict[str, Any]:
        depth_counts: dict[str, int] = {}
        cost_dimensions: dict[str, int] = {}
        for detail in self.details:
            depth = detail.result.optimization_depth
            depth_counts[depth] = depth_counts.get(depth, 0) + 1
            for dimension, _value in detail.result.cost_measurements:
                cost_dimensions[dimension] = cost_dimensions.get(dimension, 0) + 1
        return {
            "schema_version": self.schema_version,
            "candidate_snapshot_fingerprint": self.candidate_snapshot_fingerprint,
            "required_model_ids": list(self.required_model_ids),
            "result_set_fingerprint": self.review.result_set_fingerprint,
            "deep_required_model_ids": list(self.deep_required_model_ids),
            "path_denominator": {
                "model_count": len(self.required_model_ids),
                "detail_count": len(self.details),
                "trigger_census_complete": not self.trigger_census_blocked_model_ids,
            },
            "optimization_depth_counts": dict(sorted(depth_counts.items())),
            "measured_cost_dimension_counts": dict(sorted(cost_dimensions.items())),
            "deep_trigger_census": {
                "denominator_model_ids": list(self.required_model_ids),
                "denominator_count": len(self.required_model_ids),
                "triggered_model_ids": list(self.triggered_model_ids),
                "untriggered_model_ids": list(self.untriggered_model_ids),
                "blocked_model_ids": list(self.trigger_census_blocked_model_ids),
                "models": [item.to_dict() for item in self.deep_trigger_census],
            },
            "review": self.review.to_compact_dict(),
            "global_gaps": list(self.global_gaps),
            "details": [item.to_dict() for item in self.details],
            "ok": self.ok,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True)
class _ProviderProjection:
    provider_kind: str
    facts: Mapping[str, Any]
    element_groundings: Mapping[str, Mapping[str, Any]]
    source_refs: tuple[str, ...]
    gaps: tuple[str, ...] = ()

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(
            {
                "provider_kind": self.provider_kind,
                "facts": dict(self.facts),
                "element_groundings": {
                    key: dict(value)
                    for key, value in sorted(self.element_groundings.items())
                },
                "source_refs": list(self.source_refs),
                "gaps": list(self.gaps),
            }
        )


def _stable(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9._:/-]+", "-", str(value).strip()).strip("-")
    return text or canonical_fingerprint({"value": str(value)})[-16:]


def _sequence(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    if not isinstance(value, Sequence):
        return ()
    return tuple(str(item) for item in value if str(item))


def _type_name(value: Any) -> str:
    if isinstance(value, tuple):
        return "|".join(sorted(_type_name(item) for item in value))
    return str(getattr(value, "__qualname__", getattr(value, "__name__", value)))


def _load_model_module(root: Path, entry: ModelRegressionEntry, instance: ModelInstanceRef) -> ModuleType:
    model_path = (root / entry.model_path).resolve()
    if not model_path.is_file():
        raise SelfPathQualityError(f"model source is missing: {entry.model_id}")
    module_name = (
        "_flowguard_self_path_quality_"
        + _stable(entry.model_id).replace("-", "_").replace(".", "_")
        + "_"
        + instance.model_sha256[-12:]
    )
    spec = importlib.util.spec_from_file_location(module_name, model_path)
    if spec is None or spec.loader is None:
        raise SelfPathQualityError(f"model source cannot be loaded: {entry.model_id}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    added_root = False
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
        added_root = True
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise SelfPathQualityError(
            f"model provider import failed for {entry.model_id}: {type(exc).__name__}: {exc}"
        ) from exc
    finally:
        if added_root:
            try:
                sys.path.remove(str(root))
            except ValueError:
                pass
    return module


def _callable_without_required_arguments(value: Any) -> bool:
    try:
        parameters = inspect.signature(value).parameters.values()
    except (TypeError, ValueError):
        return False
    return all(
        parameter.default is not inspect.Parameter.empty
        or parameter.kind
        in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        for parameter in parameters
    )


def _current_workflows(module: ModuleType) -> tuple[Workflow, ...]:
    values: list[Workflow] = []
    for value in vars(module).values():
        if isinstance(value, Workflow) and "broken" not in value.name.casefold():
            values.append(value)
        if isinstance(value, (tuple, list)):
            for item in value:
                if (
                    isinstance(item, Scenario)
                    and item.workflow is not None
                    and "broken" not in item.workflow.name.casefold()
                ):
                    values.append(item.workflow)
    for name, value in vars(module).items():
        if (
            callable(value)
            and getattr(value, "__module__", "") == module.__name__
            and "workflow" in name.casefold()
            and "broken" not in name.casefold()
            and _callable_without_required_arguments(value)
        ):
            try:
                projected = value()
            except Exception:
                continue
            if isinstance(projected, Workflow) and "broken" not in projected.name.casefold():
                values.append(projected)
    by_fingerprint: dict[str, Workflow] = {}
    for workflow in values:
        fingerprint = canonical_fingerprint(
            {
                "name": workflow.name,
                "blocks": [
                    {
                        "name": block_name(block),
                        "type": type(block).__qualname__,
                        "accepted_input": _type_name(
                            getattr(
                                block,
                                "accepted_input_type",
                                getattr(block, "accepted_input_types", "any"),
                            )
                        ),
                        "reads": list(_sequence(getattr(block, "reads", ()))),
                        "writes": list(_sequence(getattr(block, "writes", ()))),
                        "effects": list(_sequence(getattr(block, "effects", ()))),
                    }
                    for block in workflow.blocks
                ],
            }
        )
        by_fingerprint[fingerprint] = workflow
    return tuple(by_fingerprint[key] for key in sorted(by_fingerprint))


def _current_invariants(module: ModuleType) -> tuple[Invariant, ...]:
    values: dict[tuple[str, str], Invariant] = {}
    for value in vars(module).values():
        candidates: Iterable[Any]
        if isinstance(value, Invariant):
            candidates = (value,)
        elif isinstance(value, (tuple, list)):
            candidates = value
        else:
            continue
        for item in candidates:
            if isinstance(item, Invariant):
                values[(item.name, item.description)] = item
            elif isinstance(item, Scenario):
                for invariant in item.invariants:
                    if isinstance(invariant, Invariant):
                        values[(invariant.name, invariant.description)] = invariant
    return tuple(values[key] for key in sorted(values))


def _workflow_projection(
    entry: ModelRegressionEntry,
    instance: ModelInstanceRef,
    workflows: Sequence[Workflow],
    invariants: Sequence[Invariant],
) -> _ProviderProjection:
    states: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    blocks: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    validations: list[dict[str, Any]] = []
    field_uses: dict[str, dict[str, set[str]]] = {}
    effect_ids: set[str] = set()
    groundings: dict[str, Mapping[str, Any]] = {}

    validation_ids: list[str] = []
    for invariant in invariants:
        validation_id = f"validation:{entry.model_id}:invariant:{_stable(invariant.name)}"
        validation_ids.append(validation_id)
        validations.append(
            {
                "id": validation_id,
                "obligation_id": f"obligation:native-invariant:{entry.model_id}:{_stable(invariant.name)}",
                "oracle_id": f"oracle:native-invariant:{entry.model_id}:{_stable(invariant.name)}",
                "subject_fingerprint": instance.fingerprint,
                "evidence_boundary_id": f"native-runner:{entry.model_id}",
            }
        )
        groundings[validation_id] = {
            "kind": "native_invariant_binding",
            "invariant_name": invariant.name,
            "invariant_description": invariant.description,
            "runner_fingerprint": instance.runner_sha256,
        }

    for workflow_index, workflow in enumerate(workflows):
        signature = canonical_fingerprint(
            {
                "name": workflow.name,
                "blocks": [block_name(block) for block in workflow.blocks],
            }
        )[-12:]
        workflow_id = (
            f"workflow:{entry.model_id}:{_stable(workflow.name)}:"
            f"{workflow_index}:{signature}"
        )
        state_ids = tuple(
            f"state:{workflow_id}:{index}" for index in range(len(workflow.blocks) + 1)
        )
        for index, state_id in enumerate(state_ids):
            states.append(
                {
                    "id": state_id,
                    "initial": index == 0,
                    "terminal": index == len(state_ids) - 1,
                    "behaviorally_relevant": True,
                }
            )
            groundings[state_id] = {
                "kind": "executable_workflow_state",
                "workflow_id": workflow_id,
                "position": index,
                "workflow_fingerprint": signature,
            }
        for index, block in enumerate(workflow.blocks):
            name = block_name(block)
            block_id = f"function-block:{workflow_id}:{index}:{_stable(name)}"
            transition_id = f"transition:{workflow_id}:{index}:{_stable(name)}"
            output_id = f"output:{workflow_id}:{index}:{_stable(name)}"
            reads = tuple(
                f"field:{entry.model_id}:{_stable(item)}"
                for item in _sequence(getattr(block, "reads", ()))
            )
            writes = tuple(
                f"field:{entry.model_id}:{_stable(item)}"
                for item in _sequence(getattr(block, "writes", ()))
            )
            effects = tuple(
                f"effect:{entry.model_id}:{_stable(item)}"
                for item in _sequence(getattr(block, "effects", ()))
            )
            for field_id in reads:
                field_uses.setdefault(field_id, {"reads": set(), "writes": set()})[
                    "reads"
                ].add(block_id)
            for field_id in writes:
                field_uses.setdefault(field_id, {"reads": set(), "writes": set()})[
                    "writes"
                ].add(block_id)
            effect_ids.update(effects)
            attached_validations = tuple(validation_ids) if index == len(workflow.blocks) - 1 else ()
            prior_output = (
                f"external-input:{workflow_id}"
                if index == 0
                else f"output:{workflow_id}:{index - 1}:{_stable(block_name(workflow.blocks[index - 1]))}"
            )
            blocks.append(
                {
                    "id": block_id,
                    "inputs": [prior_output],
                    "outputs": [output_id],
                    "reads": list(reads),
                    "writes": list(writes),
                    "effects": list(effects),
                    "validations": list(attached_validations),
                    "state_input": state_ids[index],
                    "state_output": state_ids[index + 1],
                    "pass_through": bool(getattr(block, "pass_through", False)),
                    "accepted_input": _type_name(
                        getattr(
                            block,
                            "accepted_input_type",
                            getattr(block, "accepted_input_types", "any"),
                        )
                    ),
                }
            )
            transitions.append(
                {
                    "id": transition_id,
                    "source": state_ids[index],
                    "target": state_ids[index + 1],
                    "trigger": _type_name(
                        getattr(
                            block,
                            "accepted_input_type",
                            getattr(block, "accepted_input_types", "any"),
                        )
                    ),
                    "guard": "flowguard-block-acceptance",
                    "outputs": [output_id],
                    "reads": list(reads),
                    "writes": list(writes),
                    "effects": list(effects),
                    "validations": list(attached_validations),
                    "function_block_ids": [block_id],
                }
            )
            outputs.append(
                {
                    "id": output_id,
                    "producer_id": transition_id,
                    "consumer_ids": (
                        []
                        if index == len(workflow.blocks) - 1
                        else [
                            f"function-block:{workflow_id}:{index + 1}:"
                            f"{_stable(block_name(workflow.blocks[index + 1]))}"
                        ]
                    ),
                    "terminal": index == len(workflow.blocks) - 1,
                }
            )
            relation = {
                "kind": "executable_workflow_block_relation",
                "workflow_id": workflow_id,
                "position": index,
                "block_name": name,
                "block_type": type(block).__qualname__,
                "source_state_id": state_ids[index],
                "target_state_id": state_ids[index + 1],
                "runner_fingerprint": instance.runner_sha256,
            }
            groundings[block_id] = relation
            groundings[transition_id] = {**relation, "kind": "executable_workflow_transition"}

    fields = [
        {
            "id": field_id,
            "reads_by": sorted(uses["reads"]),
            "writes_by": sorted(uses["writes"]),
            "observable": bool(uses["writes"]),
            "behaviorally_relevant": True,
            "declared": True,
        }
        for field_id, uses in sorted(field_uses.items())
    ]
    for row in fields:
        groundings[row["id"]] = {
            "kind": "explicit_function_block_field_contract",
            "reads_by": row["reads_by"],
            "writes_by": row["writes_by"],
            "model_fingerprint": instance.fingerprint,
        }
    effects = [{"id": effect_id} for effect_id in sorted(effect_ids)]
    for effect_id in effect_ids:
        groundings[effect_id] = {
            "kind": "explicit_function_block_effect_contract",
            "model_fingerprint": instance.fingerprint,
        }
    facts = {
        "provider_kind": "flowguard.executable-workflow-structure.v1",
        "states": states,
        "initial_state_ids": [row["id"] for row in states if row["initial"]],
        "terminal_state_ids": [row["id"] for row in states if row["terminal"]],
        "transitions": transitions,
        "function_blocks": blocks,
        "fields": fields,
        "effects": effects,
        "validations": validations,
        "outputs": outputs,
        "owners": [],
    }
    return _ProviderProjection(
        provider_kind="flowguard.executable-workflow-structure.v1",
        facts=facts,
        element_groundings=groundings,
        source_refs=(entry.model_path, entry.runner[1]),
    )


def _contract_export_projection(
    entry: ModelRegressionEntry,
    instance: ModelInstanceRef,
    exported: Mapping[str, Any],
) -> _ProviderProjection:
    steps = exported.get("steps")
    routes = exported.get("routes")
    obligations = exported.get("obligations")
    if not isinstance(steps, list) or not steps:
        raise SelfPathQualityError(f"contract export has no steps: {entry.model_id}")
    if not isinstance(routes, list) or not routes:
        raise SelfPathQualityError(f"contract export has no routes: {entry.model_id}")
    if not isinstance(obligations, list):
        raise SelfPathQualityError(f"contract export obligations are invalid: {entry.model_id}")
    step_by_id = {str(row.get("step_id", "")): row for row in steps if isinstance(row, Mapping)}
    if "" in step_by_id or len(step_by_id) != len(steps):
        raise SelfPathQualityError(f"contract export step identities are invalid: {entry.model_id}")
    blocks: list[dict[str, Any]] = []
    validations: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    groundings: dict[str, Mapping[str, Any]] = {}
    obligation_ids_by_step: dict[str, list[str]] = {}
    for raw in obligations:
        if not isinstance(raw, Mapping):
            raise SelfPathQualityError(f"contract export obligation row is invalid: {entry.model_id}")
        obligation_id = str(raw.get("obligation_id", ""))
        invariant_id = str(raw.get("invariant_id", ""))
        owner_step_ids = tuple(str(item) for item in raw.get("owner_step_ids", ()))
        if not obligation_id or not invariant_id or not owner_step_ids:
            raise SelfPathQualityError(f"contract export obligation is incomplete: {entry.model_id}")
        validation_id = f"validation:{entry.model_id}:contract:{_stable(obligation_id)}"
        validations.append(
            {
                "id": validation_id,
                "obligation_id": obligation_id,
                "oracle_id": invariant_id,
                "subject_fingerprint": instance.fingerprint,
                "evidence_boundary_id": f"contract-export:{entry.model_id}",
            }
        )
        groundings[validation_id] = {
            "kind": "exported_contract_obligation",
            "obligation_id": obligation_id,
            "invariant_id": invariant_id,
            "owner_step_ids": list(owner_step_ids),
        }
        for step_id in owner_step_ids:
            if step_id not in step_by_id:
                raise SelfPathQualityError(
                    f"contract export obligation references an unknown step: {entry.model_id}:{step_id}"
                )
            obligation_ids_by_step.setdefault(step_id, []).append(validation_id)
    route_terminal_steps = {
        str(raw.get(name, ""))
        for raw in routes
        if isinstance(raw, Mapping)
        for name in ("success_terminal_step_id", "blocked_terminal_step_id")
        if str(raw.get(name, ""))
    }
    for index, (step_id, raw) in enumerate(sorted(step_by_id.items())):
        prerequisites = tuple(str(item) for item in raw.get("prerequisite_step_ids", ()))
        if any(item not in step_by_id for item in prerequisites):
            raise SelfPathQualityError(
                f"contract export prerequisite references an unknown step: {entry.model_id}:{step_id}"
            )
        block_id = f"function-block:{entry.model_id}:contract:{_stable(step_id)}"
        output_id = f"output:{entry.model_id}:contract:{_stable(step_id)}"
        inputs = (
            [f"output:{entry.model_id}:contract:{_stable(item)}" for item in prerequisites]
            or [f"external-input:{entry.model_id}:{_stable(str(raw.get('route_id', 'route')))}"]
        )
        blocks.append(
            {
                "id": block_id,
                "inputs": inputs,
                "outputs": [output_id],
                "validations": obligation_ids_by_step.get(step_id, ()),
                "state_input": "",
                "state_output": f"contract-step-state:{_stable(step_id)}",
                "pass_through": False,
                "action_kind": str(raw.get("action_kind", "native")),
            }
        )
        outputs.append(
            {
                "id": output_id,
                "producer_id": block_id,
                "consumer_ids": [
                    f"function-block:{entry.model_id}:contract:{_stable(candidate_id)}"
                    for candidate_id, candidate in step_by_id.items()
                    if step_id in tuple(str(item) for item in candidate.get("prerequisite_step_ids", ()))
                ],
                "terminal": step_id in route_terminal_steps,
            }
        )
        groundings[block_id] = {
            "kind": "exported_contract_step",
            "step_id": step_id,
            "route_id": str(raw.get("route_id", "")),
            "action_kind": str(raw.get("action_kind", "")),
            "terminal_kind": str(raw.get("terminal_kind", "")),
            "prerequisite_step_ids": list(prerequisites),
            "contract_fingerprint": canonical_fingerprint(dict(exported)),
            "position": index,
        }
    facts = {
        "provider_kind": "flowguard.executable-contract-export.v1",
        "states": [],
        "initial_state_ids": [],
        "terminal_state_ids": [],
        "transitions": [],
        "function_blocks": blocks,
        "fields": [],
        "effects": [],
        "validations": validations,
        "outputs": outputs,
        "owners": [],
        "export_schema_version": str(exported.get("schema_version", "")),
        "export_model_id": str(exported.get("model_id", "")),
        "export_parent_model_id": str(exported.get("parent_model_id", "")),
    }
    return _ProviderProjection(
        provider_kind="flowguard.executable-contract-export.v1",
        facts=facts,
        element_groundings=groundings,
        source_refs=(entry.model_path, entry.runner[1]),
    )


def _runner_called_owner_symbols(runner_path: Path) -> tuple[str, ...]:
    try:
        tree = ast.parse(runner_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as exc:
        raise SelfPathQualityError(f"native runner cannot be inspected: {runner_path}: {exc}") from exc
    direct_imports: dict[str, str] = {}
    module_imports: dict[str, str] = {}
    local_functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            module = str(node.module or "")
            for alias in node.names:
                direct_imports[alias.asname or alias.name] = f"{module}:{alias.name}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                module_imports[alias.asname or alias.name] = alias.name
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            local_functions[node.name] = node
    root = local_functions.get("main")
    if root is None:
        return ()
    calls: list[tuple[int, str]] = []
    visited: set[str] = set()

    def visit(function: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if function.name in visited:
            return
        visited.add(function.name)
        for node in ast.walk(function):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                name = node.func.id
                if name in local_functions:
                    visit(local_functions[name])
                elif name in direct_imports:
                    calls.append((node.lineno, direct_imports[name]))
            elif (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in module_imports
            ):
                calls.append(
                    (
                        node.lineno,
                        f"{module_imports[node.func.value.id]}:{node.func.attr}",
                    )
                )

    visit(root)
    ordered: list[str] = []
    for _line, symbol in sorted(calls):
        if symbol not in ordered:
            ordered.append(symbol)
    return tuple(ordered)


def _runner_projection(
    root: Path,
    entry: ModelRegressionEntry,
    instance: ModelInstanceRef,
) -> _ProviderProjection:
    runner_path = (root / entry.runner[1]).resolve()
    symbols = _runner_called_owner_symbols(runner_path)
    gaps: list[str] = []
    if not symbols:
        symbols = (f"native-runner:{entry.model_id}:main",)
        gaps.append("provider_native_entrypoint_graph_incomplete")
    workflow = Workflow(
        tuple(_RunnerEvidenceBlock(symbol) for symbol in symbols),
        name=f"native-evidence-owner:{entry.model_id}",
    )
    projection = _workflow_projection(entry, instance, (workflow,), ())
    groundings = {
        element_id: {
            **dict(value),
            "kind": (
                "native_runner_evidence_call"
                if value.get("kind")
                in {
                    "executable_workflow_block_relation",
                    "executable_workflow_transition",
                }
                else value.get("kind")
            ),
            "called_owner_symbols": list(symbols),
        }
        for element_id, value in projection.element_groundings.items()
    }
    facts = dict(projection.facts)
    facts["provider_kind"] = "flowguard.native-runner-evidence-structure.v1"
    return _ProviderProjection(
        provider_kind="flowguard.native-runner-evidence-structure.v1",
        facts=facts,
        element_groundings=groundings,
        source_refs=projection.source_refs,
        gaps=tuple(gaps),
    )


class _RunnerEvidenceBlock:
    def __init__(self, symbol: str) -> None:
        self.name = symbol
        self.accepted_input_type = "native-evidence-input"


def _add_purpose_material(
    projection: _ProviderProjection,
    entry: ModelRegressionEntry,
    instance: ModelInstanceRef,
) -> _ProviderProjection:
    purpose = entry.purpose_closure
    if purpose is None:
        raise SelfPathQualityError(f"current model has no purpose closure: {entry.model_id}")
    facts = {key: value for key, value in projection.facts.items()}
    validations = [dict(row) for row in facts.get("validations", ())]
    groundings = {key: dict(value) for key, value in projection.element_groundings.items()}
    known_validation_ids = {str(row.get("id", "")) for row in validations}
    for binding in purpose.failure_bindings:
        validation_id = (
            f"validation:{entry.model_id}:protected-failure:{_stable(binding.failure_id)}"
        )
        if validation_id in known_validation_ids:
            continue
        validations.append(
            {
                "id": validation_id,
                "obligation_id": binding.failure_id,
                "oracle_id": binding.oracle_id,
                "subject_fingerprint": instance.fingerprint,
                "evidence_boundary_id": f"purpose-closure:{purpose.closure_fingerprint}",
            }
        )
        groundings[validation_id] = {
            "kind": "protected_failure_native_oracle",
            "failure_id": binding.failure_id,
            "known_bad_case_id": binding.known_bad_case_id,
            "oracle_id": binding.oracle_id,
            "evidence_check_ids": list(purpose.evidence_check_ids),
            "purpose_closure_fingerprint": purpose.closure_fingerprint,
        }
    facts["validations"] = validations
    facts["owners"] = [
        {
            "id": f"owner:model:{entry.model_id}",
            "intent_id": purpose.task_intent_id,
            "boundary_id": f"model-boundary:{entry.model_id}",
            "current": True,
        }
    ]
    facts["provider_contract"] = {
        "model_instance_fingerprint": instance.fingerprint,
        "model_kind": instance.model_kind,
        "model_path": instance.model_path,
        "runner_path": instance.runner_path,
        "purpose_closure_fingerprint": purpose.closure_fingerprint,
        "input_inventory_fingerprint": instance.input_inventory_fingerprint,
        "native_evidence_check_ids": list(purpose.evidence_check_ids),
    }
    return _ProviderProjection(
        provider_kind=projection.provider_kind,
        facts=facts,
        element_groundings=groundings,
        source_refs=projection.source_refs,
        gaps=projection.gaps,
    )


def _project_provider(
    root: Path,
    entry: ModelRegressionEntry,
    instance: ModelInstanceRef,
) -> _ProviderProjection:
    module = _load_model_module(root, entry, instance)
    workflows = _current_workflows(module)
    invariants = _current_invariants(module)
    if workflows:
        projection = _workflow_projection(entry, instance, workflows, invariants)
    else:
        exporter = getattr(module, "export_contract_model", None)
        exported: Mapping[str, Any] | None = None
        if callable(exporter):
            try:
                candidate = exporter()
            except Exception as exc:
                raise SelfPathQualityError(
                    f"contract export failed for {entry.model_id}: {type(exc).__name__}: {exc}"
                ) from exc
            if not isinstance(candidate, Mapping):
                raise SelfPathQualityError(
                    f"contract export is not an object: {entry.model_id}"
                )
            exported = candidate
        projection = (
            _contract_export_projection(entry, instance, exported)
            if exported is not None
            else _runner_projection(root, entry, instance)
        )
    return _add_purpose_material(projection, entry, instance)


def _element_evidence_rows(
    entry: ModelRegressionEntry,
    instance: ModelInstanceRef,
    projection: _ProviderProjection,
    retained_elements: Sequence[tuple[str, str]],
) -> tuple[dict[str, Any], ...]:
    purpose = entry.purpose_closure
    if purpose is None:
        raise SelfPathQualityError(f"current model has no purpose closure: {entry.model_id}")
    validation_by_id = {
        str(row.get("id", "")): row
        for row in projection.facts.get("validations", ())
        if isinstance(row, Mapping)
    }
    rows: list[dict[str, Any]] = []
    for element_id, element_kind in retained_elements:
        grounding = projection.element_groundings.get(element_id)
        if grounding is None:
            continue
        validation = validation_by_id.get(element_id)
        if validation is not None:
            obligation_id = str(validation.get("obligation_id", ""))
            oracle_id = str(validation.get("oracle_id", ""))
            binding = next(
                (
                    item
                    for item in purpose.failure_bindings
                    if item.failure_id == obligation_id
                ),
                None,
            )
            counterexample_id = (
                binding.known_bad_case_id
                if binding is not None
                else f"counterexample:remove-validation:{canonical_fingerprint(grounding)[-16:]}"
            )
            evidence_kind = "native_model_check"
        else:
            relation_fingerprint = canonical_fingerprint(
                {
                    "element_id": element_id,
                    "element_kind": element_kind,
                    "grounding": dict(grounding),
                }
            )
            obligation_id = (
                f"obligation:preserve-provider-relation:{entry.model_id}:"
                f"{relation_fingerprint[-16:]}"
            )
            oracle_id = "oracle:flowguard-self-element-removal.v1"
            counterexample_id = (
                f"counterexample:remove-provider-element:{entry.model_id}:"
                f"{relation_fingerprint[-16:]}"
            )
            evidence_kind = "executable_oracle"
        evidence_payload = {
            "schema_version": SELF_PATH_QUALITY_SCHEMA_VERSION,
            "oracle_kind": "element_removal_breaks_current_provider_relation",
            "model_id": entry.model_id,
            "model_instance_fingerprint": instance.fingerprint,
            "element_id": element_id,
            "element_kind": element_kind,
            "obligation_id": obligation_id,
            "counterexample_id": counterexample_id,
            "oracle_id": oracle_id,
            "grounding": dict(grounding),
            "purpose_closure_fingerprint": purpose.closure_fingerprint,
            "native_evidence_check_ids": list(purpose.evidence_check_ids),
            "outcome": "declared provider relation or protected failure is missing after removal",
        }
        rows.append(
            {
                "element_id": element_id,
                "element_kind": element_kind,
                "obligation_id": obligation_id,
                "counterexample_id": counterexample_id,
                "oracle_id": oracle_id,
                "evidence_kind": evidence_kind,
                "evidence_fingerprint": canonical_fingerprint(evidence_payload),
            }
        )
    return tuple(rows)


def _augment_provider_gaps(
    result: PathQualityResult,
    provider_gaps: Sequence[str],
) -> PathQualityResult:
    if not provider_gaps:
        return result
    unresolved = tuple(
        sorted(
            {
                *result.unresolved_ids,
                *(f"provider_gap:{gap}" for gap in provider_gaps),
            }
        )
    )
    triggers = tuple(sorted({*result.trigger_ids, "missing_necessity_witness"}))
    detail = canonical_fingerprint(
        {
            "prior_detail_evidence_fingerprint": result.detail_evidence_fingerprint,
            "provider_gaps": list(sorted(provider_gaps)),
            "trigger_ids": list(triggers),
            "unresolved_ids": list(unresolved),
        }
    )
    return replace(
        result,
        result_id=f"path-quality:provider-gap:{detail[-16:]}",
        trigger_ids=triggers,
        conclusion="unresolved",
        unresolved_ids=unresolved,
        detail_evidence_fingerprint=detail,
    )


def _measure_path_costs(
    model_id: str,
    projection: _ProviderProjection,
) -> tuple[dict[str, float], dict[str, str], str]:
    """Derive a small, deterministic cost packet from provider-neutral facts."""

    facts = projection.facts
    states = tuple(facts.get("states", ()) or ())
    transitions = tuple(facts.get("transitions", ()) or ())
    blocks = tuple(facts.get("function_blocks", ()) or ())
    validations = tuple(facts.get("validations", ()) or ())
    source_counts: dict[str, int] = {}
    for row in transitions:
        if isinstance(row, Mapping):
            source = str(row.get("source", ""))
            if source:
                source_counts[source] = source_counts.get(source, 0) + 1
    branches = sum(max(0, count - 1) for count in source_counts.values())
    branches += sum(
        max(0, len(row.get("outputs", ())) - 1)
        for row in transitions
        if isinstance(row, Mapping)
    )
    try:
        payload_bytes = len(
            json.dumps(
                facts,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                default=str,
                allow_nan=False,
            ).encode("utf-8")
        )
    except (TypeError, ValueError) as exc:
        raise SelfPathQualityError(
            f"provider facts cannot be measured for {model_id}: {exc}"
        ) from exc
    costs = {
        "steps": float(len(blocks)),
        "states": float(len(states)),
        "transitions": float(len(transitions)),
        "branches": float(branches),
        "validations": float(len(validations)),
        "payload_bytes": float(payload_bytes),
    }
    measurement_fingerprint = canonical_fingerprint(
        {
            "model_id": model_id,
            "provider_fingerprint": projection.fingerprint,
            "costs": costs,
            "thresholds": SELF_PATH_COST_THRESHOLDS,
        }
    )
    evidence = {
        dimension: canonical_fingerprint(
            {
                "measurement": measurement_fingerprint,
                "model_id": model_id,
                "dimension": dimension,
                "value": value,
                "threshold": SELF_PATH_COST_THRESHOLDS[dimension],
            }
        )
        for dimension, value in costs.items()
    }
    return costs, evidence, measurement_fingerprint


def _compile_model_detail(
    entry: ModelRegressionEntry,
    instance: ModelInstanceRef,
    candidate_snapshot_fingerprint: str,
    projection: _ProviderProjection,
    *,
    explicit_deep_request: bool,
    declared_candidate_count: int,
    path_design_model_miss: bool,
    high_cost_boundary: bool,
    release_critical_boundary: bool,
) -> SelfModelPathQualityDetail:
    purpose = entry.purpose_closure
    if purpose is None:
        raise SelfPathQualityError(f"current model has no purpose closure: {entry.model_id}")
    retained = derive_retained_elements(projection.facts)
    measured_costs, cost_evidence, measurement_fingerprint = _measure_path_costs(
        entry.model_id,
        projection,
    )
    evidence_rows = _element_evidence_rows(entry, instance, projection, retained)
    obligations = tuple(sorted({row["obligation_id"] for row in evidence_rows}))
    subject = PathQualitySubject(
        model_id=entry.model_id,
        boundary_id=f"model-boundary:{entry.model_id}",
        model_fingerprint=instance.fingerprint,
        normalized_facts_fingerprint=normalized_model_facts_fingerprint(projection.facts),
        retained_element_inventory_fingerprint=canonical_fingerprint(dict(retained)),
        purpose_fingerprint=purpose.closure_fingerprint,
        intent_fingerprint=canonical_fingerprint(
            {
                "task_intent_id": purpose.task_intent_id,
                "guarded_purpose": purpose.guarded_purpose,
                "claim_boundary": purpose.claim_boundary,
            }
        ),
        obligation_fingerprint=canonical_fingerprint(list(obligations)),
        provider_fingerprint=projection.fingerprint,
        dependency_fingerprint=instance.input_inventory_fingerprint,
        code_fingerprint=instance.model_sha256,
        test_fingerprint=canonical_fingerprint(
            {
                "runner_sha256": instance.runner_sha256,
                "test_inputs": [
                    item.to_dict()
                    for item in instance.inputs
                    if item.path.startswith("tests/")
                ],
            }
        ),
        oracle_fingerprint=canonical_fingerprint(
            {
                "known_good_case_id": purpose.known_good_case_id,
                "failure_bindings": [item.to_dict() for item in purpose.failure_bindings],
            }
        ),
        evidence_fingerprint=canonical_fingerprint(
            {
                "native_evidence_check_ids": list(purpose.evidence_check_ids),
                "element_evidence": evidence_rows,
                "runner_sha256": instance.runner_sha256,
            }
        ),
        currentness_id=candidate_snapshot_fingerprint,
    )
    witnesses = tuple(
        NecessityWitness(
            witness_id=(
                f"witness:self-path:{entry.model_id}:"
                f"{canonical_fingerprint(row)[-16:]}"
            ),
            subject_fingerprint=subject.fingerprint,
            element_id=row["element_id"],
            element_kind=row["element_kind"],
            obligation_id=row["obligation_id"],
            counterexample_id=row["counterexample_id"],
            oracle_id=row["oracle_id"],
            evidence_fingerprint=row["evidence_fingerprint"],
            evidence_currentness_id=candidate_snapshot_fingerprint,
            evidence_kind=row["evidence_kind"],
        )
        for row in evidence_rows
    )
    findings = find_lightweight_findings(projection.facts)
    witness_gaps = validate_necessity_witnesses(
        subject,
        retained,
        witnesses,
        expected_currentness_id=candidate_snapshot_fingerprint,
        active_obligation_ids=obligations,
    )
    trigger_ids = collect_deep_review_triggers(
        findings,
        explicit_request=explicit_deep_request,
        declared_candidate_count=declared_candidate_count,
        path_design_model_miss=path_design_model_miss,
        missing_necessity_witness=any(
            gap.startswith("missing_necessity_witness:") for gap in witness_gaps
        ),
        high_cost_boundary=high_cost_boundary,
        release_critical_boundary=release_critical_boundary,
        measured_costs=measured_costs,
        cost_thresholds=SELF_PATH_COST_THRESHOLDS,
    )
    trigger_evidence = {
        trigger_id: canonical_fingerprint(
            {
                "model_id": entry.model_id,
                "subject_fingerprint": subject.fingerprint,
                "trigger_id": trigger_id,
                "measurement_fingerprint": measurement_fingerprint,
                "currentness_id": candidate_snapshot_fingerprint,
            }
        )
        for trigger_id in trigger_ids
    }
    result = lightweight_path_review(
        subject,
        projection.facts,
        retained_elements=retained,
        necessity_witnesses=witnesses,
        active_obligation_ids=obligations,
        explicit_deep_request=explicit_deep_request,
        declared_candidate_count=declared_candidate_count,
        path_design_model_miss=path_design_model_miss,
        high_cost_boundary=high_cost_boundary,
        release_critical_boundary=release_critical_boundary,
        measured_costs=measured_costs,
        cost_thresholds=SELF_PATH_COST_THRESHOLDS,
        cost_evidence=cost_evidence,
        trigger_evidence=trigger_evidence,
        trigger_currentness_id=candidate_snapshot_fingerprint,
        producer_id=SELF_PATH_QUALITY_PRODUCER_ID,
    )
    result = _augment_provider_gaps(result, projection.gaps)
    return SelfModelPathQualityDetail(
        model_id=entry.model_id,
        provider_kind=projection.provider_kind,
        provider_fingerprint=projection.fingerprint,
        model_facts=projection.facts,
        retained_elements=retained,
        active_obligation_ids=obligations,
        necessity_witnesses=witnesses,
        subject=subject,
        result=result,
        source_refs=projection.source_refs,
        provider_gaps=projection.gaps,
    )


def compile_flowguard_self_path_quality_material(
    root: str | Path,
    candidate_snapshot: ModelSystemSnapshot,
    *,
    required_model_ids: Iterable[str] | None = None,
    explicit_deep_model_ids: Iterable[str] = (),
    declared_candidate_counts: Mapping[str, int] | None = None,
    path_design_model_miss_ids: Iterable[str] = (),
    high_cost_model_ids: Iterable[str] = (),
    release_critical_model_ids: Iterable[str] = (),
) -> FlowGuardSelfPathQualityMaterial:
    """Compile current self-model facts and run the ordinary light review.

    A current deep trigger remains an exact unresolved handoff.  This function
    never invents finite candidates, runs a reconstruction exercise, mutates a
    model, or writes an authority artifact.
    """

    if not isinstance(candidate_snapshot, ModelSystemSnapshot):
        raise SelfPathQualityError("candidate_snapshot must be a ModelSystemSnapshot")
    root_path = Path(root).resolve()
    manifest = ModelRegressionManifest.load(root_path)
    manifest_fingerprint = file_fingerprint(manifest.path)
    manifest_refs = tuple(
        item
        for item in candidate_snapshot.owner_artifact_refs
        if item.endpoint_kind == "parent_closure"
        and item.endpoint_id.endswith(":model-regression-manifest")
    )
    if len(manifest_refs) != 1 or manifest_refs[0].fingerprint != manifest_fingerprint:
        raise SelfPathQualityError(
            "candidate snapshot is not bound to the exact current model manifest"
        )
    entries_by_id = {
        entry.model_id: entry for entry in manifest.entries if not entry.excluded
    }
    default_required = tuple(sorted(entries_by_id))
    requested = default_required if required_model_ids is None else tuple(required_model_ids)
    required, _subjects, _results = normalize_path_quality_material(requested, (), ())
    foreign = tuple(sorted(set(required) - set(entries_by_id)))
    if foreign:
        raise SelfPathQualityError(
            "required self path-quality ids are not current manifest owners: "
            + ", ".join(foreign)
        )
    instances_by_id = {
        item.logical_model_id: item for item in candidate_snapshot.model_instances
    }
    explicit_deep = set(explicit_deep_model_ids)
    model_misses = set(path_design_model_miss_ids)
    high_cost = set(high_cost_model_ids)
    release_critical = set(release_critical_model_ids)
    counts = dict(declared_candidate_counts or {})
    invalid_counts = tuple(
        sorted(
            str(model_id)
            for model_id, count in counts.items()
            if isinstance(count, bool) or not isinstance(count, int) or count < 0
        )
    )
    if invalid_counts:
        raise SelfPathQualityError(
            "declared candidate counts must be non-negative integers: "
            + ", ".join(invalid_counts)
        )
    signal_ids = explicit_deep | model_misses | high_cost | release_critical | set(counts)
    foreign_signals = tuple(sorted(signal_ids - set(required)))
    if foreign_signals:
        raise SelfPathQualityError(
            "path-quality trigger ids are outside the required denominator: "
            + ", ".join(foreign_signals)
        )
    details: list[SelfModelPathQualityDetail] = []
    global_gaps: list[str] = []
    for model_id in required:
        instance = instances_by_id.get(model_id)
        if instance is None:
            global_gaps.append(f"candidate_model_instance_missing:{model_id}")
            continue
        entry = entries_by_id[model_id]
        if instance.model_path != entry.model_path or (
            len(entry.runner) < 2 or instance.runner_path != entry.runner[1]
        ):
            global_gaps.append(f"candidate_model_instance_owner_mismatch:{model_id}")
            continue
        stale_inputs = tuple(
            item.path
            for item in instance.inputs
            if not (root_path / item.path).is_file()
            or file_fingerprint(root_path / item.path) != item.sha256
        )
        if stale_inputs:
            global_gaps.append(
                "candidate_model_instance_inputs_stale:"
                f"{model_id}:{','.join(stale_inputs)}"
            )
            continue
        try:
            projection = _project_provider(root_path, entry, instance)
            details.append(
                _compile_model_detail(
                    entry,
                    instance,
                    candidate_snapshot.fingerprint,
                    projection,
                    explicit_deep_request=model_id in explicit_deep,
                    declared_candidate_count=counts.get(model_id, 0),
                    path_design_model_miss=model_id in model_misses,
                    high_cost_boundary=model_id in high_cost,
                    release_critical_boundary=model_id in release_critical,
                )
            )
        except (OSError, TypeError, ValueError) as exc:
            global_gaps.append(
                f"provider_material_blocked:{model_id}:{type(exc).__name__}:{exc}"
            )
    details.sort(key=lambda item: item.model_id)
    subjects = tuple(item.subject for item in details)
    results = tuple(item.result for item in details)
    expected_models = {
        model_id: instances_by_id[model_id].fingerprint
        for model_id in required
        if model_id in instances_by_id
    }
    review = review_path_quality_material(
        required,
        subjects,
        results,
        expected_currentness_id=candidate_snapshot.fingerprint,
        expected_model_fingerprints=expected_models,
        require_exact_currentness=True,
        require_exact_model_fingerprints=True,
    )
    # Recompute through the one canonical helper instead of trusting a
    # consumer projection.
    if review.result_set_fingerprint != path_quality_result_set_fingerprint(
        required, subjects, results
    ):
        raise SelfPathQualityError("path-quality result-set fingerprint drifted")
    details_by_id = {item.model_id: item for item in details}
    deep_trigger_census = tuple(
        SelfModelDeepTriggerCensusEntry(
            model_id=model_id,
            explicit_deep_request=model_id in explicit_deep,
            declared_candidate_count=counts.get(model_id, 0),
            path_design_model_miss=model_id in model_misses,
            high_cost_boundary=model_id in high_cost,
            release_critical_boundary=model_id in release_critical,
            finding_ids=(
                details_by_id[model_id].result.finding_ids
                if model_id in details_by_id
                else ()
            ),
            trigger_ids=(
                details_by_id[model_id].result.trigger_ids
                if model_id in details_by_id
                else ()
            ),
            conclusion=(
                details_by_id[model_id].result.conclusion
                if model_id in details_by_id
                else ""
            ),
            currentness_id=(
                details_by_id[model_id].result.currentness_id
                if model_id in details_by_id
                else ""
            ),
            current=(
                details_by_id[model_id].result.current
                if model_id in details_by_id
                else False
            ),
            result_available=model_id in details_by_id,
            measured_costs=(
                details_by_id[model_id].result.cost_measurements
                if model_id in details_by_id
                else ()
            ),
            optimization_depth=(
                details_by_id[model_id].result.optimization_depth
                if model_id in details_by_id
                else ""
            ),
            cost_detail_evidence_fingerprint=(
                details_by_id[model_id].result.cost_detail_evidence_fingerprint
                if model_id in details_by_id
                else ""
            ),
            trigger_evidence_fingerprint=(
                details_by_id[model_id].result.trigger_evidence_fingerprint
                if model_id in details_by_id
                else ""
            ),
        )
        for model_id in required
    )
    return FlowGuardSelfPathQualityMaterial(
        candidate_snapshot_fingerprint=candidate_snapshot.fingerprint,
        required_model_ids=required,
        details=tuple(details),
        deep_trigger_census=deep_trigger_census,
        review=review,
        global_gaps=tuple(sorted(global_gaps)),
    )


def build_flowguard_self_path_quality_material(
    root: str | Path,
    *,
    snapshot_id: str,
    system_id: str = "flowguard",
    subject_lane: str = SUBJECT_OBSERVED_IMPLEMENTATION,
    lifecycle: str = LIFECYCLE_ACTIVE,
    subject_revision: str = "",
    **review_options: Any,
) -> FlowGuardSelfPathQualityMaterial:
    """Build one candidate snapshot and compile matching self path material."""

    root_path = Path(root).resolve()
    snapshot = build_manifest_model_system_snapshot(
        root_path,
        snapshot_id=snapshot_id,
        system_id=system_id,
        subject_lane=subject_lane,
        lifecycle=lifecycle,
        subject_revision=subject_revision,
    )
    return compile_flowguard_self_path_quality_material(
        root_path,
        snapshot,
        **review_options,
    )


__all__ = [
    "SELF_PATH_QUALITY_PRODUCER_ID",
    "SELF_PATH_COST_THRESHOLDS",
    "SELF_PATH_QUALITY_SCHEMA_VERSION",
    "FlowGuardSelfPathQualityMaterial",
    "SelfModelDeepTriggerCensusEntry",
    "SelfModelPathQualityDetail",
    "SelfPathQualityError",
    "build_flowguard_self_path_quality_material",
    "compile_flowguard_self_path_quality_material",
]
