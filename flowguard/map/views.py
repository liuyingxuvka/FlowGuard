"""Token-bounded views for an AI session: show (the map), find (owner lookup), digest (API outline)."""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from pathlib import Path

from .common import read_source, tokens
from .inventory import Inventory
from .mapfile import component_files, component_graph, is_stale, owner_index


def render_show(root: Path, data: dict, inv: Inventory, *, component: str | None, detail: bool, budget: int) -> str:
    budget = max(0, budget)
    graph = component_graph(data, inv)
    comps = data["components"]
    if component:
        comps = [c for c in comps if c["id"] == component or c["id"].startswith(component + ".")]
        if not comps:
            return f"no component {component!r}; run 'python -m flowguard read' to list components"[:budget]
    head = f"# {data.get('project', '')}: {len(data['components'])} components"
    if data.get("layers"):
        head += ", layers (top > bottom) " + " > ".join(data["layers"])
    flows = [] if component else [
        f"> flow {flow['id']}: {flow.get('summary', '')} :: " + " -> ".join(flow.get("steps", []))
        for flow in data.get("flows", [])]
    top = "\n".join([head, *flows])
    blocks: list[tuple[str, str]] = []
    for c in comps:
        files = component_files(c, inv)
        flag = "STALE" if is_stale(root, c, inv) else c["status"]
        tag = "" if flag == "confirmed" else f" [{flag}]"
        lines = [f"\n## {c['id']} [{c.get('layer') or '-'}] {len(files)} files/{sum(inv.loc.get(f, 0) for f in files)} loc{tag}"]
        lines.append(f"  {c.get('summary') or '(no summary yet)'}")
        for key, label in (("responsibilities", "owns"), ("state", "state"), ("side_effects", "effects")):
            if c.get(key) and (key != "responsibilities" or component or detail):
                lines.append(f"  {label}: " + "; ".join(c[key]))
        if graph.get(c["id"]):
            lines.append("  uses: " + ", ".join(sorted(graph[c["id"]])))
        declared_only = sorted(set(c.get("depends_on", [])) - graph.get(c["id"], set()))
        if declared_only and (component or detail):
            lines.append("  declared, unverified: " + ", ".join(declared_only))
        if component or detail:
            for key, label in (("entrypoints", "entry"), ("files", "files"), ("tests", "tests"), ("models", "models")):
                if c.get(key):
                    lines.append(f"  {label}: " + ", ".join(c[key]))
            users = sorted(k for k, v in graph.items() if c["id"] in v)
            if users:
                lines.append("  used by: " + ", ".join(users))
        blocks.append((c["id"], "\n".join(lines)))
    text = top + "\n" + "\n".join(b for _, b in blocks)
    if len(text) <= budget:
        return text
    reserve = min(160, budget)
    shown = top if len(top) <= budget - reserve else top[:max(0, budget - reserve)].rsplit("\n", 1)[0]
    hidden: list[str] = []
    for cid, block in blocks:
        if not hidden and len(shown) + 1 + len(block) <= budget - reserve:
            shown += "\n" + block
        else:
            hidden.append(cid)
    named = []
    for cid in hidden:
        if len(", ".join(named + [cid])) > reserve - 90:
            break
        named.append(cid)
    names = ", ".join(named) + (f" +{len(hidden) - len(named)} more" if len(named) < len(hidden) else "")
    return (shown + f"\n... truncated at {budget} chars; not shown: {names}; use read --component ID")[:budget]


def _find_words(words: set[str]) -> set[str]:
    """Owner lookup also matches the singular of a plural word ("orders" ~ "order")."""
    return words | {w[:-1] for w in words if len(w) > 3 and w.endswith("s")}


def defined_symbols(component: dict, inv: Inventory, words: list[str]) -> list[tuple[str, str]]:
    """Exact raw-name matches, including the final name of a class member."""
    raw = {word.lower() for word in words}
    return sorted((symbol, path) for path in component_files(component, inv) if path in inv.py
                  for symbol in inv.py[path].symbols
                  if symbol.lower() in raw or symbol.rsplit(".", 1)[-1].lower() in raw)


def find_owners(data: dict, inv: Inventory, words: list[str], limit: int = 5) -> list[tuple[int, str, list[str]]]:
    """Rank components by how well they already own the described responsibility."""
    query = _find_words(tokens(" ".join(words)))
    scored = []
    for c in data["components"]:
        text = _find_words(tokens(" ".join([c["id"], c.get("summary", "")] + c.get("responsibilities", [])
                                           + c.get("state", []) + c.get("side_effects", []))))
        symbol_words = _find_words({w.lower() for f in component_files(c, inv) if f in inv.py
                                    for s in inv.py[f].symbols
                                    for w in re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z0-9]+", s)})
        score = 3 * len(query & text) + len(query & symbol_words)
        if defined_symbols(c, inv, words):
            score += 4 * len(query) + 1  # greater than every possible pure word-bag score
        if score:
            scored.append((score, c["id"], [r for r in c.get("responsibilities", []) if _find_words(tokens(r)) & query]))
    scored.sort(key=lambda x: (-x[0], -sum(len(_find_words(tokens(r)) & query) for r in x[2]), x[1]))
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
        tree = ast.parse(read_source(root / path))
    except (OSError, SyntaxError) as exc:
        return [f"  (unparseable: {exc})"]
    lines = [f"  doc:{_doc(tree)[3:]}"] if _doc(tree) else []
    def module_nodes(nodes):
        for item in nodes:
            yield item
            if isinstance(item, ast.If):
                yield from module_nodes(item.body + item.orelse)
            elif isinstance(item, (ast.Try, ast.TryStar)):
                yield from module_nodes(item.body + item.orelse + item.finalbody)
                for handler in item.handlers:
                    yield from module_nodes(handler.body)

    def target_names(target):
        if isinstance(target, ast.Name):
            return [target.id] if not target.id.startswith("_") else []
        if isinstance(target, (ast.Tuple, ast.List)):
            return [name for item in target.elts for name in target_names(item)]
        return []

    assignments = []
    for node in module_nodes(tree.body):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = [name for target in targets for name in target_names(target)]
            if names:
                value = ast.unparse(node.value) if node.value is not None else "<annotation>"
                assignments.append(f"{', '.join(names)} = {value[:32]}" + ("..." if len(value) > 32 else ""))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            lines.append(f"  def {_signature(node)}{_doc(node)}")
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            lines.append(f"  class {node.name}{_doc(node)}")
            lines += [f"    .{_signature(s)}" for s in node.body
                      if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))
                      and (not s.name.startswith("_") or s.name == "__init__")]
    if assignments:
        joined = "; ".join(assignments)
        lines.insert(0, "  vars: " + joined[:110] + ("..." if len(joined) > 110 else ""))
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
