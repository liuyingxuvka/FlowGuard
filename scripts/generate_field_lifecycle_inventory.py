"""Generate a lightweight FlowGuard dataclass field lifecycle inventory."""

from __future__ import annotations

import argparse
import ast
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


BEHAVIOR_HINTS = {
    "action",
    "actions",
    "branch",
    "branches",
    "contract",
    "contracts",
    "effect",
    "effects",
    "error",
    "event",
    "external",
    "input",
    "inputs",
    "invariant",
    "obligation",
    "obligations",
    "output",
    "outputs",
    "route",
    "state",
    "transition",
    "transitions",
}
EVIDENCE_HINTS = {
    "audit",
    "confidence",
    "decision",
    "evidence",
    "finding",
    "findings",
    "gap",
    "gaps",
    "ok",
    "proof",
    "reason",
    "report",
    "result",
    "status",
    "summary",
}
COMPATIBILITY_HINTS = {
    "alias",
    "compatibility",
    "deprecated",
    "fallback",
    "legacy",
    "old",
    "replacement",
    "replaced",
}
DISPLAY_HINTS = {"description", "display", "label", "message", "name", "text", "title"}


@dataclass(frozen=True)
class FieldInventoryRow:
    module: str
    class_name: str
    field_name: str
    annotation: str
    lifecycle_layer: str
    behavior_hint: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "module": self.module,
            "class_name": self.class_name,
            "field_name": self.field_name,
            "annotation": self.annotation,
            "lifecycle_layer": self.lifecycle_layer,
            "behavior_hint": self.behavior_hint,
        }


def _is_dataclass(node: ast.ClassDef) -> bool:
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id == "dataclass":
            return True
        if isinstance(decorator, ast.Attribute) and decorator.attr == "dataclass":
            return True
        if isinstance(decorator, ast.Call):
            func = decorator.func
            if isinstance(func, ast.Name) and func.id == "dataclass":
                return True
            if isinstance(func, ast.Attribute) and func.attr == "dataclass":
                return True
    return False


def _annotation_text(node: ast.AST) -> str:
    return ast.unparse(node) if hasattr(ast, "unparse") else node.__class__.__name__


def infer_lifecycle_layer(field_name: str, annotation: str = "") -> str:
    lowered = field_name.lower()
    tokens = {token for token in lowered.replace("-", "_").split("_") if token}
    annotation_lower = annotation.lower()
    if tokens & COMPATIBILITY_HINTS or any(hint in lowered for hint in COMPATIBILITY_HINTS):
        return "compatibility_or_old_path"
    if tokens & BEHAVIOR_HINTS or any(hint in lowered for hint in BEHAVIOR_HINTS):
        return "behavior_or_contract"
    if tokens & EVIDENCE_HINTS or any(hint in lowered for hint in EVIDENCE_HINTS):
        return "evidence_or_decision"
    if tokens & DISPLAY_HINTS:
        return "display_or_metadata"
    if "tuple" in annotation_lower or "sequence" in annotation_lower or "mapping" in annotation_lower:
        return "collection_metadata"
    return "unclassified"


def collect_field_inventory(root: str | Path = ".") -> tuple[FieldInventoryRow, ...]:
    root_path = Path(root).resolve()
    package_root = root_path / "flowguard"
    rows: list[FieldInventoryRow] = []
    for path in sorted(package_root.glob("*.py")):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        module = path.stem
        for node in tree.body:
            if not isinstance(node, ast.ClassDef) or not _is_dataclass(node):
                continue
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    annotation = _annotation_text(item.annotation)
                    layer = infer_lifecycle_layer(item.target.id, annotation)
                    rows.append(
                        FieldInventoryRow(
                            module=module,
                            class_name=node.name,
                            field_name=item.target.id,
                            annotation=annotation,
                            lifecycle_layer=layer,
                            behavior_hint=layer in {"behavior_or_contract", "compatibility_or_old_path"},
                        )
                    )
    return tuple(rows)


def build_inventory_report(rows: Sequence[FieldInventoryRow]) -> dict[str, object]:
    by_layer = Counter(row.lifecycle_layer for row in rows)
    by_module = Counter(row.module for row in rows)
    return {
        "artifact_type": "flowguard_field_lifecycle_inventory",
        "field_count": len(rows),
        "module_count": len(by_module),
        "layers": dict(sorted(by_layer.items())),
        "modules": dict(sorted(by_module.items())),
        "rows": [row.to_dict() for row in rows],
    }


def format_markdown(report: dict[str, object]) -> str:
    lines = [
        "# Field Lifecycle Inventory",
        "",
        "Generated inventory of FlowGuard dataclass fields. It is a maintenance",
        "aid, not deletion authority: behavior-bearing, compatibility-looking,",
        "and evidence-bearing fields still need route-owned proof before edits.",
        "",
        f"- Field rows: `{report['field_count']}`",
        f"- Modules: `{report['module_count']}`",
        "",
        "## Lifecycle Layers",
        "",
        "| Layer | Fields |",
        "| --- | ---: |",
    ]
    layers = report["layers"]
    assert isinstance(layers, dict)
    for layer, count in layers.items():
        lines.append(f"| `{layer}` | {count} |")

    lines.extend(["", "## Module Field Counts", "", "| Module | Fields |", "| --- | ---: |"])
    modules = report["modules"]
    assert isinstance(modules, dict)
    for module, count in sorted(modules.items(), key=lambda item: (-int(item[1]), str(item[0]))):
        lines.append(f"| `{module}` | {count} |")

    lines.extend(
        [
            "",
            "## Field Rows",
            "",
            "| Module | Class | Field | Layer | Behavior Hint |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    rows = report["rows"]
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, dict)
        lines.append(
            f"| `{row['module']}` | `{row['class_name']}` | `{row['field_name']}` | "
            f"`{row['lifecycle_layer']}` | `{str(row['behavior_hint']).lower()}` |"
        )
    return "\n".join(lines) + "\n"


def write_inventory(root: str | Path = ".", output: str | Path = "docs/field_lifecycle_inventory.md") -> dict[str, object]:
    root_path = Path(root).resolve()
    rows = collect_field_inventory(root_path)
    report = build_inventory_report(rows)
    output_path = root_path / output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(format_markdown(report), encoding="utf-8")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--output", default="docs/field_lifecycle_inventory.md", help="Markdown output path.")
    parser.add_argument("--json", action="store_true", help="Print JSON report instead of a text summary.")
    args = parser.parse_args(argv)

    report = write_inventory(args.root, args.output)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("=== flowguard field lifecycle inventory ===")
        print(f"field_count: {report['field_count']}")
        print(f"module_count: {report['module_count']}")
        print(f"output: {Path(args.root).resolve() / args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
