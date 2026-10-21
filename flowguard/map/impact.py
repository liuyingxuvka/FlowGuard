"""Change impact: declared and parsed callers, bound tests and executable models."""

from __future__ import annotations

import ast
import json
import os
import subprocess
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

from .common import DEFAULT_TEST_COMMAND, SOURCE_EXTS, git_paths, glob_match, is_collectable_test, is_product_file, is_test_file, matches_any, norm, read_source
from .inventory import Inventory
from .mapfile import component_files, component_graph, dependency_evidence, ignore_patterns, is_stale, model_registry, read_model_contract

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
    test_commands: dict[str, str] = field(default_factory=dict)
    no_checks: list[str] = field(default_factory=list)
    comment_only: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def changed_files(root: Path, base: str) -> list[str]:
    """Keep both sides of renames and deleted paths, plus untracked files."""
    files: set[str] = set()
    commands = (["git", "-C", str(root), "diff", "--name-status", "-z", "-M", base],
                ["git", "-C", str(root), "ls-files", "-o", "--exclude-standard", "-z"])
    for i, cmd in enumerate(commands):
        try:
            fields = git_paths(root, *cmd[3:])
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(os.fsdecode(exc.stderr or b"").strip() or f"failed: {' '.join(cmd)}") from exc
        if i == 1:
            files.update(norm(f) for f in fields)
            continue
        cursor = 0
        while cursor < len(fields):
            status = fields[cursor]
            count = 2 if status.startswith(("R", "C")) else 1
            files.update(norm(f) for f in fields[cursor + 1:cursor + 1 + count])
            cursor += 1 + count
    return sorted(f for f in files if "__pycache__" not in Path(f).parts and not f.endswith((".pyc", ".pyo"))
                  and not f.startswith(".flowguard/cache/"))


def project_relative(root: Path, path: str) -> str:
    """'C:\\repo\\shop\\api.py', '/repo/shop/api.py' or './shop/api.py' -> 'shop/api.py'."""
    candidate = Path(path)
    if candidate.is_absolute():
        try:
            return candidate.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            pass                                    # outside the project: reported as unmapped
    return norm(path)


def _previous_map(root: Path, base: str | None) -> dict | None:
    if base is None:
        return None
    res = subprocess.run(["git", "-C", str(root), "show", f"{base}:.flowguard/map.json"],
                         capture_output=True)                     # bytes: json.loads decodes UTF-8 itself
    try:
        data = json.loads(res.stdout) if res.returncode == 0 else None
        return data if isinstance(data, dict) and isinstance(data.get("components"), list) else None
    except ValueError:
        return None


def _comment_only(root: Path, base: str | None, path: str) -> bool:
    """An edited .py file whose AST equals its base version (comments or formatting only; docstrings count)."""
    if base is None or not path.endswith(".py"):
        return False
    old = subprocess.run(["git", "-C", str(root), "show", f"{base}:{path}"], capture_output=True)
    try:
        new = (root / path).read_bytes()
        return old.returncode == 0 and old.stdout != new and ast.dump(ast.parse(old.stdout)) == ast.dump(ast.parse(new))
    except (OSError, SyntaxError, ValueError):
        return False


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


def _tests_reaching(inv: Inventory, changed: list[str]) -> set[str]:
    """Runtime import closure including package initialization, without graph hubs."""
    targets = set(changed)
    collectable = {t for t in inv.tests if is_collectable_test(t) and inv.is_test(t)}
    out = set()
    for path in targets:
        if Path(path).name == "conftest.py":
            prefix = path.rpartition("/")[0]
            out.update(t for t in collectable if not prefix or t.startswith(prefix + "/"))
    reverse: dict[str, set[str]] = defaultdict(set)
    for path in inv.source:
        deps = set(inv.file_deps.get(path, ()))
        parts = Path(path).parts[:-1]
        deps.update("/".join((*parts[:i], "__init__.py")) for i in range(1, len(parts) + 1)
                    if "/".join((*parts[:i], "__init__.py")) in inv.py)
        for dep in deps:
            if dep != path:
                reverse[dep].add(path)
    seen, queue = set(targets), deque(targets)
    while queue:
        for caller in reverse.get(queue.popleft(), ()):
            if caller not in seen:
                seen.add(caller)
                queue.append(caller)
    return out | (seen & collectable)


def compute_impact(root: Path, data: dict, inv: Inventory, changed: list[str], depth: int | None = None,
                   *, base: str | None = None) -> Impact:
    """Select source caller closure; test/model edits retain only their explicit links."""
    if depth is not None and depth < 0:
        raise ValueError("impact depth must be nonnegative")
    changed = sorted({project_relative(root, f) for f in changed
                      if "__pycache__" not in Path(project_relative(root, f)).parts
                      and not f.endswith((".pyc", ".pyo")) and not project_relative(root, f).startswith(".flowguard/cache/")})
    previous = _previous_map(root, base) if ".flowguard/map.json" in changed else None
    # A comment-only edit keeps its owner in REVIEW but selects no callers, tests or models.
    comment_only = sorted(f for f in changed if _comment_only(root, base, f))
    by_id = {c["id"]: c for c in data["components"]}
    old_by_id = {c["id"]: c for c in (previous or {}).get("components", [])}
    inv.set_explicit_sources([p for comp in data["components"] for p in comp.get("files", [])])
    actual = component_graph(data, inv)
    evidence = dependency_evidence(data, inv)
    facades = {c["id"] for c in data["components"]
               if any(inv.py[f].lazy_exports for f in component_files(c, inv) if f in inv.py)}
    terminal = {(src, dst) for src in facades for dst in evidence.get(src, ()) - actual.get(src, set())}
    graph = {cid: set(edges) for cid, edges in actual.items()}
    declared_only = set()
    for comp in data["components"]:
        for dst in comp.get("depends_on", []):
            if dst in by_id:
                if dst not in evidence.get(comp["id"], ()):
                    declared_only.add((comp["id"], dst))
                if (comp["id"], dst) not in terminal:
                    graph.setdefault(comp["id"], set()).add(dst)
    for comp in old_by_id.values():
        for dst in comp.get("depends_on", []):
            if comp["id"] in by_id and (comp["id"], dst) not in terminal:
                graph.setdefault(comp["id"], set()).add(dst)
    reverse: dict[str, set[str]] = defaultdict(set)
    reverse_terminal: dict[str, set[str]] = defaultdict(set)
    for src, dsts in graph.items():
        for dst in dsts:
            reverse[dst].add(src)
    for src, dst in terminal:
        reverse_terminal[dst].add(src)
    test_bindings, model_bindings = _binding_indexes(data)
    old_tests, old_models = _binding_indexes(previous or {})
    registry = model_registry(root, data)
    registered = {entry.path: entry for entry in registry.entries}
    contract_inputs: dict[str, set[str]] = defaultdict(set)
    contract_tests: dict[str, set[str]] = defaultdict(set)
    for entry in registry.entries:
        if entry.kind != "contract":
            continue
        try:
            contract = read_model_contract(root / entry.path)
        except (OSError, SyntaxError, ValueError, TypeError):
            continue                    # registry/check reports the invalid contract
        for anchor in contract.get("IMPLEMENTED_BY", {}).values():
            contract_inputs[anchor.split(":", 1)[0]].add(entry.path)
        for anchors in contract.get("TESTED_BY", {}).values():
            for anchor in anchors:
                contract_tests[entry.path].add(anchor.split(":", 1)[0])
    direct, blocked, map_review = set(), [], []
    selected_model_paths, matched, seeds = set(), set(), set()
    matched_owners: dict[str, set[str]] = defaultdict(set)
    tests = {f for f in changed if f in inv.tests and is_collectable_test(f) and f not in comment_only}
    for f in changed:
        for comp in list(by_id.values()) + list(old_by_id.values()):
            if is_product_file(f, comp.get("files", [])):
                direct.add(comp["id"])
                matched.add(f)
                matched_owners[f].add(comp["id"])
                if f not in comment_only:
                    seeds.add(comp["id"])
        if f in comment_only:
            if _owner_model_paths(f, model_bindings) or any(glob_match(f, pat) for pat in test_bindings):
                matched.add(f)
            continue
        selected_model_paths.update(contract_inputs.get(f, ()))
        bound_models = _owner_model_paths(f, model_bindings)
        old_bound_models = _owner_model_paths(f, old_models)
        selected_model_paths.update(bound_models)
        if bound_models or old_bound_models:
            matched.add(f)
        # Changing a test does not imply changing its owning production component.
        # Select only this test and explicitly linked owner models.
        for pat, cids in test_bindings.items():
            if glob_match(f, pat) and inv.is_test(f):
                matched.add(f)
        for model, linked_tests in contract_tests.items():
            if f in linked_tests:
                selected_model_paths.add(model)
            if f == model:
                tests.update(linked_tests)
        if f.startswith((".flowguard/models/", ".flowguard/verification/")) and f.endswith(".py") \
                and not bound_models and not old_bound_models:
            if Path(f).parent.as_posix() == ".flowguard/models" and not Path(f).name.startswith("_"):
                selected_model_paths.add(f)
            else:
                blocked.append(f"{f}: no registered executable model/runner binding; declare its owner runner")
        if f not in inv.source and not f.startswith(".flowguard/models/") and f != ".flowguard/map.json":
            referenced = set()
            for t in inv.tests:
                if not is_collectable_test(t):
                    continue
                try:
                    text = read_source(root / t)
                except OSError:
                    continue
                if f in text or Path(f).name in text:
                    referenced.add(t)
            tests.update(referenced)
    if ".flowguard/map.json" in changed:
        if previous is None:
            if base is not None and subprocess.run(["git", "-C", str(root), "ls-files", "--error-unmatch", ".flowguard/map.json"],
                                                   capture_output=True).returncode == 0:
                blocked.append(".flowguard/map.json: previous map unavailable; verification scope cannot be compared")
        else:
            for cid in set(by_id) | set(old_by_id):
                now, old = by_id.get(cid), old_by_id.get(cid)
                if now is None or old is None or any(now.get(k, []) != old.get(k, []) for k in VERIFICATION_FIELDS):
                    direct.add(cid)
                    seeds.add(cid)
                elif {k: v for k, v in now.items() if k not in {"status", "fingerprint"}} != \
                     {k: v for k, v in old.items() if k not in {"status", "fingerprint"}}:
                    map_review.append(cid)
    affected, traversed = set(seeds), set(seeds)
    queue = deque((cid, 0) for cid in sorted(seeds))
    while queue:
        cid, distance = queue.popleft()
        if depth is not None and distance >= depth:
            continue
        affected.update(reverse_terminal.get(cid, ()))
        for caller in sorted(reverse.get(cid, ())):
            if caller not in traversed:
                affected.add(caller)
                traversed.add(caller)
                queue.append((caller, distance + 1))
    tests.update(_tests_reaching(inv, [f for f in changed if f not in comment_only]))
    owner_tests: dict[str, set[str]] = defaultdict(set)
    owner_models: dict[str, set[str]] = defaultdict(set)
    for cid in affected:
        for comp in (by_id.get(cid), old_by_id.get(cid)):
            if comp is None:
                continue
            owner_tests[cid].update(f for f in inv.tests
                                    if any(glob_match(f, pat) for pat in comp.get("tests", [])))
            owner_models[cid].update(path for path in comp.get("models", [])
                                     if comp is by_id.get(cid) or (root / path).is_file())
        tests.update(owner_tests[cid])
        selected_model_paths.update(owner_models[cid])
    for model in selected_model_paths:
        if model in changed:
            tests.update(contract_tests.get(model, ()))
    models = []
    id_counts: dict[str, int] = defaultdict(int)
    for entry in registry.entries:
        id_counts[entry.id] += 1
    for model in sorted(selected_model_paths):
        if model in registered and id_counts[registered[model].id] > 1:
            blocked.append(f"{model}: executable model id {registered[model].id!r} is duplicated; resolve its binding")
        elif model not in registered:
            details = [issue.message for issue in registry.issues if issue.path == model]
            blocked.append(f"{model}: " + ("; ".join(details) or "selected model is missing or is not an executable registered model"))
        else:
            models.append(model)
    uncertainty = [f"{src} -> {dst}: declared but unverified" for src, dst in sorted(declared_only)
                   if src in affected or dst in affected]
    owned_affected = {f for cid in affected if cid in by_id for f in component_files(by_id[cid], inv)}
    uncertainty.extend(f"{f}: dynamic imports may be unresolved; declare known component dependencies"
                       for f in sorted(inv.dynamic_files & owned_affected))
    tests = {t for t in tests if is_collectable_test(t) and inv.is_test(t)}
    test_commands = {}
    for test in sorted(tests):
        commands = {cmd for pat, cmd in data.get("test_commands", {}).items() if glob_match(test, pat)}
        if not commands:
            commands = {cmd for pat, cmd in (previous or {}).get("test_commands", {}).items()
                        if glob_match(test, pat)}
        if len(commands) == 1:
            test_commands[test] = next(iter(commands))
        elif commands:
            test_commands[test] = ""       # neither display nor run an arbitrary ambiguous command
            blocked.append(f"{test}: ambiguous test commands: {', '.join(sorted(commands))}")
        elif not test.endswith(".py"):
            blocked.append(f"{test}: no executable test command; declare test_commands or retire the test")
    covered = {f for f, cids in matched_owners.items()
               if any(owner_tests[cid] & tests or owner_models[cid] & set(models) for cid in cids)}
    no_checks = [f for f in changed if f not in inv.source and f not in covered and f != ".flowguard/map.json"
                 and not f.startswith(".flowguard/") and not any(
                     f in read_source(root / t) or Path(f).name in read_source(root / t)
                     for t in tests if (root / t).is_file())]
    return Impact(
        changed=changed, direct=sorted(direct), dependents=sorted(affected - direct),
        unmapped=[f for f in changed if f not in matched and not inv.is_test(f)
                  and (f in inv.source or Path(f).suffix in SOURCE_EXTS)
                  and not matches_any(f, ignore_patterns(data))],
        tests=sorted(tests), models=models,
        needs_review=[cid for cid in sorted(direct) if cid in by_id and is_stale(root, by_id[cid], inv)],
        test_command=data.get("test_command") or DEFAULT_TEST_COMMAND,
        total_tests=sum(is_collectable_test(t) for t in inv.tests),
        map_changed=".flowguard/map.json" in changed, depth=depth,
        uncertainty=uncertainty, blocked=sorted(set(blocked)), map_review=sorted(map_review),
        model_ids=[registered[m].id for m in models], test_commands=test_commands, no_checks=no_checks,
        comment_only=comment_only,
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
    lines.extend("NO CHECKS for: " + path for path in imp.no_checks)
    if imp.comment_only:
        lines.append("comment-only edits (no tests or models selected): " + ", ".join(imp.comment_only))
    lines.append(f"models to run: {len(imp.models)} selected (full list: python -m flowguard map impact --json)" if len(imp.models) > 8
                 else f"models to run: {', '.join(imp.models) or '-'}")
    groups: dict[str, list[str]] = defaultdict(list)
    no_command = []
    for test in imp.tests:
        command = next((cmd for pattern, cmd in imp.test_commands.items() if glob_match(test, pattern)), None)
        if command is None and test.endswith(".py"):
            command = imp.test_command
        if command:
            groups[command].append(test)
        else:
            no_command.append(test)
    broad = len(imp.tests) > 30
    if broad:
        lines.append(f"tests to run ({len(imp.tests)} of {imp.total_tests}): broad selection; run commands below (full list: python -m flowguard map impact --json)")
    else:
        # The executable command contains the list once; avoid repeating it above.
        lines.append(f"tests to run ({len(imp.tests)} of {imp.total_tests}): " + ("see run below" if imp.tests else "-"))
    for command, tests in groups.items():
        # Keep the executable command scoped even when its display is long.
        import shlex
        lines.append(f"run: {command} " + " ".join(shlex.quote(t) for t in tests))
    lines.extend("NO TEST COMMAND for: " + test for test in no_command)
    if imp.models:
        lines.append("run: python -m flowguard map models " + " ".join(imp.model_ids))
    for cid in imp.needs_review:
        lines.append(f"REVIEW {cid}: its files changed; update its description if behavior changed, then confirm {cid}")
    for cid in imp.map_review:
        lines.append(f"NOTE {cid}: map description changed; no verification fields changed")
    return "\n".join(lines)
