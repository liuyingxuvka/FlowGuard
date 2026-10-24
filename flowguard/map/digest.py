"""API outline digests of a component's files: signatures and first doc lines, never bodies."""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

from .common import read_source
from .inventory import Inventory
from .mapfile import component_files, owner_index


def _signature(node: ast.AST) -> str:
    a = node.args
    names = [x.arg for x in a.posonlyargs + a.args if x.arg not in ("self", "cls")]
    names += [f"*{a.vararg.arg}"] if a.vararg else []
    names += [x.arg for x in a.kwonlyargs] + ([f"**{a.kwarg.arg}"] if a.kwarg else [])
    return f"{node.name}({', '.join(names)})"


def _doc(node: ast.AST) -> str:
    doc = ast.get_docstring(node)
    return f"  # {doc.strip().splitlines()[0][:120]}" if doc else ""


def _overloaded(functions) -> dict[str, list]:
    """name -> its definitions, for names with a typing.overload stub (listed once in a digest)."""
    by_name: dict[str, list] = {}
    for function in functions:
        by_name.setdefault(function.name, []).append(function)
    return {name: defs for name, defs in by_name.items() if len(defs) > 1 and any(
        (decorator.id if isinstance(decorator, ast.Name) else decorator.attr if isinstance(decorator, ast.Attribute) else "")
        == "overload" for item in defs for decorator in item.decorator_list)}


def _overload_note(overloads, node) -> str:
    return f" (+{len(overloads[node.name]) - 1} overloads)" if node.name in overloads else ""


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
    module_overloads = {"": _overloaded([node for node in module_nodes(tree.body)
                                         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))])}
    for node in module_nodes(tree.body):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = [name for target in targets for name in target_names(target)]
            if names:
                value = ast.unparse(node.value) if node.value is not None else "<annotation>"
                assignments.append(f"{', '.join(names)} = {value[:32]}" + ("..." if len(value) > 32 else ""))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            if node.name not in module_overloads.get("", {}) or module_overloads[""][node.name][0] is node:
                lines.append(f"  def {_signature(node)}{_doc(node)}{_overload_note(module_overloads.get('', {}), node)}")
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            lines.append(f"  class {node.name}{_doc(node)}")
            methods = [s for s in node.body if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and (not s.name.startswith("_") or s.name == "__init__")]
            overloads = _overloaded(methods)
            lines += [f"    .{_signature(s)}{_overload_note(overloads, s)}" for s in methods
                      if s.name not in overloads or overloads[s.name][0] is s]
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
