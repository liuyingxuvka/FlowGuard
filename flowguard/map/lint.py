"""Architecture review computed from the map plus the real code.

Findings: dependency cycles, layer violations, duplicate or overlapping
responsibilities, duplicated function bodies across components, oversized
files/components, high fan-out, untested components, never-imported modules,
plus behaviour found by discovery: entrypoints no component lists and side
effects a component does not declare.
Entries in the map's ``accepted_debts`` downgrade matching findings to info.
"""

from __future__ import annotations

import ast
import re
import sys
from collections import defaultdict, deque
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from .common import Finding, matches_any, read_source, tokens
from .discover import anchor_state_writes, discover_inventory, reachable_effects
from .inventory import Inventory, is_type_checking_guard, parse_python, resolve_import
from .tree import build_tree
from .mapfile import component_files, component_graph, component_scope, component_subtree, dependency_evidence, flow_step_parts, model_registry, owner_index, read_model_contract, resolve_model_path

@dataclass
class Limits:
    max_component_loc: int = 3000
    max_file_loc: int = 800
    max_responsibilities: int = 7
    max_fan_out: int = 8


def find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Strongly connected components with more than one member (Tarjan)."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    sccs: list[list[str]] = []

    def visit(v: str) -> None:
        index[v] = low[v] = len(index)
        stack.append(v)
        on_stack.add(v)
        for w in sorted(graph.get(v, ())):
            if w not in index:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in on_stack:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1:
                sccs.append(sorted(comp))

    sys.setrecursionlimit(max(10000, sys.getrecursionlimit()))
    for v in sorted(graph):
        if v not in index:
            visit(v)
    return sccs


def _cycle_members(message: str) -> set[str]:
    return {part.strip() for part in message.split(";", 1)[0].split(" <-> ") if part.strip()}


def _debt_members(debt: dict, component_ids: set[str]) -> set[str]:
    if "members" in debt:
        return set(debt["members"])
    contains = debt.get("contains", "")
    if " <-> " in contains:
        return _cycle_members(contains)
    members = {debt["component"]} if debt.get("component") else set()
    return members | (set(re.findall(r"[a-z0-9][a-z0-9_.-]*", contains)) & component_ids)


def normalized_debts(data: dict) -> list[dict]:
    """Resolve legacy cycle-debt words against all mapped component ids."""
    component_ids = {c["id"] for c in data["components"]}
    return [{**debt, "members": sorted(_debt_members(debt, component_ids))}
            if debt.get("code") == "dependency_cycle" else debt
            for debt in data.get("accepted_debts", [])]


def apply_accepted_debts(findings: list[Finding], debts: list[dict]) -> tuple[list[Finding], set[int]]:
    used = set()
    component_ids = {f.component for f in findings}
    for finding in findings:
        if finding.code == "dependency_cycle":
            component_ids.update(_cycle_members(finding.message))
    for f in findings:
        if f.level == "error" and f.code in {"large_model", "large_test_file", "test_file_mixes_models"}:
            continue
        if f.code == "unexplained" or (f.code == "unbound_models" and "test functions call its code" in f.message):
            continue
        if f.code == "dependency_cycle":
            members = _cycle_members(f.message)
            matches = [(index, _debt_members(debt, component_ids)) for index, debt in enumerate(debts)
                       if debt.get("code") == f.code]
            matches = [(index, group) for index, group in matches
                       if group and (members <= group or group <= members)]
            used.update(index for index, _ in matches)
            accepted = [(index, group) for index, group in matches if members <= group]
            if accepted:
                index, group = min(accepted, key=lambda pair: (len(pair[1]), pair[0]))
                if members < group:
                    f.message += f"; cycle shrank; update the debt's members to {sorted(members)}"
                f.level, f.message = "info", f"{f.message} (accepted debt: {debts[index]['reason']})"
            elif matches:
                _, group = max(matches, key=lambda pair: (len(pair[1]), -pair[0]))
                f.message += (f"; grew beyond accepted debt [{', '.join(sorted(group))}]: "
                              f"new members {', '.join(sorted(members - group))}")
            continue
        for index, debt in enumerate(debts):
            if f.code == debt["code"] and debt.get("component", f.component) == f.component \
                    and debt.get("contains", "") in f.message:
                used.add(index)
                f.level, f.message = "info", f"{f.message} (accepted debt: {debt['reason']})"
                break
    return findings, used


def structural_findings(data: dict, graph: dict[str, set[str]], *,
                        root: Path | None = None, inv: Inventory | None = None) -> list[Finding]:
    """The shared raw cycle/layer rules; callers apply accepted debts once."""
    out = []
    for cycle in find_cycles(graph):
        start, members = cycle[0], set(cycle)
        pending, seen, shortest = deque([[start]]), {start}, []
        while pending and not shortest:
            path = pending.popleft()
            for destination in sorted(graph.get(path[-1], set()) & members):
                if destination == start:
                    shortest = path + [start]
                    break
                if destination not in seen:
                    seen.add(destination)
                    pending.append(path + [destination])
        message = " <-> ".join(cycle) + "; shortest cycle: " + " -> ".join(shortest)
        if root is not None and inv is not None:
            for src, dst in zip(shortest, shortest[1:]):
                sites = dependency_import_sites(root, data, inv, src, dst)
                if sites:
                    message += f"; {src} -> {dst}: {sites[0]}"
        out.append(Finding("error", "dependency_cycle", cycle[0], message))
    out.extend(layer_findings(data, graph, root=root, inv=inv))
    return out


def duplicate_owner_findings(data: dict) -> list[Finding]:
    """Type-separated token claims, shared with the root model and target checks."""
    claims: dict[tuple[str, str], set[str]] = defaultdict(set)
    original: dict[tuple[str, str], str] = {}
    for component in data["components"]:
        for kind, field in (("responsibility", "responsibilities"), ("state", "state"),
                            ("side effect", "side_effects")):
            for value in component.get(field, []):
                words = tokens(value)
                if not words or words <= {"none", "nothing"}:
                    continue
                key = kind, " ".join(sorted(words))
                claims[key].add(component["id"])
                original[key] = min(original.get(key, value), value)
    return [Finding("error", "duplicate_owner", sorted(owners)[0],
                    f"{kind} {(words if kind == 'responsibility' else original[kind, words])!r} "
                    f"is claimed by {sorted(owners)}")
            for (kind, words), owners in sorted(claims.items()) if len(owners) > 1]


def dropped_owner_findings(current_data: dict, merged_data: dict, target) -> list[Finding]:
    """Keep each changed owner's promises, unless the target explicitly retires them."""
    changed = {component["id"] for component in target.data.get("components", [])}
    changed.update(target.remove.get("component", set()))
    out = []
    for kind, field in (("entrypoint", "entrypoints"), ("state", "state"), ("side_effect", "side_effects"),
                        ("responsibility", "responsibilities")):
        def identity(value):
            return value if kind == "entrypoint" else frozenset(tokens(value))

        retained = {identity(value) for component in merged_data["components"]
                    for value in component.get(field, [])}
        removed = {identity(value) for value in target.remove.get(kind, set())}
        for component in current_data["components"]:
            if component["id"] not in changed:
                continue
            for value in component.get(field, []):
                if identity(value) not in retained and identity(value) not in removed:
                    out.append(Finding("error", "owner_dropped", component["id"],
                                       f"{kind} {value!r} of component {component['id']} is on no component "
                                       f"of the target; keep it on the component that takes over, or list "
                                       f'"{kind}:{value}" in remove'))
    return out


def architecture_findings(data, graph, *, root=None, inv=None):
    raw = structural_findings(data, graph, root=root, inv=inv) + duplicate_owner_findings(data)
    return apply_accepted_debts(raw, normalized_debts(data))[0]


def reachable(graph, start, target):
    pending, seen = [start], set()
    while pending:
        node = pending.pop()
        if node == target:
            return True
        if node not in seen:
            seen.add(node)
            pending.extend(graph.get(node, ()))
    return False


def architecture_variants(data, graph, *, only=None):
    """At most one new layer edge, closing edge and copied claim per component.

    Only a positive accepted-debt finding skips a mutation. Missing rule output
    must still reach the known-bad check, where a blind spot is a failure.
    """
    components = sorted(data["components"], key=lambda c: c["id"])
    rank = {layer: i for i, layer in enumerate(data.get("layers", []))}
    for source in components:
        src = source["id"]
        if only is not None and src != only:
            continue
        for destination in components:
            dst = destination["id"]
            if (source.get("layer") not in rank or destination.get("layer") not in rank
                    or rank[destination["layer"]] >= rank[source["layer"]] or dst in graph[src]):
                continue
            changed = {key: set(values) for key, values in graph.items()}
            changed[src].add(dst)
            matching = [f for f in architecture_findings(data, changed) if f.code == "layer_violation"
                        and f.component == src and f"({dst}):" in f.message]
            if matching and all(f.level == "info" for f in matching):
                continue
            yield f"{src}_imports_{dst}", data, changed
            break
        for dst in sorted(graph[src]):
            if reachable(graph, dst, src):
                continue
            changed = {key: set(values) for key, values in graph.items()}
            changed[dst].add(src)
            matching = [f for f in architecture_findings(data, changed) if f.code == "dependency_cycle"
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
            matching = [f for f in architecture_findings(changed_data, graph) if f.code == "duplicate_owner"
                        and repr(" ".join(sorted(tokens(claim)))) in f.message]
            if matching and all(f.level == "info" for f in matching):
                continue
            yield f"{src}_duplicates_{dst}", changed_data, graph
            break


SHAPE_CODES = ("large_component", "too_many_responsibilities", "untested_component", "high_fan_out", "large_file")


def shape_findings(data: dict, inv: Inventory, graph: dict[str, set[str]], limits: Limits | None = None) -> list[Finding]:
    """Size and test warnings computed from the map and line counts alone (no code scan); debts not applied."""
    limits = limits or Limits()
    out = []
    for c in data["components"]:
        files = component_files(c, inv)
        loc = sum(inv.loc.get(f, 0) for f in files)
        if loc > limits.max_component_loc:
            out.append(Finding("warn", "large_component", c["id"], f"{loc} LOC in {len(files)} files (limit {limits.max_component_loc}); consider splitting"))
        if len(c.get("responsibilities", [])) > limits.max_responsibilities:
            out.append(Finding("warn", "too_many_responsibilities", c["id"], f"{len(c['responsibilities'])} responsibilities (limit {limits.max_responsibilities})"))
        if not c.get("tests"):
            out.append(Finding("warn", "untested_component", c["id"], "no tests mapped"))
        if len(graph.get(c["id"], ())) > limits.max_fan_out:
            out.append(Finding("warn", "high_fan_out", c["id"], f"depends on {len(graph[c['id']])} components (limit {limits.max_fan_out})"))
        for f in files:
            if inv.loc.get(f, 0) > limits.max_file_loc:
                out.append(Finding("warn", "large_file", c["id"], f"{f}: {inv.loc[f]} LOC (limit {limits.max_file_loc})"))
    return out


def compound_responsibility_findings(data: dict, max_chars: int = 120) -> list[Finding]:
    """INFO for each responsibility that packs several duties (too long or joined by ';')."""
    return [Finding("info", "responsibility_compound", c["id"],
                    f"responsibility of {c['id']} holds several duties ({len(r)} chars or ';'); "
                    "write one present-tense duty per entry (references/first_map.md)")
            for c in data["components"] for r in c.get("responsibilities", []) if len(r) > max_chars or ";" in r]


def run_lint(
    root: Path,
    data: dict,
    inv: Inventory,
    limits: Limits | None = None,
    *,
    view=None,
    write_cache: bool | None = None,
) -> list[Finding]:
    """All architecture findings; disposable caches are written only for the current tree unless write_cache=False."""
    write_cache = view is None if write_cache is None else write_cache
    limits = limits or Limits()
    comps = data["components"]
    graph = component_graph(data, inv)
    out = structural_findings(data, graph, root=root, inv=inv)

    rows = []
    for c in comps:
        for r in c.get("responsibilities", []):
            tok = tokens(r)
            if tok:
                rows.append((c["id"], r, tok))
    out.extend(duplicate_owner_findings(data))
    for i, (ca, ra, ta) in enumerate(rows):
        for cb, rb, tb in rows[i + 1 :]:
            if ca != cb:
                similarity = len(ta & tb) / len(ta | tb)
                if 0.6 <= similarity < 1.0:
                    out.append(
                        Finding(
                            "warn",
                            "possible_duplicate",
                            ca,
                            f"{ra!r} ~ {cb}: {rb!r} (similarity {similarity:.2f})",
                        )
                    )

    out.extend(shape_findings(data, inv, graph, limits))
    out.extend(compound_responsibility_findings(data))

    owner, _ = owner_index(data, inv)
    by_body: dict[str, list[tuple[str, str, int]]] = defaultdict(list)
    for f, info in inv.py.items():
        if not inv.is_test(f):
            for symbol, digest, size in info.bodies:
                by_body[digest].append((f, symbol, size))
    for sites in by_body.values():
        if len(sites) > 1:
            hit = sorted({owner.get(f, "?") for f, _, _ in sites})
            where = ", ".join(f"{f}:{s}" for f, s, _ in sites[:4]) + (
                " ..." if len(sites) > 4 else ""
            )
            out.append(
                Finding(
                    "warn" if len(hit) > 1 else "info",
                    "duplicate_code",
                    hit[0],
                    f"{len(sites)} identical bodies ({sites[0][2]} AST nodes) in {hit}: {where}",
                )
            )

    raw = discover_inventory(root, inv, write_cache=write_cache, data=data)
    modules = {info.module: path for path, info in inv.py.items()}
    declared_state = {c["id"]: set(c.get("state", [])) for c in comps}
    for path, facts in raw["files"].items():
        if inv.is_test(path):
            continue
        for symbol, function in facts.get("functions", {}).items():
            for write in function.get("writes", []):
                if not write.startswith("<import>."):
                    continue
                target_module, _, state_name = write.removeprefix("<import>.").partition(":")
                target_owner = owner.get(modules.get(target_module, ""), "")
                if (
                    target_owner
                    and owner.get(path) != target_owner
                    and state_name in declared_state[target_owner]
                ):
                    out.append(
                        Finding(
                            "warn",
                            "foreign_state_write",
                            owner.get(path, ""),
                            f"{path}:{symbol} line {function['line']} mutates {target_owner}'s declared state {state_name}; "
                            "route the update through its owner",
                        )
                    )
    for write in raw.get("foreign_writes", ()):
        path, _, symbol = write["source"].partition("#")
        writer, holder = owner.get(path), owner.get(write["class_path"])
        if writer and holder and writer != holder and not inv.is_test(path):
            out.append(
                Finding(
                    "warn",
                    "foreign_state_write",
                    writer,
                    f"{path}:{symbol} line {write['line']} writes {write['class']}.{write['attr']} owned by "
                    f"{holder}; route the update through its owner",
                )
            )
    imported = {t for deps in inv.file_deps.values() for t in deps}
    modules = {info.module: path for path, info in inv.py.items()}
    # Registered contract models are real importers even though they are outside source ownership.
    registry = model_registry(root, data, view=view)
    for entry in registry.entries:
        physical = resolve_model_path(root, entry.path, view=view)
        if physical is None:
            continue
        source = entry.path if view is None else str(physical)
        info = parse_python(
            root, source, entry.path.removesuffix(".py").replace("/", "."), collect_bodies=False
        )
        imported.update(
            target
            for imp in info.imports
            if (
                target := resolve_import(
                    imp,
                    modules,
                    importer=entry.path,
                    py_paths=inv.py,
                    import_roots=inv.import_roots,
                )
            )
        )
    entry_files = {a.split(":", 1)[0] for c in comps for a in c.get("entrypoints", [])}
    entry_files |= {path for path, facts in raw["files"].items() if facts.get("entrypoints")}
    for f in inv.source:
        if (
            f in inv.py
            and not inv.is_test(f)
            and f not in imported
            and f not in entry_files
            and not f.endswith(("__init__.py", "__main__.py", "setup.py", "conftest.py"))
            and not any(
                symbol.startswith("pytest_") and "." not in symbol for symbol in inv.py[f].symbols
            )
        ):
            out.append(
                Finding(
                    "info",
                    "never_imported",
                    owner.get(f, ""),
                    f"{f} is not imported by any repo file (dead code or an entrypoint?)",
                )
            )
    out.extend(discovery_findings(raw, data, inv))
    covered_by_model, not_modeled = model_coverage(root, data, registry, view=view)
    tree = build_tree(root, data, inv, view=view)
    out.extend(flow_unmodeled_findings(raw, data, inv, tree))
    out.extend(
        entrypoint_coverage_findings(
            raw,
            data,
            inv,
            covered_by_model,
            not_modeled=not_modeled,
            models_by_component={
                c["id"]: [n.path for n in tree.models_for_component(c["id"])] for c in comps
            },
        )
    )
    out.extend(model_writer_findings(raw, data, root, inv, registry, view=view))
    out.extend(model_binding_notes(root, data, inv, view=view, tree=tree))
    out.extend(model_size_findings(root, data, inv, view=view, tree=tree))
    from .modelstatic import replay_call_findings

    out.extend(replay_call_findings(root, data, inv, tree, raw))
    from .testtree import test_file_findings

    out.extend(test_file_findings(root, data, inv, tree))
    out.extend(private_use_findings(root, data, inv))
    # Lint must count no-code model debts so they become stale after anchoring.
    for entry in registry.entries:
        physical = resolve_model_path(root, entry.path, view=view)
        try:
            contract = read_model_contract(physical) if physical is not None else {}
        except (OSError, SyntaxError, ValueError):
            continue
        if physical is not None and not contract.get("IMPLEMENTED_BY"):
            out.append(
                Finding(
                    "error",
                    "model_anchor_missing",
                    entry.id,
                    f"{entry.path}: no implementation anchors",
                )
            )
    out, used = apply_accepted_debts(out, normalized_debts(data))
    out.extend(stale_debt_findings(data, inv, raw, used))
    return out


REVIEW_DEBTS = {"unmodeled_owner", "hub", "flow_without_model", "never_imported", "unbound_models"}
CLOSABLE_DEBTS = REVIEW_DEBTS | {"large_model", "large_test_file", "test_file_mixes_models"}


def stale_debt_findings(data: dict, inv: Inventory, raw: dict, used: set[int]) -> list[Finding]:
    """WARN debt_stale for each accepted debt that matched no finding (``used`` from apply_accepted_debts)."""
    debts = normalized_debts(data)
    # A dep_unused debt is used by check while its declared edge has no other evidence.
    bare = dependency_evidence({**data, "accepted_debts": []}, inv, raw)
    declared = {c["id"]: set(c.get("depends_on", [])) for c in data["components"]}
    used = set(used) | {index for index, debt in enumerate(debts) if debt.get("code") == "dep_unused"
                        and debt.get("contains") in declared.get(debt.get("component"), set())
                        and debt.get("contains") not in bare.get(debt.get("component"), set())}
    return [Finding("warn", "debt_stale", debt.get("component", ""), f"accepted debt matches no finding: {debt['reason']}")
            for index, debt in enumerate(debts) if index not in used and debt.get("code") not in REVIEW_DEBTS]


def test_source(root, path, source_cache=None):
    if source_cache is None:
        return read_source(root / path)
    if path not in source_cache:
        source_cache[path] = read_source(root / path)
    return source_cache[path]


def coverage_facts(root, data, inv, tree, raw, *, source_cache=None):
    """Static explanation counts, scoped to each real component and its subtree."""
    excluded = {anchor for node in tree.nodes.values() for anchor in node.contract.get("NOT_MODELED", {})}
    cache = source_cache if source_cache is not None else {}
    from .testtree import test_calls
    all_calls = {}
    for path in inv.tests:
        if path.endswith(".py"):
            try:
                all_calls[path] = set().union(*test_calls(path, test_source(root, path, cache), inv).values())
            except OSError:
                all_calls[path] = set()
    out = {}
    for component in data["components"]:
        cid = component["id"]
        scoped = component_scope(data, component)
        covered = {anchor for node in tree.models_for_component(cid)
                   for anchor in node.contract.get("IMPLEMENTED_BY", {}).values()}
        tests = set().union(*all_calls.values())
        entries = set(scoped.get("entrypoints", []))
        writers = {f"{path}:{symbol}" for path in component_files(scoped, inv)
                   for symbol, facts in raw["files"].get(path, {}).get("functions", {}).items()
                   if facts.get("writes") and symbol.rsplit(".", 1)[-1] != "__init__"}
        kinds = {anchor: explained_by(anchor, covered, excluded, tests=tests) for anchor in entries | writers}
        explained_entries = {anchor for anchor in entries if kinds[anchor]}
        explained_writers = {anchor for anchor in writers if kinds[anchor]}

        def sources(anchors):
            return tuple(sum(kinds[anchor] == kind for anchor in anchors) for kind in ("model", "test", "reason"))
        out[cid] = {"entrypoints": (len(explained_entries), len(entries)),
                    "state_writers": (len(explained_writers), len(writers)),
                    "entry_sources": sources(entries), "writer_sources": sources(writers),
                    "unexplained": tuple(sorted((entries - explained_entries) | (writers - explained_writers))),
                    "unexplained_entries": tuple(sorted(entries - explained_entries)),
                    "unlisted": len({f"{path}:{name}" for path in component_files(scoped, inv)
                                      for name in raw["files"].get(path, {}).get("entrypoints", ())} - entries)}
        if len(component_subtree(data, cid)) > 1:
            own_entries = set(component.get("entrypoints", []))
            own_files = set(component_files(component, inv))
            own_writers = {anchor for anchor in writers if anchor.partition(":")[0] in own_files}
            out[cid]["_direct"] = {"entrypoints": (len(own_entries & explained_entries), len(own_entries)),
                                   "state_writers": (len(own_writers & explained_writers), len(own_writers)),
                                   "entry_sources": sources(own_entries & entries), "writer_sources": sources(own_writers)}
    return out


def model_binding_notes(root: Path, data: dict, inv: Inventory | None = None, *, view=None, tree=None) -> list[Finding]:
    """Non-gating binding notes: design-only models still to bind; models whose guarding tests are not named."""
    out: list[Finding] = []
    if inv is None:
        from .inventory import build_inventory
        from .mapfile import ignore_patterns
        inv = build_inventory(root, ignore_patterns(data), write_cache=view is None, import_roots=tuple(data.get("import_roots", ())))
    if tree is None:
        tree = build_tree(root, data, inv, view=view)
    from .mapfile import process_model_reason
    unbound = [node for node in tree.nodes.values()
               if not any(node.contract.get("TESTED_BY", {}).values())
               and not process_model_reason(data, node.contract)]
    if not unbound:
        return out
    from .testtree import test_calls
    calls = {}
    for test in inv.tests:
        if test.endswith(".py"):
            try:
                calls[test] = test_calls(test, read_source(root / test), inv)
            except OSError:
                continue
    for node in unbound:
        contract = node.contract
        anchors = set(contract.get("IMPLEMENTED_BY", {}).values())
        calling = [f"{path}::{name}" for path, functions in calls.items()
                   for name, values in functions.items() if values & anchors]
        if calling:
            detail = (f"{len(calling)} test functions call its code ({calling[0]}"
                      + (f", +{len(calling)-1}" if len(calling) > 1 else "") + ")")
        else:
            detail = "no tests call its code; 0 bound tests"
        out.append(Finding("warn", "unbound_models", node.id, detail))
    return out


def model_coverage(root: Path, data: dict, registry=None, *, view=None) -> tuple[dict[str, set[str]], set[str]]:
    """Read declared implementation anchors and explicit negative scope once."""
    covered = {}
    not_modeled = set()
    for entry in (registry or model_registry(root, data, view=view)).entries:
        path = resolve_model_path(root, entry.path, view=view)
        if path is None:
            continue
        try:
            contract = read_model_contract(path)
        except (OSError, SyntaxError, ValueError):
            continue
        covered[entry.path] = set(contract.get("IMPLEMENTED_BY", {}).values())
        not_modeled.update(contract.get("NOT_MODELED", {}))
    return covered, not_modeled


PRECISE_ENTRY_KINDS = {"http_route", "cli_command", "console_script", "handler"}


def discovery_findings(raw: dict, data: dict, inv) -> list:
    """Lint findings from discovered behaviour: unlisted entrypoints, undeclared side effects."""

    owner, _ = owner_index(data, inv)
    declared_anchors = {a for c in data["components"] for a in c.get("entrypoints", [])}
    out = []
    missing: dict[tuple[str, str, bool], list[str]] = defaultdict(list)
    for path, file in sorted(raw["files"].items()):
        comp = owner.get(path)
        if not comp or "functions" not in file:
            continue
        for ep in file["entrypoints"]:
            if ep["kind"] == "main_guard":
                continue
            anchor = f"{path}:{ep['symbol']}"
            if anchor in declared_anchors:
                continue
            precise = ep["kind"] in PRECISE_ENTRY_KINDS and ep.get("via") != "argparse"
            missing[(comp, anchor, precise)].append(f"{ep['kind']} {ep['name']}")
    groups: dict[tuple[str, bool], list[tuple[str, list[str]]]] = defaultdict(list)
    for (comp, anchor, precise), names in sorted(missing.items()):
        groups[(comp, precise)].append((anchor, names))
    for (comp, precise), entries in sorted(groups.items()):
        level = "warn" if precise else "info"
        if len(entries) > 3:
            sample = ", ".join(anchor for anchor, _ in entries[:3])
            out.append(Finding(level, "entrypoint_unlisted", comp,
                               f"{len(entries)} entrypoints (e.g. {sample}) are not in any component's entrypoints; "
                               f"full list: python -m flowguard map discover --component {comp}"))
        else:
            for anchor, names in entries:
                shown = ", ".join(names[:6]) + (f" ... +{len(names) - 6}" if len(names) > 6 else "")
                out.append(Finding(level, "entrypoint_unlisted", comp,
                                   f"{shown} -> {anchor} is not in any component's entrypoints"))
    for c in data["components"]:
        if c.get("side_effects"):
            continue
        counts: dict[str, int] = defaultdict(int)
        for path in component_files(c, inv):
            for fn in raw["files"].get(path, {}).get("functions", {}).values():
                for kind, _call, _line in fn["effects"]:
                    counts[kind] += 1
        if counts:
            text = ", ".join(f"{k} x{v}" for k, v in sorted(counts.items()))
            out.append(Finding("info", "effects_undeclared", c["id"], f"code shows side effects ({text}) but side_effects is empty"))
    by_id = {comp["id"]: comp for comp in data["components"]}
    adjacency = raw["edges"]
    for flow in data.get("flows", []):
        earlier = set()
        for step in flow.get("steps", []):
            cid, symbol, handoff = flow_step_parts(step)
            if cid not in by_id or not symbol:
                continue
            nodes = {f"{path}#{symbol}" for path in component_files(by_id[cid], inv)}
            if handoff:
                # A separate command reads an earlier step's file: it must be a listed entrypoint.
                scoped = component_scope(data, by_id[cid])
                entries = {entry for entry in scoped.get("entrypoints", []) if entry.partition(":")[2] == symbol}
                if not entries:
                    path = next((node.partition("#")[0] for node in sorted(nodes)
                                 if symbol in raw["files"].get(node.partition("#")[0], {}).get("functions", {})),
                                (component_files(scoped, inv) or ["<path>"])[0])
                    out.append(Finding("info", "flow_handoff_not_entrypoint", cid,
                                       f"flow {flow['id']}: step {step} is reached through a file, so it must be a "
                                       f"command entrypoint; list {path}:{symbol} in {cid}'s entrypoints"))
            elif earlier:
                reached, pending = set(earlier), list(earlier)
                while pending and len(reached) < 2000:
                    for dst in adjacency.get(pending.pop(), []):
                        if dst not in reached:
                            reached.add(dst)
                            pending.append(dst)
                if not nodes & reached:
                    out.append(Finding("info", "flow_step_unreached", cid,
                                       f"flow {flow['id']}: step {step} is not reached from earlier steps in the static call graph; verify or reorder"))
            earlier.update(nodes)
    return out


def flow_unmodeled_findings(raw: dict, data: dict, inv: Inventory, tree) -> list[Finding]:
    """A flow without a model that crosses modeled code or reaches a durable effect."""
    by_id = {comp["id"]: comp for comp in data["components"]}
    out = []
    for flow in data.get("flows", []):
        if flow.get("model"):
            continue
        message = ""
        for step in flow.get("steps", []):
            cid, symbol, _ = flow_step_parts(step)
            if cid not in by_id:
                continue
            models = tree.models_for_component(cid)
            if models:
                message = (f"flow {flow['id']} crosses {cid} (model {models[0].id}) but has no model; give the flow a "
                           f'model, for example "model": "{models[0].path}"')
                break
            for path in component_files(by_id[cid], inv) if symbol else ():
                if symbol in raw["files"].get(path, {}).get("functions", {}):
                    effects = sorted(set(reachable_effects(raw, f"{path}#{symbol}")) & {"db", "network", "fs_write", "fs_delete"})
                    if effects:
                        message = (f"flow {flow['id']} reaches {effects[0]} in {cid} but has no model; give the flow a "
                                   'model, for example "model": ".flowguard/models/<model>.py"')
                        break
            if message:
                break
        if message:
            out.append(Finding("info", "flow_unmodeled", "", message))
    return out


def dependency_import_sites(root: Path, data: dict, inv: Inventory, src: str, dst: str) -> list[str]:
    """Explain a verified dependency using concrete import lines, without a second graph."""
    components = {comp["id"]: comp for comp in data["components"]}
    destination = set(component_files(components[dst], inv))
    modules = {info.module: path for path, info in inv.py.items()}
    found = []
    for path in component_files(components[src], inv):
        if not (inv.file_deps.get(path, set()) & destination) or path not in inv.py:
            continue
        try:
            tree = ast.parse(read_source(root / path))
        except (OSError, SyntaxError, ValueError):
            continue
        info = inv.py[path]
        package = info.module if path.endswith("__init__.py") else info.module.rpartition(".")[0]
        stack = [tree]
        while stack:
            node = stack.pop()
            if is_type_checking_guard(node):
                stack.extend(node.orelse)
                continue
            stack.extend(ast.iter_child_nodes(node))
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                parts = package.split(".") if package else []
                if node.level:
                    parts = parts[:len(parts) - node.level + 1]
                    base = ".".join([*parts, *([node.module] if node.module else [])])
                else:
                    base = node.module or ""
                imports = [f"{base}:{alias.name}" for alias in node.names]
            else:
                continue
            if any(resolve_import(imp, modules, importer=path, py_paths=inv.py, import_roots=inv.import_roots) in destination for imp in imports):
                found.append((path, node.lineno, ast.unparse(node)))
    return [f"{path}:{line} {text}" for path, line, text in sorted(found)]


ARCHITECTURE_CODES = {"dependency_cycle", "layer_violation", "duplicate_owner", "possible_duplicate",
                      "duplicate_code", "foreign_state_write", "private_cross_component_use", "large_component", "large_file", "too_many_responsibilities", "high_fan_out"}


def private_name(name: str) -> bool:
    """Exactly one leading underscore: ``_helper`` is private, ``__version__`` is not."""
    return name.startswith("_") and not name.startswith("__")


def private_use_findings(root: Path, data: dict, inv: Inventory) -> list[Finding]:
    """A component importing or using another component's ``_private`` name (tests and models excluded)."""
    owner, _ = owner_index(data, inv)
    modules = {info.module: path for path, info in inv.py.items()}
    seen, out = set(), []
    for path, info in sorted(inv.py.items()):
        user = owner.get(path)
        if user is None or inv.is_test(path):
            continue
        for imported in sorted(info.imports):
            module, separator, name = imported.partition(":")
            target = resolve_import(imported, modules, importer=path, py_paths=inv.py, import_roots=inv.import_roots) if separator else None
            holder = owner.get(target or "")
            if not separator or not private_name(name) or holder is None or holder == user or (user, holder, name) in seen:
                continue
            seen.add((user, holder, name))
            line = info.import_lines.get(imported) or _name_line(root, path, name)
            out.append(Finding("warn", "private_cross_component_use", user,
                               f"{user} uses {holder}'s private {name} at {path}:{line}; "
                               f"make it public in {holder} or move this code into {holder}"))
    return out


def _name_line(root: Path, path: str, name: str) -> int:
    try:
        tree = ast.parse(read_source(root / path))
    except (OSError, SyntaxError, ValueError):
        return 0
    return min((node.lineno for node in ast.walk(tree) if isinstance(node, ast.Attribute) and node.attr == name), default=0)


def scoped_architecture_findings(root: Path, data: dict, inv: Inventory,
                                 component_ids: list[str] | set[str], *, findings: list[Finding] | None = None, view=None) -> list[Finding]:
    """Architecture findings for directly changed owners; reuse an already computed lint when supplied."""
    selected = set(component_ids)
    if not selected:
        return []
    findings = run_lint(root, data, inv, view=view) if findings is None else findings
    return [finding for finding in findings if finding.code in ARCHITECTURE_CODES
            and (finding.component in selected or
                 any(re.search(rf"(?<![\w.-]){re.escape(component)}(?![\w.-])", finding.message) for component in selected)
                 and finding.code in {"dependency_cycle", "duplicate_code", "duplicate_owner", "possible_duplicate"})]


def explained_by(anchor, covered, not_modeled=(), *, tests=""):
    """One static explanation: "model" (an IMPLEMENTED_BY anchor), "reason" (NOT_MODELED), "test"
    (its name is a whole word in the component's tests) or None. Lint leaves the test text empty."""
    if anchor in covered:
        return "model"
    if anchor in not_modeled:
        return "reason"
    return "test" if not isinstance(tests, str) and anchor in tests else None


def model_writer_findings(raw: dict, data: dict, root: Path, inv: Inventory, registry=None, *, view=None) -> list[Finding]:
    """Other exact functions in an anchor's own file that write its modeled state."""
    contracts = []
    excluded = set()
    for entry in (registry or model_registry(root, data, view=view)).entries:
        path = resolve_model_path(root, entry.path, view=view)
        if path is None:
            continue
        try:
            contract = read_model_contract(path)
        except (OSError, SyntaxError, ValueError):
            continue
        contracts.append((entry, contract))
        excluded.update(contract.get("IMPLEMENTED_BY", {}).values())
        excluded.update(contract.get("NOT_MODELED", {}))
    owner, _ = owner_index(data, inv)
    out = []
    for entry, contract in contracts:
        by_file = defaultdict(list)
        for anchor in sorted(contract.get("IMPLEMENTED_BY", {}).values()):
            writes = anchor_state_writes(raw, anchor)
            if writes:
                by_file[anchor.split(":", 1)[0]].append((anchor, writes))
        for path, anchors in sorted(by_file.items()):
            for symbol, function in sorted(raw["files"][path].get("functions", {}).items()):
                writer = f"{path}:{symbol}"
                if symbol.rsplit(".", 1)[-1] == "__init__" or explained_by(writer, excluded):
                    continue
                overlap = sorted((state, anchor) for anchor, writes in anchors
                                 for state in writes.intersection(function.get("writes", [])))
                if overlap:
                    state, anchor = overlap[0]
                    out.append(Finding("warn", "model_writer_unbound", owner.get(path, ""),
                        f"{writer} writes {state}, which model {entry.id} covers through {anchor}; "
                        "add it to IMPLEMENTED_BY, or to NOT_MODELED with a reason"))
    return out


def entrypoint_coverage_findings(raw: dict, data: dict, inv: Inventory,
                                 covered_by_model: dict[str, set[str]], *, not_modeled: set[str] | None = None,
                                 models_by_component: dict[str, list[str]] | None = None) -> list[Finding]:
    """Check external or dangerous declared entries against model anchors or explicit reasons."""
    out = []
    dangerous = {"db", "network", "fs_write", "fs_delete"}
    for comp in data["components"]:
        paths = models_by_component.get(comp["id"], []) if models_by_component is not None else comp.get("models", [])
        covered = set().union(*(covered_by_model.get(model, set()) for model in paths))
        for anchor in comp.get("entrypoints", []):
            if explained_by(anchor, covered, not_modeled or set()):
                continue
            path, sep, symbol = anchor.partition(":")
            if not sep:
                continue
            file = raw["files"].get(path, {})
            functions = file.get("functions", {})
            names = [symbol] if symbol in functions else [name for name in functions if name.endswith("." + symbol)]
            precise = sorted({entry["kind"] for entry in file.get("entrypoints", [])
                              if entry["symbol"] in names and entry["kind"] in PRECISE_ENTRY_KINDS
                              and entry.get("via") != "argparse"})
            if precise:
                out.append(Finding("warn", "entrypoint_unmodeled", comp["id"],
                                   f"external promise {anchor} ({', '.join(precise)}) has no model anchor; "
                                   "model it, or declare NOT_MODELED with a reason"))
                continue
            effects = set().union(*(set(reachable_effects(raw, f"{path}#{name}")) for name in names))
            if effects & dangerous:
                out.append(Finding("warn", "entrypoint_unmodeled", comp["id"],
                                   f"{anchor} reaches {', '.join(sorted(effects & dangerous))} without a model anchor; "
                                   "model it, or declare NOT_MODELED with a reason"))
    return out


def layer_findings(data: dict, graph: dict[str, set[str]], *,
                   root: Path | None = None, inv: Inventory | None = None) -> list[Finding]:
    """Cheap layer review reusable by check; lint adds concrete import sites when inventory is available."""
    rank = {name: index for index, name in enumerate(data.get("layers", []))}
    layer_of = {component["id"]: component.get("layer", "") for component in data["components"]}
    out = []
    for src, destinations in sorted(graph.items()):
        for dst in sorted(destinations):
            lower, higher = layer_of.get(src), layer_of.get(dst)
            if lower in rank and higher in rank and rank[higher] < rank[lower]:
                sites = dependency_import_sites(root, data, inv, src, dst) if root is not None and inv is not None else []
                cause = "; imports: " + ", ".join(sites[:3]) if sites else ""
                out.append(Finding("error", "layer_violation", src,
                                   f"{lower} -> {higher} ({dst}): a lower layer imports a higher one" + cause))
    return out


# Fixed, comparable thresholds. Only elapsed-time advice is configurable.
SIZE_LIMITS = {'rules': (8, 12), 'sequences': (2000, 10000)}


def split_recipe(model):
    return ('a staged model becomes a coarse parent plus one child per stage, a model of alternatives a dispatch parent plus one child per branch '
            f'(PARENT = "{model}"; DISPATCH); different aspects, and parts other models also use, become independent models; '
            'a test file that tests only this model is split with it (references/routes.md#Split a model)')


def size_finding(model, kind, count):
    soft, hard = SIZE_LIMITS[kind]
    if count is None or count <= soft:
        return None
    unit = 'rules' if kind == 'rules' else 'explored sequences'
    quantity = str(count) if kind == 'rules' else f'{count:,}'
    limit = (lambda number: str(number)) if kind == 'rules' else (lambda number: f'{number:,}')
    detail = (f'{quantity} {unit}, over the hard limit {limit(hard)}; split it in a target' if count>hard else
              f'{quantity} {unit} (soft limit {limit(soft)}; split before {limit(hard)})')
    return Finding('error' if count>hard else 'warn','large_model',model,detail+': '+split_recipe(model))


def model_size_findings(root, data, inv, *, view=None, tree=None):
    from .modelstatic import rule_count
    if tree is None:
        tree = build_tree(root, data, inv, view=view)
    return [finding for mid, node in tree.nodes.items()
            if (finding := size_finding(mid, 'rules', rule_count(root,node.path,view=view))) is not None]
