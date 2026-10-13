"""Map <-> code mutual verification.

Every finding is cheap and objective: ownership of every source file, anchors
that must exist, declared vs real dependencies, flows, model files and their
code anchors, and staleness of confirmed descriptions.
"""

from __future__ import annotations

import re
from pathlib import Path

from .common import MODELS_RELDIR, Finding, glob_match, is_test_file
from .inventory import Inventory
from .mapfile import component_files, component_graph, is_stale, owner_index, read_model_contract


def symbol_defined(inv: Inventory, path: str, symbol: str) -> bool:
    """'name', 'Class.method', or a bare method name defined on any class in that file."""
    symbols = inv.py[path].symbols if path in inv.py else set()
    return symbol in symbols or any(s.endswith("." + symbol) for s in symbols)


def anchor_problem(root: Path, inv: Inventory, anchor: str) -> str | None:
    """None when 'path:Symbol' exists; otherwise a human-readable problem."""
    path, sep, symbol = anchor.partition(":")
    if not sep or not symbol:
        return f"anchor {anchor!r} must look like 'path/to/file.py:Symbol'"
    if not (root / path).is_file():
        return f"anchor file missing: {path}"
    if path in inv.py:
        if inv.py[path].parse_error:
            return f"cannot parse {path}: {inv.py[path].parse_error}"
        return None if symbol_defined(inv, path, symbol) else f"symbol {symbol!r} not found in {path}"
    text = (root / path).read_text(encoding="utf-8", errors="replace")
    last = symbol.split(".")[-1]
    return None if re.search(rf"\b{re.escape(last)}\b", text) else f"symbol {symbol!r} not found in {path}"


def run_check(root: Path, data: dict, inv: Inventory, *, strict: bool = False) -> list[Finding]:
    out: list[Finding] = []
    by_id = {c["id"]: c for c in data["components"]}
    owner, owners_all = owner_index(data, inv)
    for f, ids in sorted(owners_all.items()):
        if len(ids) > 1:
            out.append(Finding("error", "file_multi_owner", ids[0], f"{f} is also matched by {ids[1:]}"))
    for f in inv.source:
        if not is_test_file(f) and f not in owner:
            out.append(Finding("error", "file_unmapped", "", f"{f} has no owning component"))

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
    models_dir = root / MODELS_RELDIR
    for path in sorted(models_dir.glob("*.py")) if models_dir.is_dir() else []:
        rel = path.relative_to(root).as_posix()
        try:
            contract = read_model_contract(path)
        except (SyntaxError, ValueError) as exc:
            out.append(Finding("error", "model_unreadable", "", f"{rel}: {exc}"))
            continue
        if "MODEL_ID" not in contract or "build_explorer" not in contract["functions"]:
            out.append(Finding("error", "model_contract", "", f"{rel}: needs MODEL_ID and def build_explorer()"))
        if rel not in referenced:
            out.append(Finding("warn", "model_unreferenced", "", f"{rel} is not listed in any component's models"))
        for comp_id in contract.get("COMPONENTS", []):
            if comp_id not in by_id:
                out.append(Finding("error", "model_component_unknown", "", f"{rel}: COMPONENTS names unknown {comp_id!r}"))
        for block, anchor in contract.get("IMPLEMENTED_BY", {}).items():
            problem = anchor_problem(root, inv, anchor)
            if problem:
                out.append(Finding("error", "model_anchor_broken", "", f"{rel}: {block} -> {problem}"))

    graph = component_graph(data, inv)
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
        for d in sorted((declared - actual) & set(by_id)):
            out.append(Finding("warn", "dep_unused", cid, f"depends_on lists {d} but no import was found"))
        if c["status"] == "draft":
            out.append(Finding(stale_level, "draft", cid, "description not confirmed yet"))
        elif not c.get("summary") or not c.get("responsibilities"):
            out.append(Finding("error", "confirmed_but_empty", cid, "a confirmed component needs summary and responsibilities"))
        elif is_stale(root, c, inv):
            out.append(Finding(stale_level, "stale", cid, "owned files changed since last confirm; re-read them, update the description if behavior changed, then confirm"))
    return out
