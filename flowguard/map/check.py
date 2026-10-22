"""Map <-> code mutual verification.

Every finding is cheap and objective: ownership of every source file, anchors
that must exist, declared vs real dependencies, flows, model files and their
code anchors, and staleness of confirmed descriptions.
"""

from __future__ import annotations

import re
from pathlib import Path

from .common import Finding, glob_match, is_test_file, read_source, matches_any
from .inventory import Inventory
from .mapfile import component_files, component_graph, dependency_evidence, is_stale, model_registry, owner_index, read_model_contract

PLACEHOLDER_ANCHOR = "REPLACE_ME"          # templates ship anchors containing it; they fail until replaced


def symbol_defined(inv: Inventory, path: str, symbol: str) -> bool:
    """'name', 'Class.method', or a bare method name defined on any class in that file."""
    symbols = inv.py[path].symbols if path in inv.py else set()
    return symbol in symbols or any(s.endswith("." + symbol) for s in symbols)


def anchor_problem(root: Path, inv: Inventory, anchor: str) -> str | None:
    """None when 'path:Symbol' exists; otherwise a human-readable problem."""
    path, sep, symbol = anchor.partition(":")
    if PLACEHOLDER_ANCHOR in anchor:
        return f"placeholder anchor {anchor!r}: replace it with the real 'path:Symbol' this model is about"
    if not sep or not symbol:
        return f"anchor {anchor!r} must look like 'path/to/file.py:Symbol'"
    if not (root / path).is_file():
        return f"anchor file missing: {path}"
    if path in inv.py:
        if inv.py[path].parse_error:
            return f"cannot parse {path}: {inv.py[path].parse_error}"
        return None if symbol_defined(inv, path, symbol) else f"symbol {symbol!r} not found in {path}"
    text = read_source(root / path)
    last = symbol.split(".")[-1]
    return None if re.search(rf"\b{re.escape(last)}\b", text) else f"symbol {symbol!r} not found in {path}"


def anchor_problems(root: Path, anchors) -> dict[str, str]:
    """{anchor: problem} for each 'path:Symbol' that does not resolve; parses only the anchored files."""
    from .inventory import parse_python

    root, anchors = Path(root), list(anchors)
    paths = sorted({anchor.partition(":")[0] for anchor in anchors})
    parsed = {path: parse_python(root, path, path[:-3].replace("/", "."), collect_bodies=False)
              for path in paths if path.endswith(".py") and (root / path).is_file()}
    inv = Inventory(root, paths, paths, [], parsed, {}, {})
    return {anchor: problem for anchor in anchors if (problem := anchor_problem(root, inv, anchor))}


def run_check(root: Path, data: dict, inv: Inventory, *, strict: bool = False) -> list[Finding]:
    out: list[Finding] = []
    by_id = {c["id"]: c for c in data["components"]}
    owner, owners_all = owner_index(data, inv)
    for f, ids in sorted(owners_all.items()):
        if len(ids) > 1:
            out.append(Finding("error", "file_multi_owner", ids[0], f"{f} is also matched by {ids[1:]}"))
    unmapped = [f for f in inv.source if not is_test_file(f) and f not in owner]
    near: dict[str, set[str]] = {}
    for path, cid in (owner.items() if unmapped else ()):
        near.setdefault(path.rpartition("/")[0], set()).add(cid)
    for f in unmapped:
        here = sorted(near.get(f.rpartition("/")[0], ()))   # point at existing owners before a new component
        hint = (f"; the files next to it belong to {here[0]}: add it there unless it is a new responsibility"
                if len(here) == 1 else
                f"; the files next to it belong to {', '.join(here)}: add it to the one that owns its responsibility"
                if 1 < len(here) <= 4 else "")
        out.append(Finding("error", "file_unmapped", "", f"{f} has no owning component{hint}"))

    for path, info in sorted(inv.py.items()):
        if path in inv.source and (path in owner or not is_test_file(path)) and info.parse_error:
            out.append(Finding("error", "source_parse_error", owner.get(path, ""),
                               f"cannot parse {path}: {info.parse_error}"))
    registry = model_registry(root, data)
    for issue in registry.issues:
        out.append(Finding("error", issue.code, "", f"{issue.path}: {issue.message}"))

    from .tree import build_tree
    out.extend(build_tree(root, data, inv).findings)

    for flow in data.get("flows", []):
        for step in flow.get("steps", []):
            comp_id, _, symbol = step.partition(":")
            if comp_id not in by_id:
                out.append(Finding("error", "flow_step_unknown", "", f"flow {flow['id']}: step {step!r} names no component"))
            elif symbol:
                owned = component_files(by_id[comp_id], inv)
                python_only = all(f in inv.py for f in owned)
                if python_only and not any(symbol_defined(inv, f, symbol) for f in owned):
                    out.append(Finding("error", "flow_step_broken", comp_id,
                                       f"flow {flow['id']}: symbol {symbol!r} not found in component {comp_id}"))
        if flow.get("model") and not (root / flow["model"]).is_file():
            out.append(Finding("error", "model_missing", "", f"flow {flow['id']}: model file {flow['model']} missing"))

    referenced = {m for c in data["components"] for m in c.get("models", [])}
    referenced |= {f["model"] for f in data.get("flows", []) if f.get("model")}
    for entry in registry.entries:              # contract models and runners: one binding rule
        rel = entry.path
        path = root / rel
        try:
            contract = read_model_contract(path)
        except (SyntaxError, ValueError) as exc:
            out.append(Finding("error", "model_unreadable", "", f"{rel}: {exc}"))
            continue
        if entry.kind == "contract":
            if "MODEL_ID" not in contract or "build_explorer" not in contract["functions"]:
                out.append(Finding("error", "model_contract", "", f"{rel}: needs MODEL_ID and def build_explorer()"))
            if rel not in referenced:
                out.append(Finding("warn", "model_unreferenced", "", f"{rel} is not listed in any component's models"))
        if not contract.get("DESIGN_ONLY"):
            if not contract.get("IMPLEMENTED_BY"):
                out.append(Finding("error", "model_anchor_missing", "",
                                   f"{rel}: declares no IMPLEMENTED_BY anchors; name the real code it checks "
                                   "('path:Symbol'), or mark DESIGN_ONLY = '<reason>' while that code does not exist"))
            if entry.kind == "contract" and "conformance" not in contract["functions"]:
                out.append(Finding("error", "model_conformance_missing", "",
                                   f"{rel}: abstract boundary only: no conformance(); replay the real code or "
                                   "compare it as code facts, or mark DESIGN_ONLY = '<reason>'"))
        for comp_id in contract.get("COMPONENTS", []):
            if comp_id not in by_id:
                out.append(Finding("error", "model_component_unknown", "", f"{rel}: COMPONENTS names unknown {comp_id!r}"))
        required_owners = set(contract.get("COMPONENTS", []))
        required_owners.update(owner.get(anchor.split(":", 1)[0])
                              for anchor in contract.get("IMPLEMENTED_BY", {}).values())
        for cid in sorted(required_owners - {None}):
            if cid in by_id and rel not in by_id[cid].get("models", []):
                out.append(Finding("error", "model_binding_missing", cid,
                                   f"{rel}: add this model to models of its COMPONENTS/IMPLEMENTED_BY owner {cid}"))
        for invariant, anchors in contract.get("TESTED_BY", {}).items():
            for anchor in anchors:
                problem = anchor_problem(root, inv, anchor)
                if problem:
                    out.append(Finding("error", "model_test_broken", "", f"{rel}: {invariant} -> {problem}"))
        for block, anchor in contract.get("IMPLEMENTED_BY", {}).items():
            problem = anchor_problem(root, inv, anchor)
            if problem:
                out.append(Finding("error", "model_anchor_broken", "", f"{rel}: {block} -> {problem}"))

    bound_tests = [pat for comp in data["components"] for pat in comp.get("tests", [])]
    for test in inv.tests:
        if test not in owner and (Path(test).name.startswith("test_") or Path(test).name.endswith("_test.py")
                                   or ".test." in test or ".spec." in test) and not matches_any(test, bound_tests):
            out.append(Finding("warn", "test_unbound", "", f"{test}: no component lists this test in tests"))
    graph = component_graph(data, inv)
    evidence_graph = dependency_evidence(data, inv)
    from .lint import apply_accepted_debts, layer_findings
    out.extend(apply_accepted_debts(layer_findings(data, graph), data.get("accepted_debts", []))[0])
    stale_level = "error" if strict else "warn"
    for c in data["components"]:
        cid, files = c["id"], component_files(c, inv)
        if not files:
            out.append(Finding("error", "component_empty", cid, f"files {c.get('files')} match no source file"))
        for pat in c.get("files", []):
            if not any(glob_match(f, pat) for f in inv.source):
                out.append(Finding("warn", "pattern_dead", cid, f"files pattern {pat!r} matches nothing"))
        for anchor in c.get("entrypoints", []):
            problem = anchor_problem(root, inv, anchor)
            if problem:
                out.append(Finding("error", "anchor_broken", cid, problem))
        for pat in c.get("tests", []):
            if not any(glob_match(f, pat) for f in inv.files):
                out.append(Finding("error", "test_missing", cid, f"tests pattern {pat!r} matches nothing"))
        for m in c.get("models", []):
            if not (root / m).is_file():
                out.append(Finding("error", "model_missing", cid, f"model file {m} missing"))
        declared, actual = set(c.get("depends_on", [])), graph.get(cid, set())
        for d in sorted(declared - set(by_id)):
            out.append(Finding("error", "dep_unknown", cid, f"depends_on {d!r} is not a component"))
        for d in sorted(actual - declared):
            out.append(Finding("error", "dep_undeclared", cid, f"imports {d} but depends_on does not list it"))
        unverified = sorted((declared - evidence_graph.get(cid, set())) & set(by_id))
        if unverified:
            out.append(Finding("error", "dep_unused", cid,
                               f"no import, module literal or accepted debt evidence for: {', '.join(unverified)}"))
        if c["status"] == "draft":
            out.append(Finding(stale_level, "draft", cid, "description not confirmed yet"))
        elif not c.get("summary") or not c.get("responsibilities"):
            out.append(Finding("error", "confirmed_but_empty", cid, "a confirmed component needs summary and responsibilities"))
        elif is_stale(root, c, inv):
            out.append(Finding(stale_level, "stale", cid, "owned files changed since last confirm; re-read them, update the description if behavior changed, then confirm"))
    from .discover import discover_inventory
    from .lint import apply_accepted_debts, entrypoint_coverage_findings, model_coverage
    covered, not_modeled = model_coverage(root, data, registry)
    entry_findings = entrypoint_coverage_findings(discover_inventory(root, inv), data, inv, covered, not_modeled=not_modeled)
    out.extend(apply_accepted_debts(entry_findings, data.get("accepted_debts", []))[0])
    return out
