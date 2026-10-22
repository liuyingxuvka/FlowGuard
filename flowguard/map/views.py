"""Token-bounded views for an AI session: show (the map), find (owner lookup), digest (API outline)."""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from pathlib import Path

from .common import Finding, read_source, tokens
from .inventory import Inventory
from .tree import build_tree
from .lint import apply_accepted_debts, find_cycles, layer_findings, normalized_debts
from .mapfile import component_files, component_graph, is_stale, owner_index


def _architecture(data: dict, graph: dict[str, set[str]]):
    """Only cheap cycle/layer rules; share full debt normalization with lint."""
    findings, by_component = [], defaultdict(list)
    for cycle in find_cycles(graph):
        finding = Finding("error", "dependency_cycle", cycle[0], " <-> ".join(cycle))
        findings.append(finding)
        for cid in cycle:
            by_component[cid].append(finding)
    for finding in layer_findings(data, graph):
        findings.append(finding)
        by_component[finding.component].append(finding)
    findings, used = apply_accepted_debts(findings, normalized_debts(data))
    return findings, used, by_component


def _model_lines(tree, ids: set[str], *, component: str | None = None, bindings: bool = False) -> list[str]:
    roots = sorted((tree.nodes[mid] for mid in ids if tree.nodes[mid].parent_kind != "model"
                    or tree.nodes[mid].parent not in ids), key=lambda n: n.id)
    pending, lines = [(node, 1) for node in reversed(roots)], []
    while pending:
        node, depth = pending.pop()
        count = sum(len(anchors) for anchors in node.contract.get("TESTED_BY", {}).values())
        home = f" (home {node.home})" if component and (node.home_kind != "component" or node.home != component) else ""
        lines.append("  " * depth + f"model {node.id} [{node.kind}] tests: {count} bound{home}")
        if bindings:
            for invariant, anchors in sorted(node.contract.get("TESTED_BY", {}).items()):
                lines.extend("  " * (depth + 1) + f"{invariant} -> {anchor}" for anchor in anchors)
        pending.extend((child, depth + 1) for child in reversed(tree.children(node.id, "model")) if child.id in ids)
    return lines


def render_show(root: Path, data: dict, inv: Inventory, *, component: str | None, detail: bool, budget: int) -> str:
    budget = max(0, budget)
    graph = component_graph(data, inv)
    tree = build_tree(root, data, inv)
    comps = data["components"]
    if component:
        comps = [c for c in comps if c["id"] == component or c["id"].startswith(component + ".")]
        if not comps:
            return f"no component {component!r}; run 'python -m flowguard read' to list components"[:budget]
    architecture, debts, problems = _architecture(data, graph)
    head = f"# {data.get('project', '')}: system, {len(data['components'])} components"
    if data.get("layers"):
        head += ", layers (top > bottom) " + " > ".join(data["layers"])
    else:
        head += ", layers: none"
    head += f"; architecture: {sum(f.level == 'error' for f in architecture)} error(s), {len(debts)} accepted debt(s)"
    model_ids = {node.path: node.id for node in tree.nodes.values()}
    flows = [] if component else [
        f"> flow {flow['id']}: {flow.get('summary', '')} :: " + " -> ".join(flow.get("steps", []))
        + (f" model: {model_ids.get(flow['model'], flow['model'])}" if flow.get("model") else "")
        for flow in data.get("flows", [])]
    essential = "\n".join([head, *flows])
    root_models = [] if component else _model_lines(tree, {n.id for n in tree.nodes.values() if n.home_kind == "system"})
    top = "\n".join([essential, *root_models])
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
            for key, label in (("entrypoints", "entry"), ("files", "files"), ("tests", "tests")):
                if c.get(key):
                    lines.append(f"  {label}: " + ", ".join(c[key]))
            users = sorted(k for k, v in graph.items() if c["id"] in v)
            if users:
                lines.append("  used by: " + ", ".join(users))
        if problems.get(c["id"]):
            lines.append("  problems: " + "; ".join(
                ("cycle" if f.code == "dependency_cycle" else f.code) + (" (debt)" if f.level == "info" else "")
                + ": " + f.message.partition(" (accepted debt:")[0] for f in problems[c["id"]]))
        models = {n.id for n in tree.models_for_component(c["id"])} if component or detail else {
            n.id for n in tree.nodes.values() if n.home_kind == "component" and n.home == c["id"]}
        lines.extend(_model_lines(tree, models, component=c["id"] if component or detail else None,
                                  bindings=bool(component or detail)))
        blocks.append((c["id"], "\n".join(lines)))
    text = top + "\n" + "\n".join(b for _, b in blocks)
    if len(text) <= budget:
        return text
    reserve = min(160, max(0, budget - len(essential)))
    shown = ""
    for line in top.splitlines():
        candidate = shown + ("\n" if shown else "") + line
        if len(candidate) > budget - reserve:
            break
        shown = candidate
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


def render_mermaid(root: Path, data: dict, inv: Inventory, *, component: str | None = None) -> str:
    """Export the same home/parent tree, with no dependency hairball or text budget."""
    comps = [c for c in data["components"] if component is None or c["id"] == component]
    if component and not comps:
        return f"no component {component!r}; run 'python -m flowguard read' to list components"
    tree = build_tree(root, data, inv)
    _, _, problems = _architecture(data, component_graph(data, inv))
    homes = {c["id"] for c in comps}
    models = [node for node in tree.nodes.values() if
              (node.home_kind == "component" and node.home in homes) or
              (component is None and node.home_kind == "system")]
    used = set()

    def identifier(prefix, name):
        base = prefix + re.sub(r"[^A-Za-z0-9_]", "_", name)
        candidate, number = base, 1
        while candidate in used:
            number += 1
            candidate = f"{base}_{number}"
        used.add(candidate)
        return candidate

    def label(text):
        return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "'").replace("\r", "").replace("\n", "<br/>")

    components = {c["id"]: identifier("c_", c["id"]) for c in comps}
    model_ids = {node.id: identifier("m_", node.id) for node in sorted(models, key=lambda n: n.id)}
    lines = ["flowchart TD", f'  root_system["{label(data.get("project", ""))}: {len(comps)} components"]']
    groups = list(dict.fromkeys([*data.get("layers", []), *[c.get("layer", "") for c in comps]]))
    for index, layer in enumerate(groups):
        members = [c for c in comps if c.get("layer", "") == layer]
        lines.append(f'  subgraph l_{index}["{label(layer or "unlayered")}"]')
        for comp in members:
            codes = sorted({("cycle" if f.code == "dependency_cycle" else f.code)
                            + (" (debt)" if f.level == "info" else "") for f in problems.get(comp["id"], [])})
            title = label(comp["id"]) + ("<br/>" + ", ".join(codes) if codes else "")
            lines.append(f'    {components[comp["id"]]}["{title}"]')
        lines.append("  end")
    for node in sorted(models, key=lambda n: n.id):
        lines.append(f'  {model_ids[node.id]}(["model {label(node.id)}"])')
    lines.extend(f"  root_system --> {components[c['id']]}" for c in comps)
    for node in sorted(models, key=lambda n: n.id):
        if node.parent_kind == "model" and node.parent in model_ids:
            parent = model_ids[node.parent]
        elif node.parent_kind == "component" and node.parent in components:
            parent = components[node.parent]
        else:
            parent = "root_system"
        lines.append(f"  {parent} --> {model_ids[node.id]}")
    return "\n".join(lines)


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
