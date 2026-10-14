"""Reverse-wrap step 1: propose draft components for a project that has no map yet."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from .common import SCHEMA
from .inventory import Inventory
from .mapfile import component_files, component_graph

MAX_DIR_FILES = 8    # a directory with more source files than this is split by name prefix, then per file


def propose_components(inv: Inventory, max_components: int = 40) -> list[dict]:
    """Propose bounded directory owners, merging deepest directory groups first."""
    if max_components < 1:
        raise ValueError("max_components must be at least 1")
    groups: dict[str, list[str]] = defaultdict(list)
    for path in inv.source:
        if not inv.is_test(path):
            groups[str(Path(path).parent).replace("\\", "/")].append(path)
    recursive = set()
    while len(groups) > max_components:
        deepest = max(groups, key=lambda directory: (directory.count("/") + (directory != "."), directory))
        parent = str(Path(deepest).parent).replace("\\", "/")
        descendants = [directory for directory in groups
                       if parent == "." or directory == parent or directory.startswith(parent + "/")]
        members = [path for directory in descendants for path in groups.pop(directory)]
        groups[parent] = members
        recursive.difference_update(descendants)
        recursive.add(parent)
    total_loc = sum(inv.loc.get(path, 0) for paths in groups.values() for path in paths)
    # Split only an unusually dominant group, and only while the component budget permits it.
    buckets, split_count = [], 0
    for directory, files in sorted(groups.items()):
        loc = sum(inv.loc.get(path, 0) for path in files)
        by_prefix: dict[str, list[str]] = defaultdict(list)
        if len(files) > MAX_DIR_FILES and loc > total_loc * .25:
            for path in files:
                by_prefix[Path(path).stem.strip("_").split("_", 1)[0] or "init"].append(path)
        if len(by_prefix) > 1 and len(groups) + split_count + len(by_prefix) - 1 <= max_components:
            split_count += len(by_prefix) - 1
            buckets.extend((directory, prefix, members) for prefix, members in sorted(by_prefix.items()))
        else:
            buckets.append((directory, "", files))
    proposals, ids = [], set()
    for directory, prefix, members in buckets:
        base = re.sub(r"^src(\.|$)", "", directory.replace("/", ".").strip(".")) or "root"
        cid = re.sub(r"[^a-z0-9_.-]", "_", (f"{base}.{prefix}" if prefix else base).lower())
        original, suffix = cid, 2
        while cid in ids:
            cid, suffix = f"{original}.{suffix}", suffix + 1
        ids.add(cid)
        symbols = sorted({symbol for path in members if path in inv.py for symbol in inv.py[path].symbols
                          if not symbol.startswith("_") and "." not in symbol})
        if not prefix:
            marker = "**/" if directory in recursive else ""
            base_path = directory + "/" if directory != "." else ""
            patterns = [f"{base_path}{marker}*{extension}" for extension in sorted({Path(path).suffix for path in members})]
        else:
            # A split uses exact membership; the dominant-group split is deliberately uncommon.
            patterns = sorted(members)
        proposals.append({
            "id": cid, "layer": "", "summary": "", "responsibilities": [], "files": patterns,
            "entrypoints": [], "state": [], "side_effects": [], "depends_on": [], "tests": [],
            "models": [], "status": "draft", "fingerprint": "",
            "_hint": {"file_count": len(members), "loc": sum(inv.loc.get(path, 0) for path in members),
                      "public_symbols_sample": symbols[:8]},
        })
    return proposals


def guess_tests(comp_files: list[str], tests: list[str], inv: Inventory | None = None) -> list[str]:
    """Guess executable test modules by file name or a real import of owned code."""
    stems = {Path(f).stem.strip("_") for f in comp_files}
    found = []
    for t in tests:
        stem = Path(t).stem
        if not re.search(r"^test_|_test$|\.test$|\.spec$", stem):
            continue
        core = re.sub(r"^test_|_test$|\.test$|\.spec$", "", stem)
        if core in stems or any(core.startswith(s + "_") for s in stems if len(s) > 3):
            found.append(t)
        elif inv is not None and set(comp_files) & inv.file_deps.get(t, set()):
            found.append(t)
    return sorted(found)


def new_map(root: Path, inv: Inventory, max_components: int = 40) -> dict:
    comps = propose_components(inv, max_components)
    for c in comps:
        c["tests"] = guess_tests(component_files(c, inv), inv.tests, inv)
    data = {"schema": SCHEMA, "project": root.resolve().name, "layers": [], "ignore": [],
            "test_command": "", "components": comps, "flows": [], "accepted_debts": []}
    graph = component_graph(data, inv)
    for c in comps:
        c["depends_on"] = sorted(graph[c["id"]])
    return data
