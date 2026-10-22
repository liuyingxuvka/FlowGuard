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
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .common import Finding, read_source, tokens
from .discover import discover_inventory, reachable_effects
from .inventory import Inventory, is_type_checking_guard, parse_python, resolve_import
from .tree import build_tree
from .mapfile import component_files, component_graph, dependency_evidence, model_registry, owner_index, read_model_contract

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


def run_lint(root: Path, data: dict, inv: Inventory, limits: Limits | None = None) -> list[Finding]:
    limits = limits or Limits()
    out: list[Finding] = []
    comps = data["components"]
    graph = component_graph(data, inv)
    for cycle in find_cycles(graph):
        sites = [site for src in cycle for dst in sorted(graph[src] & set(cycle))
                 for site in dependency_import_sites(root, data, inv, src, dst)]
        evidence = "; imports: " + ", ".join(sites[:4]) if sites else ""
        if len(sites) > 4:
            evidence += f" ... +{len(sites) - 4} import sites"
        out.append(Finding("error", "dependency_cycle", cycle[0], " <-> ".join(cycle) + evidence))

    out.extend(layer_findings(data, graph, root=root, inv=inv))

    claims: dict[str, set[str]] = defaultdict(set)
    rows = []
    for c in comps:
        for r in c.get("responsibilities", []):
            tok = tokens(r)
            if tok:
                claims[" ".join(sorted(tok))].add(c["id"])
                rows.append((c["id"], r, tok))
    for key, owners in sorted(claims.items()):
        if len(owners) > 1:
            out.append(Finding("error", "duplicate_owner", sorted(owners)[0], f"responsibility {key!r} is claimed by {sorted(owners)}"))
    for i, (ca, ra, ta) in enumerate(rows):
        for cb, rb, tb in rows[i + 1:]:
            if ca != cb:
                similarity = len(ta & tb) / len(ta | tb)
                if 0.6 <= similarity < 1.0:
                    out.append(Finding("warn", "possible_duplicate", ca, f"{ra!r} ~ {cb}: {rb!r} (similarity {similarity:.2f})"))

    for c in comps:
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

    owner, _ = owner_index(data, inv)
    by_body: dict[str, list[tuple[str, str, int]]] = defaultdict(list)
    for f, info in inv.py.items():
        if not inv.is_test(f):
            for symbol, digest, size in info.bodies:
                by_body[digest].append((f, symbol, size))
    for sites in by_body.values():
        if len(sites) > 1:
            hit = sorted({owner.get(f, "?") for f, _, _ in sites})
            where = ", ".join(f"{f}:{s}" for f, s, _ in sites[:4]) + (" ..." if len(sites) > 4 else "")
            out.append(Finding("warn" if len(hit) > 1 else "info", "duplicate_code", hit[0],
                               f"{len(sites)} identical bodies ({sites[0][2]} AST nodes) in {hit}: {where}"))

    raw = discover_inventory(root, inv)
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
                if target_owner and owner.get(path) != target_owner and state_name in declared_state[target_owner]:
                    out.append(Finding("warn", "foreign_state_write", owner.get(path, ""),
                                       f"{path}:{symbol} line {function['line']} mutates {target_owner}'s declared state {state_name}; "
                                       "route the update through its owner"))
    imported = {t for deps in inv.file_deps.values() for t in deps}
    modules = {info.module: path for path, info in inv.py.items()}
    # Registered executable models/runners are real importers even though they are outside source ownership.
    for entry in model_registry(root, data).entries:
        info = parse_python(root, entry.path, entry.path.removesuffix(".py").replace("/", "."), collect_bodies=False)
        imported.update(target for imp in info.imports if (target := resolve_import(imp, modules)))
    entry_files = {a.split(":", 1)[0] for c in comps for a in c.get("entrypoints", [])}
    entry_files |= {path for path, facts in raw["files"].items() if facts.get("entrypoints")}
    for f in inv.source:
        if f in inv.py and not inv.is_test(f) and f not in imported and f not in entry_files \
                and not f.endswith(("__init__.py", "__main__.py", "setup.py", "conftest.py")) \
                and not any(symbol.startswith("pytest_") and "." not in symbol for symbol in inv.py[f].symbols):
            out.append(Finding("info", "never_imported", owner.get(f, ""), f"{f} is not imported by any repo file (dead code or an entrypoint?)"))
    out.extend(discovery_findings(raw, data, inv))
    covered_by_model, not_modeled = model_coverage(root, data)
    tree = build_tree(root, data, inv)
    out.extend(entrypoint_coverage_findings(raw, data, inv, covered_by_model, not_modeled=not_modeled,
        models_by_component={c["id"]: [n.path for n in tree.models_for_component(c["id"])] for c in comps}))
    out.extend(model_binding_notes(root, data, inv))
    debts = normalized_debts(data)
    out, used = apply_accepted_debts(out, debts)
    # A dep_unused debt is used by check while its declared edge has no other evidence.
    bare = dependency_evidence({**data, "accepted_debts": []}, inv)
    declared = {c["id"]: set(c.get("depends_on", [])) for c in comps}
    used |= {index for index, debt in enumerate(debts) if debt.get("code") == "dep_unused"
             and debt.get("contains") in declared.get(debt.get("component"), set())
             and debt.get("contains") not in bare.get(debt.get("component"), set())}
    for index, debt in enumerate(debts):
        if index not in used:
            out.append(Finding("warn", "debt_stale", debt.get("component", ""),
                               f"accepted debt matches no finding: {debt['reason']}"))
    return out


def model_binding_notes(root: Path, data: dict, inv: Inventory | None = None) -> list[Finding]:
    """Non-gating binding notes: design-only models still to bind; models whose guarding tests are not named."""
    out: list[Finding] = []
    if inv is None:
        from .inventory import build_inventory
        from .mapfile import ignore_patterns
        inv = build_inventory(root, ignore_patterns(data))
    tree = build_tree(root, data, inv)
    tested = {n.path for c in data.get("components", []) if c.get("tests") for n in tree.models_for_component(c["id"])}
    for entry in model_registry(root, data).entries:
        try:
            contract = read_model_contract(root / entry.path)
        except (OSError, SyntaxError, ValueError):
            continue
        if contract.get("DESIGN_ONLY"):
            out.append(Finding("warn", "model_design_only", "", f"{entry.path}: DESIGN_ONLY ({contract['DESIGN_ONLY']}); "
                               "bind it with IMPLEMENTED_BY and conformance() once the code exists"))
        elif not contract.get("TESTED_BY") and entry.path in tested:
            out.append(Finding("warn", "model_tests_unbound", "", f"{entry.path}: TESTED_BY names no test although its "
                               "component lists tests; name the tests that guard this model"))
    return out


def model_coverage(root: Path, data: dict, registry=None) -> tuple[dict[str, set[str]], set[str]]:
    """Read declared implementation anchors and explicit negative scope once."""
    covered = {}
    not_modeled = set()
    for entry in (registry or model_registry(root, data)).entries:
        try:
            contract = read_model_contract(root / entry.path)
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
            cid, sep, symbol = step.partition(":")
            if cid not in by_id or not sep:
                continue
            nodes = {f"{path}#{symbol}" for path in component_files(by_id[cid], inv)}
            if earlier:
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
            if any(resolve_import(imp, modules) in destination for imp in imports):
                found.append((path, node.lineno, ast.unparse(node)))
    return [f"{path}:{line} {text}" for path, line, text in sorted(found)]


ARCHITECTURE_CODES = {"dependency_cycle", "layer_violation", "duplicate_owner", "possible_duplicate",
                      "duplicate_code", "foreign_state_write", "large_component", "large_file", "too_many_responsibilities", "high_fan_out"}


def scoped_architecture_findings(root: Path, data: dict, inv: Inventory,
                                 component_ids: list[str] | set[str], *, findings: list[Finding] | None = None) -> list[Finding]:
    """Architecture findings for directly changed owners; reuse an already computed lint when supplied."""
    selected = set(component_ids)
    if not selected:
        return []
    findings = run_lint(root, data, inv) if findings is None else findings
    return [finding for finding in findings if finding.code in ARCHITECTURE_CODES
            and (finding.component in selected or
                 any(re.search(rf"(?<![\w.-]){re.escape(component)}(?![\w.-])", finding.message) for component in selected)
                 and finding.code in {"dependency_cycle", "duplicate_code", "duplicate_owner", "possible_duplicate"})]


def entrypoint_coverage_findings(raw: dict, data: dict, inv: Inventory,
                                 covered_by_model: dict[str, set[str]], *, not_modeled: set[str] | None = None,
                                 models_by_component: dict[str, list[str]] | None = None) -> list[Finding]:
    """Reverse check dangerous declared entries against their existing model anchors or explicit reasons."""
    out = []
    dangerous = {"db", "network", "fs_write", "fs_delete"}
    for comp in data["components"]:
        paths = models_by_component.get(comp["id"], []) if models_by_component is not None else comp.get("models", [])
        covered = set().union(*(covered_by_model.get(model, set()) for model in paths))
        for anchor in comp.get("entrypoints", []):
            if anchor in covered or anchor in (not_modeled or set()):
                continue
            path, sep, symbol = anchor.partition(":")
            if not sep:
                continue
            file = raw["files"].get(path, {})
            functions = file.get("functions", {})
            names = [symbol] if symbol in functions else [name for name in functions if name.endswith("." + symbol)]
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
