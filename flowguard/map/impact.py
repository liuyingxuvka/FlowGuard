"""Change impact: declared and parsed callers, bound tests and executable models."""

from __future__ import annotations

import ast
import json
import re
import subprocess
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

from .common import DEFAULT_TEST_COMMAND, SOURCE_EXTS, glob_match, is_test_file, matches_any, norm
from .inventory import Inventory
from .mapfile import component_graph, is_stale, model_registry

VERIFICATION_FIELDS = ("files", "entrypoints", "depends_on", "tests", "models", "state", "side_effects")


@dataclass
class Impact:
    changed: list[str]
    direct: list[str]
    dependents: list[str]
    unmapped: list[str]
    tests: list[str]
    models: list[str]
    needs_review: list[str]
    test_command: str = DEFAULT_TEST_COMMAND
    total_tests: int = 0
    map_changed: bool = False
    depth: int | None = None
    uncertainty: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)
    map_review: list[str] = field(default_factory=list)
    model_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def changed_files(root: Path, base: str) -> list[str]:
    """Keep both sides of renames and deleted paths, plus untracked files."""
    files: set[str] = set()
    commands = (["git", "-C", str(root), "diff", "--name-status", "-z", "-M", base],
                ["git", "-C", str(root), "ls-files", "-o", "--exclude-standard", "-z"])
    for i, cmd in enumerate(commands):
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(res.stderr.strip() or f"failed: {' '.join(cmd)}")
        fields = res.stdout.rstrip("\0").split("\0") if res.stdout else []
        if i == 1:
            files.update(norm(f) for f in fields)
            continue
        cursor = 0
        while cursor < len(fields):
            status = fields[cursor]
            count = 2 if status.startswith(("R", "C")) else 1
            files.update(norm(f) for f in fields[cursor + 1:cursor + 1 + count])
            cursor += 1 + count
    return sorted(files)


def _previous_map(root: Path, base: str | None) -> dict | None:
    if base is None:
        return None
    res = subprocess.run(["git", "-C", str(root), "show", f"{base}:.flowguard/map.json"],
                         capture_output=True, text=True)
    try:
        data = json.loads(res.stdout) if res.returncode == 0 else None
        return data if isinstance(data, dict) and isinstance(data.get("components"), list) else None
    except ValueError:
        return None


def _binding_indexes(data: dict) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    tests: dict[str, set[str]] = defaultdict(set)
    models: dict[str, set[str]] = defaultdict(set)
    for comp in data.get("components", []):
        for pat in comp.get("tests", []):
            tests[pat].add(comp["id"])
        for path in comp.get("models", []):
            models[path].add(comp["id"])
    return tests, models


def _owner_model_paths(path: str, declared: dict[str, set[str]]) -> set[str]:
    parts = Path(path).parts
    if len(parts) >= 5 and parts[:3] == (".flowguard", "models", "owners"):
        runner = f".flowguard/verification/owners/{parts[3]}/run_checks.py"
        return {runner} if runner in declared else set()
    return {path} if path in declared else set()


def compute_impact(root: Path, data: dict, inv: Inventory, changed: list[str], depth: int | None = None,
                   *, base: str | None = None) -> Impact:
    """Conservative reverse closure; a depth limit is only used when explicitly given.

    The old map supplies change scope, never current execution authority. Declared
    edges are retained separately from the actual import graph and disclosed.
    """
    if depth is not None and depth < 0:
        raise ValueError("impact depth must be nonnegative")
    changed = sorted({norm(f) for f in changed})
    previous = _previous_map(root, base) if base is not None else None
    by_id = {c["id"]: c for c in data["components"]}
    old_by_id = {c["id"]: c for c in (previous or {}).get("components", [])}
    actual = component_graph(data, inv)
    graph = {cid: set(edges) for cid, edges in actual.items()}
    declared_only = set()
    for comp in data["components"]:
        for dst in comp.get("depends_on", []):
            if dst in by_id:
                if dst not in actual.get(comp["id"], ()):
                    declared_only.add((comp["id"], dst))
                graph.setdefault(comp["id"], set()).add(dst)
    # Preserve callers removed by a mapping edit when determining its change scope.
    for comp in old_by_id.values():
        for dst in comp.get("depends_on", []):
            if comp["id"] in by_id:
                graph.setdefault(comp["id"], set()).add(dst)
    reverse: dict[str, set[str]] = defaultdict(set)
    for src, dsts in graph.items():
        for dst in dsts:
            reverse[dst].add(src)
    test_bindings, model_bindings = _binding_indexes(data)
    old_tests, old_models = _binding_indexes(previous or {})
    direct, blocked, map_review = set(), [], []
    selected_model_paths = set()
    matched = set()
    for f in changed:
        for comp in list(by_id.values()) + list(old_by_id.values()):
            if matches_any(f, comp.get("files", [])) and not is_test_file(f):
                direct.add(comp["id"])
                matched.add(f)
        for pat, cids in list(test_bindings.items()) + list(old_tests.items()):
            if glob_match(f, pat):
                direct.update(cids)
                matched.add(f)
        bound_models = _owner_model_paths(f, model_bindings)
        old_bound_models = _owner_model_paths(f, old_models)
        for m in bound_models | old_bound_models:
            direct.update(model_bindings.get(m, set()) | old_models.get(m, set()))
        selected_model_paths.update(bound_models)
        if bound_models or old_bound_models:
            matched.add(f)
        if f.startswith((".flowguard/models/", ".flowguard/verification/")) and f.endswith(".py") \
                and not bound_models and not old_bound_models:
            # Top-level contracts are executable even when no component binds them.
            if Path(f).parent.as_posix() == ".flowguard/models" and not Path(f).name.startswith("_"):
                selected_model_paths.add(f)
            else:
                blocked.append(f"{f}: no registered executable model/runner binding; declare its owner runner")
    if ".flowguard/map.json" in changed:
        if previous is None:
            blocked.append(".flowguard/map.json: previous map unavailable; verification scope cannot be compared")
        else:
            for cid in set(by_id) | set(old_by_id):
                now, old = by_id.get(cid), old_by_id.get(cid)
                if now is None or old is None or any(now.get(k, []) != old.get(k, []) for k in VERIFICATION_FIELDS):
                    direct.add(cid)
                elif now != old:
                    map_review.append(cid)
    affected = set(direct)
    queue = deque((cid, 0) for cid in sorted(direct))
    while queue:
        cid, distance = queue.popleft()
        if depth is not None and distance >= depth:
            continue
        for caller in sorted(reverse.get(cid, ())):
            if caller not in affected:
                affected.add(caller)
                queue.append((caller, distance + 1))
    tests = {f for f in changed if f in inv.tests or is_test_file(f) and (root / f).is_file()}
    for cid in affected:
        comp = by_id.get(cid)
        if comp is None:
            continue
        for pat in comp.get("tests", []):
            tests.update(f for f in inv.files if glob_match(f, pat))
        selected_model_paths.update(comp.get("models", []))
    registry = model_registry(root, data)
    registered = {entry.path: entry for entry in registry.entries}
    models = []
    duplicate_ids = {entry.id for entry in registry.entries
                     if sum(other.id == entry.id for other in registry.entries) > 1}
    for m in sorted(selected_model_paths):
        if m in registered and registered[m].id in duplicate_ids:
            blocked.append(f"{m}: executable model id {registered[m].id!r} is duplicated; resolve its binding")
        elif m not in registered:
            details = [issue.message for issue in registry.issues if issue.path == m]
            blocked.append(f"{m}: " + ("; ".join(details) or "selected model is missing or is not an executable registered model"))
        else:
            models.append(m)
    uncertainty = [f"{src} -> {dst}: declared but unverified" for src, dst in sorted(declared_only)
                   if src in affected or dst in affected]
    for f in inv.source:
        if not any(matches_any(f, by_id[cid].get("files", [])) for cid in affected if cid in by_id):
            continue
        try:
            text = (root / f).read_text(encoding="utf-8")
        except OSError:
            continue
        unresolved = False
        if f.endswith(".py"):
            try:
                tree = ast.parse(text)
                unresolved = any(isinstance(node, ast.Call) and
                                 (getattr(node.func, "id", "") or getattr(node.func, "attr", ""))
                                 in {"__import__", "import_module"} for node in ast.walk(tree))
            except SyntaxError:
                unresolved = True
        elif Path(f).suffix in {".ts", ".tsx", ".js", ".jsx"}:
            unresolved = bool(re.search(r"\bimport\s*\(|\bfrom\s*['\"][^.][^'\"]*['\"]", text))
        if unresolved:
            uncertainty.append(f"{f}: dynamic/nonrelative imports may be unresolved; declare known component dependencies")
    return Impact(
        changed=changed, direct=sorted(direct), dependents=sorted(affected - direct),
        unmapped=[f for f in changed if f not in matched and not is_test_file(f)
                  and (f in inv.source or Path(f).suffix in SOURCE_EXTS)
                  and not f.startswith(".flowguard/")],
        tests=sorted(tests), models=models,
        needs_review=[cid for cid in sorted(direct) if cid in by_id and is_stale(root, by_id[cid], inv)],
        test_command=data.get("test_command") or DEFAULT_TEST_COMMAND, total_tests=len(inv.tests),
        map_changed=".flowguard/map.json" in changed, depth=depth,
        uncertainty=uncertainty, blocked=sorted(set(blocked)), map_review=sorted(map_review),
        model_ids=[registered[m].id for m in models],
    )


def render_impact(imp: Impact) -> str:
    lines = [f"changed files: {len(imp.changed)}  directly affected: {', '.join(imp.direct) or '-'}",
             f"dependents: {', '.join(imp.dependents) or '-'}"]
    if imp.depth is not None:
        lines.append(f"TRUNCATED impact: explicit --depth {imp.depth}; callers beyond this depth were not selected")
    if imp.unmapped:
        lines.append("UNMAPPED changed files (add each to one component's files): " + ", ".join(imp.unmapped))
    lines.extend("UNCERTAIN " + message for message in imp.uncertainty[:5])
    if len(imp.uncertainty) > 5:
        lines.append(f"UNCERTAIN {len(imp.uncertainty) - 5} more surfaces; use map impact --json for all paths")
    lines.extend("BLOCKED " + message for message in imp.blocked)
    lines.append(f"models to run: {', '.join(imp.models) or '-'}")
    lines.append(f"tests to run ({len(imp.tests)} of {imp.total_tests}): " + (" ".join(imp.tests) or "-"))
    if imp.tests:
        lines.append(f"run: {imp.test_command} {' '.join(imp.tests)}")
    if imp.models:
        lines.append("run: python -m flowguard.map models " + " ".join(imp.model_ids))
    for cid in imp.needs_review:
        lines.append(f"REVIEW {cid}: its files changed; update its description if behavior changed, then confirm {cid}")
    for cid in imp.map_review:
        lines.append(f"REVIEW {cid}: map description changed; no verification fields changed")
    return "\n".join(lines)
