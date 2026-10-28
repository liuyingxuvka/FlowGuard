"""A complete field view joining model promises with native read and write sites."""

from __future__ import annotations
import ast
import re
from collections import defaultdict
from pathlib import Path
from .common import read_source
from .discover import discover_inventory
from .facets import model_facets
from .inventory import Inventory
from .tree import build_tree


def render_field(root: Path, data: dict, inv: Inventory, name: str) -> str:
    """Join field sites and promises statically, with no model execution or persisted index."""
    from .discover import literal_sites, function_spans
    from .port import model_port

    tree = build_tree(root, data, inv)
    raw = discover_inventory(root, inv, data=data)
    word = re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)")
    parts = defaultdict(list)
    bound = defaultdict(set)
    code_priority = {}
    for component in data["components"]:
        values = component.get("state", [])
        if isinstance(values, str):
            values = [values]
        for value in values:
            if word.search(value):
                parts["map"].append(f"{component['id']} (state: {value})")
    for mid, node in tree.nodes.items():
        port = node.contract["port"]
        labels = []
        if name in (port.state or ()):
            labels.append("State." + name)
        for block, spec in port.blocks.items():
            modes = [mode for mode in ("reads", "writes") if name in (spec[mode] or ())]
            if modes:
                labels.append("block " + block + " " + " and ".join(modes) + " it")
        if name in port.reads_parent:
            labels.append("reads parent." + name)
        if name in (port.outputs or {}):
            labels.append("OUTPUTS." + name)
        if name in port.keeps:
            labels.append("KEEPS." + name)
        for producer, keys in (port.handoff or {}).items():
            for key, into in keys.items():
                if (into if isinstance(into, str) or into is None else into[0]) == name:
                    labels.append(f"HANDOFF {producer}.{key} -> {name}")
        if labels:
            parts["models"].append(mid + " " + ", ".join(labels))
        fact = model_facets(root, node)
        rules = [
            rule
            for rule, note in zip(
                fact.rules, fact.rule_notes or ("",) * len(fact.rules)
            )
            if word.search(rule) or word.search(note)
        ]
        bads = [bad for bad in fact.known_bad if word.search(bad)]
        if rules or bads:
            parts["rules"].append(
                ", ".join(mid + "." + rule for rule in rules)
                + (
                    ("; " if rules else "") + "known-bad: " + ", ".join(bads)
                    if bads
                    else ""
                )
            )
        for rule in rules:
            for anchor in node.contract.get("TESTED_BY", {}).get(rule, ()):
                path, _, symbol = anchor.partition(":")
                bound[path].add(symbol)
    for path, facts in raw.get("files", {}).items():
        for attr, writers in facts.get("state", {}).items():
            if attr.rsplit(".", 1)[-1] == name:
                parts["code writes"].extend(path + ":" + writer for writer in writers)
        try:
            source = read_source(root / path)
        except OSError:
            continue
        # Discovery supplies lexical start lines; select the innermost containing function.
        syntax = ast.parse(source)
        spans = function_spans(syntax)
        stores = {
            node.lineno
            for node in ast.walk(syntax)
            if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store)
        }
        for value, line, role in literal_sites(source):
            if value != name or role not in ("key_write", "key_read"):
                continue
            candidates = [span for span in spans if span[0] <= line <= span[1]]
            symbol = (
                min(candidates, key=lambda span: span[1] - span[0])[2]
                if candidates
                else "<module>"
            )
            site = path + ":" + symbol
            code_priority[site] = min(
                code_priority.get(site, 1),
                0 if role == "key_write" and line in stores else 1,
            )
            parts["code writes" if role == "key_write" else "code reads"].append(site)
    parts["tests"] = [
        f"{path} ({len(symbols)} bound)" for path, symbols in sorted(bound.items())
    ]
    if not any(parts.values()):
        return f"field {name}: no model, rule or code site"
    if parts["code writes"] and not parts["rules"]:
        parts["rules"] = [
            f"none (a field no rule names: python -m flowguard read --field {name} before changing it)"
        ]
    lines = ["field " + name]
    for label in ("map", "models", "rules", "code writes", "code reads", "tests"):
        items = list(dict.fromkeys(parts[label]))
        if label == "code writes":
            items.sort(key=lambda site: (code_priority.get(site, 0), site))
        if items:
            lines.append(
                "  "
                + label
                + ": "
                + ", ".join(items[:5])
                + (f" (+{len(items)-5})" if len(items) > 5 else "")
            )
    return "\n".join(lines)
