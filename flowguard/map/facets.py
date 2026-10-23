"""Static node facets: literals and source facts, never imported model hooks."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from .common import matches_any, read_source
from .inventory import Inventory
from .lint import _variants
from .mapfile import component_files, is_stale


@dataclass(frozen=True)
class Facets:
    purpose: str
    rules: tuple[str, ...]
    rules_source: str
    known_bad: tuple[str, ...]
    known_bad_source: str
    code: tuple[str, ...]
    tests: tuple[str, ...]
    rule_count: int | None
    test_count: int

    @property
    def known_bad_count(self) -> int | None:
        return None if self.known_bad_source == "runtime" else len(self.known_bad)


def _returned_dicts(function):
    """Only this hook's actual return values, not nested helpers or metadata dicts."""
    pending = list(function.body)
    returned = []
    while pending:
        node = pending.pop()
        if isinstance(node, ast.Return):
            returned.append(node.value)
        elif not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            pending.extend(ast.iter_child_nodes(node))
    return returned


def model_facets(root: Path, node) -> Facets:
    contract = node.contract
    try:
        syntax = ast.parse(read_source(root / node.path))
    except (OSError, SyntaxError):
        syntax = ast.Module(body=[], type_ignores=[])
    doc = ast.get_docstring(syntax)
    purpose = doc.strip().splitlines()[0] if doc and doc.strip() else "(no purpose line: add a module docstring)"
    rules = set()
    helpers = {"at_most_once_by", "no_duplicate_by", "all_items_have_source", "cache_matches_source"}
    for call in ast.walk(syntax):
        if not isinstance(call, ast.Call):
            continue
        name = call.func.id if isinstance(call.func, ast.Name) else call.func.attr if isinstance(call.func, ast.Attribute) else ""
        value = call.args[0] if call.args else None
        if name == "Invariant" and value is None:
            value = next((k.value for k in call.keywords if k.arg == "name"), None)
        if name in helpers | {"Invariant"} and isinstance(value, ast.Constant) and isinstance(value.value, str):
            rules.add(value.value)
    source = "literal"
    if not rules:
        rules = set(contract.get("TESTED_BY", {}))
        source = "TESTED_BY" if rules else "runtime"
    hook = next((n for n in syntax.body if isinstance(n, ast.FunctionDef) and n.name == "broken_variants"), None)
    returns = _returned_dicts(hook) if hook else []
    literal_bad = bool(returns) and all(isinstance(value, ast.Dict) and all(
        isinstance(key, ast.Constant) and isinstance(key.value, str) for key in value.keys) for value in returns)
    bad = tuple(sorted({key.value for value in returns for key in value.keys})) if literal_bad else ()
    code = [f"{block} -> {anchor}" for block, anchor in sorted(contract.get("IMPLEMENTED_BY", {}).items())]
    if contract.get("NOT_MODELED"):
        code.append(f"not modeled: {len(contract['NOT_MODELED'])}")
    tests = [f"{rule} -> {anchor}" + (" (not nested)" if anchor.split(":", 1)[0] in node.nonnested_tests else "")
             for rule, anchors in sorted(contract.get("TESTED_BY", {}).items()) for anchor in anchors]
    untested = sorted(rule for rule in rules if not contract.get("TESTED_BY", {}).get(rule))
    if untested:
        tests.append("untested: " + ", ".join(untested))
    return Facets(purpose, tuple(sorted(rules)), source, bad, "literal" if literal_bad else "runtime",
                  tuple(code), tuple(tests), len(rules) if source != "runtime" else None,
                  sum(len(anchors) for anchors in contract.get("TESTED_BY", {}).values()))


def _test_function_index(root: Path, inv: Inventory) -> dict[str, set[str]]:
    """One view-local index: inventory symbols alone also include variables and classes."""
    found = {}
    for path in inv.tests:
        if not path.endswith(".py"):
            continue
        try:
            syntax = ast.parse(read_source(root / path))
        except (OSError, SyntaxError):
            continue
        names, pending = set(), list(syntax.body)
        while pending:
            node = pending.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test"):
                    names.add(node.name)
            elif isinstance(node, ast.ClassDef):
                names.update(f"{node.name}.{method.name}" for method in node.body
                             if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and method.name.startswith("test"))
            elif isinstance(node, (ast.If, ast.Try, ast.With)):
                pending.extend(node.body + getattr(node, "orelse", []) + getattr(node, "finalbody", []))
                for handler in getattr(node, "handlers", []):
                    pending.extend(handler.body)
        found[path] = names
    return found


def _test_facts(paths, nodes, functions):
    actual = {(path, name) for path in paths for name in functions.get(path, ())}
    bound = set()
    for node in nodes:
        for anchors in node.contract.get("TESTED_BY", {}).values():
            for anchor in anchors:
                path, _, name = anchor.partition(":")
                matches = {(p, s) for p, s in actual if p == path and s == name}
                if not matches:
                    matches = {(p, s) for p, s in actual if p == path and s.endswith("." + name)}
                if len(matches) == 1:
                    bound.update(matches)
    unbound = sorted(f"{path}:{name}" for path, name in actual - bound)
    facts = [f"{len(paths)} files: " + (", ".join(sorted(paths)) or "-"), f"{len(actual)} functions, {len(bound)} bound"]
    if unbound:
        facts.append("unbound: " + ", ".join(unbound[:5]) + (f" +{len(unbound) - 5} more" if len(unbound) > 5 else ""))
    return tuple(facts), len(actual)


def component_facets(root: Path, data: dict, inv: Inventory, component: dict, tree, graph, functions) -> Facets:
    cid = component["id"]
    files = component_files(component, inv)
    code = [f"{len(files)} files/{sum(inv.loc.get(path, 0) for path in files)} loc"]
    if component.get("files"):
        code.append("files: " + ", ".join(component["files"]))
    for key, label in (("entrypoints", "entry"), ("state", "state"), ("side_effects", "effects")):
        if component.get(key):
            code.append(label + ": " + "; ".join(component[key]))
    if is_stale(root, component, inv):
        code.append("STALE")
    paths = {path for path in inv.tests if matches_any(path, component.get("tests", []))}
    tests, count = _test_facts(paths, tree.models_for_component(cid), functions)
    rules = tuple(component.get("responsibilities", [])) + (
        f"layer {component.get('layer') or '-'} may use: " + (", ".join(component.get("depends_on", [])) or "-"),)
    return Facets(component.get("summary") or "(no summary yet)", rules, "map",
                  tuple(name for name, _, _ in _variants(data, graph, only=cid)), "system", tuple(code), tests,
                  len(component.get("responsibilities", [])), count)


def system_facets(data: dict, inv: Inventory, tree, graph, functions) -> Facets:
    tests, count = _test_facts(set(inv.tests), tree.nodes.values(), functions)
    return Facets(f"{data.get('project', '')}: {len(data['components'])} components",
                  ("layers order: " + (" > ".join(data.get("layers", [])) or "none"),
                   "no unaccepted dependency cycle", "one owner per responsibility"), "map",
                  tuple(name for name, _, _ in _variants(data, graph)), "system-root",
                  (f"{len(data['components'])} components, {len(inv.source)} source files",), tests, 3, count)
