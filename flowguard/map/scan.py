"""Reverse-wrap step 1: propose draft components for a project that has no map yet."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from .common import SCHEMA, is_test_file
from .inventory import Inventory
from .mapfile import component_files, component_graph

MAX_DIR_FILES = 8    # a directory with more source files than this is split by name prefix, then per file


def propose_components(inv: Inventory) -> list[dict]:
    groups: dict[str, list[str]] = defaultdict(list)
    for f in inv.source:
        if not is_test_file(f):
            groups[f.rsplit("/", 1)[0] if "/" in f else "."].append(f)
    proposals = []
    for directory, files in sorted(groups.items()):
        if len(files) <= MAX_DIR_FILES:
            buckets = {"": files}
        else:
            by_prefix: dict[str, list[str]] = defaultdict(list)
            for f in files:
                by_prefix[Path(f).stem.strip("_").split("_", 1)[0] or "init"].append(f)
            buckets = {}
            for prefix, members in by_prefix.items():
                if len(members) >= 3:
                    buckets[prefix] = members
                else:
                    for m in members:
                        buckets[Path(m).stem.strip("_") or "init"] = [m]
        base = re.sub(r"^src(\.|$)", "", directory.replace("/", ".").strip(".")) or "root"
        for prefix, members in sorted(buckets.items()):
            cid = re.sub(r"[^a-z0-9_.-]", "_", (f"{base}.{prefix}" if prefix else base).lower())
            pats = sorted(members) if prefix else [
                (f"{directory}/*{ext}" if directory != "." else f"*{ext}") for ext in sorted({Path(m).suffix for m in members})]
            symbols = sorted({s for m in members if m in inv.py for s in inv.py[m].symbols
                              if not s.startswith("_") and "." not in s})
            proposals.append({
                "id": cid, "layer": "", "summary": "", "responsibilities": [], "files": pats,
                "entrypoints": [], "state": [], "side_effects": [], "depends_on": [], "tests": [],
                "models": [], "status": "draft", "fingerprint": "",
                "_hint": {"file_count": len(members), "loc": sum(inv.loc.get(m, 0) for m in members),
                          "public_symbols_sample": symbols[:12]},
            })
    return proposals


def guess_tests(comp_files: list[str], tests: list[str]) -> list[str]:
    """Test files named after a component file: test_<stem>.py, <stem>_test.py, <stem>.test.ts ..."""
    stems = {Path(f).stem.strip("_") for f in comp_files}
    found = []
    for t in tests:
        stem = Path(t).stem
        if not re.search(r"^test_|_test$|\.test$|\.spec$", stem):
            continue
        core = re.sub(r"^test_|_test$|\.test$|\.spec$", "", stem)
        if core in stems or any(core.startswith(s + "_") for s in stems if len(s) > 3):
            found.append(t)
    return sorted(found)


def new_map(root: Path, inv: Inventory) -> dict:
    comps = propose_components(inv)
    for c in comps:
        c["tests"] = guess_tests(component_files(c, inv), inv.tests)
    data = {"schema": SCHEMA, "project": root.resolve().name, "layers": [], "ignore": [],
            "test_command": "", "components": comps, "flows": [], "accepted_debts": []}
    graph = component_graph(data, inv)
    for c in comps:
        c["depends_on"] = sorted(graph[c["id"]])
    from .discover import component_summary, discover_inventory

    raw = discover_inventory(root, inv)
    for c in comps:
        found = component_summary(raw, component_files(c, inv))
        if found["entrypoints"] or found["effects"] or found["state_writers"]:
            c["_hint"]["discovered"] = {k: found[k] for k in ("entrypoints", "effects", "entrypoint_effect_reach", "state_writers") if found[k]}
    return data
