"""Architecture review computed from the map plus the real code.

Findings: dependency cycles, layer violations, duplicate or overlapping
responsibilities, duplicated function bodies across components, oversized
files/components, high fan-out, untested components, never-imported modules,
plus behaviour found by discovery: entrypoints no component lists and side
effects a component does not declare.
Entries in the map's ``accepted_debts`` downgrade matching findings to info.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .common import Finding, is_test_file, tokens
from .discover import discover_inventory
from .inventory import Inventory
from .mapfile import component_files, component_graph, owner_index

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


def apply_accepted_debts(findings: list[Finding], debts: list[dict]) -> list[Finding]:
    for f in findings:
        for debt in debts:
            if f.code == debt["code"] and debt.get("component", f.component) == f.component \
                    and debt.get("contains", "") in f.message:
                f.level, f.message = "info", f"{f.message} (accepted debt: {debt['reason']})"
                break
    return findings


def run_lint(root: Path, data: dict, inv: Inventory, limits: Limits | None = None) -> list[Finding]:
    limits = limits or Limits()
    out: list[Finding] = []
    comps = data["components"]
    graph = component_graph(data, inv)
    for cycle in find_cycles(graph):
        out.append(Finding("warn", "dependency_cycle", cycle[0], " <-> ".join(cycle)))

    rank = {name: i for i, name in enumerate(data.get("layers", []))}
    layer_of = {c["id"]: c.get("layer", "") for c in comps}
    for src, dsts in sorted(graph.items()):
        for dst in sorted(dsts):
            ls, ld = layer_of.get(src), layer_of.get(dst)
            if ls in rank and ld in rank and rank[ld] < rank[ls]:
                out.append(Finding("error", "layer_violation", src, f"{ls} -> {ld} ({dst}): a lower layer imports a higher one"))

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
        if not is_test_file(f):
            for symbol, digest, size in info.bodies:
                by_body[digest].append((f, symbol, size))
    for sites in by_body.values():
        if len(sites) > 1:
            hit = sorted({owner.get(f, "?") for f, _, _ in sites})
            where = ", ".join(f"{f}:{s}" for f, s, _ in sites[:4]) + (" ..." if len(sites) > 4 else "")
            out.append(Finding("warn" if len(hit) > 1 else "info", "duplicate_code", hit[0],
                               f"{len(sites)} identical bodies ({sites[0][2]} AST nodes) in {hit}: {where}"))

    raw = discover_inventory(root, inv)
    imported = {t for deps in inv.file_deps.values() for t in deps}
    entry_files = {a.split(":", 1)[0] for c in comps for a in c.get("entrypoints", [])}
    entry_files |= {path for path, facts in raw["files"].items() if facts.get("entrypoints")}
    for f in inv.source:
        if f in inv.py and not is_test_file(f) and f not in imported and f not in entry_files \
                and not f.endswith(("__init__.py", "__main__.py", "setup.py", "conftest.py")):
            out.append(Finding("info", "never_imported", owner.get(f, ""), f"{f} is not imported by any repo file (dead code or an entrypoint?)"))
    out.extend(discovery_findings(raw, data, inv))
    return apply_accepted_debts(out, data.get("accepted_debts", []))


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
    for (comp, anchor, precise), names in sorted(missing.items()):
        shown = ", ".join(names[:6]) + (f" ... +{len(names) - 6}" if len(names) > 6 else "")
        out.append(Finding("warn" if precise else "info", "entrypoint_unlisted", comp,
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
    return out
