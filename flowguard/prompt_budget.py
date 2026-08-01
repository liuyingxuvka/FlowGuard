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

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "trigger": self.trigger,
            "guaranteed": self.guaranteed,
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
class PromptBundleMetric:
    route_id: str
    components: tuple[PromptComponentMetric, ...]
    max_utf8_bytes: int
    min_headroom_ratio: float
    conditional_edges: tuple[PromptReferenceEdge, ...] = ()
    missing_paths: tuple[str, ...] = ()

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
        return not self.missing_paths and self.headroom_ok

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


def _reference_edges(skill_path: Path, root_path: Path) -> tuple[PromptReferenceEdge, ...]:
    text = skill_path.read_text(encoding="utf-8")
    edges: list[PromptReferenceEdge] = []
    seen: set[tuple[str, bool]] = set()
    for line in _local_material_routing(text):
        lowered = line.lower()
        guaranteed = not any(cue in lowered for cue in _CONDITIONAL_CUES)
        for reference in _REFERENCE_PATH_RE.findall(line):
            absolute = (skill_path.parent / reference).resolve()
            try:
                relative = absolute.relative_to(root_path).as_posix()
            except ValueError as exc:
                raise ValueError(f"prompt reference escapes root: {reference}") from exc
            key = (relative, guaranteed)
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                PromptReferenceEdge(
                    relative,
                    "guaranteed_before_route_work" if guaranteed else line,
                    guaranteed,
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
        edges = _reference_edges(skill_candidate, root_path) if skill_candidate.is_file() else ()
        guaranteed_paths = [edge.path for edge in edges if edge.guaranteed]
        conditional_edges = tuple(edge for edge in edges if not edge.guaranteed)
        resolved_paths = tuple(dict.fromkeys((*configured_paths, *guaranteed_paths)))
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
        metrics.append(
            PromptBundleMetric(
                route_id,
                tuple(components),
                int(row.get("max_utf8_bytes", 0)),
                float(row.get("min_headroom_ratio", 0.10)),
                conditional_edges,
                tuple(missing),
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
