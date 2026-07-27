"""Deterministic first-read prompt bundle telemetry."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


PROMPT_BUNDLE_SCHEMA = "flowguard.prompt_bundle_manifest.v1"


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
    def conservative_token_estimate(self) -> int:
        return (self.utf8_bytes + 2) // 3

    @property
    def ok(self) -> bool:
        return not self.missing_paths and self.utf8_bytes <= self.max_utf8_bytes

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "status": "pass" if self.ok else "blocked",
            "ok": self.ok,
            "utf8_bytes": self.utf8_bytes,
            "characters": self.characters,
            "lines": self.lines,
            "conservative_token_estimate": self.conservative_token_estimate,
            "max_utf8_bytes": self.max_utf8_bytes,
            "max_conservative_token_estimate": (
                self.max_utf8_bytes + 2
            )
            // 3,
            "missing_paths": list(self.missing_paths),
            "components": [item.to_dict() for item in self.components],
        }


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
        components: list[PromptComponentMetric] = []
        missing: list[str] = []
        for relative in row.get("paths", ()):
            relative_path = str(relative).replace("\\", "/")
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
                tuple(missing),
            )
        )
    ok = bool(metrics) and all(item.ok for item in metrics)
    return {
        "schema_version": "flowguard.prompt_bundle_report.v1",
        "status": "pass" if ok else "blocked",
        "ok": ok,
        "token_estimate": "ceil(utf8_bytes/3)",
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
    "review_prompt_bundles",
]
