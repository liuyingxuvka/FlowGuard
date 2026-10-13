"""Token-bounded views for an AI session: show (the map), find (owner lookup), digest (API outline)."""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from pathlib import Path

from .common import tokens
from .inventory import Inventory
from .mapfile import component_files, component_graph, is_stale, owner_index


def render_show(root: Path, data: dict, inv: Inventory, *, component: str | None, detail: bool, budget: int) -> str:
    graph = component_graph(data, inv)
    comps = data["components"]
    if component:
        comps = [c for c in comps if c["id"] == component or c["id"].startswith(component + ".")]
        if not comps:
            return f"no component {component!r}; run 'show' to list components"
    head = f"# {data.get('project', '')}: {len(data['components'])} components"
    if data.get("layers"):
        head += ", layers (top > bottom) " + " > ".join(data["layers"])
    lines = [head]
    for c in comps:
        files = component_files(c, inv)
        flag = "STALE" if is_stale(root, c, inv) else c["status"]
        lines.append(f"\n## {c['id']} [{c.get('layer') or '-'}] {len(files)} files/{sum(inv.loc.get(f, 0) for f in files)} loc [{flag}]")
        lines.append(f"  {c.get('summary') or '(no summary yet)'}")
        for key, label in (("responsibilities", "owns"), ("state", "state"), ("side_effects", "effects")):
            if c.get(key):
                lines.append(f"  {label}: " + "; ".join(c[key]))
        if graph.get(c["id"]):
            lines.append("  uses: " + ", ".join(sorted(graph[c["id"]])))
        if component or detail:
            for key, label in (("entrypoints", "entry"), ("files", "files"), ("tests", "tests"), ("models", "models")):
                if c.get(key):
                    lines.append(f"  {label}: " + ", ".join(c[key]))
            users = sorted(k for k, v in graph.items() if c["id"] in v)
            if users:
                lines.append("  used by: " + ", ".join(users))
    if not component:
        for flow in data.get("flows", []):
            lines.append(f"\n> flow {flow['id']}: {flow.get('summary', '')} :: " + " -> ".join(flow.get("steps", [])))
    text = "\n".join(lines)
    if len(text) > budget:
        text = text[:budget].rsplit("\n", 1)[0] + f"\n... truncated at {budget} chars; use --component ID"
    return text


def find_owners(data: dict, inv: Inventory, words: list[str], limit: int = 5) -> list[tuple[int, str, list[str]]]:
    """Rank components by how well they already own the described responsibility."""
    query = tokens(" ".join(words))
    scored = []
    for c in data["components"]:
        text = tokens(" ".join([c["id"], c.get("summary", "")] + c.get("responsibilities", [])
                               + c.get("state", []) + c.get("side_effects", [])))
        symbol_words = {w for f in component_files(c, inv) if f in inv.py
                        for s in inv.py[f].symbols for w in re.findall(r"[a-z0-9]+", s.lower())}
        score = 3 * len(query & text) + len(query & symbol_words)
        if score:
            scored.append((score, c["id"], [r for r in c.get("responsibilities", []) if tokens(r) & query]))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored[:limit]


def _signature(node: ast.AST) -> str:
    a = node.args
    names = [x.arg for x in a.posonlyargs + a.args if x.arg not in ("self", "cls")]
    names += [f"*{a.vararg.arg}"] if a.vararg else []
    names += [x.arg for x in a.kwonlyargs] + ([f"**{a.kwarg.arg}"] if a.kwarg else [])
    return f"{node.name}({', '.join(names)})"


def _doc(node: ast.AST) -> str:
    doc = ast.get_docstring(node)
    return f"  # {doc.strip().splitlines()[0][:120]}" if doc else ""


def file_outline(root: Path, path: str) -> list[str]:
    """Public API outline of a Python file: docstrings and signatures, never bodies."""
    try:
        tree = ast.parse((root / path).read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError) as exc:
        return [f"  (unparseable: {exc})"]
    lines = [f"  doc:{_doc(tree)[3:]}"] if _doc(tree) else []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            lines.append(f"  def {_signature(node)}{_doc(node)}")
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            lines.append(f"  class {node.name}{_doc(node)}")
            lines += [f"    .{_signature(s)}" for s in node.body
                      if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))
                      and (not s.name.startswith("_") or s.name == "__init__")]
    return lines


def render_digest(root: Path, data: dict, inv: Inventory, ids: list[str], max_lines: int) -> str:
    by_id = {c["id"]: c for c in data["components"]}
    wanted = list(by_id) if ids == ["all"] else ids
    unknown = [i for i in wanted if i not in by_id]
    if unknown:
        return f"unknown component(s) {unknown}"
    owner, _ = owner_index(data, inv)
    users_of: dict[str, set[str]] = defaultdict(set)
    for src, dsts in inv.file_deps.items():
        if src in owner:
            for dst in dsts:
                users_of[dst].add(owner[src])
    out = []
    for cid in wanted:
        files = component_files(by_id[cid], inv)
        out.append(f"# digest {cid}: {len(files)} files")
        for f in files:
            users = sorted(users_of.get(f, set()) - {cid})
            out.append(f"{f} ({inv.loc.get(f, 0)} loc)" + (f"  used by: {', '.join(users)}" if users else ""))
            if f in inv.py:
                out += file_outline(root, f)[:max_lines]
    return "\n".join(out)
