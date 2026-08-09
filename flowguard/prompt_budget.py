"""Deterministic first-read prompt bundle telemetry."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any


PROMPT_BUNDLE_SCHEMA = "flowguard.prompt_bundle_manifest.v2"


_REFERENCE_PATH_RE = re.compile(r"`(references/[^`]+)`")
_CONDITIONAL_CUES = (
    "after ",
    "when ",
    "only when ",
    "if ",
    "once ",
)


@dataclass(frozen=True)
class PromptReferenceEdge:
    path: str
    trigger: str
    guaranteed: bool
    stage: str = "triggered_expansion"
    owner: str = ""
    claim: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "trigger": self.trigger,
            "guaranteed": self.guaranteed,
            "stage": self.stage,
            "mandatory": self.guaranteed,
            "owner": self.owner,
            "claim": self.claim,
        }


@dataclass(frozen=True)
class PromptComponentMetric:
    path: str
    utf8_bytes: int
    characters: int
    lines: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "utf8_bytes": self.utf8_bytes,
            "characters": self.characters,
            "lines": self.lines,
        }


@dataclass(frozen=True)
class PromptStageMetric:
    stage: str
    components: tuple[PromptComponentMetric, ...]
    max_utf8_bytes: int = 0
    min_headroom_ratio: float = 0.10
    enforced: bool = False

    @property
    def utf8_bytes(self) -> int:
        return sum(item.utf8_bytes for item in self.components)

    @property
    def headroom_bytes(self) -> int:
        return self.max_utf8_bytes - self.utf8_bytes

    @property
    def headroom_ratio(self) -> float:
        if self.max_utf8_bytes <= 0:
            return 0.0
        return self.headroom_bytes / self.max_utf8_bytes

    @property
    def ok(self) -> bool:
        return (
            not self.enforced
            or (
                self.headroom_bytes >= 0
                and self.headroom_ratio >= self.min_headroom_ratio
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "utf8_bytes": self.utf8_bytes,
            "source_size_token_proxy": (self.utf8_bytes + 2) // 3,
            "max_utf8_bytes": self.max_utf8_bytes,
            "headroom_bytes": self.headroom_bytes,
            "headroom_ratio": self.headroom_ratio,
            "min_headroom_ratio": self.min_headroom_ratio,
            "enforced": self.enforced,
            "ok": self.ok,
            "components": [item.to_dict() for item in self.components],
        }


@dataclass(frozen=True)
class PromptBundleMetric:
    route_id: str
    components: tuple[PromptComponentMetric, ...]
    max_utf8_bytes: int
    min_headroom_ratio: float
    conditional_edges: tuple[PromptReferenceEdge, ...] = ()
    missing_paths: tuple[str, ...] = ()
    stages: tuple[PromptStageMetric, ...] = ()
    persistent_context: PromptStageMetric | None = None

    @property
    def utf8_bytes(self) -> int:
        return sum(item.utf8_bytes for item in self.components)

    @property
    def characters(self) -> int:
        return sum(item.characters for item in self.components)

    @property
    def lines(self) -> int:
        return sum(item.lines for item in self.components)

    @property
    def source_size_token_proxy(self) -> int:
        return (self.utf8_bytes + 2) // 3

    @property
    def headroom_bytes(self) -> int:
        return self.max_utf8_bytes - self.utf8_bytes

    @property
    def headroom_ratio(self) -> float:
        if self.max_utf8_bytes <= 0:
            return 0.0
        return self.headroom_bytes / self.max_utf8_bytes

    @property
    def headroom_ok(self) -> bool:
        return self.headroom_bytes >= 0 and self.headroom_ratio >= self.min_headroom_ratio

    @property
    def ok(self) -> bool:
        return not self.missing_paths and self.headroom_ok and all(
            stage.ok for stage in self.stages
        ) and (
            self.persistent_context is None or self.persistent_context.ok
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "status": "pass" if self.ok else "blocked",
            "ok": self.ok,
            "utf8_bytes": self.utf8_bytes,
            "characters": self.characters,
            "lines": self.lines,
            "source_size_token_proxy": self.source_size_token_proxy,
            "source_size_proxy_formula": "ceil(utf8_bytes/3)",
            "max_utf8_bytes": self.max_utf8_bytes,
            "max_source_size_token_proxy": (
                self.max_utf8_bytes + 2
            )
            // 3,
            "headroom_bytes": self.headroom_bytes,
            "headroom_ratio": self.headroom_ratio,
            "min_headroom_ratio": self.min_headroom_ratio,
            "headroom_ok": self.headroom_ok,
            "conditional_edges": [edge.to_dict() for edge in self.conditional_edges],
            "stages": [stage.to_dict() for stage in self.stages],
            "persistent_context": (
                self.persistent_context.to_dict()
                if self.persistent_context is not None
                else None
            ),
            "missing_paths": list(self.missing_paths),
            "components": [item.to_dict() for item in self.components],
        }


def _local_material_routing(text: str) -> tuple[str, ...]:
    lines = text.splitlines()
    try:
        start = lines.index("## Local Material Routing") + 1
    except ValueError:
        return ()
    routed: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if line.strip():
            routed.append(line.strip())
    return tuple(routed)


def _reference_edges(
    skill_path: Path,
    root_path: Path,
    material_by_path: dict[str, dict[str, Any]] | None = None,
) -> tuple[PromptReferenceEdge, ...]:
    text = skill_path.read_text(encoding="utf-8")
    edges: list[PromptReferenceEdge] = []
    seen: set[tuple[str, bool, str]] = set()
    for line in _local_material_routing(text):
        lowered = line.lower()
        guaranteed = not any(cue in lowered for cue in _CONDITIONAL_CUES)
        for reference in _REFERENCE_PATH_RE.findall(line):
            absolute = (skill_path.parent / reference).resolve()
            try:
                relative = absolute.relative_to(root_path).as_posix()
            except ValueError as exc:
                raise ValueError(f"prompt reference escapes root: {reference}") from exc
            edge_guaranteed = guaranteed
            metadata = dict((material_by_path or {}).get(relative, {}))
            stage = str(
                metadata.get(
                    "stage",
                    "preselection" if edge_guaranteed else "triggered_expansion",
                )
            )
            edge_guaranteed = bool(metadata.get("mandatory", edge_guaranteed))
            key = (relative, edge_guaranteed, stage)
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                PromptReferenceEdge(
                    relative,
                    str(metadata.get("trigger", "route_admitted" if edge_guaranteed else line)),
                    edge_guaranteed,
                    stage,
                    str(metadata.get("owner", "")),
                    str(metadata.get("claim", "")),
                )
            )
    return tuple(edges)


def review_prompt_bundles(
    root: str | Path = ".",
    *,
    manifest_path: str | Path = "flowguard/prompt_bundle_manifest.json",
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    path = Path(manifest_path)
    if not path.is_absolute():
        path = root_path / path
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != PROMPT_BUNDLE_SCHEMA:
        raise ValueError("unsupported prompt bundle manifest schema")
    metrics: list[PromptBundleMetric] = []
    route_ids: set[str] = set()
    for row in payload.get("bundles", ()):
        route_id = str(row.get("route_id", ""))
        if not route_id or route_id in route_ids:
            raise ValueError("prompt bundle route ids must be unique and non-empty")
        route_ids.add(route_id)
        configured_paths = [str(item).replace("\\", "/") for item in row.get("paths", ())]
        skill_paths = [item for item in configured_paths if item.endswith("/SKILL.md")]
        if len(skill_paths) != 1:
            raise ValueError(f"prompt bundle {route_id} must name exactly one SKILL.md")
        skill_candidate = (root_path / skill_paths[0]).resolve()
        material_by_path: dict[str, dict[str, Any]] = {}
        for material in row.get("material", ()) or ():
            if not isinstance(material, dict):
                raise ValueError(f"prompt bundle {route_id} material row must be an object")
            material_path = str(material.get("path", "")).replace("\\", "/")
            if not material_path:
                raise ValueError(f"prompt bundle {route_id} material path is required")
            if material_path in material_by_path:
                raise ValueError(f"prompt bundle {route_id} material paths must be unique")
            material_by_path[material_path] = dict(material)
        edges = (
            _reference_edges(skill_candidate, root_path, material_by_path)
            if skill_candidate.is_file()
            else ()
        )
        guaranteed_paths = [
            edge.path for edge in edges if edge.guaranteed and edge.stage == "preselection"
        ]
        # Keep the historical field as the complete on-demand/after-admission
        # edge list.  An edge may be mandatory for the admitted route while it
        # is still excluded from the first-read preselection bundle.
        conditional_edges = tuple(
            edge for edge in edges if not edge.guaranteed or edge.stage != "preselection"
        )
        catalog_paths = [
            str(item).replace("\\", "/")
            for item in row.get("catalog_paths", skill_paths)
        ]
        if not catalog_paths:
            raise ValueError(f"prompt bundle {route_id} must name catalog paths")
        resolved_paths = tuple(
            dict.fromkeys((*configured_paths, *catalog_paths, *guaranteed_paths))
        )
        components: list[PromptComponentMetric] = []
        missing: list[str] = [
            edge.path
            for edge in conditional_edges
            if not (root_path / edge.path).is_file()
        ]
        for relative_path in resolved_paths:
            candidate = (root_path / relative_path).resolve()
            if root_path != candidate and root_path not in candidate.parents:
                raise ValueError(f"prompt component escapes root: {relative_path}")
            if not candidate.is_file():
                missing.append(relative_path)
                continue
            text = candidate.read_text(encoding="utf-8")
            components.append(
                PromptComponentMetric(
                    relative_path,
                    len(text.encode("utf-8")),
                    len(text),
                    len(text.splitlines()),
                )
            )
        stage_paths: dict[str, set[str]] = {
            "catalog": set(catalog_paths),
            "preselection": set(configured_paths).difference(catalog_paths),
        }
        for edge in edges:
            stage_paths.setdefault(edge.stage, set()).add(edge.path)
        for material_path, material in material_by_path.items():
            stage_paths.setdefault(
                str(material.get("stage", "triggered_expansion")), set()
            ).add(material_path)
        stage_metrics: list[PromptStageMetric] = []
        stage_budgets = row.get("stage_budgets", {}) or {}
        for stage, stage_paths_for_route in sorted(stage_paths.items()):
            stage_components: list[PromptComponentMetric] = []
            for relative_path in sorted(stage_paths_for_route):
                candidate = (root_path / relative_path).resolve()
                if root_path != candidate and root_path not in candidate.parents:
                    raise ValueError(
                        f"prompt stage component escapes root: {relative_path}"
                    )
                if not candidate.is_file():
                    continue
                text = candidate.read_text(encoding="utf-8")
                stage_components.append(
                    PromptComponentMetric(
                        relative_path,
                        len(text.encode("utf-8")),
                        len(text),
                        len(text.splitlines()),
                    )
                )
            budget_value = stage_budgets.get(stage, 0)
            stage_metrics.append(
                PromptStageMetric(
                    stage=stage,
                    components=tuple(stage_components),
                    max_utf8_bytes=int(budget_value or 0),
                    min_headroom_ratio=float(
                        row.get("stage_min_headroom_ratio", row.get("min_headroom_ratio", 0.10))
                    ),
                    enforced=stage in stage_budgets,
                )
            )
        persistent_paths = set().union(
            *(stage_paths.get(stage, set()) for stage in (
                "catalog",
                "preselection",
                "admitted_core",
            ))
        )
        persistent_components: list[PromptComponentMetric] = []
        for relative_path in sorted(persistent_paths):
            candidate = (root_path / relative_path).resolve()
            if not candidate.is_file():
                continue
            text = candidate.read_text(encoding="utf-8")
            persistent_components.append(
                PromptComponentMetric(
                    relative_path,
                    len(text.encode("utf-8")),
                    len(text),
                    len(text.splitlines()),
                )
            )
        persistent_budget = int(row.get("persistent_context_max_utf8_bytes", 0) or 0)
        persistent_context = PromptStageMetric(
            stage="persistent_context",
            components=tuple(persistent_components),
            max_utf8_bytes=persistent_budget,
            min_headroom_ratio=float(
                row.get("persistent_context_min_headroom_ratio", row.get("min_headroom_ratio", 0.10))
            ),
            enforced=persistent_budget > 0,
        )
        metrics.append(
            PromptBundleMetric(
                route_id,
                tuple(components),
                int(row.get("max_utf8_bytes", 0)),
                float(row.get("min_headroom_ratio", 0.10)),
                conditional_edges,
                tuple(missing),
                tuple(stage_metrics),
                persistent_context,
            )
        )
    ok = bool(metrics) and all(item.ok for item in metrics)
    return {
        "schema_version": "flowguard.prompt_bundle_report.v2",
        "status": "pass" if ok else "blocked",
        "ok": ok,
        "source_size_proxy_formula": "ceil(utf8_bytes/3)",
        "provider_token_usage_available": False,
        "bundle_count": len(metrics),
        "failed_route_ids": [
            item.route_id for item in metrics if not item.ok
        ],
        "bundles": [item.to_dict() for item in metrics],
        "claim_boundary": (
            "Prompt bundle telemetry is deterministic source-size regression "
            "evidence, not provider billing or proof of future AI behavior."
        ),
    }


__all__ = [
    "PROMPT_BUNDLE_SCHEMA",
    "PromptBundleMetric",
    "PromptComponentMetric",
    "PromptReferenceEdge",
    "review_prompt_bundles",
]
