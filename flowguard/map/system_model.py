"""The built-in map root: real architecture, generated bad changes and code consistency."""

from __future__ import annotations

import time
from copy import deepcopy

from .check import run_check
from .common import tokens
from .lint import apply_accepted_debts, duplicate_owner_findings, normalized_debts, structural_findings
from .mapfile import component_graph


def _rules(data, graph, *, root=None, inv=None):
    raw = structural_findings(data, graph, root=root, inv=inv) + duplicate_owner_findings(data)
    return apply_accepted_debts(raw, normalized_debts(data))[0]


def _reachable(graph, start, target):
    pending, seen = [start], set()
    while pending:
        node = pending.pop()
        if node == target:
            return True
        if node not in seen:
            seen.add(node)
            pending.extend(graph.get(node, ()))
    return False


def _variants(data, graph):
    """At most one new layer edge, closing edge and copied claim per component.

    Only a positive accepted-debt finding skips a mutation. Missing rule output
    must still reach the known-bad check, where a blind spot is a failure.
    """
    components = sorted(data["components"], key=lambda c: c["id"])
    rank = {layer: i for i, layer in enumerate(data.get("layers", []))}
    for source in components:
        src = source["id"]
        for destination in components:
            dst = destination["id"]
            if (source.get("layer") not in rank or destination.get("layer") not in rank
                    or rank[destination["layer"]] >= rank[source["layer"]] or dst in graph[src]):
                continue
            changed = {key: set(values) for key, values in graph.items()}
            changed[src].add(dst)
            matching = [f for f in _rules(data, changed) if f.code == "layer_violation"
                        and f.component == src and f"({dst}):" in f.message]
            if matching and all(f.level == "info" for f in matching):
                continue
            yield f"{src}_imports_{dst}", data, changed
            break
        for dst in sorted(graph[src]):
            if _reachable(graph, dst, src):
                continue
            changed = {key: set(values) for key, values in graph.items()}
            changed[dst].add(src)
            matching = [f for f in _rules(data, changed) if f.code == "dependency_cycle"
                        and {src, dst} <= set(f.message.split(";", 1)[0].split(" <-> "))]
            if matching and all(f.level == "info" for f in matching):
                continue
            yield f"{src}_closes_cycle_with_{dst}", data, changed
            break
        for destination in components:
            dst = destination["id"]
            if dst == src or not destination.get("responsibilities"):
                continue
            existing = [tokens(r) for r in destination["responsibilities"]]
            claim = next((r for r in source.get("responsibilities", [])
                          if tokens(r) and tokens(r) not in existing), None)
            if claim is None:
                continue
            changed_data = deepcopy(data)
            next(c for c in changed_data["components"] if c["id"] == dst)["responsibilities"].append(claim)
            matching = [f for f in _rules(changed_data, graph) if f.code == "duplicate_owner"
                        and repr(" ".join(sorted(tokens(claim)))) in f.message]
            if matching and all(f.level == "info" for f in matching):
                continue
            yield f"{src}_duplicates_{dst}", changed_data, graph
            break


def run_system_model(root, data, inv):
    """Run every time in-process; no user model imports, result cache or receipt."""
    from .proof import ModelResult

    started = time.monotonic()
    result = ModelResult(model="system", file=".flowguard/map.json")
    graph = component_graph(data, inv)
    result.problems.extend(f"{f.code} {f.component}: {f.message}"
                           for f in _rules(data, graph, root=root, inv=inv) if f.level == "error")
    generated = 0
    for name, changed_data, changed_graph in _variants(data, graph):
        generated += 1
        if not any(f.level == "error" for f in _rules(changed_data, changed_graph)):
            result.problems.append(f"generated known-bad variant '{name}' passed: the architecture rules do not catch it")
    consistency = run_check(root, data, inv)
    errors = [f for f in consistency if f.level == "error"]
    if errors:
        result.problems.append("the map does not match the code:\n" + "\n".join(
            f"{f.code} {f.component}: {f.message}" for f in errors[:5]))
    unbound = sum(f.code == "test_unbound" for f in consistency)
    if unbound:
        result.warnings.append(f"{unbound} test file(s) belong to no component")
    if not data.get("layers"):
        result.warnings.append('no layers in the map: the layer rule cannot be checked; add "layers"')
    if not generated:
        result.warnings.append("no known-bad variants could be generated")
    if result.problems:
        result.status = "fail"
    result.seconds = round(time.monotonic() - started, 3)
    return result
