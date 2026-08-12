"""Project-neutral composition of an inspectable target-system blueprint.

The builder joins independently declared model semantics, discovered code or
workflow surfaces, exact test/checker design, intent, and owned resources.  It
is read-only with respect to the target project.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, replace
from functools import cached_property
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .implementation_blueprint import (
    BlueprintResourceReference,
    ModelImplementationBinding,
    ModelImplementationBindingReport,
    OracleReference,
    SemanticSpecReference,
    SoftwareBlueprintManifest,
    BlueprintManifestQualificationReport,
    _qualify_blueprint_manifest,
    review_model_implementation_bindings,
)
from .implementation_inventory import (
    DiscoveryAdapter,
    DynamicSelectorContract,
    ImplementationFileDisposition,
    ImplementationInventoryAuditReport,
    ImplementationSurface,
    ImplementationSurfaceInventory,
    IMPLEMENTATION_DISPOSITION_MODEL,
    SoftwareBoundary,
    build_implementation_surface_inventory,
    implementation_behavior_surface_ids,
    review_implementation_surface_inventory,
)
from .implementation_inventory_python import _collect_node_specs
from .test_inventory import (
    ProjectTestInventory,
    TestDiscoveryAdapter,
    review_project_test_inventory,
)
from .source_identity import source_file_fingerprint
from .evidence_receipts import fingerprint_value
from .model_test_alignment import (
    CodeContract,
    ModelObligation,
    ModelTestAlignmentPlan,
    ModelTestAlignmentReport,
    TestEvidence,
    review_model_test_alignment,
)
from .blueprint_topology import (
    BlueprintTopologyNode,
    BlueprintTopologyPort,
    BlueprintTopologyPortMapping,
    BlueprintTopologyProgressContract,
    BlueprintTopologyRelation,
    BlueprintTopologyReport,
    review_blueprint_topology,
)
from .hierarchy import ChildModelEvidence, ChildReattachmentContract
from .software_blueprint_readiness import (
    BEHAVIOR_CASE_DIMENSIONS,
    BEHAVIOR_DIMENSIONS,
    INTENT_INVENTORY_SCHEMA,
    BehaviorCaseContract,
    BehaviorBlockContract,
    BehaviorBlueprintReport,
    BehaviorCoverageEdge,
    BehaviorDimensionContract,
    CoverageExecutionEvidence,
    DelegatedAssertionHelper,
    IntentSourceAuthority,
    NoDeclaredIntentRationale,
    NormalizedBlueprintProjection,
    ObservedResourceMember,
    ProjectIntentInventory,
    ProjectIntentContribution,
    ProjectResourceInventory,
    ProjectResourceMember,
    ProjectTestNodeDisposition,
    PortableBehaviorBinding,
    ReadinessFinding,
    StaticBlueprintReadinessReport,
    SupportingSurfaceRelation,
    normalize_behavior_blueprint,
    materialize_behavior_blueprint_shards,
    review_behavior_blueprint,
    review_static_blueprint_readiness,
)
from .affected_blueprint_reader import (
    AffectedBlueprintIndex,
    AffectedBlueprintReadResult,
    AffectedBlueprintUnderstanding,
    materialize_affected_blueprint_index,
    read_affected_blueprint,
    read_affected_blueprint_understanding,
)
from .target_system_blueprint import (
    CANONICAL_SOFTWARE_LAYER_PLAN,
    BlueprintGapRef,
    BlueprintLayerResult,
    BlueprintNativeReportRef,
    BlueprintReadinessLedger,
    BlueprintUnderstandingSummary,
    FrozenTargetSystemEvidence,
    ModelPathQualityBlueprintBinding,
    ProviderCapabilityBinding,
    TargetSystemBlueprintReport,
    TargetSystemDescriptor,
    TargetSystemProviderDeclaration,
    TargetSystemProviderRegistry,
    TargetSystemProviderResult,
    build_target_system_provider_registry,
    capture_target_system_snapshot,
    _assemble_target_system_blueprint,
    project_blueprint_understanding,
    validate_blueprint_native_reports,
)


PROJECT_BLUEPRINT_DEFINITION_SCHEMA = "flowguard.project_blueprint_definition.v11"


class ProjectBlueprintError(ValueError):
    """Raised when a project blueprint declaration is not exact-current."""


def _project_native_report_refs(subject: Any) -> dict[str, BlueprintNativeReportRef]:
    """Return only exact child reports currently supplied by a project wrapper."""

    inventory = getattr(subject, "inventory", None)
    inventory_audit = getattr(subject, "implementation_inventory_audit", None)
    binding = getattr(subject, "binding_report", None)
    manifest = getattr(subject, "manifest", None)
    qualification = getattr(subject, "qualification", None)
    model_test = getattr(subject, "model_test_alignment_report", None)
    topology = getattr(subject, "topology_report", None)
    behavior = getattr(subject, "behavior_report", None)
    resources = getattr(subject, "resource_inventory", None)
    intent = getattr(subject, "intent_inventory", None)
    normalized = getattr(subject, "normalized_projection", None)
    readiness = getattr(subject, "static_readiness", None)
    evidence = getattr(subject, "evidence", None)
    test_inventory = getattr(subject, "test_inventory", None)
    if test_inventory is None and evidence is not None:
        test_inventory = getattr(evidence, "test_inventory", None)

    refs: dict[str, BlueprintNativeReportRef] = {}

    def add(key: str, owner_id: str, report_id: str, fingerprint: str) -> None:
        if report_id and fingerprint:
            refs[key] = BlueprintNativeReportRef(
                owner_id=owner_id,
                report_id=report_id,
                report_fingerprint=fingerprint,
            )

    if inventory is not None and isinstance(
        inventory_audit, ImplementationInventoryAuditReport
    ):
        add(
            "implementation_inventory",
            "implementation-inventory",
            f"implementation-inventory-audit:{inventory.inventory_id}",
            str(inventory_audit.fingerprint),
        )
    if binding is not None and inventory is not None:
        add(
            "binding",
            "model-implementation-binding",
            f"binding-report:{inventory.inventory_id}",
            str(binding.fingerprint),
        )
    if topology is not None:
        add(
            "topology",
            "blueprint-topology",
            str(topology.topology_id),
            str(topology.fingerprint),
        )
    if behavior is not None and inventory is not None:
        add(
            "behavior",
            "behavior-blueprint",
            f"behavior-report:{inventory.inventory_id}",
            str(behavior.fingerprint),
        )
    if model_test is not None:
        add(
            "model_test_alignment",
            "model-test-alignment",
            str(model_test.model_id),
            str(model_test.fingerprint),
        )
    if test_inventory is not None:
        add(
            "test_inventory",
            "project-test-inventory",
            str(test_inventory.inventory_id),
            str(test_inventory.inventory_fingerprint),
        )
    if resources is not None:
        add(
            "resource_inventory",
            "project-resource-inventory",
            str(resources.inventory_id),
            str(resources.fingerprint),
        )
    if intent is not None:
        add(
            "intent_inventory",
            "project-intent-inventory",
            str(intent.inventory_id),
            str(intent.fingerprint),
        )
    if manifest is not None:
        add(
            "manifest",
            "software-blueprint-manifest",
            str(manifest.blueprint_id),
            str(manifest.fingerprint),
        )
    if qualification is not None:
        add(
            "qualification",
            "software-blueprint-qualification",
            str(qualification.blueprint_id),
            str(qualification.fingerprint),
        )
    if normalized is not None and manifest is not None:
        add(
            "normalized_projection",
            "normalized-blueprint-projection",
            f"normalized-projection:{manifest.blueprint_id}",
            str(normalized.fingerprint),
        )
    if readiness is not None and manifest is not None:
        add(
            "static_readiness",
            "static-blueprint-readiness",
            f"static-readiness:{manifest.blueprint_id}",
            str(readiness.fingerprint),
        )
    return refs


def derive_project_blueprint_readiness_ledger(subject: Any) -> BlueprintReadinessLedger:
    """Bind one project or self wrapper to the same canonical child-report ledger."""

    target_report = getattr(subject, "target_system_report", None)
    if not isinstance(target_report, TargetSystemBlueprintReport):
        raise ProjectBlueprintError(
            "project/self wrapper has no typed canonical target-system report"
        )
    return validate_blueprint_native_reports(
        target_report,
        tuple(_project_native_report_refs(subject).values()),
    )


def _pairs(value: Mapping[str, str] | Sequence[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    rows = value.items() if isinstance(value, Mapping) else value
    return tuple(sorted((str(key), str(item)) for key, item in rows))


def _provider_declarations(
    value: Mapping[str, Sequence[str]] | Sequence[tuple[str, Sequence[str]]],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    rows = value.items() if isinstance(value, Mapping) else value
    normalized = tuple(
        sorted(
            (
                str(provider_id).strip(),
                tuple(sorted({str(item).strip() for item in capabilities if str(item).strip()})),
            )
            for provider_id, capabilities in rows
        )
    )
    if any(not provider_id or not capabilities for provider_id, capabilities in normalized):
        raise ProjectBlueprintError(
            "project blueprint providers require identity and capabilities"
        )
    if len(normalized) != len({provider_id for provider_id, _capabilities in normalized}):
        raise ProjectBlueprintError("project blueprint provider identity is duplicated")
    return normalized


def project_surface_dimensions(surface: ImplementationSurface) -> tuple[str, ...]:
    # Deep project blueprints make lifecycle dimensions explicit even when the
    # owning model declares them not applicable; silence is not closure.
    dimensions = {"input", "output", "error", "order", "retry", "timeout", "completion"}
    if surface.state_writes or surface.side_effect_candidates or surface.dynamic_operations:
        dimensions.add("state_effect")
    if surface.calls or surface.dynamic_operations:
        dimensions.add("decision")
    return tuple(sorted(dimensions))


def _project_behavior_surface_ids(
    inventory: ImplementationSurfaceInventory,
) -> set[str]:
    """Return the active observation provider's behavior denominator."""

    return set(implementation_behavior_surface_ids(inventory))


@dataclass(frozen=True)
class _CanonicalConsumerIndex:
    callers_by_surface_id: dict[str, frozenset[str]]
    gap_ids_by_surface_id: dict[str, tuple[str, ...]]
    gaps: tuple[dict[str, Any], ...]


def _canonical_consumer_index(
    surfaces: Sequence[ImplementationSurface],
    *,
    root: str | Path | None = None,
) -> _CanonicalConsumerIndex:
    """Resolve one shared, exact call graph for blueprint and reduction use.

    A same-file definition is a stronger identity than a repository-wide short
    name.  This matters for ordinary repeated names such as ``main``,
    ``run_case``, and ``from_dict``: treating all of them as globally
    ambiguous makes local code look unreferenced and inflates cleanup work.
    Object-qualified calls without a same-file type proof remain explicit
    gaps instead of being guessed.
    """

    ordered = tuple(surfaces)
    surface_ids = {row.surface_id for row in ordered}
    surface_path_by_id = {
        row.surface_id: str(getattr(row, "path", "")) for row in ordered
    }
    by_symbol: dict[str, set[str]] = {}
    by_short_name: dict[str, set[str]] = {}
    by_path_symbol: dict[tuple[str, str], set[str]] = {}
    by_path_short_name: dict[tuple[str, str], set[str]] = {}
    for surface in ordered:
        symbol = str(getattr(surface, "symbol", surface.surface_id))
        path = str(getattr(surface, "path", ""))
        short_name = symbol.rsplit(".", 1)[-1]
        by_symbol.setdefault(symbol, set()).add(surface.surface_id)
        by_short_name.setdefault(short_name, set()).add(surface.surface_id)
        if path:
            by_path_symbol.setdefault((path, symbol), set()).add(
                surface.surface_id
            )
            by_path_short_name.setdefault((path, short_name), set()).add(
                surface.surface_id
            )

    direct_imports_by_path: dict[str, dict[str, tuple[str, str]]] = {}
    module_imports_by_path: dict[str, dict[str, str]] = {}
    receiver_types_by_surface_id: dict[str, dict[str, tuple[str, str]]] = {}
    if root is not None:
        root_path = Path(root).resolve()
        known_paths = {
            str(getattr(surface, "path", ""))
            for surface in ordered
            if str(getattr(surface, "path", ""))
        }

        def module_candidates(
            caller_path: str,
            module: str,
            level: int = 0,
        ) -> tuple[str, ...]:
            caller_parts = caller_path.removesuffix(".py").split("/")
            if caller_parts[-1:] == ["__init__"]:
                caller_parts = caller_parts[:-1]
            else:
                caller_parts = caller_parts[:-1]
            if level:
                keep = max(0, len(caller_parts) - level + 1)
                module_parts = caller_parts[:keep] + (
                    module.split(".") if module else []
                )
            else:
                module_parts = module.split(".") if module else []
            candidates: list[str] = []
            if module_parts:
                module_path = "/".join(module_parts)
                candidates.extend(
                    (f"{module_path}.py", f"{module_path}/__init__.py")
                )
                same_directory = "/".join(
                    caller_path.split("/")[:-1] + [f"{module_parts[-1]}.py"]
                )
                candidates.insert(0, same_directory)
            return tuple(
                dict.fromkeys(path for path in candidates if path in known_paths)
            )

        for source_path in sorted(known_paths):
            if not source_path.endswith(".py"):
                continue
            absolute_path = (root_path / source_path).resolve()
            try:
                absolute_path.relative_to(root_path)
                syntax = ast.parse(absolute_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, SyntaxError, ValueError):
                continue
            direct_rows: dict[str, set[tuple[str, str]]] = {}
            module_rows: dict[str, set[str]] = {}
            for node in syntax.body:
                if isinstance(node, ast.ImportFrom):
                    candidates = module_candidates(
                        source_path,
                        str(node.module or ""),
                        int(node.level or 0),
                    )
                    if len(candidates) != 1:
                        continue
                    target_path = candidates[0]
                    for alias in node.names:
                        if alias.name == "*":
                            continue
                        direct_rows.setdefault(
                            alias.asname or alias.name,
                            set(),
                        ).add((target_path, alias.name))
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        candidates = module_candidates(
                            source_path,
                            alias.name,
                        )
                        if len(candidates) != 1:
                            continue
                        module_rows.setdefault(
                            alias.asname or alias.name.split(".", 1)[0],
                            set(),
                        ).add(candidates[0])
            direct_imports_by_path[source_path] = {
                alias: next(iter(targets))
                for alias, targets in direct_rows.items()
                if len(targets) == 1
            }
            module_imports_by_path[source_path] = {
                alias: next(iter(targets))
                for alias, targets in module_rows.items()
                if len(targets) == 1
            }

            direct_imports = direct_imports_by_path[source_path]
            module_imports = module_imports_by_path[source_path]

            def expression_name(expression: ast.AST | None) -> str:
                if isinstance(expression, ast.Name):
                    return expression.id
                if isinstance(expression, ast.Attribute):
                    base = expression_name(expression.value)
                    return f"{base}.{expression.attr}" if base else expression.attr
                if isinstance(expression, ast.Subscript):
                    return expression_name(expression.value)
                if isinstance(expression, ast.Constant) and isinstance(
                    expression.value,
                    str,
                ):
                    return expression.value
                return ""

            def resolve_type_name(type_name: str) -> tuple[str, str] | None:
                if not type_name:
                    return None
                if "." not in type_name:
                    imported = direct_imports.get(type_name)
                    if imported is not None:
                        target_path, target_symbol = imported
                        targets = set(
                            by_path_symbol.get(
                                (target_path, target_symbol),
                                (),
                            )
                        ) or set(
                            by_path_short_name.get(
                                (target_path, target_symbol),
                                (),
                            )
                        )
                        if len(targets) == 1:
                            return target_path, target_symbol
                    local_targets = set(
                        by_path_short_name.get((source_path, type_name), ())
                    )
                    if len(local_targets) == 1:
                        target_id = next(iter(local_targets))
                        target_symbol = next(
                            surface.symbol
                            for surface in ordered
                            if surface.surface_id == target_id
                        )
                        return source_path, target_symbol
                    return None
                receiver, symbol = type_name.rsplit(".", 1)
                target_path = module_imports.get(receiver)
                if target_path is not None:
                    targets = set(
                        by_path_short_name.get((target_path, symbol), ())
                    )
                    if len(targets) == 1:
                        return target_path, symbol
                return None

            class _ReceiverTypeCollector(ast.NodeVisitor):
                def __init__(self) -> None:
                    self.rows: dict[str, tuple[str, str]] = {}

                def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                    return None

                def visit_AsyncFunctionDef(
                    self,
                    node: ast.AsyncFunctionDef,
                ) -> None:
                    return None

                def visit_ClassDef(self, node: ast.ClassDef) -> None:
                    return None

                def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
                    if isinstance(node.target, ast.Name):
                        resolved = resolve_type_name(
                            expression_name(node.annotation)
                        )
                        if resolved is not None:
                            self.rows[node.target.id] = resolved
                    self.generic_visit(node)

                def visit_Assign(self, node: ast.Assign) -> None:
                    if (
                        len(node.targets) == 1
                        and isinstance(node.targets[0], ast.Name)
                        and isinstance(node.value, ast.Call)
                    ):
                        resolved = resolve_type_name(
                            expression_name(node.value.func)
                        )
                        if resolved is not None:
                            self.rows[node.targets[0].id] = resolved
                    self.generic_visit(node)

            surface_id_by_symbol = {
                str(getattr(surface, "symbol", surface.surface_id)): surface.surface_id
                for surface in ordered
                if str(getattr(surface, "path", "")) == source_path
            }
            for spec in _collect_node_specs(syntax):
                surface_id = surface_id_by_symbol.get(spec.symbol)
                node = spec.node
                if surface_id is None or not isinstance(
                    node,
                    (ast.FunctionDef, ast.AsyncFunctionDef),
                ):
                    continue
                collector = _ReceiverTypeCollector()
                for argument in (
                    *node.args.posonlyargs,
                    *node.args.args,
                    *node.args.kwonlyargs,
                ):
                    resolved = resolve_type_name(
                        expression_name(argument.annotation)
                    )
                    if resolved is not None:
                        collector.rows[argument.arg] = resolved
                caller_owner = spec.symbol.rsplit(".", 1)[0] if "." in spec.symbol else ""
                if caller_owner:
                    collector.rows.setdefault(
                        "self",
                        (source_path, caller_owner),
                    )
                    collector.rows.setdefault(
                        "cls",
                        (source_path, caller_owner),
                    )
                for statement in node.body:
                    collector.visit(statement)
                if collector.rows:
                    receiver_types_by_surface_id[surface_id] = collector.rows

    consumers: dict[str, set[str]] = {}
    ambiguous_callers: dict[str, set[str]] = {}
    ambiguous_targets: dict[str, set[str]] = {}
    def exact_local_reference_targets(
        caller: ImplementationSurface,
        raw_reference: str,
    ) -> set[str]:
        caller_path = str(getattr(caller, "path", ""))
        caller_symbol = str(getattr(caller, "symbol", caller.surface_id))
        caller_parts = caller_symbol.split(".")
        caller_owner = (
            ".".join(caller_parts[:-1]) if len(caller_parts) > 1 else ""
        )
        if raw_reference in surface_ids:
            return {raw_reference}
        direct_imports = direct_imports_by_path.get(caller_path, {})
        module_imports = module_imports_by_path.get(caller_path, {})
        if "." not in raw_reference:
            imported = direct_imports.get(raw_reference)
            if imported is not None:
                target_path, target_symbol = imported
                targets = set(
                    by_path_symbol.get((target_path, target_symbol), ())
                ) or set(
                    by_path_short_name.get((target_path, target_symbol), ())
                )
                if len(targets) == 1:
                    return targets
            same_owner_targets = (
                set(
                    by_path_symbol.get(
                        (caller_path, f"{caller_owner}.{raw_reference}"),
                        (),
                    )
                )
                if caller_owner
                else set()
            )
            if len(same_owner_targets) == 1:
                return same_owner_targets
            same_file_targets = (
                set(
                    by_path_short_name.get(
                        (caller_path, raw_reference),
                        (),
                    )
                )
                if caller_path
                else set()
            )
            return same_file_targets if len(same_file_targets) == 1 else set()
        receiver, short_name = raw_reference.rsplit(".", 1)
        receiver_type = receiver_types_by_surface_id.get(
            caller.surface_id,
            {},
        ).get(receiver)
        if receiver_type is not None:
            target_path, target_type_symbol = receiver_type
            targets = set(
                by_path_symbol.get(
                    (
                        target_path,
                        f"{target_type_symbol}.{short_name}",
                    ),
                    (),
                )
            )
            if len(targets) == 1:
                return targets
        imported_receiver = direct_imports.get(receiver)
        if imported_receiver is not None:
            target_path, target_symbol = imported_receiver
            targets = set(
                by_path_symbol.get(
                    (target_path, f"{target_symbol}.{short_name}"),
                    (),
                )
            )
            if len(targets) == 1:
                return targets
        imported_module_path = module_imports.get(receiver)
        if imported_module_path is not None:
            targets = set(
                by_path_symbol.get((imported_module_path, short_name), ())
            ) or set(
                by_path_short_name.get(
                    (imported_module_path, short_name),
                    (),
                )
            )
            if len(targets) == 1:
                return targets
        if receiver in {"self", "cls"} and caller_owner:
            return set(
                by_path_symbol.get(
                    (caller_path, f"{caller_owner}.{short_name}"),
                    (),
                )
            )
        return (
            set(by_path_symbol.get((caller_path, raw_reference), ()))
            if caller_path
            else set()
        )

    for caller in ordered:
        caller_path = str(getattr(caller, "path", ""))
        caller_symbol = str(getattr(caller, "symbol", caller.surface_id))
        caller_parts = caller_symbol.split(".")
        caller_owner = (
            ".".join(caller_parts[:-1]) if len(caller_parts) > 1 else ""
        )
        for raw_call in getattr(caller, "calls", ()):
            targets: set[str]
            receiver_suffix_fallback = False
            exact_reference_targets = exact_local_reference_targets(
                caller,
                raw_call,
            )
            if len(exact_reference_targets) == 1:
                targets = exact_reference_targets
            elif raw_call in surface_ids:
                targets = {raw_call}
            elif "." not in raw_call:
                same_owner_targets = (
                    set(
                        by_path_symbol.get(
                            (caller_path, f"{caller_owner}.{raw_call}"),
                            (),
                        )
                    )
                    if caller_owner
                    else set()
                )
                same_file_targets = set(
                    by_path_short_name.get((caller_path, raw_call), ())
                )
                if len(same_owner_targets) == 1:
                    targets = same_owner_targets
                elif len(same_file_targets) == 1:
                    targets = same_file_targets
                elif raw_call in by_symbol:
                    targets = set(by_symbol[raw_call])
                else:
                    targets = set(by_short_name.get(raw_call, ()))
            elif raw_call in by_symbol:
                targets = set(by_symbol[raw_call])
            else:
                receiver, short_name = raw_call.rsplit(".", 1)
                if receiver in {"self", "cls"} and caller_owner:
                    targets = set(
                        by_path_symbol.get(
                            (caller_path, f"{caller_owner}.{short_name}"),
                            (),
                        )
                    )
                    if not targets:
                        targets = set(by_short_name.get(short_name, ()))
                        receiver_suffix_fallback = bool(targets)
                else:
                    targets = set(
                        by_path_symbol.get((caller_path, raw_call), ())
                    )
                    if not targets:
                        targets = set(by_short_name.get(short_name, ()))
                        receiver_suffix_fallback = bool(targets)
            if len(targets) == 1 and not receiver_suffix_fallback:
                target = next(iter(targets))
                consumers.setdefault(target, set()).add(caller.surface_id)
                target_path = surface_path_by_id.get(target, "")
                module_targets = set(
                    by_path_symbol.get((target_path, "<module>"), ())
                )
                if len(module_targets) == 1:
                    module_target = next(iter(module_targets))
                    if module_target != caller.surface_id:
                        consumers.setdefault(module_target, set()).add(
                            caller.surface_id
                        )
                continue
            if not targets:
                continue
            ambiguous_callers.setdefault(raw_call, set()).add(caller.surface_id)
            ambiguous_targets.setdefault(raw_call, set()).update(targets)

        # First-class callables, local decorators, and local properties can be
        # consumed without appearing in ast.Call position.  The Python
        # inventory already records these load references.  Admit only one
        # same-file target; never use a repository-wide suffix guess here.
        for raw_reference in getattr(caller, "state_reads", ()):
            targets = exact_local_reference_targets(caller, raw_reference)
            if len(targets) == 1:
                target = next(iter(targets))
                if target != caller.surface_id:
                    consumers.setdefault(target, set()).add(caller.surface_id)

    gaps: dict[str, dict[str, Any]] = {}
    gap_ids_by_surface: dict[str, set[str]] = {}
    for raw_call in sorted(ambiguous_callers):
        targets = ambiguous_targets[raw_call]
        gap_payload = {
            "raw_call": raw_call,
            "caller_surface_ids": sorted(ambiguous_callers[raw_call]),
            "candidate_surface_ids": sorted(targets),
        }
        gap_id = "caller-resolution-gap:" + fingerprint_value(
            gap_payload
        ).split(":", 1)[1]
        gaps[gap_id] = {"gap_id": gap_id, **gap_payload}
        for target in targets:
            gap_ids_by_surface.setdefault(target, set()).add(gap_id)

    return _CanonicalConsumerIndex(
        callers_by_surface_id={
            surface_id: frozenset(caller_ids)
            for surface_id, caller_ids in consumers.items()
        },
        gap_ids_by_surface_id={
            surface_id: tuple(sorted(gap_ids))
            for surface_id, gap_ids in gap_ids_by_surface.items()
        },
        gaps=tuple(gaps[gap_id] for gap_id in sorted(gaps)),
    )


def _canonical_consumer_surface_ids(
    surfaces: Sequence[ImplementationSurface],
    *,
    root: str | Path | None = None,
) -> dict[str, tuple[str, ...]]:
    return {
        surface_id: tuple(sorted(caller_ids))
        for surface_id, caller_ids in _canonical_consumer_index(
            surfaces,
            root=root,
        ).callers_by_surface_id.items()
    }


@dataclass(frozen=True)
class ProjectBlueprintOwner:
    """One stable model obligation and its exact code/test realization."""

    model_element_id: str
    owner_id: str
    owner_contract_id: str
    model_fingerprint: str
    owner_contract_fingerprint: str
    portable_model_id: str
    portable_model_fingerprint: str
    portable_transition_ids: tuple[str, ...]
    portable_property_ids: tuple[str, ...]
    portable_invariant_ids: tuple[str, ...]
    portable_input_field_mappings: tuple[tuple[str, str], ...]
    portable_output_field_mappings: tuple[tuple[str, str], ...]
    portable_state_field_mappings: tuple[tuple[str, str], ...]
    portable_assumption_ids: tuple[str, ...]
    portable_guarantee_ids: tuple[str, ...]
    protected_failure_ids: tuple[str, ...]
    portable_behavior_bindings: tuple[PortableBehaviorBinding, ...]
    implementation_surface_ids: tuple[str, ...]
    primary_surface_id: str
    semantic_specs: tuple[SemanticSpecReference, ...]
    oracles: tuple[OracleReference, ...]
    test_evidence_fingerprints: tuple[tuple[str, str], ...]
    native_evidence_fingerprints: tuple[tuple[str, str], ...]
    behavior_accepted: bool
    behavior_acceptance_evidence_fingerprints: tuple[tuple[str, str], ...]
    behavior_case_contracts: tuple[BehaviorCaseContract, ...] = ()
    checker_design_fingerprints: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "model_element_id",
            "owner_id",
            "owner_contract_id",
            "model_fingerprint",
            "owner_contract_fingerprint",
            "portable_model_id",
            "portable_model_fingerprint",
            "primary_surface_id",
        ):
            if not getattr(self, field_name):
                raise ProjectBlueprintError(f"project owner {field_name} is required")
        object.__setattr__(
            self,
            "implementation_surface_ids",
            tuple(sorted(set(self.implementation_surface_ids))),
        )
        object.__setattr__(self, "semantic_specs", tuple(self.semantic_specs))
        object.__setattr__(self, "oracles", tuple(self.oracles))
        object.__setattr__(
            self,
            "behavior_case_contracts",
            tuple(sorted(self.behavior_case_contracts, key=lambda row: row.case_id)),
        )
        object.__setattr__(
            self,
            "portable_behavior_bindings",
            tuple(
                sorted(
                    self.portable_behavior_bindings,
                    key=lambda row: row.binding_id,
                )
            ),
        )
        object.__setattr__(
            self,
            "test_evidence_fingerprints",
            _pairs(self.test_evidence_fingerprints),
        )
        object.__setattr__(
            self,
            "native_evidence_fingerprints",
            _pairs(self.native_evidence_fingerprints),
        )
        object.__setattr__(
            self,
            "protected_failure_ids",
            tuple(sorted(set(self.protected_failure_ids))),
        )
        for field_name in (
            "portable_transition_ids",
            "portable_property_ids",
            "portable_invariant_ids",
            "portable_assumption_ids",
            "portable_guarantee_ids",
        ):
            object.__setattr__(
                self,
                field_name,
                tuple(sorted(set(getattr(self, field_name)))),
            )
        for field_name in (
            "portable_input_field_mappings",
            "portable_output_field_mappings",
            "portable_state_field_mappings",
            "behavior_acceptance_evidence_fingerprints",
            "checker_design_fingerprints",
        ):
            object.__setattr__(self, field_name, _pairs(getattr(self, field_name)))
        if not (
            self.portable_transition_ids
            and self.portable_property_ids
            and self.portable_invariant_ids
            and self.portable_assumption_ids
            and self.portable_guarantee_ids
        ):
            raise ProjectBlueprintError(
                "project owner requires an exact portable model member catalog"
            )
        if not self.portable_behavior_bindings:
            raise ProjectBlueprintError(
                "project owner requires exact per-behavior-block portable bindings"
            )
        binding_ids = tuple(
            binding.binding_id for binding in self.portable_behavior_bindings
        )
        binding_block_ids = tuple(
            binding.behavior_block_id for binding in self.portable_behavior_bindings
        )
        if len(binding_ids) != len(set(binding_ids)):
            raise ProjectBlueprintError(
                "project owner portable behavior binding identity is duplicated"
            )
        if len(binding_block_ids) != len(set(binding_block_ids)):
            raise ProjectBlueprintError(
                "project owner has more than one portable binding for a behavior block"
            )
        if any(
            binding.portable_model_id != self.portable_model_id
            or binding.portable_model_fingerprint
            != self.portable_model_fingerprint
            for binding in self.portable_behavior_bindings
        ):
            raise ProjectBlueprintError(
                "project owner portable behavior binding targets another model authority"
            )
        implementation_surface_ids = set(self.implementation_surface_ids)
        binding_surface_ids = {
            binding.behavior_block_id.removeprefix("behavior-block:")
            for binding in self.portable_behavior_bindings
        }
        if not binding_surface_ids.issubset(implementation_surface_ids):
            raise ProjectBlueprintError(
                "project owner portable behavior binding targets an unowned surface"
            )
        primary_block_id = f"behavior-block:{self.primary_surface_id}"
        primary_bindings = tuple(
            binding
            for binding in self.portable_behavior_bindings
            if binding.behavior_block_id == primary_block_id
        )
        if len(primary_bindings) != 1:
            raise ProjectBlueprintError(
                "project owner primary surface requires one exact portable binding"
            )
        primary_binding = primary_bindings[0]
        if (
            primary_binding.transition_ids != self.portable_transition_ids
            or primary_binding.property_ids != self.portable_property_ids
            or primary_binding.invariant_ids != self.portable_invariant_ids
            or primary_binding.input_field_mappings
            != self.portable_input_field_mappings
            or primary_binding.output_field_mappings
            != self.portable_output_field_mappings
            or primary_binding.state_field_mappings
            != self.portable_state_field_mappings
            or primary_binding.assumption_ids != self.portable_assumption_ids
            or primary_binding.guarantee_ids != self.portable_guarantee_ids
            or primary_binding.protected_failure_ids != self.protected_failure_ids
        ):
            raise ProjectBlueprintError(
                "project owner primary portable summary differs from its exact binding"
            )
        for field_name, declared_members in (
            ("transition_ids", self.portable_transition_ids),
            ("property_ids", self.portable_property_ids),
            ("invariant_ids", self.portable_invariant_ids),
            ("assumption_ids", self.portable_assumption_ids),
            ("guarantee_ids", self.portable_guarantee_ids),
            ("protected_failure_ids", self.protected_failure_ids),
        ):
            bound_members = {
                member_id
                for binding in self.portable_behavior_bindings
                for member_id in getattr(binding, field_name)
            }
            if bound_members != set(declared_members):
                raise ProjectBlueprintError(
                    "project owner portable child-member union differs from its "
                    f"independent catalog for {field_name}: "
                    f"missing={sorted(set(declared_members) - bound_members)} "
                    f"unexpected={sorted(bound_members - set(declared_members))}"
                )
        if self.behavior_accepted and not self.behavior_acceptance_evidence_fingerprints:
            raise ProjectBlueprintError(
                "accepted project behavior requires explicit acceptance evidence"
            )
        checker_by_id = dict(self.checker_design_fingerprints)
        declared_block_ids = set(binding_block_ids)
        case_ids = tuple(case.case_id for case in self.behavior_case_contracts)
        if len(case_ids) != len(set(case_ids)):
            raise ProjectBlueprintError(
                "project owner behavior case identity is duplicated"
            )
        for case in self.behavior_case_contracts:
            if case.behavior_block_id not in declared_block_ids:
                raise ProjectBlueprintError(
                    "project behavior case targets a block without a portable binding"
                )
            if checker_by_id.get(case.case_evidence_id) != case.case_evidence_fingerprint:
                raise ProjectBlueprintError(
                    "project behavior case requires an exact declared checker design"
                )
        if self.primary_surface_id not in self.implementation_surface_ids:
            raise ProjectBlueprintError("primary surface must belong to its project owner")
        if not self.semantic_specs:
            raise ProjectBlueprintError("project owner requires declared/imported semantics")
        if not self.oracles:
            raise ProjectBlueprintError("project owner requires at least one oracle")
        if not self.test_evidence_fingerprints and not self.native_evidence_fingerprints:
            raise ProjectBlueprintError(
                "project owner requires a real test node or native evidence member"
            )

    @property
    def test_evidence_ids(self) -> tuple[str, ...]:
        return tuple(key for key, _value in self.test_evidence_fingerprints)

    @property
    def native_evidence_ids(self) -> tuple[str, ...]:
        return tuple(key for key, _value in self.native_evidence_fingerprints)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_element_id": self.model_element_id,
            "owner_id": self.owner_id,
            "owner_contract_id": self.owner_contract_id,
            "model_fingerprint": self.model_fingerprint,
            "owner_contract_fingerprint": self.owner_contract_fingerprint,
            "portable_model_id": self.portable_model_id,
            "portable_model_fingerprint": self.portable_model_fingerprint,
            "portable_transition_ids": list(self.portable_transition_ids),
            "portable_property_ids": list(self.portable_property_ids),
            "portable_invariant_ids": list(self.portable_invariant_ids),
            "portable_input_field_mappings": dict(self.portable_input_field_mappings),
            "portable_output_field_mappings": dict(self.portable_output_field_mappings),
            "portable_state_field_mappings": dict(self.portable_state_field_mappings),
            "portable_assumption_ids": list(self.portable_assumption_ids),
            "portable_guarantee_ids": list(self.portable_guarantee_ids),
            "protected_failure_ids": list(self.protected_failure_ids),
            "portable_behavior_bindings": [
                row.to_dict() for row in self.portable_behavior_bindings
            ],
            "implementation_surface_ids": list(self.implementation_surface_ids),
            "primary_surface_id": self.primary_surface_id,
            "semantic_specs": [row.to_dict() for row in self.semantic_specs],
            "oracles": [row.to_dict() for row in self.oracles],
            "test_evidence_fingerprints": dict(self.test_evidence_fingerprints),
            "native_evidence_fingerprints": dict(self.native_evidence_fingerprints),
            "behavior_accepted": self.behavior_accepted,
            "behavior_acceptance_evidence_fingerprints": dict(
                self.behavior_acceptance_evidence_fingerprints
            ),
            "behavior_case_contracts": [
                row.to_dict() for row in self.behavior_case_contracts
            ],
            "checker_design_fingerprints": dict(
                self.checker_design_fingerprints
            ),
        }


@dataclass(frozen=True)
class ProjectEvidenceArtifact:
    """One non-pytest evidence producer verified from the current project."""

    evidence_id: str
    artifact_path: str
    artifact_fingerprint: str
    kind: str

    def __post_init__(self) -> None:
        for field_name in (
            "evidence_id",
            "artifact_path",
            "artifact_fingerprint",
            "kind",
        ):
            if not str(getattr(self, field_name)).strip():
                raise ProjectBlueprintError(
                    f"project evidence artifact {field_name} is required"
                )
        normalized = self.artifact_path.replace("\\", "/")
        path = Path(normalized)
        if path.is_absolute() or ".." in path.parts:
            raise ProjectBlueprintError("project evidence artifact path must be bounded")
        object.__setattr__(self, "artifact_path", normalized)

    def to_dict(self) -> dict[str, str]:
        return {
            "evidence_id": self.evidence_id,
            "artifact_path": self.artifact_path,
            "artifact_fingerprint": self.artifact_fingerprint,
            "kind": self.kind,
        }


@dataclass(frozen=True)
class PortableModelMemberCatalog:
    """Independent current member inventory for one portable model authority."""

    portable_model_id: str
    portable_model_fingerprint: str
    transition_ids: tuple[str, ...]
    property_ids: tuple[str, ...]
    invariant_ids: tuple[str, ...]
    input_field_ids: tuple[str, ...]
    output_field_ids: tuple[str, ...]
    state_field_ids: tuple[str, ...]
    assumption_ids: tuple[str, ...]
    guarantee_ids: tuple[str, ...]
    protected_failure_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.portable_model_id or not self.portable_model_fingerprint:
            raise ProjectBlueprintError("portable member catalog identity is incomplete")
        for field_name in (
            "transition_ids", "property_ids", "invariant_ids", "input_field_ids",
            "output_field_ids", "state_field_ids", "assumption_ids", "guarantee_ids",
            "protected_failure_ids",
        ):
            object.__setattr__(
                self, field_name, tuple(sorted(set(getattr(self, field_name))))
            )
        if not (
            self.transition_ids
            and self.property_ids
            and self.invariant_ids
            and self.assumption_ids
            and self.guarantee_ids
        ):
            raise ProjectBlueprintError(
                "portable member catalog lacks required behavioral members"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "portable_model_id": self.portable_model_id,
            "portable_model_fingerprint": self.portable_model_fingerprint,
            "transition_ids": list(self.transition_ids),
            "property_ids": list(self.property_ids),
            "invariant_ids": list(self.invariant_ids),
            "input_field_ids": list(self.input_field_ids),
            "output_field_ids": list(self.output_field_ids),
            "state_field_ids": list(self.state_field_ids),
            "assumption_ids": list(self.assumption_ids),
            "guarantee_ids": list(self.guarantee_ids),
            "protected_failure_ids": list(self.protected_failure_ids),
        }


@dataclass(frozen=True)
class ProjectBlueprintDefinition:
    blueprint_id: str
    inventory_id: str
    boundary: SoftwareBoundary
    file_dispositions: tuple[ImplementationFileDisposition, ...]
    surface_dispositions: tuple[tuple[str, str], ...]
    supporting_owners: tuple[tuple[str, str], ...]
    dynamic_allowances: tuple[tuple[str, tuple[str, ...]], ...]
    owners: tuple[ProjectBlueprintOwner, ...]
    claim_boundary: str
    target_kind: str
    target_profile: str
    observation_providers: tuple[TargetSystemProviderDeclaration, ...]
    authority_providers: tuple[TargetSystemProviderDeclaration, ...]
    dynamic_selector_contracts: tuple[DynamicSelectorContract, ...] = ()

    def __post_init__(self) -> None:
        if not (
            self.blueprint_id
            and self.inventory_id
            and self.claim_boundary
            and self.target_kind
            and self.target_profile
        ):
            raise ProjectBlueprintError("project blueprint identity is incomplete")
        object.__setattr__(self, "file_dispositions", tuple(self.file_dispositions))
        object.__setattr__(self, "surface_dispositions", _pairs(self.surface_dispositions))
        object.__setattr__(self, "supporting_owners", _pairs(self.supporting_owners))
        object.__setattr__(
            self,
            "dynamic_allowances",
            tuple(
                sorted(
                    (str(key), tuple(sorted(set(values))))
                    for key, values in self.dynamic_allowances
                )
            ),
        )
        object.__setattr__(self, "owners", tuple(sorted(self.owners, key=lambda row: row.model_element_id)))
        object.__setattr__(
            self,
            "dynamic_selector_contracts",
            tuple(
                sorted(
                    self.dynamic_selector_contracts,
                    key=lambda row: (row.surface_key, row.operation),
                )
            ),
        )
        contract_keys = [
            (row.surface_key, row.operation)
            for row in self.dynamic_selector_contracts
        ]
        if len(contract_keys) != len(set(contract_keys)):
            raise ProjectBlueprintError(
                "project blueprint contains duplicate dynamic selector contracts"
            )
        object.__setattr__(
            self,
            "observation_providers",
            tuple(sorted(self.observation_providers, key=lambda row: row.provider_id)),
        )
        object.__setattr__(
            self,
            "authority_providers",
            tuple(sorted(self.authority_providers, key=lambda row: row.provider_id)),
        )
        if not self.observation_providers or not self.authority_providers:
            raise ProjectBlueprintError(
                "project blueprint requires observation and authority providers"
            )
        if any(row.provider_role != "observation" for row in self.observation_providers):
            raise ProjectBlueprintError("observation provider declaration has the wrong role")
        if any(row.provider_role != "authority" for row in self.authority_providers):
            raise ProjectBlueprintError("authority provider declaration has the wrong role")
        provider_ids = {
            row.provider_id
            for row in self.observation_providers + self.authority_providers
        }
        if len(provider_ids) != len(
            self.observation_providers + self.authority_providers
        ):
            raise ProjectBlueprintError(
                "provider identity cannot own observation and authority roles simultaneously"
            )
        model_ids = [row.model_element_id for row in self.owners]
        if len(model_ids) != len(set(model_ids)):
            raise ProjectBlueprintError("project blueprint contains duplicate model owners")
        claimed_surfaces = [
            surface_id for row in self.owners for surface_id in row.implementation_surface_ids
        ]
        if len(claimed_surfaces) != len(set(claimed_surfaces)):
            raise ProjectBlueprintError("implementation surface is claimed by multiple owners")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PROJECT_BLUEPRINT_DEFINITION_SCHEMA,
            "target_kind": self.target_kind,
            "target_profile": self.target_profile,
            "observation_providers": [
                row.to_dict() for row in self.observation_providers
            ],
            "authority_providers": [
                row.to_dict() for row in self.authority_providers
            ],
            "blueprint_id": self.blueprint_id,
            "inventory_id": self.inventory_id,
            "boundary": self.boundary.to_dict(),
            "file_dispositions": [row.to_dict() for row in self.file_dispositions],
            "surface_dispositions": dict(self.surface_dispositions),
            "supporting_owners": dict(self.supporting_owners),
            "dynamic_allowances": {
                key: list(values) for key, values in self.dynamic_allowances
            },
            "dynamic_selector_contracts": [
                row.to_dict() for row in self.dynamic_selector_contracts
            ],
            "owners": [row.to_dict() for row in self.owners],
            "claim_boundary": self.claim_boundary,
        }


@dataclass(frozen=True)
class ProjectBlueprintEvidence:
    observed_snapshot_id: str
    observed_snapshot_fingerprint: str
    semantic_mesh_id: str
    portable_owner_fingerprints: tuple[tuple[str, str], ...]
    portable_member_catalogs: tuple[PortableModelMemberCatalog, ...]
    resources: tuple[BlueprintResourceReference, ...]
    observed_resources: tuple[ObservedResourceMember, ...]
    intent_inventory: ProjectIntentInventory
    test_inventory: ProjectTestInventory
    topology_nodes: tuple[BlueprintTopologyNode, ...]
    topology_relations: tuple[BlueprintTopologyRelation, ...]
    child_models: tuple[ChildModelEvidence, ...]
    reattachment_contracts: tuple[ChildReattachmentContract, ...]
    current_relation_evidence_fingerprints: tuple[tuple[str, str], ...]
    current_refinement_fingerprints: tuple[tuple[str, str], ...]
    current_progress_evidence_fingerprints: tuple[tuple[str, str], ...]
    current_child_evidence_fingerprints: tuple[tuple[str, str], ...]
    native_evidence_artifacts: tuple[ProjectEvidenceArtifact, ...] = ()
    path_quality_bindings: tuple[ModelPathQualityBlueprintBinding, ...] = ()

    def __post_init__(self) -> None:
        identities = (
            self.observed_snapshot_id,
            self.observed_snapshot_fingerprint,
            self.semantic_mesh_id,
        )
        if not all(identities):
            raise ProjectBlueprintError("project blueprint evidence identity is incomplete")
        object.__setattr__(
            self,
            "portable_owner_fingerprints",
            _pairs(self.portable_owner_fingerprints),
        )
        object.__setattr__(
            self,
            "portable_member_catalogs",
            tuple(sorted(self.portable_member_catalogs, key=lambda row: row.portable_model_id)),
        )
        catalog_ids = tuple(row.portable_model_id for row in self.portable_member_catalogs)
        if len(catalog_ids) != len(set(catalog_ids)):
            raise ProjectBlueprintError("portable member catalog identity is duplicated")
        object.__setattr__(self, "resources", tuple(sorted(self.resources, key=lambda row: row.resource_id)))
        declared_resource_ids = tuple(row.resource_id for row in self.resources)
        if len(declared_resource_ids) != len(set(declared_resource_ids)):
            raise ProjectBlueprintError("declared resource identity is duplicated")
        object.__setattr__(
            self,
            "observed_resources",
            tuple(sorted(self.observed_resources, key=lambda row: row.resource_id)),
        )
        observed_resource_ids = tuple(
            row.resource_id for row in self.observed_resources
        )
        if len(observed_resource_ids) != len(set(observed_resource_ids)):
            raise ProjectBlueprintError(
                "observed resource identity is duplicated"
            )
        object.__setattr__(
            self,
            "topology_nodes",
            tuple(sorted(self.topology_nodes, key=lambda row: row.node_id)),
        )
        object.__setattr__(
            self,
            "topology_relations",
            tuple(sorted(self.topology_relations, key=lambda row: row.relation_id)),
        )
        object.__setattr__(
            self,
            "child_models",
            tuple(sorted(self.child_models, key=lambda row: row.model_id)),
        )
        object.__setattr__(
            self,
            "reattachment_contracts",
            tuple(sorted(self.reattachment_contracts, key=lambda row: row.child_model_id)),
        )
        for field_name in (
            "current_relation_evidence_fingerprints",
            "current_refinement_fingerprints",
            "current_progress_evidence_fingerprints",
            "current_child_evidence_fingerprints",
        ):
            object.__setattr__(self, field_name, _pairs(getattr(self, field_name)))
        object.__setattr__(
            self,
            "native_evidence_artifacts",
            tuple(sorted(self.native_evidence_artifacts, key=lambda row: row.evidence_id)),
        )
        evidence_ids = tuple(row.evidence_id for row in self.native_evidence_artifacts)
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ProjectBlueprintError("project native evidence identity is not unique")
        if any(
            not isinstance(row, ModelPathQualityBlueprintBinding)
            for row in self.path_quality_bindings
        ):
            raise ProjectBlueprintError(
                "project path-quality evidence requires current typed bindings"
            )
        object.__setattr__(
            self,
            "path_quality_bindings",
            tuple(
                sorted(
                    self.path_quality_bindings,
                    key=lambda row: (
                        row.model_element_id,
                        row.compact_current_fingerprint,
                    ),
                )
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "observed_snapshot_id": self.observed_snapshot_id,
            "observed_snapshot_fingerprint": self.observed_snapshot_fingerprint,
            "semantic_mesh_id": self.semantic_mesh_id,
            "portable_owner_fingerprints": dict(self.portable_owner_fingerprints),
            "portable_member_catalogs": [
                row.to_dict() for row in self.portable_member_catalogs
            ],
            "resources": [row.to_dict() for row in self.resources],
            "observed_resources": [
                row.to_dict() for row in self.observed_resources
            ],
            "intent_inventory": self.intent_inventory.to_dict(),
            "test_inventory": self.test_inventory.to_dict(),
            "topology_nodes": [row.to_dict() for row in self.topology_nodes],
            "topology_relations": [row.to_dict() for row in self.topology_relations],
            "child_models": [row.to_dict() for row in self.child_models],
            "reattachment_contracts": [
                row.to_dict() for row in self.reattachment_contracts
            ],
            "current_relation_evidence_fingerprints": dict(
                self.current_relation_evidence_fingerprints
            ),
            "current_refinement_fingerprints": dict(
                self.current_refinement_fingerprints
            ),
            "current_progress_evidence_fingerprints": dict(
                self.current_progress_evidence_fingerprints
            ),
            "current_child_evidence_fingerprints": dict(
                self.current_child_evidence_fingerprints
            ),
            "native_evidence_artifacts": [
                row.to_dict() for row in self.native_evidence_artifacts
            ],
            "path_quality_bindings": [
                row.to_dict() for row in self.path_quality_bindings
            ],
        }


def project_blueprint_document(
    definition: ProjectBlueprintDefinition,
    evidence: ProjectBlueprintEvidence,
    frozen_target_evidence: FrozenTargetSystemEvidence,
) -> dict[str, Any]:
    """Return the canonical strict document consumed by the read-only CLI."""

    return {
        **definition.to_dict(),
        "evidence": evidence.to_dict(),
        "frozen_target_evidence": frozen_target_evidence.to_dict(),
    }


@dataclass(frozen=True)
class ProjectBlueprintPreparation:
    """Native project reports produced before provider evidence is frozen."""

    definition: ProjectBlueprintDefinition
    evidence: ProjectBlueprintEvidence
    inventory: ImplementationSurfaceInventory
    implementation_inventory_audit: ImplementationInventoryAuditReport
    binding_report: ModelImplementationBindingReport
    manifest: SoftwareBlueprintManifest
    qualification: BlueprintManifestQualificationReport
    model_test_alignment_report: ModelTestAlignmentReport
    topology_report: BlueprintTopologyReport
    behavior_report: BehaviorBlueprintReport
    resource_inventory: ProjectResourceInventory
    intent_inventory: ProjectIntentInventory
    normalized_projection: NormalizedBlueprintProjection
    static_readiness: StaticBlueprintReadinessReport
    normalized_shared_objects: tuple[tuple[str, Any], ...]
    normalized_shards: tuple[tuple[str, Any], ...]


@dataclass(frozen=True)
class ProjectBlueprintBundle:
    inventory: ImplementationSurfaceInventory
    binding_report: ModelImplementationBindingReport
    manifest: SoftwareBlueprintManifest
    qualification: BlueprintManifestQualificationReport
    implementation_inventory_audit: ImplementationInventoryAuditReport
    model_test_alignment_report: ModelTestAlignmentReport | None = None
    topology_report: BlueprintTopologyReport | None = None
    behavior_report: BehaviorBlueprintReport | None = None
    resource_inventory: ProjectResourceInventory | None = None
    intent_inventory: ProjectIntentInventory | None = None
    normalized_projection: NormalizedBlueprintProjection | None = None
    static_readiness: StaticBlueprintReadinessReport | None = None
    target_system_report: TargetSystemBlueprintReport | None = None
    understanding_summary: BlueprintUnderstandingSummary | None = None
    normalized_shared_objects: tuple[tuple[str, Any], ...] = ()
    normalized_shards: tuple[tuple[str, Any], ...] = ()
    normalized_affected_index: AffectedBlueprintIndex | None = None
    test_inventory: ProjectTestInventory | None = None
    definition: ProjectBlueprintDefinition | None = None
    project_evidence: ProjectBlueprintEvidence | None = None
    frozen_target_evidence: FrozenTargetSystemEvidence | None = None

    @cached_property
    def canonical_child_fingerprints(self) -> tuple[tuple[str, str], ...]:
        """Expose the exact child identity map used by export and bundle identity."""

        child_fingerprints = {
            "definition": (
                fingerprint_value(self.definition.to_dict())
                if self.definition is not None
                else ""
            ),
            "project_evidence": (
                fingerprint_value(self.project_evidence.to_dict())
                if self.project_evidence is not None
                else ""
            ),
            "frozen_target_evidence": (
                self.frozen_target_evidence.fingerprint
                if self.frozen_target_evidence is not None
                else ""
            ),
            "implementation_inventory": self.inventory.inventory_fingerprint,
            "implementation_inventory_audit": (
                self.implementation_inventory_audit.fingerprint
            ),
            "binding_report": self.binding_report.fingerprint,
            "manifest": self.manifest.fingerprint,
            "qualification": self.qualification.fingerprint,
            "model_test_alignment": (
                self.model_test_alignment_report.fingerprint
                if self.model_test_alignment_report is not None
                else ""
            ),
            "topology": (
                self.topology_report.fingerprint
                if self.topology_report is not None
                else ""
            ),
            "behavior": (
                self.behavior_report.fingerprint
                if self.behavior_report is not None
                else ""
            ),
            "resource_inventory": (
                self.resource_inventory.fingerprint
                if self.resource_inventory is not None
                else ""
            ),
            "intent_inventory": (
                self.intent_inventory.fingerprint
                if self.intent_inventory is not None
                else ""
            ),
            "normalized_projection": (
                self.normalized_projection.fingerprint
                if self.normalized_projection is not None
                else ""
            ),
            "static_readiness": (
                self.static_readiness.fingerprint
                if self.static_readiness is not None
                else ""
            ),
            "target_system_report": (
                self.target_system_report.fingerprint
                if self.target_system_report is not None
                else ""
            ),
            "understanding_summary": (
                self.understanding_summary.fingerprint
                if self.understanding_summary is not None
                else ""
            ),
            "normalized_shared_objects": fingerprint_value(
                [
                    {"object_id": str(object_id), "payload": payload}
                    for object_id, payload in sorted(
                        self.normalized_shared_objects,
                        key=lambda row: str(row[0]),
                    )
                ]
            ),
            "normalized_shards": fingerprint_value(
                [
                    {"shard_id": str(shard_id), "payload": payload}
                    for shard_id, payload in sorted(
                        self.normalized_shards,
                        key=lambda row: str(row[0]),
                    )
                ]
            ),
            "affected_index": (
                self.normalized_affected_index.fingerprint
                if self.normalized_affected_index is not None
                else ""
            ),
            "test_inventory": (
                self.test_inventory.inventory_fingerprint
                if self.test_inventory is not None
                else ""
            ),
        }
        return tuple(sorted(child_fingerprints.items()))

    @cached_property
    def fingerprint(self) -> str:
        """Bind the complete portable project-blueprint content, not one label."""

        return fingerprint_value(
            {
                "schema_version": PROJECT_BLUEPRINT_DEFINITION_SCHEMA,
                "blueprint_id": self.manifest.blueprint_id,
                "children": dict(self.canonical_child_fingerprints),
            }
        )

    @property
    def canonical_projection_blockers(self) -> tuple[str, ...]:
        """Return missing canonical layers for the native projection.

        A modeled gap is content, not a projection failure. Readiness,
        currentness, and execution findings remain part of the native model so
        a partial model can grow without being mistaken for a complete one.
        """

        blockers: list[str] = []
        required_objects = {
            "definition": self.definition,
            "project_evidence": self.project_evidence,
            "frozen_target_evidence": self.frozen_target_evidence,
            "model_test_alignment_report": self.model_test_alignment_report,
            "topology_report": self.topology_report,
            "behavior_report": self.behavior_report,
            "resource_inventory": self.resource_inventory,
            "intent_inventory": self.intent_inventory,
            "normalized_projection": self.normalized_projection,
            "static_readiness": self.static_readiness,
            "target_system_report": self.target_system_report,
            "understanding_summary": self.understanding_summary,
            "normalized_affected_index": self.normalized_affected_index,
            "test_inventory": self.test_inventory,
        }
        blockers.extend(
            f"missing:{name}"
            for name, value in required_objects.items()
            if value is None
        )
        object_ids = tuple(str(object_id) for object_id, _ in self.normalized_shared_objects)
        shard_ids = tuple(str(shard_id) for shard_id, _ in self.normalized_shards)
        if len(object_ids) != len(set(object_ids)):
            blockers.append("invalid:normalized_shared_objects:duplicate_id")
        if len(shard_ids) != len(set(shard_ids)):
            blockers.append("invalid:normalized_shards:duplicate_id")
        actual_object_fingerprints = {
            str(object_id): fingerprint_value(payload)
            for object_id, payload in self.normalized_shared_objects
        }
        actual_shard_fingerprints = {
            str(shard_id): fingerprint_value(payload)
            for shard_id, payload in self.normalized_shards
        }
        if self.normalized_projection is not None:
            base_objects = dict(self.normalized_projection.object_fingerprints)
            if any(
                actual_object_fingerprints.get(object_id) != expected
                for object_id, expected in base_objects.items()
            ):
                blockers.append("stale:normalized_projection:shared_objects")
            if actual_shard_fingerprints != dict(
                self.normalized_projection.shard_fingerprints
            ):
                blockers.append("stale:normalized_projection:shards")
        if self.normalized_affected_index is not None:
            if actual_object_fingerprints != dict(
                self.normalized_affected_index.object_fingerprints
            ):
                blockers.append("stale:affected_index:shared_objects")
            if actual_shard_fingerprints != dict(
                self.normalized_affected_index.shard_fingerprints
            ):
                blockers.append("stale:affected_index:shards")
        if (
            self.target_system_report is not None
            and self.understanding_summary is not None
        ):
            expected_understanding = project_blueprint_understanding(
                self.target_system_report,
                affected_surface_ids=(
                    self.understanding_summary.affected_surface_ids
                ),
            )
            if expected_understanding.fingerprint != self.understanding_summary.fingerprint:
                blockers.append("stale:understanding_summary:target_report")

        if not any(value is None for value in required_objects.values()):
            blockers.extend(_project_bundle_rebinding_blockers(self))
        return tuple(sorted(set(blockers)))

    @property
    def canonical_projection_complete(self) -> bool:
        """True when every canonical layer can be represented without omission."""

        return not self.canonical_projection_blockers

    @property
    def readiness_ledger(self) -> BlueprintReadinessLedger:
        return derive_project_blueprint_readiness_ledger(self)

    @property
    def ok(self) -> bool:
        return self.readiness_ledger.ok

    @property
    def deepest_proven_layer(self) -> str:
        return self.readiness_ledger.deepest_proven_layer

    @property
    def first_gap(self) -> BlueprintGapRef | None:
        return self.readiness_ledger.first_gap

    @property
    def gap_count(self) -> int:
        return self.readiness_ledger.gap_count

    @property
    def implementation_admitted(self) -> bool:
        return self.readiness_ledger.implementation_admitted

    def affected_neighborhood(
        self,
        *,
        affected_surface_ids: Sequence[str] = (),
        affected_behavior_block_ids: Sequence[str] = (),
    ) -> AffectedBlueprintReadResult:
        if self.normalized_affected_index is None or self.behavior_report is None:
            raise ProjectBlueprintError("project bundle has no normalized behavior blueprint")
        affected_ids = tuple(
            sorted(
                {
                    *(str(item) for item in affected_surface_ids if str(item)),
                    *(
                        str(item)
                        for item in affected_behavior_block_ids
                        if str(item)
                    ),
                }
            )
        )
        return read_affected_blueprint(
            self.normalized_affected_index,
            affected_ids=affected_ids,
            load_shard=dict(self.normalized_shards).__getitem__,
            load_object=dict(self.normalized_shared_objects).__getitem__,
        )

    def affected_understanding(
        self,
        *,
        affected_ids: Sequence[str],
    ) -> AffectedBlueprintUnderstanding:
        if self.normalized_affected_index is None:
            raise ProjectBlueprintError(
                "project bundle has no normalized affected-read ledger index"
            )
        return read_affected_blueprint_understanding(
            self.normalized_affected_index,
            affected_ids=affected_ids,
            load_shard=dict(self.normalized_shards).__getitem__,
            load_object=dict(self.normalized_shared_objects).__getitem__,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "project_blueprint_fingerprint": self.fingerprint,
            "canonical_projection_complete": self.canonical_projection_complete,
            "canonical_projection_blockers": list(self.canonical_projection_blockers),
            "inventory_fingerprint": self.inventory.inventory_fingerprint,
            "binding_report_fingerprint": self.binding_report.fingerprint,
            "blueprint_fingerprint": self.manifest.fingerprint,
            "qualification": self.qualification.to_dict(),
            "model_test_alignment_report": (
                self.model_test_alignment_report.to_dict()
                if self.model_test_alignment_report
                else None
            ),
            "topology_report": (
                self.topology_report.to_dict() if self.topology_report else None
            ),
            "behavior_report": (
                self.behavior_report.to_dict() if self.behavior_report else None
            ),
            "resource_inventory": (
                self.resource_inventory.to_dict() if self.resource_inventory else None
            ),
            "intent_inventory": (
                self.intent_inventory.to_dict() if self.intent_inventory else None
            ),
            "normalized_projection": (
                self.normalized_projection.to_dict() if self.normalized_projection else None
            ),
            "normalized_affected_index": (
                self.normalized_affected_index.to_dict()
                if self.normalized_affected_index
                else None
            ),
            "static_readiness": (
                self.static_readiness.to_dict()
                if self.static_readiness
                else None
            ),
            "target_system_report": (
                self.target_system_report.to_dict()
                if self.target_system_report
                else None
            ),
            "understanding_summary": (
                self.understanding_summary.to_dict()
                if self.understanding_summary
                else None
            ),
            "readiness_ledger": (
                self.readiness_ledger.to_dict()
                if self.target_system_report is not None
                else None
            ),
            "counts": {
                "files": len(self.inventory.file_dispositions),
                "implementation_surfaces": len(self.inventory.surfaces),
                "model_obligations": len(self.binding_report.required_model_element_ids),
                "bindings": len(self.binding_report.bindings),
                "semantic_specs": len(self.binding_report.semantic_specs),
                "test_evidence": len(self.binding_report.test_evidence_ids),
                "oracles": len(self.binding_report.oracles),
                "resources": len(self.manifest.resources),
                "normalized_shared_objects": len(self.normalized_shared_objects),
                "behavior_blocks": (
                    len(self.behavior_report.contracts)
                    if self.behavior_report
                    else 0
                ),
                "behavior_coverage_edges": (
                    len(self.behavior_report.coverage_edges)
                    if self.behavior_report
                    else 0
                ),
            },
        }


def _project_model_test_alignment(
    *,
    definition: ProjectBlueprintDefinition,
    evidence: ProjectBlueprintEvidence,
    inventory: ImplementationSurfaceInventory,
    binding_report: ModelImplementationBindingReport,
) -> ModelTestAlignmentReport:
    """Build the real static model/code/test alignment review.

    This review deliberately leaves execution as ``not_run``.  Its purpose in
    a blueprint is to prove that a checker design names the exact model owner,
    code contract, and test/native member.  Runtime success remains a separate
    receipt-backed claim.
    """

    surface_by_id = {row.surface_id: row for row in inventory.surfaces}
    owner_by_model = {row.model_element_id: row for row in definition.owners}
    bindings_by_model: dict[str, list[ModelImplementationBinding]] = {}
    for binding in binding_report.bindings:
        bindings_by_model.setdefault(binding.model_element_id, []).append(binding)

    obligations: list[ModelObligation] = []
    code_contracts: list[CodeContract] = []
    code_ids_by_block: dict[str, str] = {}
    for model_element_id, owner in sorted(owner_by_model.items()):
        owner_bindings = tuple(bindings_by_model.get(model_element_id, ()))
        portable_by_block = {
            row.behavior_block_id: row
            for row in owner.portable_behavior_bindings
        }
        for binding in owner_bindings:
            surface = surface_by_id.get(binding.implementation_surface_id)
            if surface is None:
                continue
            behavior_block_id = (
                f"behavior-block:{binding.implementation_surface_id}"
            )
            portable = portable_by_block.get(behavior_block_id)
            if portable is None:
                continue
            external_outputs = (
                ("return",) if surface.returns_value else ()
            )
            error_paths = tuple(
                sorted(
                    {
                        *surface.raised_errors,
                        *portable.protected_failure_ids,
                    }
                )
            )
            obligations.append(
                ModelObligation(
                    obligation_id=behavior_block_id,
                    obligation_type="behavior_contract",
                    description=(
                        "exact block-local behavior owned by "
                        f"{owner.owner_id}"
                    ),
                    required=True,
                    required_test_kinds=("happy_path",),
                    allow_shared_evidence=False,
                    allow_shared_implementation=False,
                    external_inputs=surface.parameters,
                    external_outputs=external_outputs,
                    state_reads=surface.state_reads,
                    state_writes=surface.state_writes,
                    side_effects=surface.side_effect_candidates,
                    error_paths=error_paths,
                    exact_external_contract=True,
                )
            )
            code_id = f"code-contract:{binding.binding_id}"
            code_ids_by_block[behavior_block_id] = code_id
            code_contracts.append(
                CodeContract(
                    code_contract_id=code_id,
                    path=surface.path,
                    symbol=surface.symbol,
                    surface_type=surface.surface_kind,
                    role="owner",
                    implements_obligations=(behavior_block_id,),
                    external_inputs=surface.parameters,
                    external_outputs=external_outputs,
                    state_reads=surface.state_reads,
                    state_writes=surface.state_writes,
                    side_effects=surface.side_effect_candidates,
                    error_paths=error_paths,
                )
            )

    test_evidence: list[TestEvidence] = []
    case_kind_to_test_kind = {
        "good": "happy_path",
        "boundary": "boundary",
        "bad": "error_path",
    }
    for owner in definition.owners:
        oracle_path = owner.oracles[0].source_id
        for case in owner.behavior_case_contracts:
            code_id = code_ids_by_block.get(case.behavior_block_id)
            if code_id is None:
                continue
            test_evidence.append(
                TestEvidence(
                    evidence_id=case.case_evidence_id,
                    test_name=case.case_id,
                    path=oracle_path,
                    command=(
                        "block-local checker design; execution receipt is separate"
                    ),
                    result_status="not_run",
                    evidence_current=True,
                    test_kind=case_kind_to_test_kind[case.case_kind],
                    covered_obligations=(case.behavior_block_id,),
                    covered_code_contracts=(code_id,),
                    assertion_scope="external_contract",
                    evidence_role="primary",
                )
            )
    return review_model_test_alignment(
        ModelTestAlignmentPlan(
            model_id=definition.blueprint_id,
            obligations=tuple(obligations),
            code_contracts=tuple(code_contracts),
            test_evidence=tuple(test_evidence),
            allow_orphan_tests=True,
            require_implementation_blueprint=True,
            implementation_binding_report=binding_report,
        )
    )


def _behavior_dimension(
    surface: ImplementationSurface,
    owner: ProjectBlueprintOwner,
    dimension: str,
) -> BehaviorDimensionContract:
    semantic = owner.semantic_specs[0]
    semantics = dict(semantic.semantics)
    source_key = {
        "state": "state_effect",
        "effect": "state_effect",
        "completion": "output",
    }.get(dimension, dimension)
    applicability = {
        "input": True,
        "state": bool(surface.state_reads or surface.state_writes),
        "output": True,
        "effect": bool(surface.side_effect_candidates or surface.dynamic_operations),
        "error": True,
        "decision": bool(surface.calls or surface.dynamic_operations),
        "order": bool(surface.calls),
        "retry": not semantics.get("retry", "").startswith("not_applicable"),
        "timeout": not semantics.get("timeout", "").startswith("not_applicable"),
        "completion": True,
    }[dimension]
    observed_facts = {
        "input": "parameters=" + ",".join(surface.parameters or ("none",)),
        "state": (
            "reads="
            + ",".join(surface.state_reads or ("none",))
            + ";writes="
            + ",".join(surface.state_writes or ("none",))
        ),
        "output": f"returns_value={str(surface.returns_value).lower()}",
        "effect": "effects="
        + ",".join(
            tuple(surface.side_effect_candidates)
            + tuple(surface.dynamic_operations)
            or ("none",)
        ),
        "error": "raised_errors=" + ",".join(surface.raised_errors or ("none",)),
        "decision": "calls=" + ",".join(surface.calls or ("none",)),
        "order": "ordered_calls=" + ",".join(surface.calls or ("none",)),
        "retry": "owner_retry_rule=" + semantics.get("retry", "missing"),
        "timeout": "owner_timeout_rule=" + semantics.get("timeout", "missing"),
        "completion": (
            f"returns_value={str(surface.returns_value).lower()};"
            + "errors="
            + ",".join(surface.raised_errors or ("none",))
        ),
    }[dimension]
    if applicability:
        owner_rule = semantics.get(source_key, "")
        if not owner_rule:
            owner_rule = "missing-independent-owner-rule"
        value = (
            f"surface={surface.path}#{surface.symbol}; {observed_facts}; "
            f"independent_owner_rule={owner_rule}"
        )
        disposition = "modeled"
        rationale = (
            "the exact current surface facts are bound to one independently accepted owner rule"
        )
    else:
        value = (
            f"surface={surface.path}#{surface.symbol}; {observed_facts}; not applicable: "
            f"the exact surface inventory and independent owner rule declare no {dimension} behavior"
        )
        disposition = "not_applicable"
        rationale = "typed absence is explicit; silence does not close the dimension"
    provenance = dict(semantic.provenance_fingerprints)
    provenance["owner-contract"] = owner.owner_contract_fingerprint
    return BehaviorDimensionContract(
        dimension=dimension,
        disposition=disposition,
        semantics=value,
        rationale=rationale,
        provenance_fingerprints=tuple(provenance.items()),
        semantic_rule_ids=(
            f"semantic-rule:{semantic.semantic_spec_id}:{dimension}",
        ),
        applicability_surface_ids=(surface.surface_id,),
    )


def _owner_surface_contracts(
    owner: ProjectBlueprintOwner,
    surface: ImplementationSurface,
    *,
    portable_binding_by_block: Mapping[str, PortableBehaviorBinding] | None = None,
    cases_by_block: Mapping[str, tuple[BehaviorCaseContract, ...]] | None = None,
    oracle_ids: frozenset[str] | None = None,
) -> tuple[PortableBehaviorBinding, tuple[BehaviorCaseContract, ...]]:
    """Select one owner's exact declarations for one observed behavior surface."""

    behavior_block_id = f"behavior-block:{surface.surface_id}"
    if portable_binding_by_block is None:
        portable_binding_by_block = {
            binding.behavior_block_id: binding
            for binding in owner.portable_behavior_bindings
        }
    portable_binding = portable_binding_by_block.get(behavior_block_id)
    if portable_binding is None:
        raise ProjectBlueprintError(
            "behavior surface requires one exact portable binding for "
            f"{owner.owner_id}: {surface.surface_id}"
        )
    expected_field_sets = (
        (
            "input",
            {field for field, _member in portable_binding.input_field_mappings},
            set(surface.parameters),
        ),
        (
            "output",
            {field for field, _member in portable_binding.output_field_mappings},
            {"return"} if surface.returns_value else set(),
        ),
        (
            "state",
            {field for field, _member in portable_binding.state_field_mappings},
            (
                set(surface.state_reads) | set(surface.state_writes)
            )
            - set(surface.parameters),
        ),
    )
    for field_kind, declared_fields, expected_fields in expected_field_sets:
        if declared_fields != expected_fields:
            raise ProjectBlueprintError(
                f"portable {field_kind} mapping differs from the exact behavior "
                f"surface fields for {surface.surface_id}: "
                f"missing={sorted(expected_fields - declared_fields)} "
                f"unexpected={sorted(declared_fields - expected_fields)}"
            )
    for field_name, parent_catalog in (
        ("transition_ids", set(owner.portable_transition_ids)),
        ("property_ids", set(owner.portable_property_ids)),
        ("invariant_ids", set(owner.portable_invariant_ids)),
        ("assumption_ids", set(owner.portable_assumption_ids)),
        ("guarantee_ids", set(owner.portable_guarantee_ids)),
        ("protected_failure_ids", set(owner.protected_failure_ids)),
    ):
        unexpected = set(getattr(portable_binding, field_name)) - parent_catalog
        if unexpected:
            raise ProjectBlueprintError(
                "portable behavior binding references members outside its parent "
                f"catalog for {surface.surface_id}: {field_name}={sorted(unexpected)}"
            )
    if cases_by_block is None:
        grouped_cases: dict[str, list[BehaviorCaseContract]] = {}
        for case in owner.behavior_case_contracts:
            grouped_cases.setdefault(case.behavior_block_id, []).append(case)
        cases_by_block = {
            block_id: tuple(rows) for block_id, rows in grouped_cases.items()
        }
    declared_cases = cases_by_block.get(behavior_block_id, ())
    current_oracle_ids = (
        oracle_ids
        if oracle_ids is not None
        else frozenset(row.oracle_id for row in owner.oracles)
    )
    if any(case.oracle_id not in current_oracle_ids for case in declared_cases):
        raise ProjectBlueprintError(
            f"declared behavior cases target another oracle for {owner.owner_id}"
        )
    good_cases = tuple(case for case in declared_cases if case.case_kind == "good")
    boundary_cases = tuple(
        case for case in declared_cases if case.case_kind == "boundary"
    )
    bad_cases = tuple(case for case in declared_cases if case.case_kind == "bad")
    bound_failures = set(portable_binding.protected_failure_ids)
    case_failures = {
        failure_id
        for case in bad_cases
        for failure_id in case.protected_failure_ids
    }
    if (
        len(good_cases) != 1
        or len(boundary_cases) != 1
        or len(bad_cases) != len(bound_failures)
        or case_failures != bound_failures
        or any(
            set(case.protected_failure_ids) - bound_failures
            for case in declared_cases
        )
    ):
        raise ProjectBlueprintError(
            "behavior cases do not exactly match the block-local protected-failure "
            f"binding for {surface.surface_id}"
        )
    return portable_binding, declared_cases


def build_project_resource_inventory(
    definition: ProjectBlueprintDefinition,
    evidence: ProjectBlueprintEvidence,
) -> ProjectResourceInventory:
    kind_to_category = {
        "verification": "behavioral_oracle",
    }
    members: list[ProjectResourceMember] = []
    findings: list[ReadinessFinding] = []
    present: set[str] = set()
    declarations = {row.resource_id: row for row in evidence.resources}
    observations = {row.resource_id: row for row in evidence.observed_resources}
    observation_providers = {
        row.provider_id: row for row in definition.observation_providers
    }
    for resource_id in sorted(set(declarations) | set(observations)):
        resource = declarations.get(resource_id)
        observation = observations.get(resource_id)
        resource_kind = (
            resource.kind if resource is not None else str(observation.kind)
        )
        category = kind_to_category.get(resource_kind, resource_kind)
        present.add(category)
        row_findings: list[ReadinessFinding] = []
        if resource is None:
            row_findings.append(
                ReadinessFinding(
                    "resource_observed_but_undeclared",
                    "independent resource observation has no declared owner or consumer binding",
                    (resource_id,),
                    "blocked",
                )
            )
        if observation is None:
            row_findings.append(
                ReadinessFinding(
                    "resource_declared_but_unobserved",
                    "declared resource is absent from the independent observation denominator",
                    (resource_id,),
                    "blocked",
                )
            )
        if resource is not None and observation is not None:
            if observation.subject_revision != evidence.observed_snapshot_fingerprint:
                row_findings.append(
                    ReadinessFinding(
                        "resource_subject_revision_stale",
                        "resource observation targets another subject revision",
                        (resource_id, observation.subject_revision),
                        "stale",
                    )
                )
            if observation.status != "current":
                row_findings.append(
                    ReadinessFinding(
                        "resource_observation_not_current",
                        "resource observation is not current",
                        (resource_id, observation.status),
                        "stale" if observation.status == "stale" else "blocked",
                    )
                )
            provider = observation_providers.get(observation.provider_id)
            if provider is None:
                row_findings.append(
                    ReadinessFinding(
                        "resource_observation_provider_missing",
                        "resource observation is not owned by a declared observation provider",
                        (resource_id, observation.provider_id),
                        "blocked",
                    )
                )
            elif (
                observation.capability_id not in provider.capability_ids
                or observation.capability_id != "resource_inventory"
            ):
                row_findings.append(
                    ReadinessFinding(
                        "resource_observation_capability_mismatch",
                        "resource observation provider does not own the canonical resource capability",
                        (
                            resource_id,
                            observation.provider_id,
                            observation.capability_id,
                        ),
                        "blocked",
                    )
                )
            if observation.payload_id != observation.capability_id:
                row_findings.append(
                    ReadinessFinding(
                        "resource_observation_payload_mismatch",
                        "resource observation does not bind the canonical provider payload",
                        (resource_id, observation.payload_id),
                        "blocked",
                    )
                )
            mismatched_identity_fields = tuple(
                field_name
                for field_name, declared, observed in (
                    ("kind", resource.kind, observation.kind),
                    ("owner_id", resource.owner_id, observation.owner_id),
                    ("artifact_id", resource.artifact_id, observation.artifact_id),
                )
                if declared != observed
            )
            if mismatched_identity_fields:
                row_findings.append(
                    ReadinessFinding(
                        "resource_observation_identity_mismatch",
                        "resource observation differs from the declared resource identity",
                        (resource_id, *mismatched_identity_fields),
                        "blocked",
                    )
                )
            if (
                resource.artifact_fingerprint
                and observation.current_artifact_fingerprint
                != resource.artifact_fingerprint
            ):
                row_findings.append(
                    ReadinessFinding(
                        "resource_artifact_fingerprint_stale",
                        "declared resource fingerprint differs from the independent current observation",
                        (resource_id,),
                        "stale",
                    )
                )
        findings.extend(row_findings)
        declared_disposition = (
            resource.disposition if resource is not None else "blocked"
        )
        disposition = (
            declared_disposition
            if not row_findings
            and declared_disposition in {"current", "external", "scoped_out"}
            else "blocked"
        )
        members.append(
            ProjectResourceMember(
                member_id=resource_id,
                category=category,
                category_disposition=disposition,
                category_evidence_fingerprint=(
                    observation.fingerprint
                    if observation is not None
                    else fingerprint_value(resource.to_dict())
                ),
                resource_reference=resource,
                observed_resource=observation,
                consuming_behavior_ids=(
                    resource.consuming_behavior_ids if resource is not None else ()
                ),
                consuming_model_ids=(
                    resource.consuming_model_ids if resource is not None else ()
                ),
                rationale=(
                    "declared resource and independent current observation agree"
                    if not row_findings
                    else "; ".join(row.code for row in row_findings)
                ),
            )
        )
    for category in (
        "build",
        "runtime",
        "dependency",
        "configuration",
        "schema",
        "data",
        "asset",
        "migration",
        "external_service",
        "behavioral_oracle",
    ):
        if category in present:
            continue
        if category == "external_service" and not definition.boundary.external_patterns:
            rationale = "the independently declared target boundary contains no external-service pattern"
            scoped_reference = BlueprintResourceReference(
                resource_id="resource:external-service:none-declared",
                kind="external_service",
                owner_id=definition.blueprint_id,
                artifact_id="target-boundary:external-patterns",
                purpose="preserve the explicit absence of an external-service dependency",
                lifecycle_role="not_applicable",
                consuming_behavior_ids=(),
                consuming_model_ids=(),
                disposition="scoped_out",
                rationale=rationale,
            )
            members.append(
                ProjectResourceMember(
                    member_id=scoped_reference.resource_id,
                    category=category,
                    category_disposition="scoped_out",
                    category_evidence_fingerprint=fingerprint_value(
                        definition.boundary.to_dict()
                    ),
                    resource_reference=scoped_reference,
                    observed_resource=None,
                    consuming_behavior_ids=(),
                    consuming_model_ids=(),
                    rationale=rationale,
                )
            )
        else:
            members.append(
                ProjectResourceMember(
                    member_id=f"resource:missing:{category}",
                    category=category,
                    category_disposition="blocked",
                    category_evidence_fingerprint=fingerprint_value(
                        {
                            "boundary": definition.boundary.to_dict(),
                            "missing_category": category,
                        }
                    ),
                    resource_reference=None,
                    observed_resource=None,
                    consuming_behavior_ids=(),
                    consuming_model_ids=(),
                    rationale="independent resource discovery found no terminal member for this category",
                )
            )
    return ProjectResourceInventory(
        inventory_id=f"resource-inventory:{definition.blueprint_id}",
        boundary_fingerprint=fingerprint_value(definition.boundary.to_dict()),
        members=tuple(members),
        discovery_fingerprints=(
            ("implementation-manifest", fingerprint_value([row.to_dict() for row in definition.file_dispositions])),
            ("software-boundary", fingerprint_value(definition.boundary.to_dict())),
            (
                "observed-resource-denominator",
                fingerprint_value(
                    [row.to_dict() for row in evidence.observed_resources]
                ),
            ),
        ),
        findings=tuple(findings),
    )


def _project_test_node_dispositions(
    *,
    required_test_node_ids: Sequence[str],
    coverage_edges: Sequence[BehaviorCoverageEdge],
    contract_owner_by_block: Mapping[str, str],
) -> tuple[ProjectTestNodeDisposition, ...]:
    """Project coverage ownership from exact coverage contracts only.

    A required test node can be relevant to several model input manifests and
    still own no behavior coverage.  Such model/test provenance remains on the
    implementation binding and test inventory; it never expands this owner
    set.  Planned checker identities are included because their coverage rows
    are exact, while execution remains a separate ``not_run`` disposition.
    """

    coverage_by_test: dict[str, list[BehaviorCoverageEdge]] = {}
    for edge in coverage_edges:
        coverage_by_test.setdefault(edge.test_node_id, []).append(edge)

    required_ids = set(required_test_node_ids)
    node_ids = tuple(sorted(required_ids | set(coverage_by_test)))
    dispositions: list[ProjectTestNodeDisposition] = []
    for test_node_id in node_ids:
        node_coverage = tuple(coverage_by_test.get(test_node_id, ()))
        coverage_ids = tuple(sorted(edge.coverage_id for edge in node_coverage))
        owner_ids = tuple(
            sorted(
                {
                    owner_id
                    for edge in node_coverage
                    if (
                        owner_id := contract_owner_by_block.get(
                            edge.behavior_block_id
                        )
                    )
                }
            )
        )
        if not coverage_ids:
            disposition = "supporting"
            rationale = (
                "the current project test remains evidence/support provenance, "
                "but no exact coverage contract assigns it behavior ownership"
            )
        elif not owner_ids:
            disposition = "blocked"
            rationale = (
                "one or more coverage rows reference no current behavior contract owner"
            )
        elif len(owner_ids) == 1:
            disposition = "behavior_coverage"
            rationale = (
                "the exact current test node owns block-local coverage rows"
                if test_node_id in required_ids
                else "the block-local planned checker identity owns exact design coverage; "
                "execution remains separate"
            )
        else:
            disposition = "cross_owner_integration"
            rationale = (
                "this exact checker identity owns coverage rows whose contracts span "
                "the complete declared behavior-owner set"
            )
        dispositions.append(
            ProjectTestNodeDisposition(
                test_node_id=test_node_id,
                disposition=disposition,
                owner_ids=owner_ids,
                coverage_ids=coverage_ids,
                rationale=rationale,
            )
        )
    return tuple(dispositions)


def _behavior_readiness(
    *,
    inventory: ImplementationSurfaceInventory,
    definition: ProjectBlueprintDefinition,
    evidence: ProjectBlueprintEvidence,
    manifest: SoftwareBlueprintManifest,
    binding_report: ModelImplementationBindingReport,
    intent_inventory: ProjectIntentInventory,
    model_test_alignment_report: ModelTestAlignmentReport,
    topology_report: BlueprintTopologyReport,
    delegated_assertion_helpers: Sequence[DelegatedAssertionHelper] = (),
    delegated_helper_fingerprints: Mapping[str, str] | None = None,
) -> tuple[
    BehaviorBlueprintReport,
    ProjectResourceInventory,
    NormalizedBlueprintProjection,
    StaticBlueprintReadinessReport,
    tuple[tuple[str, Any], ...],
    tuple[tuple[str, Any], ...],
]:
    owner_by_surface = {
        surface_id: owner
        for owner in definition.owners
        for surface_id in owner.implementation_surface_ids
    }
    bindings_by_surface: dict[str, list[ModelImplementationBinding]] = {}
    for binding in binding_report.bindings:
        bindings_by_surface.setdefault(
            binding.implementation_surface_id, []
        ).append(binding)
    semantic_by_id = {
        row.semantic_spec_id: row for row in binding_report.semantic_specs
    }
    oracle_by_id = {row.oracle_id: row for row in binding_report.oracles}
    portable_bindings_by_owner: dict[
        str, dict[str, PortableBehaviorBinding]
    ] = {}
    cases_by_owner: dict[
        str, dict[str, tuple[BehaviorCaseContract, ...]]
    ] = {}
    oracle_ids_by_owner: dict[str, frozenset[str]] = {}
    for owner in definition.owners:
        portable_bindings_by_owner[owner.owner_id] = {
            binding.behavior_block_id: binding
            for binding in owner.portable_behavior_bindings
        }
        grouped_cases: dict[str, list[BehaviorCaseContract]] = {}
        for case in owner.behavior_case_contracts:
            grouped_cases.setdefault(case.behavior_block_id, []).append(case)
        cases_by_owner[owner.owner_id] = {
            block_id: tuple(rows) for block_id, rows in grouped_cases.items()
        }
        oracle_ids_by_owner[owner.owner_id] = frozenset(
            row.oracle_id for row in owner.oracles
        )
    intent_ids_by_target: dict[str, set[str]] = {}
    for contribution in intent_inventory.contributions:
        for target_id in contribution.target_ids:
            intent_ids_by_target.setdefault(target_id, set()).add(
                contribution.contribution_id
            )
    behavior_ids = _project_behavior_surface_ids(inventory)
    for owner in definition.owners:
        expected_behavior_block_ids = {
            f"behavior-block:{surface_id}"
            for surface_id in owner.implementation_surface_ids
            if surface_id in behavior_ids
        }
        declared_binding_block_ids = set(
            portable_bindings_by_owner[owner.owner_id]
        )
        if declared_binding_block_ids != expected_behavior_block_ids:
            raise ProjectBlueprintError(
                "project owner portable binding behavior-block denominator differs "
                "from independently observed behavior surfaces for "
                f"{owner.owner_id}: "
                f"missing={sorted(expected_behavior_block_ids - declared_binding_block_ids)} "
                f"extra={sorted(declared_binding_block_ids - expected_behavior_block_ids)}"
            )
        declared_case_block_ids = set(cases_by_owner[owner.owner_id])
        if declared_case_block_ids != expected_behavior_block_ids:
            raise ProjectBlueprintError(
                "project owner behavior-case block denominator differs from "
                "independently observed behavior surfaces for "
                f"{owner.owner_id}: "
                f"missing={sorted(expected_behavior_block_ids - declared_case_block_ids)} "
                f"extra={sorted(declared_case_block_ids - expected_behavior_block_ids)}"
            )
    behavior_surfaces = tuple(
        row
        for row in inventory.surfaces
        if row.surface_id in behavior_ids
    )
    required_surface_ids = set(inventory.required_surface_ids)
    supporting_surfaces = tuple(
        row
        for row in inventory.surfaces
        if row.surface_id in required_surface_ids
        and row.surface_id not in behavior_ids
    )
    contracts: list[BehaviorBlockContract] = []
    portable_bindings: list[PortableBehaviorBinding] = []
    case_contracts: list[BehaviorCaseContract] = []
    behavior_by_surface: dict[str, BehaviorBlockContract] = {}
    for surface in behavior_surfaces:
        owner = owner_by_surface.get(surface.surface_id)
        surface_bindings = tuple(
            bindings_by_surface.get(surface.surface_id, ())
        )
        if owner is None or len(surface_bindings) != 1:
            continue
        implementation_binding = surface_bindings[0]
        portable_binding, declared_cases = _owner_surface_contracts(
            owner,
            surface,
            portable_binding_by_block=portable_bindings_by_owner[owner.owner_id],
            cases_by_block=cases_by_owner[owner.owner_id],
            oracle_ids=oracle_ids_by_owner[owner.owner_id],
        )
        declared_cases = tuple(
            replace(
                case,
                oracle_id=implementation_binding.oracle_ids[0],
            )
            for case in declared_cases
        )
        behavior_block_id = f"behavior-block:{surface.surface_id}"
        contract = BehaviorBlockContract(
            behavior_block_id=behavior_block_id,
            implementation_surface_id=surface.surface_id,
            model_element_id=owner.model_element_id,
            model_fingerprint=owner.model_fingerprint,
            owner_contract_id=owner.owner_contract_id,
            owner_id=owner.owner_id,
            function_relation="Input x State -> Set(Output x State)",
            dimensions=tuple(
                _behavior_dimension(surface, owner, dimension)
                for dimension in BEHAVIOR_DIMENSIONS
            ),
                semantic_spec_ids=implementation_binding.semantic_spec_ids,
                oracle_ids=implementation_binding.oracle_ids,
                intent_contribution_ids=tuple(
                    sorted(
                        intent_ids_by_target.get(behavior_block_id, set())
                        | intent_ids_by_target.get(surface.surface_id, set())
                        | intent_ids_by_target.get(owner.model_element_id, set())
                    )
                ),
                portable_binding_ids=(portable_binding.binding_id,),
            protected_failure_ids=portable_binding.protected_failure_ids,
            accepted=owner.behavior_accepted,
            acceptance_evidence_fingerprints=(
                owner.behavior_acceptance_evidence_fingerprints
            ),
            source_fingerprint=surface.content_fingerprint,
        )
        contracts.append(contract)
        behavior_by_surface[surface.surface_id] = contract
        portable_bindings.append(portable_binding)
        case_contracts.extend(declared_cases)

    planned_checker_fingerprints = {
        checker_id: checker_fingerprint
        for owner in definition.owners
        for checker_id, checker_fingerprint in owner.checker_design_fingerprints
    }
    planned_test_node_fingerprints = {
        case.case_evidence_id: planned_checker_fingerprints[case.case_evidence_id]
        for owner in definition.owners
        for case in owner.behavior_case_contracts
        if case.case_evidence_id in planned_checker_fingerprints
    }

    supporting_relations: list[SupportingSurfaceRelation] = []
    supporting_owner_block_ids = {
        surface.surface_id: f"behavior-block:{surface.owning_surface_id}"
        for surface in supporting_surfaces
        if surface.owning_surface_id
    }
    for surface in supporting_surfaces:
        candidate = behavior_by_surface.get(surface.owning_surface_id)
        if candidate is not None:
            supporting_relations.append(
                SupportingSurfaceRelation(
                    supporting_surface_id=surface.surface_id,
                    behavior_block_id=candidate.behavior_block_id,
                    relation_kind="delegates",
                    evidence_id=f"supporting-edge:{surface.surface_id}:{candidate.behavior_block_id}",
                    evidence_fingerprint=surface.structure_fingerprint,
                    rationale="the active provider's exact owning-surface disposition binds this supporting member to one behavior block",
                )
            )

    coverage: list[BehaviorCoverageEdge] = []
    coverage_execution: list[CoverageExecutionEvidence] = []
    cases_by_block: dict[str, list[BehaviorCaseContract]] = {}
    for case in case_contracts:
        cases_by_block.setdefault(case.behavior_block_id, []).append(case)
    for contract in contracts:
        semantic = semantic_by_id[contract.semantic_spec_ids[0]]
        oracle = oracle_by_id[contract.oracle_ids[0]]
        for case in cases_by_block.get(contract.behavior_block_id, ()):
            planned_test_node_id = case.case_evidence_id
            if planned_test_node_id not in planned_test_node_fingerprints:
                continue
            for dimension in BEHAVIOR_CASE_DIMENSIONS[case.case_kind]:
                coverage_id = (
                    f"coverage:{contract.behavior_block_id}:{case.case_id}:{dimension}"
                )
                dimension_member_id = f"{case.case_evidence_id}:{dimension}"
                dimension_member_fingerprint = planned_checker_fingerprints.get(
                    dimension_member_id
                )
                if dimension_member_fingerprint is None:
                    continue
                coverage_edge = BehaviorCoverageEdge(
                        coverage_id=coverage_id,
                        behavior_block_id=contract.behavior_block_id,
                        implementation_surface_id=contract.implementation_surface_id,
                        model_obligation_id=contract.model_element_id,
                        semantic_spec_id=contract.semantic_spec_ids[0],
                        semantic_content_fingerprint=(
                            semantic.source_content_fingerprint
                        ),
                        owner_contract_id=contract.owner_contract_id,
                        behavior_owner_id=contract.owner_id,
                        implementation_content_fingerprint=contract.source_fingerprint,
                        test_node_id=planned_test_node_id,
                        oracle_member_id=dimension_member_id,
                        oracle_member_fingerprint=dimension_member_fingerprint,
                        case_id=case.case_id,
                        case_content_fingerprint=case.content_fingerprint,
                        covered_dimensions=(dimension,),
                        evidence_role="planned_checker",
                        oracle_id=contract.oracle_ids[0],
                        oracle_content_fingerprint=(
                            oracle.source_content_fingerprint
                        ),
                    )
                coverage.append(coverage_edge)
                coverage_execution.append(
                    CoverageExecutionEvidence(
                        coverage_id=coverage_id,
                        execution_owner_id=f"execution-owner:{contract.owner_id}",
                        disposition="not_run",
                    )
                )
    contract_owner_by_block = {
        row.behavior_block_id: row.owner_id for row in contracts
    }
    test_dispositions = _project_test_node_dispositions(
        required_test_node_ids=evidence.test_inventory.required_node_ids,
        coverage_edges=coverage,
        contract_owner_by_block=contract_owner_by_block,
    )
    validation_member_fingerprints = dict(
        artifact_pair
        for owner in definition.owners
        for artifact_pair in owner.native_evidence_fingerprints
    )
    for checker_id, checker_fingerprint in planned_test_node_fingerprints.items():
        validation_member_fingerprints.setdefault(checker_id, checker_fingerprint)
    behavior_report = review_behavior_blueprint(
        inventory_fingerprint=inventory.inventory_fingerprint,
        required_behavior_surface_ids=tuple(row.surface_id for row in behavior_surfaces),
        supporting_surface_ids=tuple(row.surface_id for row in supporting_surfaces),
        contracts=tuple(contracts),
        portable_bindings=tuple(portable_bindings),
        case_contracts=tuple(case_contracts),
        supporting_relations=tuple(supporting_relations),
        coverage_edges=tuple(coverage),
        coverage_execution_evidence=tuple(coverage_execution),
        test_node_dispositions=test_dispositions,
        required_test_node_ids=evidence.test_inventory.required_node_ids,
        test_nodes=evidence.test_inventory.nodes,
        semantic_specs=binding_report.semantic_specs,
        oracles=binding_report.oracles,
        intent_inventory=intent_inventory,
        implementation_source_fingerprints={
            row.surface_id: row.content_fingerprint for row in behavior_surfaces
        },
        implementation_owner_ids={
            surface_id: owner.owner_id
            for owner in definition.owners
            for surface_id in owner.implementation_surface_ids
            if surface_id in behavior_ids
        },
        path_quality_bindings=evidence.path_quality_bindings,
        expected_path_quality_currentness_id=(
            evidence.observed_snapshot_fingerprint
        ),
        native_member_fingerprints=validation_member_fingerprints,
        planned_checker_fingerprints=planned_checker_fingerprints,
        delegated_assertion_helpers=delegated_assertion_helpers,
        delegated_helper_fingerprints=delegated_helper_fingerprints,
        expected_portable_fingerprints={
            catalog.portable_model_id: catalog.portable_model_fingerprint
            for catalog in evidence.portable_member_catalogs
        },
        expected_portable_members={
            catalog.portable_model_id: {
                "transition_ids": catalog.transition_ids,
                "property_ids": catalog.property_ids,
                "invariant_ids": catalog.invariant_ids,
                "input_field_ids": catalog.input_field_ids,
                "output_field_ids": catalog.output_field_ids,
                "state_field_ids": catalog.state_field_ids,
                "assumption_ids": catalog.assumption_ids,
                "guarantee_ids": catalog.guarantee_ids,
                "protected_failure_ids": catalog.protected_failure_ids,
            }
            for catalog in evidence.portable_member_catalogs
        },
        supporting_surface_fingerprints={
            row.surface_id: row.structure_fingerprint
            for row in supporting_surfaces
        },
        supporting_surface_owner_block_ids=supporting_owner_block_ids,
    )
    resource_inventory = build_project_resource_inventory(definition, evidence)
    shared_objects: dict[str, Any] = {}
    path_quality_object_ids_by_model: dict[str, list[str]] = {}
    for binding in evidence.path_quality_bindings:
        object_id = (
            f"model-path-quality:{binding.model_element_id}:"
            + binding.compact_current_fingerprint.split(":", 1)[-1]
        )
        path_quality_object_ids_by_model.setdefault(
            binding.model_element_id, []
        ).append(object_id)
        shared_objects[object_id] = {
            "kind": "model_path_quality_binding",
            **binding.to_dict(),
        }
    for owner in definition.owners:
        shared_objects[owner.owner_id] = {
            "kind": "behavior_owner",
            "model_element_id": owner.model_element_id,
            "model_fingerprint": owner.model_fingerprint,
        }
        shared_objects[owner.owner_contract_id] = {
            "kind": "owner_contract",
            "owner_id": owner.owner_id,
            "fingerprint": owner.owner_contract_fingerprint,
        }
        shared_objects[owner.model_element_id] = {
            "kind": "model_element",
            "owner_id": owner.owner_id,
            "owner_contract_id": owner.owner_contract_id,
            "referenced_object_ids": [
                owner.owner_id,
                owner.owner_contract_id,
                f"topology-index:{owner.model_element_id}",
                f"model-test-alignment-owner:{owner.model_element_id}",
                *sorted(
                    path_quality_object_ids_by_model.get(
                        owner.model_element_id, ()
                    )
                ),
            ],
        }
    for semantic in binding_report.semantic_specs:
        shared_objects[semantic.semantic_spec_id] = semantic.to_dict()
    for oracle in binding_report.oracles:
        shared_objects[oracle.oracle_id] = oracle.to_dict()
    for row in evidence.test_inventory.nodes:
        shared_objects[row.node_id] = row.to_dict()
        for assertion in row.assertions:
            shared_objects[assertion.assertion_id] = assertion.to_dict()
        for marker in row.parameterization_markers:
            shared_objects[marker.marker_id] = marker.to_dict()
            for case_id in marker.case_ids:
                shared_objects[f"case:{marker.marker_id}:{case_id}"] = {
                    "kind": "test_case",
                    "marker_id": marker.marker_id,
                    "case_id": case_id,
                    "test_node_id": row.node_id,
                }
    for row in portable_bindings:
        shared_objects[row.binding_id] = {
            "kind": "portable_behavior_binding",
            **row.to_dict(),
        }
    for checker_id, checker_fingerprint in planned_checker_fingerprints.items():
        shared_objects[checker_id] = {
            "kind": "declared_checker_design",
            "fingerprint": checker_fingerprint,
        }
    for row in case_contracts:
        shared_objects[row.case_id] = {
            "kind": "behavior_case_contract",
            **row.to_dict(),
        }
    for row in coverage:
        shared_objects[row.coverage_id] = {
            "kind": "behavior_coverage_edge",
            **row.to_dict(),
        }
    coverage_ids_by_block: dict[str, list[str]] = {}
    for row in coverage:
        coverage_ids_by_block.setdefault(row.behavior_block_id, []).append(
            row.coverage_id
        )
    cases_by_block_ids: dict[str, list[str]] = {}
    for row in case_contracts:
        cases_by_block_ids.setdefault(row.behavior_block_id, []).append(row.case_id)
    resource_ids_by_behavior: dict[str, list[str]] = {}
    resource_ids_by_model: dict[str, list[str]] = {}
    for resource_member in resource_inventory.members:
        for behavior_id in resource_member.consuming_behavior_ids:
            resource_ids_by_behavior.setdefault(behavior_id, []).append(
                resource_member.member_id
            )
        for model_id in resource_member.consuming_model_ids:
            resource_ids_by_model.setdefault(model_id, []).append(
                resource_member.member_id
            )
    for row in contracts:
        shared_objects[row.behavior_block_id] = {
            "kind": "behavior_block",
            **row.to_dict(),
            "referenced_object_ids": sorted(
                {
                    row.model_element_id,
                    row.owner_id,
                    row.owner_contract_id,
                    *row.semantic_spec_ids,
                    *row.oracle_ids,
                    *row.portable_binding_ids,
                    *row.intent_contribution_ids,
                    *resource_ids_by_behavior.get(row.behavior_block_id, ()),
                    *resource_ids_by_model.get(row.model_element_id, ()),
                    *path_quality_object_ids_by_model.get(
                        row.model_element_id, ()
                    ),
                    *coverage_ids_by_block.get(row.behavior_block_id, ()),
                    *cases_by_block_ids.get(row.behavior_block_id, ()),
                }
            ),
        }
        shared_objects[row.implementation_surface_id] = {
            "kind": "implementation_surface_index",
            "implementation_surface_id": row.implementation_surface_id,
            "behavior_block_id": row.behavior_block_id,
            "model_element_id": row.model_element_id,
            "referenced_object_ids": [
                row.behavior_block_id,
                row.model_element_id,
            ],
        }
    for row in coverage_execution:
        if row.receipt_id:
            shared_objects[row.receipt_id] = {
                "kind": "terminal_execution_receipt",
                "fingerprint": row.receipt_fingerprint,
                "disposition": row.disposition,
            }
    for artifact in evidence.native_evidence_artifacts:
        shared_objects[artifact.evidence_id] = {
            "kind": "native_evidence_artifact",
            **artifact.to_dict(),
        }
    for row in resource_inventory.members:
        shared_objects[row.member_id] = row.to_dict()
    for row in intent_inventory.contributions:
        shared_objects[row.contribution_id] = row.to_dict()
    model_test_alignment_fingerprint = model_test_alignment_report.fingerprint
    shared_objects[
        f"model-test-alignment:{model_test_alignment_fingerprint}"
    ] = {
        "kind": "model_test_alignment_report",
        **model_test_alignment_report.to_dict(),
    }
    shared_objects[f"blueprint-topology:{topology_report.topology_id}"] = {
        "kind": "blueprint_topology_report",
        **topology_report.to_dict(),
    }
    for row in evidence.topology_nodes:
        shared_objects[f"topology-node:{row.node_id}"] = {
            "kind": "blueprint_topology_node",
            **row.to_dict(),
        }
    for row in evidence.topology_relations:
        shared_objects[f"topology-relation:{row.relation_id}"] = {
            "kind": "blueprint_topology_relation",
            **row.to_dict(),
            "referenced_object_ids": [
                f"topology-node:{row.producer_id}",
                f"topology-node:{row.consumer_id}",
            ],
        }
    for row in evidence.topology_nodes:
        shared_objects[f"topology-index:{row.node_id}"] = {
            "kind": "blueprint_topology_index",
            "node_object_id": f"topology-node:{row.node_id}",
            "relation_object_ids": sorted(
                f"topology-relation:{relation.relation_id}"
                for relation in evidence.topology_relations
                if row.node_id in (relation.producer_id, relation.consumer_id)
            ),
        }
    for owner in definition.owners:
        shared_objects[
            f"model-test-alignment-owner:{owner.model_element_id}"
        ] = {
            "kind": "model_test_alignment_owner",
            "model_test_alignment_report_fingerprint": (
                model_test_alignment_fingerprint
            ),
            "implementation_binding_report_fingerprint": (
                model_test_alignment_report.implementation_binding_report_fingerprint
            ),
            "pre_code_status": model_test_alignment_report.pre_code_status,
            "executed_evidence_status": (
                model_test_alignment_report.executed_evidence_status
            ),
            "test_evidence_ids": list(owner.test_evidence_ids),
            "native_evidence_ids": list(owner.native_evidence_ids),
        }
    normalized_shards = materialize_behavior_blueprint_shards(
        behavior_report,
        shared_objects=shared_objects,
    )
    projection = normalize_behavior_blueprint(
        blueprint_fingerprint=manifest.fingerprint,
        behavior_report=behavior_report,
        shared_objects=shared_objects,
        coverage_reference_shards=normalized_shards,
        source_projection=binding_report.to_dict(),
    )
    readiness = review_static_blueprint_readiness(
        blueprint_fingerprint=manifest.fingerprint,
        behavior_report=behavior_report,
        resource_inventory=resource_inventory,
        intent_inventory=intent_inventory,
        topology_fingerprint=topology_report.fingerprint,
        normalized_projection_fingerprint=projection.fingerprint,
        topology_findings=tuple(
            ReadinessFinding(
                row.code,
                row.message,
                row.subject_ids,
                "blocked",
            )
            for row in topology_report.findings
        ),
    )
    return (
        behavior_report,
        resource_inventory,
        projection,
        readiness,
        tuple(sorted(shared_objects.items())),
        normalized_shards,
    )


def _project_target_descriptor(
    definition: ProjectBlueprintDefinition,
    evidence: ProjectBlueprintEvidence,
) -> TargetSystemDescriptor:
    return TargetSystemDescriptor(
        target_system_id=f"target-system:{definition.blueprint_id}",
        target_kind=definition.target_kind,
        target_profile=definition.target_profile,
        subject_revision=evidence.observed_snapshot_fingerprint,
        boundary_fingerprint=fingerprint_value(definition.boundary.to_dict()),
        required_observation_capabilities=(
            "implementation_inventory",
            "resource_inventory",
            "test_inventory",
        ),
        required_authority_capabilities=(
            "behavior_semantics",
            "intent_lineage",
            "model_authority",
            "model_topology",
            "oracle_inventory",
            "portable_behavior",
        ),
        claim_boundary=definition.claim_boundary,
    )


def collect_project_blueprint_provider_results(
    preparation: ProjectBlueprintPreparation,
) -> tuple[TargetSystemProviderResult, ...]:
    """Run project-native provider projections without freezing or qualifying them."""

    definition = preparation.definition
    evidence = preparation.evidence
    descriptor = _project_target_descriptor(definition, evidence)
    portable_fingerprint = fingerprint_value(
        {
            "owners": dict(evidence.portable_owner_fingerprints),
            "member_catalogs": [
                row.to_dict() for row in evidence.portable_member_catalogs
            ],
        }
    )
    payload_fingerprints = {
        "implementation_inventory": preparation.inventory.inventory_fingerprint,
        "resource_inventory": preparation.resource_inventory.fingerprint,
        "test_inventory": evidence.test_inventory.inventory_fingerprint,
        "behavior_semantics": preparation.behavior_report.fingerprint,
        "intent_lineage": preparation.intent_inventory.fingerprint,
        "model_authority": evidence.observed_snapshot_fingerprint,
        "model_topology": preparation.topology_report.fingerprint,
        "oracle_inventory": fingerprint_value(
            [row.to_dict() for row in preparation.binding_report.oracles]
        ),
        "portable_behavior": portable_fingerprint,
    }
    input_fingerprints = {
        "boundary": descriptor.boundary_fingerprint,
        "file_dispositions": fingerprint_value(
            [row.to_dict() for row in definition.file_dispositions]
        ),
        "resource_observations": fingerprint_value(
            [row.to_dict() for row in evidence.observed_resources]
        ),
        "test_inventory_declaration": evidence.test_inventory.inventory_fingerprint,
        "owner_declarations": fingerprint_value(
            [row.to_dict() for row in definition.owners]
        ),
        "intent_authority": preparation.intent_inventory.canonical_review_fingerprint,
        "observed_model_snapshot": evidence.observed_snapshot_fingerprint,
        "topology_declaration": fingerprint_value(
            {
                "nodes": [row.to_dict() for row in evidence.topology_nodes],
                "relations": [row.to_dict() for row in evidence.topology_relations],
            }
        ),
        "oracle_declarations": fingerprint_value(
            [row.to_dict() for owner in definition.owners for row in owner.oracles]
        ),
        "portable_catalogs": portable_fingerprint,
    }
    capability_inputs = {
        "implementation_inventory": ("boundary", "file_dispositions"),
        "resource_inventory": ("boundary", "resource_observations"),
        "test_inventory": ("boundary", "test_inventory_declaration"),
        "behavior_semantics": ("owner_declarations",),
        "intent_lineage": ("intent_authority",),
        "model_authority": ("observed_model_snapshot",),
        "model_topology": ("topology_declaration",),
        "oracle_inventory": ("oracle_declarations",),
        "portable_behavior": ("portable_catalogs",),
    }
    providers: list[TargetSystemProviderResult] = []
    for declaration in definition.observation_providers + definition.authority_providers:
        missing_payloads = tuple(
            capability
            for capability in declaration.capability_ids
            if capability not in payload_fingerprints or capability not in capability_inputs
        )
        used_inputs = tuple(
            sorted(
                {
                    input_id
                    for capability in declaration.capability_ids
                    for input_id in capability_inputs.get(capability, ())
                }
            )
        )
        providers.append(
            TargetSystemProviderResult(
                provider_id=declaration.provider_id,
                provider_role=declaration.provider_role,
                provider_kind=declaration.provider_kind,
                provider_version=declaration.provider_version,
                target_system_id=descriptor.target_system_id,
                subject_revision=descriptor.subject_revision,
                capability_ids=declaration.capability_ids,
                input_fingerprints=tuple(
                    (input_id, input_fingerprints[input_id]) for input_id in used_inputs
                ),
                payload_fingerprints=tuple(
                    (capability, payload_fingerprints[capability])
                    for capability in declaration.capability_ids
                    if capability in payload_fingerprints
                ),
                capability_bindings=tuple(
                    ProviderCapabilityBinding(
                        capability_id=capability,
                        input_ids=capability_inputs[capability],
                        payload_ids=(capability,),
                    )
                    for capability in declaration.capability_ids
                    if capability in payload_fingerprints
                    and capability in capability_inputs
                ),
                status=("incomplete" if missing_payloads else "current"),
                findings=tuple(
                    f"provider capability has no canonical payload: {capability}"
                    for capability in missing_payloads
                ),
                claim_boundary=declaration.claim_boundary,
            )
        )
    return tuple(sorted(providers, key=lambda row: row.provider_id))


def freeze_project_blueprint_evidence(
    preparation: ProjectBlueprintPreparation,
    provider_results: Sequence[TargetSystemProviderResult],
) -> FrozenTargetSystemEvidence:
    """Freeze already-produced provider results; this function runs no provider."""

    definition = preparation.definition
    descriptor = _project_target_descriptor(definition, preparation.evidence)
    declarations = definition.observation_providers + definition.authority_providers
    registry = build_target_system_provider_registry(
        f"provider-registry:{definition.blueprint_id}", declarations
    )
    snapshot = capture_target_system_snapshot(
        f"target-system-snapshot:{definition.blueprint_id}:{descriptor.subject_revision}",
        descriptor,
        registry,
        provider_results,
    )
    layer_plan = CANONICAL_SOFTWARE_LAYER_PLAN
    if definition.target_profile != layer_plan.target_profile:
        raise ProjectBlueprintError(
            "project blueprint preparation supports only the software layer profile"
        )
    return FrozenTargetSystemEvidence(
        evidence_id=f"frozen-target-evidence:{definition.blueprint_id}",
        layer_plan=layer_plan,
        provider_registry=registry,
        provider_results=tuple(provider_results),
        snapshot=snapshot,
        claim_boundary=(
            "Frozen project-native provider outputs for one exact target revision; "
            "qualification is performed separately."
        ),
    )


def _project_target_layers(
    preparation: ProjectBlueprintPreparation,
) -> tuple[tuple[BlueprintLayerResult, ...], tuple[BlueprintGapRef, ...]]:
    inventory = preparation.inventory
    inventory_audit = preparation.implementation_inventory_audit
    binding_report = preparation.binding_report
    model_test_alignment_report = preparation.model_test_alignment_report
    topology_report = preparation.topology_report
    manifest = preparation.manifest
    qualification = preparation.qualification
    behavior_report = preparation.behavior_report
    resource_inventory = preparation.resource_inventory
    intent_inventory = preparation.intent_inventory
    readiness = preparation.static_readiness
    native_reports = _project_native_report_refs(preparation)
    gaps: list[BlueprintGapRef] = []
    layers: list[BlueprintLayerResult] = []

    def add_layer(
        layer: str,
        passed: bool,
        evidence_ids: Sequence[str],
        *,
        object_kind: str,
        object_id: str,
        message: str,
        status: str = "incomplete",
        native_report_keys: Sequence[str] = (),
        pre_code_status: str = "",
        executed_evidence_status: str = "not_applicable",
        detail_gaps: Sequence[BlueprintGapRef] = (),
    ) -> None:
        refs = tuple(native_reports[key] for key in native_report_keys)
        exact_evidence_ids = tuple(
            sorted(
                {
                    *(str(item) for item in evidence_ids),
                    *(row.report_fingerprint for row in refs),
                }
            )
        )
        design_status = pre_code_status or (
            "ready" if passed else (
                status if status in {"blocked", "stale"} else "incomplete"
            )
        )
        if passed:
            layers.append(
                BlueprintLayerResult._derived(
                    layer=layer,
                    status="pass",
                    evidence_ids=exact_evidence_ids,
                    native_reports=refs,
                    pre_code_status=design_status,
                    executed_evidence_status=executed_evidence_status,
                )
            )
            return
        layer_gaps = tuple(detail_gaps) or (
            BlueprintGapRef(
                layer=layer,
                object_kind=object_kind,
                object_id=object_id,
                status=status,
                evidence_ref=(exact_evidence_ids[0] if exact_evidence_ids else ""),
                message=message,
            ),
        )
        if any(row.layer != layer for row in layer_gaps):
            raise ProjectBlueprintError(
                "detailed readiness gaps must belong to their exact layer"
            )
        gaps.extend(layer_gaps)
        layers.append(
            BlueprintLayerResult._derived(
                layer=layer,
                status=(status if status in {"stale", "blocked"} else "incomplete"),
                evidence_ids=exact_evidence_ids,
                gap_ids=tuple(row.gap_id for row in layer_gaps),
                native_reports=refs,
                pre_code_status=design_status,
                executed_evidence_status=executed_evidence_status,
            )
        )

    add_layer(
        "implementation_inventory",
        inventory_audit.ok,
        (inventory.inventory_fingerprint, inventory_audit.fingerprint),
        object_kind="implementation_inventory",
        object_id=inventory.inventory_id,
        message=(
            "implementation inventory is exact-current"
            if inventory_audit.ok
            else "implementation inventory is blocked: "
            + ",".join(row.code for row in inventory_audit.findings)
        ),
        status=("incomplete" if inventory_audit.ok else "blocked"),
        native_report_keys=("implementation_inventory",),
        detail_gaps=(
            tuple(
                BlueprintGapRef(
                    layer="implementation_inventory",
                    object_kind="implementation_inventory_finding",
                    object_id=(
                        f"{row.code}:{row.path or '-'}:{row.surface_id or '-'}"
                    ),
                    status=(
                        "stale"
                        if row.code == "stale_file_fingerprint"
                        else "blocked"
                    ),
                    owner_id="implementation-inventory",
                    evidence_ref=inventory_audit.fingerprint,
                    message=row.message,
                )
                for row in inventory_audit.findings
                if row.severity == "blocker"
            )
            if not inventory_audit.ok
            else ()
        ),
    )
    add_layer(
        "traceability",
        binding_report.ok and topology_report.ok,
        (binding_report.fingerprint, topology_report.fingerprint),
        object_kind="model_implementation_binding_report",
        object_id=f"binding-report:{binding_report.fingerprint}",
        message="model-to-implementation traceability is incomplete",
        status=("blocked" if not binding_report.ok else "incomplete"),
        native_report_keys=("binding", "topology"),
    )
    semantic_complete = bool(behavior_report.contracts) and all(
        row.accepted for row in behavior_report.contracts
    ) and not any(
        row.code
        in {
            "behavior_contract_missing",
            "behavior_contract_unaccepted",
            "same_source_semantic_oracle_circularity",
            "generic_semantics_reused_across_blocks",
            "portable_behavior_binding_missing",
            "portable_behavior_binding_stale",
        }
        for row in behavior_report.findings
    )
    add_layer(
        "independent_semantics",
        semantic_complete,
        (behavior_report.fingerprint,),
        object_kind="behavior_semantics",
        object_id=behavior_report.fingerprint,
        message="one or more behavior blocks lack independent exact semantics",
        native_report_keys=("behavior",),
        pre_code_status=behavior_report.pre_code_status,
        executed_evidence_status=behavior_report.executed_evidence_status,
    )
    add_layer(
        "model_code_test",
        behavior_report.complete
        and model_test_alignment_report.pre_code_status == "ready"
        and model_test_alignment_report.implementation_binding_report_fingerprint
        == binding_report.fingerprint,
        (
            behavior_report.fingerprint,
            binding_report.fingerprint,
            model_test_alignment_report.fingerprint,
        ),
        object_kind="behavior_coverage",
        object_id=behavior_report.fingerprint,
        message="exact model-code-test behavior coverage is incomplete",
        status=(
            "blocked"
            if any(row.severity == "blocked" for row in behavior_report.findings)
            else "incomplete"
        ),
        native_report_keys=(
            "behavior",
            "binding",
            "model_test_alignment",
            "test_inventory",
        ),
        pre_code_status=(
            "ready"
            if (
                behavior_report.pre_code_status == "ready"
                and model_test_alignment_report.pre_code_status == "ready"
            )
            else (
                "blocked"
                if "blocked"
                in {
                    behavior_report.pre_code_status,
                    model_test_alignment_report.pre_code_status,
                }
                else "stale"
                if "stale"
                in {
                    behavior_report.pre_code_status,
                    model_test_alignment_report.pre_code_status,
                }
                else "incomplete"
            )
        ),
        executed_evidence_status=(
            "passed"
            if {
                behavior_report.executed_evidence_status,
                model_test_alignment_report.executed_evidence_status,
            }
            == {"passed"}
            else "blocked"
            if "blocked"
            in {
                behavior_report.executed_evidence_status,
                model_test_alignment_report.executed_evidence_status,
            }
            else "failed"
            if "failed"
            in {
                behavior_report.executed_evidence_status,
                model_test_alignment_report.executed_evidence_status,
            }
            else "not_run"
        ),
    )
    resource_oracle_complete = resource_inventory.complete and intent_inventory.complete
    add_layer(
        "resource_oracle",
        resource_oracle_complete,
        (resource_inventory.fingerprint, intent_inventory.fingerprint),
        object_kind="resource_intent_oracle_closure",
        object_id=manifest.blueprint_id,
        message="resource, intent, or oracle closure is incomplete",
        status=("blocked" if not resource_inventory.complete else "incomplete"),
        native_report_keys=("resource_inventory", "intent_inventory"),
    )
    static_ready = (
        qualification.static_manifest_ready and readiness.status == "ready"
    )
    add_layer(
        "static_blueprint",
        static_ready,
        (manifest.fingerprint, readiness.fingerprint),
        object_kind="static_blueprint",
        object_id=manifest.blueprint_id,
        message="canonical static target-system blueprint is not ready",
        status=(
            readiness.status
            if readiness.status in {"stale", "blocked"}
            else "incomplete"
        ),
        native_report_keys=(
            "manifest",
            "qualification",
            "normalized_projection",
            "static_readiness",
        ),
        pre_code_status=readiness.status,
    )
    return tuple(layers), tuple(gaps)


def prepare_project_blueprint(
    root: str | Path,
    definition: ProjectBlueprintDefinition,
    evidence: ProjectBlueprintEvidence,
    *,
    discovery_adapters: Mapping[str, DiscoveryAdapter],
    test_discovery_adapters: Mapping[str, TestDiscoveryAdapter],
    implementation_inventory: ImplementationSurfaceInventory | None = None,
    delegated_assertion_helpers: Sequence[DelegatedAssertionHelper] = (),
    delegated_helper_fingerprints: Mapping[str, str] | None = None,
) -> ProjectBlueprintPreparation:
    """Build project-native reports without freezing or claiming target readiness."""

    root_path = Path(root).resolve()
    if implementation_inventory is None:
        inventory = build_implementation_surface_inventory(
            root_path,
            definition.boundary,
            inventory_id=definition.inventory_id,
            file_dispositions=definition.file_dispositions,
            surface_dispositions=dict(definition.surface_dispositions),
            supporting_owners=dict(definition.supporting_owners),
            dynamic_allowances=dict(definition.dynamic_allowances),
            dynamic_selector_contracts=definition.dynamic_selector_contracts,
            discovery_adapters=discovery_adapters,
            claim_boundary=definition.claim_boundary,
        )
    else:
        inventory = implementation_inventory
        if inventory.inventory_id != definition.inventory_id:
            raise ProjectBlueprintError("supplied inventory identity does not match definition")
        if inventory.boundary != definition.boundary:
            raise ProjectBlueprintError("supplied inventory boundary does not match definition")
        if inventory.file_dispositions != definition.file_dispositions:
            raise ProjectBlueprintError("supplied inventory file manifest does not match definition")
        if inventory.claim_boundary != definition.claim_boundary:
            raise ProjectBlueprintError("supplied inventory claim boundary does not match definition")
    implementation_inventory_audit = review_implementation_surface_inventory(
        inventory,
        root=root_path,
    )
    test_audit = review_project_test_inventory(
        evidence.test_inventory,
        root=root_path,
        discovery_adapters=test_discovery_adapters,
    )
    if not test_audit.ok:
        codes = ",".join(row.code for row in test_audit.findings)
        raise ProjectBlueprintError(
            f"project test inventory is not exact-current: {codes}"
        )
    surface_by_id = {row.surface_id: row for row in inventory.surfaces}
    required_surface_ids = set(inventory.required_surface_ids)
    consumers_by_surface_id = _canonical_consumer_surface_ids(
        inventory.surfaces,
        root=root_path,
    )
    bindings: list[ModelImplementationBinding] = []
    semantic_specs: list[SemanticSpecReference] = []
    oracles: list[OracleReference] = []
    current_models: dict[str, str] = {}
    current_contracts: dict[str, str] = {}
    current_tests = {
        row.node_id: row.structure_fingerprint
        for row in evidence.test_inventory.nodes
    }
    for artifact in evidence.native_evidence_artifacts:
        if artifact.evidence_id in current_tests:
            raise ProjectBlueprintError(
                "project evidence identity collides with a test node"
            )
        current_path = (root_path / artifact.artifact_path).resolve()
        try:
            current_path.relative_to(root_path)
        except ValueError as exc:
            raise ProjectBlueprintError(
                "project evidence artifact escapes the root"
            ) from exc
        if not current_path.is_file():
            raise ProjectBlueprintError(
                f"project evidence artifact is missing: {artifact.artifact_path}"
            )
        if source_file_fingerprint(current_path) != artifact.artifact_fingerprint:
            raise ProjectBlueprintError(
                f"project evidence artifact is stale: {artifact.artifact_path}"
            )
        current_tests[artifact.evidence_id] = artifact.artifact_fingerprint
    behavior_surface_ids = _project_behavior_surface_ids(inventory)
    for owner in definition.owners:
        current_models[owner.model_element_id] = owner.model_fingerprint
        current_contracts[owner.owner_contract_id] = owner.owner_contract_fingerprint
        owner_behavior_ids = tuple(
            sorted(set(owner.implementation_surface_ids) & behavior_surface_ids)
        )
        primary_behavior_id = (
            owner.primary_surface_id
            if owner.primary_surface_id in owner_behavior_ids
            else (owner_behavior_ids[0] if owner_behavior_ids else "")
        )
        for surface_id in owner_behavior_ids:
            surface = surface_by_id.get(surface_id)
            dimensions = project_surface_dimensions(surface) if surface is not None else ("input", "output", "error")
            primary = surface_id == primary_behavior_id
            source_semantic = owner.semantic_specs[0]
            behavior_dimensions = tuple(
                _behavior_dimension(surface, owner, dimension)
                for dimension in BEHAVIOR_DIMENSIONS
            )
            semantic_payload = {
                row.dimension: row.semantics
                for row in behavior_dimensions
                if row.dimension in set(dimensions)
            }
            if "state_effect" in dimensions:
                semantic_payload["state_effect"] = next(
                    row.semantics
                    for row in behavior_dimensions
                    if row.dimension in {"state", "effect"}
                    and row.disposition == "modeled"
                )
            semantic_id = f"semantic-spec:{owner.model_element_id}:{surface_id}"
            semantic_fingerprint = fingerprint_value(
                {
                    "owner_semantic_fingerprint": source_semantic.artifact_fingerprint,
                    "surface_id": surface_id,
                    "dimensions": semantic_payload,
                }
            )
            semantic_specs.append(
                SemanticSpecReference(
                    semantic_spec_id=semantic_id,
                    owner_id=owner.owner_id,
                    artifact_id=f"{source_semantic.artifact_id}#{surface_id}",
                    artifact_fingerprint=semantic_fingerprint,
                    source_id=source_semantic.source_id,
                    source_owner_id=source_semantic.source_owner_id,
                    source_content_fingerprint=(
                        source_semantic.source_content_fingerprint
                    ),
                    covered_model_element_ids=(owner.model_element_id,),
                    covered_dimensions=tuple(sorted(semantic_payload)),
                    semantics=tuple(semantic_payload.items()),
                    authority_kind=source_semantic.authority_kind,
                    provenance_fingerprints=tuple(
                        {
                            **dict(source_semantic.provenance_fingerprints),
                            "owner-contract": owner.owner_contract_fingerprint,
                            "surface-structure": surface.structure_fingerprint,
                        }.items()
                    ),
                )
            )
            source_oracle = owner.oracles[0]
            oracle_payload = {
                dimension: dict(source_oracle.semantics).get(
                    {
                        "completion": "output",
                    }.get(dimension, dimension),
                    f"inspect the accepted {dimension} contract for {surface.symbol}",
                )
                for dimension in dimensions
            }
            oracle_id = f"oracle:{owner.model_element_id}:{surface_id}"
            oracle_fingerprint = fingerprint_value(
                {
                    "owner_oracle_fingerprint": source_oracle.artifact_fingerprint,
                    "surface_id": surface_id,
                    "dimensions": oracle_payload,
                }
            )
            oracles.append(
                OracleReference(
                    oracle_id=oracle_id,
                    owner_id=source_oracle.owner_id,
                    artifact_id=f"{source_oracle.artifact_id}#{surface_id}",
                    artifact_fingerprint=oracle_fingerprint,
                    source_id=source_oracle.source_id,
                    source_owner_id=source_oracle.source_owner_id,
                    source_content_fingerprint=(
                        source_oracle.source_content_fingerprint
                    ),
                    covered_model_element_ids=(owner.model_element_id,),
                    covered_dimensions=tuple(sorted(oracle_payload)),
                    semantics=tuple(oracle_payload.items()),
                )
            )
            current_owner_evidence = (
                owner.test_evidence_fingerprints
                + owner.native_evidence_fingerprints
            )
            bindings.append(
                ModelImplementationBinding(
                    binding_id=f"binding:{owner.model_element_id}:{surface_id}",
                    model_element_id=owner.model_element_id,
                    model_obligation_ids=(
                        f"behavior-block:{surface_id}",
                    ),
                    implementation_surface_id=surface_id,
                    relation_kind="implements",
                    owner_contract_id=owner.owner_contract_id,
                    implementation_source_id=(
                        f"{surface.path}::{surface.symbol}" if surface else surface_id
                    ),
                    implementation_owner_id=owner.owner_id,
                    implementation_content_fingerprint=(
                        surface.content_fingerprint if surface else "missing"
                    ),
                    semantic_spec_ids=(semantic_id,),
                    oracle_ids=(oracle_id,),
                    required_dimensions=dimensions,
                    consumer_surface_ids=consumers_by_surface_id.get(
                        surface_id, ()
                    ),
                    test_evidence_ids=tuple(
                        evidence_id for evidence_id, _fingerprint in current_owner_evidence
                    ),
                    test_evidence_fingerprints=current_owner_evidence,
                    primary=primary,
                    model_fingerprint=owner.model_fingerprint,
                    implementation_fingerprint=(surface.content_fingerprint if surface else None),
                    owner_contract_fingerprint=owner.owner_contract_fingerprint,
                )
            )

    owner_by_surface = {
        surface_id: owner
        for owner in definition.owners
        for surface_id in owner.implementation_surface_ids
    }
    behavior_binding_by_surface = {
        binding.implementation_surface_id: binding for binding in bindings
    }
    for surface_id in sorted(required_surface_ids - behavior_surface_ids):
        surface = surface_by_id.get(surface_id)
        owner = owner_by_surface.get(surface_id)
        if surface is None or owner is None or not surface.owning_surface_id:
            continue
        target = behavior_binding_by_surface.get(surface.owning_surface_id)
        if target is None or (
            target.model_element_id != owner.model_element_id
            or target.owner_contract_id != owner.owner_contract_id
            or target.implementation_owner_id != owner.owner_id
        ):
            continue
        bindings.append(
            ModelImplementationBinding(
                binding_id=f"binding:{owner.model_element_id}:{surface_id}",
                model_element_id=owner.model_element_id,
                model_obligation_ids=target.model_obligation_ids,
                implementation_surface_id=surface_id,
                relation_kind="supports",
                owner_contract_id=owner.owner_contract_id,
                implementation_source_id=f"{surface.path}::{surface.symbol}",
                implementation_owner_id=owner.owner_id,
                implementation_content_fingerprint=surface.content_fingerprint,
                semantic_spec_ids=target.semantic_spec_ids,
                oracle_ids=target.oracle_ids,
                required_dimensions=target.required_dimensions,
                consumer_surface_ids=consumers_by_surface_id.get(surface_id, ()),
                test_evidence_ids=target.test_evidence_ids,
                test_evidence_fingerprints=target.test_evidence_fingerprints,
                primary=False,
                delegating=True,
                model_fingerprint=owner.model_fingerprint,
                implementation_fingerprint=surface.content_fingerprint,
                owner_contract_fingerprint=owner.owner_contract_fingerprint,
            )
        )

    binding_report = review_model_implementation_bindings(
        inventory,
        required_model_element_ids=tuple(row.model_element_id for row in definition.owners),
        required_implementation_surface_ids=tuple(sorted(required_surface_ids)),
        bindings=tuple(bindings),
        semantic_specs=tuple(semantic_specs),
        oracles=tuple(oracles),
        current_model_fingerprints=current_models,
        current_contract_fingerprints=current_contracts,
        current_semantic_spec_fingerprints={row.semantic_spec_id: row.artifact_fingerprint for row in semantic_specs},
        current_oracle_fingerprints={row.oracle_id: row.artifact_fingerprint for row in oracles},
        current_test_evidence_fingerprints=current_tests,
    )
    model_test_alignment_report = _project_model_test_alignment(
        definition=definition,
        evidence=evidence,
        inventory=inventory,
        binding_report=binding_report,
    )
    declared_evidence_by_owner = {
        owner.model_element_id: dict(
            owner.test_evidence_fingerprints
            + owner.native_evidence_fingerprints
        )
        for owner in definition.owners
    }
    current_topology_evidence = dict(current_tests)
    for evidence_id, evidence_fingerprint in (
        evidence.current_child_evidence_fingerprints
    ):
        existing = current_topology_evidence.get(evidence_id)
        if existing is not None and existing != evidence_fingerprint:
            raise ProjectBlueprintError(
                "current child evidence identity collides with another current "
                "evidence artifact"
            )
        current_topology_evidence[evidence_id] = evidence_fingerprint
    current_child_evidence = dict(
        evidence.current_child_evidence_fingerprints
    )
    child_evidence_by_owner: dict[str, dict[str, str]] = {}
    for child in evidence.child_models:
        owner_evidence = declared_evidence_by_owner.get(child.model_id, {})
        exact_binding: dict[str, str] = {}
        if child.evidence_id:
            declared_child_fingerprint = current_child_evidence.get(
                child.evidence_id
            )
            if declared_child_fingerprint is not None:
                exact_binding[child.evidence_id] = declared_child_fingerprint
        for evidence_id in (
            *child.validation_evidence,
            *child.runtime_path_evidence_ids,
        ):
            declared_fingerprint = current_child_evidence.get(
                evidence_id,
                owner_evidence.get(evidence_id),
            )
            if declared_fingerprint is not None:
                exact_binding[evidence_id] = declared_fingerprint
        child_evidence_by_owner[child.model_id] = exact_binding
    topology_report = review_blueprint_topology(
        topology_id=evidence.semantic_mesh_id,
        nodes=evidence.topology_nodes,
        relations=evidence.topology_relations,
        required_owner_ids=tuple(
            owner.model_element_id for owner in definition.owners
        ),
        required_surface_ids_by_owner={
            owner.model_element_id: owner.implementation_surface_ids
            for owner in definition.owners
        },
        child_models=evidence.child_models,
        reattachment_contracts=evidence.reattachment_contracts,
        current_evidence_fingerprints=current_topology_evidence,
        declared_evidence_fingerprints_by_owner=child_evidence_by_owner,
        current_relation_evidence_fingerprints=dict(
            evidence.current_relation_evidence_fingerprints
        ),
        current_refinement_fingerprints=dict(
            evidence.current_refinement_fingerprints
        ),
        current_progress_evidence_fingerprints=dict(
            evidence.current_progress_evidence_fingerprints
        ),
    )
    manifest = SoftwareBlueprintManifest(
        blueprint_id=definition.blueprint_id,
        observed_snapshot_id=evidence.observed_snapshot_id,
        observed_snapshot_fingerprint=evidence.observed_snapshot_fingerprint,
        inventory_id=inventory.inventory_id,
        inventory_fingerprint=inventory.inventory_fingerprint,
        binding_report_id=f"binding-report:{binding_report.fingerprint}",
        binding_report_fingerprint=binding_report.fingerprint,
        semantic_mesh_id=evidence.semantic_mesh_id,
        semantic_mesh_fingerprint=topology_report.fingerprint,
        test_inventory_id=evidence.test_inventory.inventory_id,
        test_inventory_fingerprint=evidence.test_inventory.inventory_fingerprint,
        model_test_alignment_report_id=(
            f"model-test-alignment:{model_test_alignment_report.fingerprint}"
        ),
        model_test_alignment_report_fingerprint=(
            model_test_alignment_report.fingerprint
        ),
        portable_owner_fingerprints=evidence.portable_owner_fingerprints,
        resources=evidence.resources,
        oracles=tuple(oracles),
        required_resource_ids=tuple(row.resource_id for row in evidence.resources),
        required_resource_kinds=tuple(row.kind for row in evidence.resources),
        required_oracle_ids=tuple(row.oracle_id for row in oracles),
        excluded_source_ids=tuple(
            row.path for row in inventory.file_dispositions if row.category == "production"
        ),
    )
    qualification = _qualify_blueprint_manifest(
        manifest,
        binding_report,
        implementation_inventory=inventory,
        current_observed_snapshot_fingerprint=evidence.observed_snapshot_fingerprint,
        current_semantic_mesh_fingerprint=topology_report.fingerprint,
        current_test_inventory_fingerprint=evidence.test_inventory.inventory_fingerprint,
        current_model_test_alignment_report_fingerprint=(
            model_test_alignment_report.fingerprint
        ),
        current_portable_owner_fingerprints=dict(evidence.portable_owner_fingerprints),
        current_resource_fingerprints={
            row.resource_id: row.current_artifact_fingerprint
            for row in evidence.observed_resources
            if row.status == "current"
        },
        current_oracle_fingerprints={row.oracle_id: row.artifact_fingerprint for row in oracles},
    )
    intent_provider_capabilities = tuple(
        (provider.provider_id, capability_id)
        for provider in definition.authority_providers
        for capability_id in provider.capability_ids
        if capability_id == "intent_lineage"
    )
    current_intent = replace(
        evidence.intent_inventory,
        observed_subject_revision=evidence.observed_snapshot_fingerprint,
        authority_provider_capabilities=intent_provider_capabilities,
    )
    (
        behavior_report,
        resource_inventory,
        projection,
        readiness,
        normalized_shared_objects,
        normalized_shards,
    ) = _behavior_readiness(
        inventory=inventory,
        definition=definition,
        evidence=evidence,
        manifest=manifest,
        binding_report=binding_report,
        intent_inventory=current_intent,
        model_test_alignment_report=model_test_alignment_report,
        topology_report=topology_report,
        delegated_assertion_helpers=delegated_assertion_helpers,
        delegated_helper_fingerprints=delegated_helper_fingerprints,
    )
    return ProjectBlueprintPreparation(
        definition=definition,
        evidence=evidence,
        inventory=inventory,
        implementation_inventory_audit=implementation_inventory_audit,
        binding_report=binding_report,
        manifest=manifest,
        qualification=qualification,
        model_test_alignment_report=model_test_alignment_report,
        topology_report=topology_report,
        behavior_report=behavior_report,
        resource_inventory=resource_inventory,
        intent_inventory=current_intent,
        normalized_projection=projection,
        static_readiness=readiness,
        normalized_shared_objects=normalized_shared_objects,
        normalized_shards=normalized_shards,
    )


def _provider_result_divergences(
    expected: TargetSystemProviderResult,
    supplied: TargetSystemProviderResult,
) -> tuple[str, ...]:
    """Name each exact provider field or capability binding that drifted."""

    divergences: list[str] = []
    for field_name in (
        "provider_role",
        "provider_kind",
        "provider_version",
        "target_system_id",
        "subject_revision",
        "status",
        "findings",
        "claim_boundary",
    ):
        if getattr(expected, field_name) != getattr(supplied, field_name):
            divergences.append(field_name)

    expected_capabilities = set(expected.capability_ids)
    supplied_capabilities = set(supplied.capability_ids)
    for capability_id in sorted(expected_capabilities | supplied_capabilities):
        if (capability_id in expected_capabilities) != (
            capability_id in supplied_capabilities
        ):
            divergences.append(f"capability_ids:{capability_id}")

    for field_name in ("input_fingerprints", "payload_fingerprints"):
        expected_values = dict(getattr(expected, field_name))
        supplied_values = dict(getattr(supplied, field_name))
        for value_id in sorted(set(expected_values) | set(supplied_values)):
            if expected_values.get(value_id) != supplied_values.get(value_id):
                divergences.append(f"{field_name}:{value_id}")

    expected_bindings = {
        row.capability_id: row.to_dict() for row in expected.capability_bindings
    }
    supplied_bindings = {
        row.capability_id: row.to_dict() for row in supplied.capability_bindings
    }
    for capability_id in sorted(set(expected_bindings) | set(supplied_bindings)):
        if expected_bindings.get(capability_id) != supplied_bindings.get(
            capability_id
        ):
            divergences.append(f"capability_bindings:{capability_id}")
    return tuple(divergences or ("result_fingerprint",))


def _provider_registry_divergences(
    expected: TargetSystemProviderRegistry,
    supplied: TargetSystemProviderRegistry,
) -> tuple[str, ...]:
    divergences: list[str] = []
    if expected.registry_id != supplied.registry_id:
        divergences.append("registry_id")
    expected_by_id = expected.declaration_by_id
    supplied_by_id = supplied.declaration_by_id
    for provider_id in sorted(set(expected_by_id) | set(supplied_by_id)):
        if expected_by_id.get(provider_id) != supplied_by_id.get(provider_id):
            if provider_id not in supplied_by_id:
                disposition = "missing"
            elif provider_id not in expected_by_id:
                disposition = "extra"
            else:
                disposition = "changed"
            divergences.append(f"provider_declaration:{provider_id}:{disposition}")
    return tuple(divergences or ("registry_fingerprint",))


def _qualify_project_blueprint(
    preparation: ProjectBlueprintPreparation,
    frozen_target_evidence: FrozenTargetSystemEvidence,
    *,
    scope: str = "whole",
    affected_surface_ids: Sequence[str] = (),
) -> ProjectBlueprintBundle:
    """Compile one preparation against independently frozen provider evidence."""

    descriptor = _project_target_descriptor(
        preparation.definition, preparation.evidence
    )
    layers, gaps = _project_target_layers(preparation)
    expected_frozen = freeze_project_blueprint_evidence(
        preparation,
        collect_project_blueprint_provider_results(preparation),
    )
    supplied_by_id = {
        row.provider_id: row for row in frozen_target_evidence.provider_results
    }
    expected_by_id = {
        row.provider_id: row for row in expected_frozen.provider_results
    }
    provider_currentness_gaps: list[BlueprintGapRef] = []
    for provider_id in sorted(set(expected_by_id) | set(supplied_by_id)):
        expected = expected_by_id.get(provider_id)
        supplied = supplied_by_id.get(provider_id)
        if expected is not None and supplied is not None and expected == supplied:
            continue
        if expected is None:
            divergences = ("provider_result:extra",)
        elif supplied is None:
            divergences = ("provider_result:missing",)
        else:
            divergences = _provider_result_divergences(expected, supplied)
        for divergence in divergences:
            provider_currentness_gaps.append(
                BlueprintGapRef(
                    layer="evidence_qualification",
                    object_kind="current_native_provider_result",
                    object_id=f"{provider_id}#{divergence}",
                    status=("missing" if supplied is None else "stale"),
                    expected_fingerprint=(
                        expected.fingerprint if expected else ""
                    ),
                    observed_fingerprint=(
                        supplied.fingerprint if supplied else ""
                    ),
                    evidence_ref=(supplied.fingerprint if supplied else ""),
                    message=(
                        "frozen provider result diverges from the exact current "
                        f"project-native compilation at {divergence}"
                    ),
                )
            )
    if (
        frozen_target_evidence.provider_registry.fingerprint
        != expected_frozen.provider_registry.fingerprint
    ):
        for divergence in _provider_registry_divergences(
            expected_frozen.provider_registry,
            frozen_target_evidence.provider_registry,
        ):
            provider_currentness_gaps.append(
                BlueprintGapRef(
                    layer="evidence_qualification",
                    object_kind="current_native_provider_registry",
                    object_id=(
                        f"{expected_frozen.provider_registry.registry_id}#{divergence}"
                    ),
                    status="stale",
                    expected_fingerprint=(
                        expected_frozen.provider_registry.fingerprint
                    ),
                    observed_fingerprint=(
                        frozen_target_evidence.provider_registry.fingerprint
                    ),
                    message=(
                        "frozen provider registry diverges from the exact current "
                        f"project provider declarations at {divergence}"
                    ),
                )
            )
    target_system_report = _assemble_target_system_blueprint(
        descriptor,
        frozen_target_evidence,
        downstream_layers=layers,
        downstream_gaps=(*gaps, *provider_currentness_gaps),
        required_path_quality_model_ids=(
            preparation.behavior_report.required_path_quality_model_ids
        ),
        path_quality_bindings=(
            preparation.behavior_report.path_quality_bindings
        ),
        scope=scope,
    )
    understanding_summary = project_blueprint_understanding(
        target_system_report,
        affected_surface_ids=affected_surface_ids,
    )
    bundle = ProjectBlueprintBundle(
        inventory=preparation.inventory,
        binding_report=preparation.binding_report,
        manifest=preparation.manifest,
        qualification=preparation.qualification,
        implementation_inventory_audit=(
            preparation.implementation_inventory_audit
        ),
        model_test_alignment_report=preparation.model_test_alignment_report,
        topology_report=preparation.topology_report,
        behavior_report=preparation.behavior_report,
        resource_inventory=preparation.resource_inventory,
        intent_inventory=preparation.intent_inventory,
        normalized_projection=preparation.normalized_projection,
        static_readiness=preparation.static_readiness,
        target_system_report=target_system_report,
        understanding_summary=understanding_summary,
        normalized_shared_objects=preparation.normalized_shared_objects,
        normalized_shards=preparation.normalized_shards,
        test_inventory=preparation.evidence.test_inventory,
        definition=preparation.definition,
        project_evidence=preparation.evidence,
        frozen_target_evidence=frozen_target_evidence,
    )
    affected_index, affected_objects = materialize_affected_blueprint_index(
        preparation.normalized_projection,
        target_system_id=descriptor.target_system_id,
        target_profile=target_system_report.target_profile,
        subject_revision=descriptor.subject_revision,
        descriptor_fingerprint=descriptor.fingerprint,
        target_blueprint_fingerprint=target_system_report.fingerprint,
        layer_plan_id=target_system_report.layer_plan.plan_id,
        layer_plan_fingerprint=target_system_report.layer_plan_fingerprint,
        readiness_ledger=bundle.readiness_ledger,
        shared_objects=dict(preparation.normalized_shared_objects),
        required_path_quality_model_ids=(
            target_system_report.required_path_quality_model_ids
        ),
    )
    return replace(
        bundle,
        normalized_affected_index=affected_index,
        normalized_shared_objects=affected_objects,
    )


def _project_bundle_rebinding_blockers(
    bundle: ProjectBlueprintBundle,
) -> tuple[str, ...]:
    """Recompute cross-layer project identity without reading or executing target code.

    Content hashes prove that individual children were not changed in place.  This
    second pass proves that the children still belong to one compiler-owned project
    assembly.  Model gaps remain exportable; inconsistent source relationships do
    not.
    """

    required = (
        bundle.definition,
        bundle.project_evidence,
        bundle.frozen_target_evidence,
        bundle.model_test_alignment_report,
        bundle.topology_report,
        bundle.behavior_report,
        bundle.resource_inventory,
        bundle.intent_inventory,
        bundle.normalized_projection,
        bundle.static_readiness,
        bundle.target_system_report,
        bundle.understanding_summary,
        bundle.normalized_affected_index,
        bundle.test_inventory,
    )
    if any(value is None for value in required):
        return ("invalid:canonical_projection:rederivation_inputs",)

    definition = bundle.definition
    project_evidence = bundle.project_evidence
    frozen_target_evidence = bundle.frozen_target_evidence
    model_test_alignment_report = bundle.model_test_alignment_report
    topology_report = bundle.topology_report
    behavior_report = bundle.behavior_report
    resource_inventory = bundle.resource_inventory
    intent_inventory = bundle.intent_inventory
    normalized_projection = bundle.normalized_projection
    static_readiness = bundle.static_readiness
    target_system_report = bundle.target_system_report
    understanding_summary = bundle.understanding_summary
    normalized_affected_index = bundle.normalized_affected_index
    test_inventory = bundle.test_inventory
    blockers: list[str] = []

    if definition.inventory_id != bundle.inventory.inventory_id:
        blockers.append("stale:inventory:definition_id")
    if (
        definition.boundary.to_dict() != bundle.inventory.boundary.to_dict()
        or tuple(definition.file_dispositions)
        != tuple(bundle.inventory.file_dispositions)
    ):
        blockers.append("stale:inventory:definition_boundary")
    if (
        bundle.binding_report.inventory_id != bundle.inventory.inventory_id
        or bundle.binding_report.inventory_fingerprint
        != bundle.inventory.inventory_fingerprint
    ):
        blockers.append("stale:binding_report:inventory")
    if (
        bundle.manifest.blueprint_id != definition.blueprint_id
        or bundle.manifest.inventory_id != bundle.inventory.inventory_id
        or bundle.manifest.inventory_fingerprint
        != bundle.inventory.inventory_fingerprint
        or bundle.manifest.binding_report_fingerprint
        != bundle.binding_report.fingerprint
    ):
        blockers.append("stale:manifest:project_inputs")
    if (
        project_evidence.test_inventory.inventory_fingerprint
        != test_inventory.inventory_fingerprint
    ):
        blockers.append("stale:test_inventory:project_evidence")

    base_object_ids = set(dict(normalized_projection.object_fingerprints))
    base_shared_objects = tuple(
        (object_id, payload)
        for object_id, payload in bundle.normalized_shared_objects
        if str(object_id) in base_object_ids
    )
    try:
        expected_shards = materialize_behavior_blueprint_shards(
            behavior_report,
            shared_objects=dict(base_shared_objects),
        )
        expected_projection = normalize_behavior_blueprint(
            blueprint_fingerprint=bundle.manifest.fingerprint,
            behavior_report=behavior_report,
            shared_objects=dict(base_shared_objects),
            coverage_reference_shards=expected_shards,
            source_projection=bundle.binding_report.to_dict(),
        )
        expected_bundle = _qualify_project_blueprint(
            ProjectBlueprintPreparation(
                definition=definition,
                evidence=project_evidence,
                inventory=bundle.inventory,
                implementation_inventory_audit=bundle.implementation_inventory_audit,
                binding_report=bundle.binding_report,
                manifest=bundle.manifest,
                qualification=bundle.qualification,
                model_test_alignment_report=model_test_alignment_report,
                topology_report=topology_report,
                behavior_report=behavior_report,
                resource_inventory=resource_inventory,
                intent_inventory=intent_inventory,
                normalized_projection=expected_projection,
                static_readiness=static_readiness,
                normalized_shared_objects=base_shared_objects,
                normalized_shards=expected_shards,
            ),
            frozen_target_evidence,
            scope=target_system_report.scope,
            affected_surface_ids=understanding_summary.affected_surface_ids,
        )
    except ValueError:
        return tuple(sorted({*blockers, "invalid:canonical_projection:rederivation"}))

    if expected_projection.to_dict() != normalized_projection.to_dict():
        blockers.append("stale:normalized_projection:canonical_inputs")
    if expected_shards != bundle.normalized_shards:
        blockers.append("stale:normalized_shards:behavior_report")
    if (
        expected_bundle.target_system_report is None
        or expected_bundle.target_system_report.fingerprint
        != target_system_report.fingerprint
    ):
        blockers.append("stale:target_system_report:canonical_inputs")
    if (
        expected_bundle.understanding_summary is None
        or expected_bundle.understanding_summary.fingerprint
        != understanding_summary.fingerprint
    ):
        blockers.append("stale:understanding_summary:canonical_inputs")
    if (
        expected_bundle.test_inventory is None
        or expected_bundle.test_inventory.inventory_fingerprint
        != test_inventory.inventory_fingerprint
    ):
        blockers.append("stale:test_inventory:project_evidence")
    if (
        expected_bundle.normalized_affected_index is None
        or expected_bundle.normalized_affected_index.to_dict()
        != normalized_affected_index.to_dict()
    ):
        blockers.append("stale:affected_index:canonical_inputs")
    expected_object_store_fingerprint = fingerprint_value(
        [
            {"object_id": str(object_id), "payload": payload}
            for object_id, payload in expected_bundle.normalized_shared_objects
        ]
    )
    actual_object_store_fingerprint = fingerprint_value(
        [
            {"object_id": str(object_id), "payload": payload}
            for object_id, payload in bundle.normalized_shared_objects
        ]
    )
    if expected_object_store_fingerprint != actual_object_store_fingerprint:
        blockers.append("stale:normalized_shared_objects:canonical_inputs")
    return tuple(sorted(set(blockers)))


def build_project_blueprint(
    root: str | Path,
    definition: ProjectBlueprintDefinition,
    evidence: ProjectBlueprintEvidence,
    *,
    frozen_target_evidence: FrozenTargetSystemEvidence,
    discovery_adapters: Mapping[str, DiscoveryAdapter],
    test_discovery_adapters: Mapping[str, TestDiscoveryAdapter],
    implementation_inventory: ImplementationSurfaceInventory | None = None,
    delegated_assertion_helpers: Sequence[DelegatedAssertionHelper] = (),
    delegated_helper_fingerprints: Mapping[str, str] | None = None,
    scope: str = "whole",
    affected_surface_ids: Sequence[str] = (),
) -> ProjectBlueprintBundle:
    """Prepare and qualify using caller-supplied frozen target evidence."""

    preparation = prepare_project_blueprint(
        root,
        definition,
        evidence,
        discovery_adapters=discovery_adapters,
        test_discovery_adapters=test_discovery_adapters,
        implementation_inventory=implementation_inventory,
        delegated_assertion_helpers=delegated_assertion_helpers,
        delegated_helper_fingerprints=delegated_helper_fingerprints,
    )
    return _qualify_project_blueprint(
        preparation,
        frozen_target_evidence,
        scope=scope,
        affected_surface_ids=affected_surface_ids,
    )


def _exact_object(value: Any, *, fields: set[str], context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProjectBlueprintError(f"{context} must be a JSON object")
    missing = fields - set(value)
    unexpected = set(value) - fields
    if missing or unexpected:
        raise ProjectBlueprintError(
            f"{context} fields are not exact-current: missing={sorted(missing)}, "
            f"unexpected={sorted(unexpected)}"
        )
    return value


def _semantic_from_document(value: Any) -> SemanticSpecReference:
    fields = {
        "semantic_spec_id", "owner_id", "artifact_id", "artifact_fingerprint",
        "source_id", "source_owner_id", "source_content_fingerprint",
        "covered_model_element_ids", "covered_dimensions", "semantics",
        "authority_kind", "provenance_fingerprints",
    }
    row = _exact_object(value, fields=fields, context="project semantic specification")
    semantics = _exact_object(
        row["semantics"], fields=set(str(item) for item in row["covered_dimensions"]),
        context="project semantic payload",
    )
    provenance = row["provenance_fingerprints"]
    if not isinstance(provenance, Mapping):
        raise ProjectBlueprintError("semantic provenance fingerprints must be an object")
    return SemanticSpecReference(
        semantic_spec_id=str(row["semantic_spec_id"]), owner_id=str(row["owner_id"]),
        artifact_id=str(row["artifact_id"]), artifact_fingerprint=str(row["artifact_fingerprint"]),
        source_id=str(row["source_id"]), source_owner_id=str(row["source_owner_id"]),
        source_content_fingerprint=str(row["source_content_fingerprint"]),
        covered_model_element_ids=tuple(str(item) for item in row["covered_model_element_ids"]),
        covered_dimensions=tuple(str(item) for item in row["covered_dimensions"]),
        semantics=tuple((str(key), str(item)) for key, item in semantics.items()),
        authority_kind=str(row["authority_kind"]),
        provenance_fingerprints=tuple((str(key), str(item)) for key, item in provenance.items()),
    )


def _oracle_from_document(value: Any) -> OracleReference:
    fields = {
        "oracle_id", "owner_id", "artifact_id", "artifact_fingerprint",
        "source_id", "source_owner_id", "source_content_fingerprint",
        "covered_model_element_ids", "covered_dimensions", "semantics",
    }
    row = _exact_object(value, fields=fields, context="project oracle")
    semantics = _exact_object(
        row["semantics"], fields=set(str(item) for item in row["covered_dimensions"]),
        context="project oracle payload",
    )
    return OracleReference(
        oracle_id=str(row["oracle_id"]), owner_id=str(row["owner_id"]),
        artifact_id=str(row["artifact_id"]), artifact_fingerprint=str(row["artifact_fingerprint"]),
        source_id=str(row["source_id"]), source_owner_id=str(row["source_owner_id"]),
        source_content_fingerprint=str(row["source_content_fingerprint"]),
        covered_model_element_ids=tuple(str(item) for item in row["covered_model_element_ids"]),
        covered_dimensions=tuple(str(item) for item in row["covered_dimensions"]),
        semantics=tuple((str(key), str(item)) for key, item in semantics.items()),
    )


def _portable_behavior_binding_from_document(
    value: Any,
) -> PortableBehaviorBinding:
    fields = {
        "binding_id",
        "behavior_block_id",
        "portable_model_id",
        "portable_model_fingerprint",
        "implementation_fingerprint",
        "transition_ids",
        "property_ids",
        "invariant_ids",
        "input_field_mappings",
        "output_field_mappings",
        "state_field_mappings",
        "assumption_ids",
        "guarantee_ids",
        "protected_failure_ids",
        "provider_fingerprints",
    }
    row = _exact_object(
        value,
        fields=fields,
        context="project portable behavior binding",
    )
    mapping_fields = (
        "input_field_mappings",
        "output_field_mappings",
        "state_field_mappings",
        "provider_fingerprints",
    )
    if any(not isinstance(row[field], Mapping) for field in mapping_fields):
        raise ProjectBlueprintError(
            "portable behavior binding mappings must be objects"
        )
    return PortableBehaviorBinding(
        binding_id=str(row["binding_id"]),
        behavior_block_id=str(row["behavior_block_id"]),
        portable_model_id=str(row["portable_model_id"]),
        portable_model_fingerprint=str(row["portable_model_fingerprint"]),
        implementation_fingerprint=str(row["implementation_fingerprint"]),
        transition_ids=tuple(str(item) for item in row["transition_ids"]),
        property_ids=tuple(str(item) for item in row["property_ids"]),
        invariant_ids=tuple(str(item) for item in row["invariant_ids"]),
        input_field_mappings=tuple(
            (str(key), str(item))
            for key, item in row["input_field_mappings"].items()
        ),
        output_field_mappings=tuple(
            (str(key), str(item))
            for key, item in row["output_field_mappings"].items()
        ),
        state_field_mappings=tuple(
            (str(key), str(item))
            for key, item in row["state_field_mappings"].items()
        ),
        assumption_ids=tuple(str(item) for item in row["assumption_ids"]),
        guarantee_ids=tuple(str(item) for item in row["guarantee_ids"]),
        protected_failure_ids=tuple(
            str(item) for item in row["protected_failure_ids"]
        ),
        provider_fingerprints=tuple(
            (str(key), str(item))
            for key, item in row["provider_fingerprints"].items()
        ),
    )


def _behavior_case_from_document(value: Any) -> BehaviorCaseContract:
    fields = {
        "case_id", "behavior_block_id", "case_kind", "input_values",
        "initial_state", "expected_output", "expected_state", "expected_effects",
        "expected_errors", "oracle_id", "case_evidence_id",
        "case_evidence_fingerprint", "value_mode", "protected_failure_ids",
        "parameter_case_id", "source_case_id",
    }
    row = _exact_object(value, fields=fields, context="project behavior case")
    mapping_names = (
        "input_values", "initial_state", "expected_output", "expected_state"
    )
    if any(not isinstance(row[name], Mapping) for name in mapping_names):
        raise ProjectBlueprintError("project behavior case value fields must be objects")
    return BehaviorCaseContract(
        case_id=str(row["case_id"]),
        behavior_block_id=str(row["behavior_block_id"]),
        case_kind=str(row["case_kind"]),
        input_values=tuple((str(key), str(item)) for key, item in row["input_values"].items()),
        initial_state=tuple((str(key), str(item)) for key, item in row["initial_state"].items()),
        expected_output=tuple((str(key), str(item)) for key, item in row["expected_output"].items()),
        expected_state=tuple((str(key), str(item)) for key, item in row["expected_state"].items()),
        expected_effects=tuple(str(item) for item in row["expected_effects"]),
        expected_errors=tuple(str(item) for item in row["expected_errors"]),
        oracle_id=str(row["oracle_id"]),
        case_evidence_id=str(row["case_evidence_id"]),
        case_evidence_fingerprint=str(row["case_evidence_fingerprint"]),
        value_mode=str(row["value_mode"]),
        protected_failure_ids=tuple(str(item) for item in row["protected_failure_ids"]),
        parameter_case_id=str(row["parameter_case_id"]),
        source_case_id=str(row["source_case_id"]),
    )


def _resource_from_document(value: Any) -> BlueprintResourceReference:
    fields = {
        "resource_id", "kind", "owner_id", "artifact_id", "purpose",
        "lifecycle_role", "disposition", "artifact_fingerprint", "rationale",
        "consuming_behavior_ids", "consuming_model_ids", "semantics",
    }
    row = _exact_object(value, fields=fields, context="project resource")
    semantics = row["semantics"]
    if not isinstance(semantics, Mapping):
        raise ProjectBlueprintError("project resource semantics must be an object")
    return BlueprintResourceReference(
        resource_id=str(row["resource_id"]), kind=str(row["kind"]),
        owner_id=str(row["owner_id"]), artifact_id=str(row["artifact_id"]),
        purpose=str(row["purpose"]), lifecycle_role=str(row["lifecycle_role"]),
        consuming_behavior_ids=tuple(
            str(item) for item in row["consuming_behavior_ids"]
        ),
        consuming_model_ids=tuple(
            str(item) for item in row["consuming_model_ids"]
        ),
        disposition=str(row["disposition"]),
        artifact_fingerprint=(None if row["artifact_fingerprint"] is None else str(row["artifact_fingerprint"])),
        rationale=None if row["rationale"] is None else str(row["rationale"]),
        semantics=tuple((str(key), str(item)) for key, item in semantics.items()),
    )


def _observed_resource_from_document(value: Any) -> ObservedResourceMember:
    fields = {
        "resource_id",
        "kind",
        "owner_id",
        "artifact_id",
        "subject_revision",
        "current_artifact_fingerprint",
        "provider_id",
        "capability_id",
        "payload_id",
        "status",
    }
    row = _exact_object(
        value,
        fields=fields,
        context="observed project resource",
    )
    return ObservedResourceMember(
        resource_id=str(row["resource_id"]),
        kind=str(row["kind"]),
        owner_id=str(row["owner_id"]),
        artifact_id=str(row["artifact_id"]),
        subject_revision=str(row["subject_revision"]),
        current_artifact_fingerprint=str(
            row["current_artifact_fingerprint"]
        ),
        provider_id=str(row["provider_id"]),
        capability_id=str(row["capability_id"]),
        payload_id=str(row["payload_id"]),
        status=str(row["status"]),
    )


def _evidence_artifact_from_document(value: Any) -> ProjectEvidenceArtifact:
    fields = {"evidence_id", "artifact_path", "artifact_fingerprint", "kind"}
    row = _exact_object(value, fields=fields, context="project evidence artifact")
    return ProjectEvidenceArtifact(
        evidence_id=str(row["evidence_id"]),
        artifact_path=str(row["artifact_path"]),
        artifact_fingerprint=str(row["artifact_fingerprint"]),
        kind=str(row["kind"]),
    )


def _topology_node_from_document(value: Any) -> BlueprintTopologyNode:
    fields = {
        "node_id", "disposition", "structural_role", "purpose",
        "structural_parent_id", "cross_boundary_parent_ids",
        "implementation_surface_ids", "input_ports", "output_ports",
        "state_owned", "side_effects_owned",
    }
    row = _exact_object(value, fields=fields, context="blueprint topology node")
    def ports(name: str) -> tuple[BlueprintTopologyPort, ...]:
        values: list[BlueprintTopologyPort] = []
        for item in row[name]:
            port = _exact_object(
                item,
                fields={"port_id", "schema_id", "schema_fingerprint", "required"},
                context="blueprint topology port",
            )
            values.append(
                BlueprintTopologyPort(
                    port_id=str(port["port_id"]),
                    schema_id=str(port["schema_id"]),
                    schema_fingerprint=str(port["schema_fingerprint"]),
                    required=bool(port["required"]),
                )
            )
        return tuple(values)
    return BlueprintTopologyNode(
        node_id=str(row["node_id"]),
        disposition=str(row["disposition"]),
        structural_role=str(row["structural_role"]),
        purpose=str(row["purpose"]),
        structural_parent_id=str(row["structural_parent_id"]),
        cross_boundary_parent_ids=tuple(
            str(item) for item in row["cross_boundary_parent_ids"]
        ),
        implementation_surface_ids=tuple(
            str(item) for item in row["implementation_surface_ids"]
        ),
        input_ports=ports("input_ports"),
        output_ports=ports("output_ports"),
        state_owned=tuple(str(item) for item in row["state_owned"]),
        side_effects_owned=tuple(str(item) for item in row["side_effects_owned"]),
    )


def _portable_catalog_from_document(value: Any) -> PortableModelMemberCatalog:
    fields = {
        "portable_model_id", "portable_model_fingerprint", "transition_ids",
        "property_ids", "invariant_ids", "input_field_ids", "output_field_ids",
        "state_field_ids", "assumption_ids", "guarantee_ids",
        "protected_failure_ids",
    }
    row = _exact_object(value, fields=fields, context="portable member catalog")
    return PortableModelMemberCatalog(
        portable_model_id=str(row["portable_model_id"]),
        portable_model_fingerprint=str(row["portable_model_fingerprint"]),
        transition_ids=tuple(str(item) for item in row["transition_ids"]),
        property_ids=tuple(str(item) for item in row["property_ids"]),
        invariant_ids=tuple(str(item) for item in row["invariant_ids"]),
        input_field_ids=tuple(str(item) for item in row["input_field_ids"]),
        output_field_ids=tuple(str(item) for item in row["output_field_ids"]),
        state_field_ids=tuple(str(item) for item in row["state_field_ids"]),
        assumption_ids=tuple(str(item) for item in row["assumption_ids"]),
        guarantee_ids=tuple(str(item) for item in row["guarantee_ids"]),
        protected_failure_ids=tuple(
            str(item) for item in row["protected_failure_ids"]
        ),
    )


def _topology_relation_from_document(value: Any) -> BlueprintTopologyRelation:
    fields = {
        "relation_id", "producer_id", "consumer_id", "relation_kind",
        "interface_mappings", "evidence_fingerprint", "rationale",
        "consumed_child_evidence_id", "consumed_runtime_path_evidence_ids",
        "progress_contract",
    }
    row = _exact_object(value, fields=fields, context="blueprint topology relation")
    mappings: list[BlueprintTopologyPortMapping] = []
    for raw_mapping in row["interface_mappings"]:
        mapping = _exact_object(
            raw_mapping,
            fields={
                "producer_output_id", "consumer_input_id",
                "refinement_id", "refinement_fingerprint",
            },
            context="blueprint topology interface mapping",
        )
        mappings.append(
            BlueprintTopologyPortMapping(
                producer_output_id=str(mapping["producer_output_id"]),
                consumer_input_id=str(mapping["consumer_input_id"]),
                refinement_id=str(mapping["refinement_id"]),
                refinement_fingerprint=str(mapping["refinement_fingerprint"]),
            )
        )
    progress = row["progress_contract"]
    progress_contract = None
    if progress is not None:
        progress = _exact_object(
            progress,
            fields={
                "contract_id", "contract_kind", "evidence_fingerprint",
                "finite_bound", "rationale",
            },
            context="blueprint topology progress contract",
        )
        progress_contract = BlueprintTopologyProgressContract(
            contract_id=str(progress["contract_id"]),
            contract_kind=str(progress["contract_kind"]),
            evidence_fingerprint=str(progress["evidence_fingerprint"]),
            finite_bound=int(progress["finite_bound"]),
            rationale=str(progress["rationale"]),
        )
    return BlueprintTopologyRelation(
        relation_id=str(row["relation_id"]),
        producer_id=str(row["producer_id"]),
        consumer_id=str(row["consumer_id"]),
        relation_kind=str(row["relation_kind"]),
        interface_mappings=tuple(mappings),
        evidence_fingerprint=str(row["evidence_fingerprint"]),
        rationale=str(row["rationale"]),
        consumed_child_evidence_id=str(row["consumed_child_evidence_id"]),
        consumed_runtime_path_evidence_ids=tuple(
            str(item) for item in row["consumed_runtime_path_evidence_ids"]
        ),
        progress_contract=progress_contract,
    )


def _child_model_from_document(value: Any) -> ChildModelEvidence:
    fields = {
        "model_id", "model_fingerprint", "evidence_id", "risk_boundary", "functions_owned",
        "inputs_accepted", "outputs_emitted", "state_owned",
        "side_effects_owned", "functional_areas", "invariants_owned",
        "contracts_in", "contracts_out", "depends_on", "risk_classes",
        "validation_evidence", "runtime_path_evidence_ids", "evidence_tier",
        "evidence_current", "skipped_checks", "not_run_checks",
        "estimated_state_count", "observed_state_count", "budgeted_incomplete",
        "unrelated_functional_areas", "structurally_cohesive", "is_legacy",
        "has_compatibility_contract", "overlaps_existing_model",
    }
    row = _exact_object(value, fields=fields, context="blueprint child model evidence")
    tuple_fields = {
        "functions_owned", "inputs_accepted", "outputs_emitted", "state_owned",
        "side_effects_owned", "functional_areas", "invariants_owned",
        "contracts_in", "contracts_out", "depends_on", "risk_classes",
        "validation_evidence", "runtime_path_evidence_ids", "skipped_checks",
        "not_run_checks",
    }
    kwargs = {name: tuple(str(item) for item in row[name]) for name in tuple_fields}
    return ChildModelEvidence(
        model_id=str(row["model_id"]),
        model_fingerprint=str(row["model_fingerprint"]),
        evidence_id=str(row["evidence_id"]),
        risk_boundary=str(row["risk_boundary"]),
        evidence_tier=str(row["evidence_tier"]),
        evidence_current=bool(row["evidence_current"]),
        estimated_state_count=row["estimated_state_count"],
        observed_state_count=row["observed_state_count"],
        budgeted_incomplete=bool(row["budgeted_incomplete"]),
        unrelated_functional_areas=bool(row["unrelated_functional_areas"]),
        structurally_cohesive=bool(row["structurally_cohesive"]),
        is_legacy=bool(row["is_legacy"]),
        has_compatibility_contract=bool(row["has_compatibility_contract"]),
        overlaps_existing_model=str(row["overlaps_existing_model"]),
        **kwargs,
    )


def _reattachment_from_document(value: Any) -> ChildReattachmentContract:
    fields = {
        "child_model_id", "consumed_evidence_id",
        "consumed_path_quality_result_fingerprint",
        "consumed_runtime_path_evidence_ids", "expected_inputs",
        "expected_outputs", "expected_state_owned", "expected_side_effects_owned",
        "expected_contracts_out", "allow_extra_inputs", "allow_extra_outputs",
        "rationale",
    }
    row = _exact_object(
        value, fields=fields, context="blueprint child reattachment contract"
    )
    return ChildReattachmentContract(
        child_model_id=str(row["child_model_id"]),
        consumed_evidence_id=str(row["consumed_evidence_id"]),
        consumed_path_quality_result_fingerprint=str(
            row["consumed_path_quality_result_fingerprint"]
        ),
        consumed_runtime_path_evidence_ids=tuple(
            str(item) for item in row["consumed_runtime_path_evidence_ids"]
        ),
        expected_inputs=tuple(str(item) for item in row["expected_inputs"]),
        expected_outputs=tuple(str(item) for item in row["expected_outputs"]),
        expected_state_owned=tuple(str(item) for item in row["expected_state_owned"]),
        expected_side_effects_owned=tuple(
            str(item) for item in row["expected_side_effects_owned"]
        ),
        expected_contracts_out=tuple(
            str(item) for item in row["expected_contracts_out"]
        ),
        allow_extra_inputs=bool(row["allow_extra_inputs"]),
        allow_extra_outputs=bool(row["allow_extra_outputs"]),
        rationale=str(row["rationale"]),
    )


def _intent_inventory_from_document(value: Any) -> ProjectIntentInventory:
    if not isinstance(value, Mapping):
        raise ProjectBlueprintError("project intent inventory must be an object")
    if value.get("schema_version") != INTENT_INVENTORY_SCHEMA:
        raise ProjectBlueprintError("project intent inventory schema is not current")
    fields = {
        "schema_version",
        "inventory_id",
        "subject_revision",
        "observed_subject_revision",
        "canonical_review_fingerprint",
        "contributions",
        "source_authorities",
        "findings",
        "authority_provider_capabilities",
        "required_model_target_ids",
        "no_declared_intent",
    }
    row = _exact_object(
        value,
        fields=fields,
        context="project intent inventory",
    )
    for array_name in (
        "contributions",
        "source_authorities",
        "findings",
        "authority_provider_capabilities",
        "required_model_target_ids",
    ):
        if not isinstance(row[array_name], list):
            raise ProjectBlueprintError(
                f"project intent inventory {array_name} must be an array"
            )

    contribution_fields = {
        "contribution_id",
        "source_kind",
        "source_id",
        "source_owner_id",
        "source_fingerprint",
        "expectation_id",
        "expectation_fingerprint",
        "disposition",
        "target_ids",
        "rationale",
    }
    contributions: list[ProjectIntentContribution] = []
    for value in row["contributions"]:
        item = _exact_object(
            value,
            fields=contribution_fields,
            context="project intent contribution",
        )
        contributions.append(
            ProjectIntentContribution(
                contribution_id=str(item["contribution_id"]),
                source_kind=str(item["source_kind"]),
                source_id=str(item["source_id"]),
                source_owner_id=str(item["source_owner_id"]),
                source_fingerprint=str(item["source_fingerprint"]),
                expectation_id=str(item["expectation_id"]),
                expectation_fingerprint=str(item["expectation_fingerprint"]),
                disposition=str(item["disposition"]),
                target_ids=tuple(str(target) for target in item["target_ids"]),
                rationale=str(item["rationale"]),
            )
        )

    authority_fields = {
        "source_kind",
        "source_id",
        "source_owner_id",
        "subject_revision",
        "current_source_fingerprint",
        "expectation_id",
        "current_expectation_fingerprint",
        "target_ids",
        "provider_id",
        "capability_id",
        "payload_id",
        "status",
    }
    authorities: list[IntentSourceAuthority] = []
    for value in row["source_authorities"]:
        item = _exact_object(
            value,
            fields=authority_fields,
            context="project intent source authority",
        )
        authorities.append(
            IntentSourceAuthority(
                source_kind=str(item["source_kind"]),
                source_id=str(item["source_id"]),
                source_owner_id=str(item["source_owner_id"]),
                subject_revision=str(item["subject_revision"]),
                current_source_fingerprint=str(
                    item["current_source_fingerprint"]
                ),
                expectation_id=str(item["expectation_id"]),
                current_expectation_fingerprint=str(
                    item["current_expectation_fingerprint"]
                ),
                target_ids=tuple(str(target) for target in item["target_ids"]),
                provider_id=str(item["provider_id"]),
                capability_id=str(item["capability_id"]),
                payload_id=str(item["payload_id"]),
                status=str(item["status"]),
            )
        )

    capability_pairs: list[tuple[str, str]] = []
    for value in row["authority_provider_capabilities"]:
        item = _exact_object(
            value,
            fields={"provider_id", "capability_id"},
            context="project intent provider capability",
        )
        capability_pairs.append(
            (str(item["provider_id"]), str(item["capability_id"]))
        )

    no_declared_intent = None
    if row["no_declared_intent"] is not None:
        item = _exact_object(
            row["no_declared_intent"],
            fields={
                "rationale_id",
                "subject_revision",
                "provider_id",
                "capability_id",
                "payload_id",
                "evidence_fingerprints",
                "rationale",
                "status",
            },
            context="project no-declared-intent rationale",
        )
        evidence_fingerprints = item["evidence_fingerprints"]
        if not isinstance(evidence_fingerprints, Mapping):
            raise ProjectBlueprintError(
                "project no-declared-intent evidence fingerprints must be an object"
            )
        no_declared_intent = NoDeclaredIntentRationale(
            rationale_id=str(item["rationale_id"]),
            subject_revision=str(item["subject_revision"]),
            provider_id=str(item["provider_id"]),
            capability_id=str(item["capability_id"]),
            payload_id=str(item["payload_id"]),
            evidence_fingerprints=tuple(
                (str(key), str(fingerprint))
                for key, fingerprint in evidence_fingerprints.items()
            ),
            rationale=str(item["rationale"]),
            status=str(item["status"]),
        )

    inventory = ProjectIntentInventory(
        inventory_id=str(row["inventory_id"]),
        subject_revision=str(row["subject_revision"]),
        observed_subject_revision=str(row["observed_subject_revision"]),
        contributions=tuple(contributions),
        source_authorities=tuple(authorities),
        authority_provider_capabilities=tuple(capability_pairs),
        required_model_target_ids=tuple(
            str(target_id) for target_id in row["required_model_target_ids"]
        ),
        no_declared_intent=no_declared_intent,
    )
    if row["canonical_review_fingerprint"] != inventory.canonical_review_fingerprint:
        raise ProjectBlueprintError(
            "project intent inventory canonical review fingerprint mismatch"
        )
    if row["findings"] != [finding.to_dict() for finding in inventory.findings]:
        raise ProjectBlueprintError(
            "project intent inventory findings do not match current derivation"
        )
    return inventory


def load_project_blueprint_document(
    path: str | Path,
) -> tuple[
    ProjectBlueprintDefinition,
    ProjectBlueprintEvidence,
    FrozenTargetSystemEvidence,
]:
    """Load one strict current project-blueprint JSON document for CLI adapters."""

    document_path = Path(path)
    try:
        value = json.loads(document_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectBlueprintError(f"cannot load {document_path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProjectBlueprintError("project blueprint document must be a JSON object")
    if value.get("schema_version") != PROJECT_BLUEPRINT_DEFINITION_SCHEMA:
        raise ProjectBlueprintError("project blueprint document schema is not current")
    fields = {
        "schema_version", "target_kind", "target_profile", "observation_providers",
        "authority_providers", "blueprint_id", "inventory_id", "boundary",
        "file_dispositions", "surface_dispositions", "supporting_owners",
        "dynamic_allowances", "dynamic_selector_contracts", "owners", "evidence", "frozen_target_evidence",
        "claim_boundary",
    }
    row = _exact_object(value, fields=fields, context="project blueprint document")
    owners: list[ProjectBlueprintOwner] = []
    owner_fields = {
        "model_element_id", "owner_id", "owner_contract_id", "model_fingerprint",
        "owner_contract_fingerprint", "portable_model_id",
        "portable_model_fingerprint", "portable_transition_ids",
        "portable_property_ids", "portable_invariant_ids",
        "portable_input_field_mappings", "portable_output_field_mappings",
        "portable_state_field_mappings", "portable_assumption_ids",
        "portable_guarantee_ids", "protected_failure_ids",
        "portable_behavior_bindings",
        "implementation_surface_ids", "primary_surface_id",
        "semantic_specs", "oracles", "test_evidence_fingerprints",
        "native_evidence_fingerprints", "behavior_accepted",
        "behavior_acceptance_evidence_fingerprints",
        "behavior_case_contracts", "checker_design_fingerprints",
    }
    for raw_owner in row["owners"]:
        owner = _exact_object(raw_owner, fields=owner_fields, context="project blueprint owner")
        tests = owner["test_evidence_fingerprints"]
        if not isinstance(tests, Mapping):
            raise ProjectBlueprintError("test evidence fingerprints must be an object")
        native_evidence = owner["native_evidence_fingerprints"]
        if not isinstance(native_evidence, Mapping):
            raise ProjectBlueprintError("native evidence fingerprints must be an object")
        checker_designs = owner["checker_design_fingerprints"]
        if not isinstance(checker_designs, Mapping):
            raise ProjectBlueprintError("checker design fingerprints must be an object")
        portable_mapping_names = (
            "portable_input_field_mappings",
            "portable_output_field_mappings",
            "portable_state_field_mappings",
            "behavior_acceptance_evidence_fingerprints",
        )
        if any(not isinstance(owner[name], Mapping) for name in portable_mapping_names):
            raise ProjectBlueprintError(
                "portable field mappings and acceptance evidence must be objects"
            )
        owners.append(ProjectBlueprintOwner(
            model_element_id=str(owner["model_element_id"]), owner_id=str(owner["owner_id"]),
            owner_contract_id=str(owner["owner_contract_id"]),
            model_fingerprint=str(owner["model_fingerprint"]),
            owner_contract_fingerprint=str(owner["owner_contract_fingerprint"]),
            portable_model_id=str(owner["portable_model_id"]),
            portable_model_fingerprint=str(owner["portable_model_fingerprint"]),
            portable_transition_ids=tuple(str(item) for item in owner["portable_transition_ids"]),
            portable_property_ids=tuple(str(item) for item in owner["portable_property_ids"]),
            portable_invariant_ids=tuple(str(item) for item in owner["portable_invariant_ids"]),
            portable_input_field_mappings=tuple(
                (str(key), str(item)) for key, item in owner["portable_input_field_mappings"].items()
            ),
            portable_output_field_mappings=tuple(
                (str(key), str(item)) for key, item in owner["portable_output_field_mappings"].items()
            ),
            portable_state_field_mappings=tuple(
                (str(key), str(item)) for key, item in owner["portable_state_field_mappings"].items()
            ),
            portable_assumption_ids=tuple(str(item) for item in owner["portable_assumption_ids"]),
            portable_guarantee_ids=tuple(str(item) for item in owner["portable_guarantee_ids"]),
            protected_failure_ids=tuple(
                str(item) for item in owner["protected_failure_ids"]
            ),
            portable_behavior_bindings=tuple(
                _portable_behavior_binding_from_document(item)
                for item in owner["portable_behavior_bindings"]
            ),
            implementation_surface_ids=tuple(str(item) for item in owner["implementation_surface_ids"]),
            primary_surface_id=str(owner["primary_surface_id"]),
            semantic_specs=tuple(_semantic_from_document(item) for item in owner["semantic_specs"]),
            oracles=tuple(_oracle_from_document(item) for item in owner["oracles"]),
            test_evidence_fingerprints=tuple((str(key), str(item)) for key, item in tests.items()),
            native_evidence_fingerprints=tuple(
                (str(key), str(item)) for key, item in native_evidence.items()
            ),
            behavior_accepted=bool(owner["behavior_accepted"]),
            behavior_acceptance_evidence_fingerprints=tuple(
                (str(key), str(item))
                for key, item in owner["behavior_acceptance_evidence_fingerprints"].items()
            ),
            behavior_case_contracts=tuple(
                _behavior_case_from_document(item)
                for item in owner["behavior_case_contracts"]
            ),
            checker_design_fingerprints=tuple(
                (str(key), str(item)) for key, item in checker_designs.items()
            ),
        ))
    for mapping_name in (
        "surface_dispositions",
        "supporting_owners",
        "dynamic_allowances",
    ):
        if not isinstance(row[mapping_name], Mapping):
            raise ProjectBlueprintError(f"{mapping_name} must be an object")
    if not isinstance(row["dynamic_selector_contracts"], list):
        raise ProjectBlueprintError(
            "dynamic_selector_contracts must be a list"
        )
    definition = ProjectBlueprintDefinition(
        blueprint_id=str(row["blueprint_id"]), inventory_id=str(row["inventory_id"]),
        boundary=SoftwareBoundary.from_dict(row["boundary"]),
        file_dispositions=tuple(ImplementationFileDisposition.from_dict(item) for item in row["file_dispositions"]),
        surface_dispositions=tuple((str(key), str(item)) for key, item in row["surface_dispositions"].items()),
        supporting_owners=tuple((str(key), str(item)) for key, item in row["supporting_owners"].items()),
        dynamic_allowances=tuple((str(key), tuple(str(value) for value in item)) for key, item in row["dynamic_allowances"].items()),
        dynamic_selector_contracts=tuple(
            DynamicSelectorContract.from_dict(item)
            for item in row["dynamic_selector_contracts"]
        ),
        owners=tuple(owners),
        claim_boundary=str(row["claim_boundary"]),
        target_kind=str(row["target_kind"]),
        target_profile=str(row["target_profile"]),
        observation_providers=tuple(
            TargetSystemProviderDeclaration.from_dict(item)
            for item in row["observation_providers"]
        ),
        authority_providers=tuple(
            TargetSystemProviderDeclaration.from_dict(item)
            for item in row["authority_providers"]
        ),
    )
    evidence_fields = {
        "observed_snapshot_id", "observed_snapshot_fingerprint", "semantic_mesh_id",
        "portable_owner_fingerprints",
        "portable_member_catalogs", "resources", "observed_resources",
        "intent_inventory", "test_inventory", "topology_nodes", "topology_relations",
        "child_models", "reattachment_contracts",
        "current_relation_evidence_fingerprints",
        "current_refinement_fingerprints",
        "current_progress_evidence_fingerprints",
        "current_child_evidence_fingerprints",
        "native_evidence_artifacts",
        "path_quality_bindings",
    }
    raw_evidence = _exact_object(row["evidence"], fields=evidence_fields, context="project blueprint evidence")
    portable = raw_evidence["portable_owner_fingerprints"]
    if not isinstance(portable, Mapping):
        raise ProjectBlueprintError("portable owner fingerprints must be an object")
    topology_fingerprint_fields = (
        "current_relation_evidence_fingerprints",
        "current_refinement_fingerprints",
        "current_progress_evidence_fingerprints",
        "current_child_evidence_fingerprints",
    )
    if any(not isinstance(raw_evidence[name], Mapping) for name in topology_fingerprint_fields):
        raise ProjectBlueprintError("current topology fingerprints must be objects")
    evidence = ProjectBlueprintEvidence(
        observed_snapshot_id=str(raw_evidence["observed_snapshot_id"]),
        observed_snapshot_fingerprint=str(raw_evidence["observed_snapshot_fingerprint"]),
        semantic_mesh_id=str(raw_evidence["semantic_mesh_id"]),
        portable_owner_fingerprints=tuple((str(key), str(item)) for key, item in portable.items()),
        portable_member_catalogs=tuple(
            _portable_catalog_from_document(item)
            for item in raw_evidence["portable_member_catalogs"]
        ),
        resources=tuple(_resource_from_document(item) for item in raw_evidence["resources"]),
        observed_resources=tuple(
            _observed_resource_from_document(item)
            for item in raw_evidence["observed_resources"]
        ),
        intent_inventory=_intent_inventory_from_document(
            raw_evidence["intent_inventory"]
        ),
        test_inventory=ProjectTestInventory.from_dict(raw_evidence["test_inventory"]),
        topology_nodes=tuple(
            _topology_node_from_document(item)
            for item in raw_evidence["topology_nodes"]
        ),
        topology_relations=tuple(
            _topology_relation_from_document(item)
            for item in raw_evidence["topology_relations"]
        ),
        child_models=tuple(
            _child_model_from_document(item)
            for item in raw_evidence["child_models"]
        ),
        reattachment_contracts=tuple(
            _reattachment_from_document(item)
            for item in raw_evidence["reattachment_contracts"]
        ),
        current_relation_evidence_fingerprints=tuple(
            (str(key), str(item))
            for key, item in raw_evidence[
                "current_relation_evidence_fingerprints"
            ].items()
        ),
        current_refinement_fingerprints=tuple(
            (str(key), str(item))
            for key, item in raw_evidence["current_refinement_fingerprints"].items()
        ),
        current_progress_evidence_fingerprints=tuple(
            (str(key), str(item))
            for key, item in raw_evidence[
                "current_progress_evidence_fingerprints"
            ].items()
        ),
        current_child_evidence_fingerprints=tuple(
            (str(key), str(item))
            for key, item in raw_evidence[
                "current_child_evidence_fingerprints"
            ].items()
        ),
        native_evidence_artifacts=tuple(
            _evidence_artifact_from_document(item)
            for item in raw_evidence["native_evidence_artifacts"]
        ),
        path_quality_bindings=tuple(
            ModelPathQualityBlueprintBinding.from_dict(item)
            for item in raw_evidence["path_quality_bindings"]
        ),
    )
    frozen_target_evidence = FrozenTargetSystemEvidence.from_dict(
        row["frozen_target_evidence"]
    )
    return definition, evidence, frozen_target_evidence


__all__ = [
    "PROJECT_BLUEPRINT_DEFINITION_SCHEMA",
    "ProjectBlueprintBundle",
    "ProjectBlueprintDefinition",
    "ProjectBlueprintError",
    "ProjectBlueprintEvidence",
    "ProjectEvidenceArtifact",
    "PortableModelMemberCatalog",
    "ProjectBlueprintOwner",
    "build_project_blueprint",
    "build_project_resource_inventory",
    "collect_project_blueprint_provider_results",
    "derive_project_blueprint_readiness_ledger",
    "freeze_project_blueprint_evidence",
    "load_project_blueprint_document",
    "prepare_project_blueprint",
    "project_blueprint_document",
    "project_surface_dimensions",
]
