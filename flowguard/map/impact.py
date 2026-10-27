"""Change impact: declared and parsed callers, bound tests and executable models."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import tempfile
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

from .common import DEFAULT_TEST_COMMAND, SOURCE_EXTS, git_paths, glob_match, is_collectable_test, is_product_file, is_test_file, matches_any, norm, normalize_newlines, read_source
from .inventory import Inventory
from .mapfile import component_files, component_scope, component_subtree, component_graph, dependency_evidence, flow_step_parts, ignore_patterns, is_stale, model_registry, read_model_contract, top_level_imports

from .tree import build_tree

VERIFICATION_FIELDS = ("files", "entrypoints", "depends_on", "tests", "models", "state", "side_effects", "parent")


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
    selected_test_functions: int = 0
    total_test_functions: int = 0
    map_changed: bool = False
    depth: int | None = None
    uncertainty: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)
    map_review: list[str] = field(default_factory=list)
    model_ids: list[str] = field(default_factory=list)
    test_commands: dict[str, str] = field(default_factory=dict)
    no_checks: list[str] = field(default_factory=list)
    comment_only: list[str] = field(default_factory=list)
    review_models: dict[str, list[str]] = field(default_factory=dict)
    relied_models: list[str] = field(default_factory=list)     # "<model> via <owner>:<anchor symbol>"
    flow_models: list[str] = field(default_factory=list)       # "flow <id>: step <n> changed; model <M>"
    port_lines: list[str] = field(default_factory=list)
    unexplained: list[str] = field(default_factory=list)       # "<component>: <path:symbol> (<entrypoint|state writer>)"

    changed_functions: list[str] = field(default_factory=list)
    uncertain_files: dict[str,str] = field(default_factory=dict)
    unreached: list[str] = field(default_factory=list)
    test_functions: dict[str,list[str]] = field(default_factory=dict)
    whole_test_files: list[str] = field(default_factory=list)
    model_reasons: dict[str,list[str]] = field(default_factory=dict)
    bound_test_count: int = 0
    calling_test_count: int = 0
    also_reached: list[str] = field(default_factory=list)
    no_git: str = ''
    consumer_lines: list[str] = field(default_factory=list)
    promise_lines: list[str] = field(default_factory=list)
    promise_findings: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {key: value for key, value in self.__dict__.items() if key != "_test_function_counts"}


def changed_files(root: Path, base: str, *, data=None, inv=None) -> list[str]:
    """Keep both sides of renames and deleted paths, plus untracked files."""
    files: set[str] = set()
    commands = (["git", "-C", str(root), "diff", "--name-status", "-z", "-M", base],
                ["git", "-C", str(root), "ls-files", "-o", "--exclude-standard", "-z"])
    for i, cmd in enumerate(commands):
        try:
            fields = _read_git_paths(root, *cmd[3:])
        except subprocess.CalledProcessError as exc:
            return _no_git_changes(root,data,inv)
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


def _broad_impact(
    root: Path,
    data: dict,
    inv: Inventory,
    changed: list[str],
    depth: int | None = None,
    *,
    base: str | None = None,
    broad: bool = False,
    package_init: bool = True,
) -> Impact:
    """Select source caller closure; test/model edits retain only their explicit links."""
    if depth is not None and depth < 0:
        raise ValueError("impact depth must be nonnegative")
    changed = sorted(
        {
            project_relative(root, f)
            for f in changed
            if "__pycache__" not in Path(project_relative(root, f)).parts
            and not f.endswith((".pyc", ".pyo"))
            and not project_relative(root, f).startswith(
                (".flowguard/cache/", ".flowguard/target/")
            )
        }
    )
    previous = _previous_map(root, base) if ".flowguard/map.json" in changed else None
    # A comment-only edit keeps its owner in REVIEW but selects no callers, tests or models.
    comment_only = sorted(f for f in changed if _comment_only(root, base, f))
    by_id = {c["id"]: c for c in data["components"]}
    old_by_id = {c["id"]: c for c in (previous or {}).get("components", [])}
    inv.set_explicit_sources([p for comp in data["components"] for p in comp.get("files", [])])
    actual = component_graph(data, inv)
    evidence = dependency_evidence(data, inv)
    facades = {
        c["id"]
        for c in data["components"]
        if any(inv.py[f].lazy_exports for f in component_files(c, inv) if f in inv.py)
    }
    terminal = {
        (src, dst) for src in facades for dst in evidence.get(src, ()) - actual.get(src, set())
    }
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
    removed, prior_contracts, historical_imports = _removed_model_context(root, base, changed)
    tree = build_tree(root, data, inv, historical_imports=historical_imports)
    test_bindings, model_bindings = _binding_indexes(data, tree)
    old_tests, old_models = _binding_indexes(previous or {})
    registry = model_registry(root, data)
    registered = {entry.path: entry for entry in registry.entries}
    contract_inputs: dict[str, set[str]] = defaultdict(set)
    contract_tests: dict[str, set[str]] = defaultdict(set)
    readonly_unchanged = set()
    uses_diffs = {}
    for entry in registry.entries:  # contract models bind code and tests in one way
        try:
            contract = read_model_contract(root / entry.path)
        except (OSError, SyntaxError, ValueError, TypeError):
            continue  # registry/check reports the invalid contract
        for anchor in contract.get("IMPLEMENTED_BY", {}).values():
            contract_inputs[anchor.split(":", 1)[0]].add(entry.path)
        uses = [
            anchor
            for anchor in contract.get("USES", {}).values()
            if anchor.partition(":")[0] in changed and anchor.partition(":")[0] not in comment_only
        ]
        hits = []
        for anchor in uses:
            path, _, symbol = anchor.partition(":")
            key = (path, symbol)
            if key not in uses_diffs:
                uses_diffs[key] = _anchor_changed(root, base, path, symbol)
            if uses_diffs[key]:
                contract_inputs[path].add(entry.path)
                hits.append(anchor)
        own_changed = any(
            anchor.partition(":")[0] in changed
            for anchor in contract.get("IMPLEMENTED_BY", {}).values()
        )
        if uses and not hits and not own_changed:
            readonly_unchanged.add(entry.path)
        for anchors in contract.get("TESTED_BY", {}).values():
            for anchor in anchors:
                contract_tests[entry.path].add(anchor.split(":", 1)[0])
    direct, blocked, map_review = set(), [], []
    selected_model_paths, matched, seeds = set(), set(), set()
    retired = set()
    matched_owners: dict[str, set[str]] = defaultdict(set)
    tests = {
        f for f in changed if f in inv.tests and is_collectable_test(f) and f not in comment_only
    }
    for f in changed:
        for comp in list(by_id.values()) + list(old_by_id.values()):
            if is_product_file(f, comp.get("files", [])):
                direct.add(comp["id"])
                matched.add(f)
                matched_owners[f].add(comp["id"])
                if f not in comment_only:
                    seeds.add(comp["id"])
        if f in comment_only:
            if _owner_model_paths(f, model_bindings) or any(
                glob_match(f, pat) for pat in test_bindings
            ):
                matched.add(f)
            continue
        selected_model_paths.update(contract_inputs.get(f, ()))
        for model in contract_inputs.get(
            f, ()
        ):  # anchored code changed: the model's named tests too
            tests.update(contract_tests.get(model, ()))
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
            if f == model or model in bound_models:
                tests.update(linked_tests)
        if (
            f.startswith((".flowguard/models/", ".flowguard/verification/"))
            and f.endswith(".py")
            and not bound_models
            and not old_bound_models
        ):
            if Path(f).parent.as_posix() == ".flowguard/models":
                if not Path(f).name.startswith("_"):
                    selected_model_paths.add(f)
            else:
                blocked.append(
                    f"{f}: no registered executable model binding; declare a contract model or remove this file"
                )
        if (
            f not in inv.source
            and not f.startswith(".flowguard/models/")
            and f != ".flowguard/map.json"
        ):
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
    referenced_models = {p for comp in data["components"] for p in comp.get("models", [])}
    referenced_models.update(flow["model"] for flow in data.get("flows", []) if flow.get("model"))
    current_ids = {entry.id for entry in registry.entries}
    prior_by_id = {contract["MODEL_ID"]: contract for contract in prior_contracts.values()}
    for path in sorted(removed.intersection(changed)):
        if Path(path).name.startswith("_"):
            continue
        selected_model_paths.add(path)
        contract = prior_contracts.get(path)
        if contract is None:
            continue  # unknown/malformed/ambiguous old contracts still fail
        mid = contract["MODEL_ID"]
        importers = tree.importers(path)
        dangling_children = {
            n.id
            for n in tree.nodes.values()
            if n.contract.get("PARENT") == mid
            and mid not in current_ids
            and mid not in by_id
            and mid != "system"
        }
        linked = importers | dangling_children
        linked.update(entry.id for entry in registry.entries if entry.id == mid)
        parent, seen = contract.get("PARENT"), set()
        while parent and parent not in by_id and parent != "system" and parent not in seen:
            seen.add(parent)
            if parent in tree.nodes:
                linked.add(parent)
                break
            parent = prior_by_id.get(parent, {}).get("PARENT")
        for linked_id in linked:
            node = tree.nodes[linked_id]
            selected_model_paths.add(node.path)
            tests.update(contract_tests.get(node.path, ()))
        prior_tests = {
            anchor.split(":", 1)[0]
            for anchors in contract.get("TESTED_BY", {}).values()
            for anchor in anchors
        }
        tests.update(prior_tests & set(inv.tests))
        if (
            path not in referenced_models
            and not importers
            and not dangling_children
            and not contract_inputs.get(path)
        ):
            retired.add(path)
            matched.add(path)
        else:
            blocked.append(
                f"{path}: removed model is still referenced by the current map, model tree or code anchors"
            )
    # Rules travel along direct calls: an edit that calls another component's anchored code selects its model.
    relied, unexplained = [], []
    edited_sources = [
        f for f in changed if f in inv.py and f not in comment_only and not inv.is_test(f)
    ]
    if edited_sources:
        from .discover import discover_inventory, relied_models
        from .lint import coverage_facts

        raw = discover_inventory(root, inv, data=data, write_cache=False)
        # Functions of the edited files that no model anchor, test or NOT_MODELED reason explains.
        for cid, record in sorted(coverage_facts(root, data, inv, tree, raw).items()):
            entries = set(record.get("unexplained_entries", ()))
            unexplained.extend(
                f"{cid}: {anchor} ({'entrypoint' if anchor in entries else 'state writer'})"
                for anchor in record["unexplained"]
                if anchor.partition(":")[0] in edited_sources
            )
        anchors = {
            mid: list(node.contract.get("IMPLEMENTED_BY", {}).values())
            for mid, node in tree.nodes.items()
        }
        for mid, sites in sorted(
            relied_models(raw, data, inv, anchors, files=edited_sources).items()
        ):
            node = tree.nodes[mid]
            selected_model_paths.add(node.path)
            tests.update(contract_tests.get(node.path, ()))
            relied.extend(f"{mid} via {owner}:{symbol}" for owner, symbol in sorted(sites))
    # A flow's model protects every step: a real edit to a step's code selects it.
    flow_lines = []
    registered_ids = {entry.path: entry.id for entry in registry.entries}
    for flow in data.get("flows", []):
        if not flow.get("model"):
            continue
        for number, step in enumerate(flow.get("steps", []), 1):
            cid, symbol, _ = flow_step_parts(step)
            if cid not in by_id:
                continue
            owned = set(component_files(component_scope(data, by_id[cid]), inv))
            hit = [
                f
                for f in changed
                if f in owned
                and f not in comment_only
                and (not symbol or f in inv.py and symbol in inv.py[f].symbols)
            ]
            if hit:
                selected_model_paths.add(flow["model"])
                tests.update(contract_tests.get(flow["model"], ()))
                flow_lines.append(
                    f"flow {flow['id']}: step {number} changed; model "
                    f"{registered_ids.get(flow['model'], flow['model'])}"
                )
    top_model_files = [
        f for f in changed if Path(f).parent.as_posix() == ".flowguard/models" and f.endswith(".py")
    ]
    importers = {f: tree.importers(f) for f in top_model_files}
    for f in top_model_files:
        if f not in comment_only:
            selected_model_paths.update(tree.nodes[mid].path for mid in importers[f])
            if f in registered:
                selected_model_paths.add(f)
            if importers[f] or f in registered:
                matched.add(f)
    if ".flowguard/map.json" in changed:
        if previous is None:
            if (
                base is not None
                and subprocess.run(
                    ["git", "-C", str(root), "ls-files", "--error-unmatch", ".flowguard/map.json"],
                    capture_output=True,
                ).returncode
                == 0
            ):
                blocked.append(
                    ".flowguard/map.json: previous map unavailable; verification scope cannot be compared"
                )
        else:
            for cid in set(by_id) | set(old_by_id):
                now, old = by_id.get(cid), old_by_id.get(cid)
                if now is not None:
                    now = {**now, "depends_on": sorted(set(now.get("depends_on", [])))}
                if old is not None:
                    old = {**old, "depends_on": sorted(set(old.get("depends_on", [])))}
                if (
                    now is None
                    or old is None
                    or any(now.get(k, []) != old.get(k, []) for k in VERIFICATION_FIELDS)
                ):
                    direct.add(cid)
                    seeds.add(cid)
                elif {k: v for k, v in now.items() if k not in {"status", "fingerprint"}} != {
                    k: v for k, v in old.items() if k not in {"status", "fingerprint"}
                }:
                    map_review.append(cid)
                if now is not None and old is not None and now.get("parent") != old.get("parent"):
                    # Keep a still-registered model whose explicitly protected old
                    # subsystem lost this member. Placement alone does not claim siblings.
                    for node in tree.nodes.values():
                        if any(
                            cid
                            in {member["id"] for member in component_subtree(previous, protected)}
                            for protected in node.contract.get("COMPONENTS", [])
                        ):
                            selected_model_paths.add(node.path)
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
    tests.update(
        _tests_reaching(
            inv, [f for f in changed if f not in comment_only], package_init=package_init
        )
    )
    owner_tests: dict[str, set[str]] = defaultdict(set)
    owner_models: dict[str, set[str]] = defaultdict(set)
    for cid in affected:
        for comp in (by_id.get(cid), old_by_id.get(cid)):
            if comp is None:
                continue
            owner_tests[cid].update(
                f for f in inv.tests if any(glob_match(f, pat) for pat in comp.get("tests", []))
            )
            if comp is by_id.get(cid):
                owner_models[cid].update(n.path for n in tree.models_for_component(cid))
            else:
                owner_models[cid].update(
                    path for path in comp.get("models", []) if (root / path).is_file()
                )
        if cid not in seeds:
            owner_models[cid].difference_update(readonly_unchanged)
        tests.update(owner_tests[cid])
        selected_model_paths.update(owner_models[cid])
    for model in selected_model_paths:
        if model in changed:
            tests.update(contract_tests.get(model, ()))
    from .port import model_port, port_selection, code_callers

    ports = {
        mid: node.contract["port"] for mid, node in tree.nodes.items() if "port" in node.contract
    }
    port_lines = []
    for path in top_model_files:
        if path in comment_only or path in removed or path not in registered:
            continue
        mid = registered[path].id
        if mid not in ports:
            continue
        blob = (
            subprocess.run(["git", "-C", str(root), "show", f"{base}:{path}"], capture_output=True)
            if base
            else None
        )
        available = blob is not None and blob.returncode == 0
        missing = False
        if blob is not None and not available:
            # Distinguish an actual new file from an unavailable revision/repository.
            missing = (
                subprocess.run(
                    ["git", "-C", str(root), "rev-parse", "--verify", base], capture_output=True
                ).returncode
                == 0
            )
        try:
            previous_port = model_port(normalize_newlines(blob.stdout)) if available else None
        except (SyntaxError, ValueError, TypeError):
            previous_port, available, missing = None, False, False
        chosen, line, _ = port_selection(
            mid,
            previous_port,
            ports[mid],
            tree,
            ports,
            new_model=missing,
            unavailable=not available and not missing,
        )
        if "(no model consumer)" in line:
            from .discover import discover_inventory

            scope = {
                path
                for cid in tree.nodes[mid].components
                if cid in by_id
                for path in component_files(by_id[cid], inv)
            }
            callers = code_callers(
                discover_inventory(root, inv, data=data, write_cache=False), tree.nodes[mid], scope
            )
            line = line.replace(
                "(no model consumer)",
                "(no model consumer; code callers: " + (", ".join(callers) or "-") + ")",
            )
        port_lines.append(line)
        selected_model_paths.update(tree.nodes[chosen_id].path for chosen_id, _ in chosen)
    if broad:
        while True:
            ancestors = {
                tree.nodes[mid].path
                for path in selected_model_paths
                if path in registered
                for mid in tree.ancestors(registered[path].id)
            }
            selected_ids = {
                registered[path].id for path in selected_model_paths if path in registered
            }
            review_children = {
                node.path
                for node in tree.nodes.values()
                if node.kind == "contract"
                and node.source == "PARENT"
                and node.parent_kind == "model"
                and node.parent in selected_ids
                and node.parent in tree.nodes
                and tree.nodes[node.parent].path in node.import_files | node.local_import_files
            }
            expanded = ancestors | review_children
            if expanded <= selected_model_paths:
                break
            selected_model_paths.update(expanded)
    models = []
    selected_model_paths.difference_update(retired)
    id_counts: dict[str, int] = defaultdict(int)
    for entry in registry.entries:
        id_counts[entry.id] += 1
    duplicate_ids = {mid for mid, count in id_counts.items() if count > 1}
    blocked.extend(
        f"executable model id {mid!r} is duplicated; resolve its binding"
        for mid in sorted(duplicate_ids)
    )
    for model in sorted(selected_model_paths):
        if model in registered and registered[model].id in duplicate_ids:
            continue
        elif model not in registered:
            details = [issue.message for issue in registry.issues if issue.path == model]
            blocked.append(
                f"{model}: "
                + (
                    "; ".join(details)
                    or "selected model is missing or is not an executable registered model"
                )
            )
        else:
            models.append(model)
    uncertainty = [
        f"{src} -> {dst}: declared but unverified"
        for src, dst in sorted(declared_only)
        if src in affected or dst in affected
    ]
    owned_affected = {
        f for cid in affected if cid in by_id for f in component_files(by_id[cid], inv)
    }
    uncertainty.extend(
        f"{f}: dynamic imports may be unresolved; declare known component dependencies"
        for f in sorted(inv.dynamic_files & owned_affected)
    )
    tests = {t for t in tests if is_collectable_test(t) and inv.is_test(t)}
    test_commands, command_problems = _commands_for_tests(data, previous, tests)
    blocked.extend(command_problems)
    covered = {
        f
        for f, cids in matched_owners.items()
        if any(owner_tests[cid] & tests or owner_models[cid] & set(models) for cid in cids)
    }
    no_checks = [
        f
        for f in changed
        if f not in inv.source
        and f not in covered
        and f != ".flowguard/map.json"
        and (
            not f.startswith(".flowguard/")
            or f in importers
            and Path(f).name.startswith("_")
            and not importers[f]
        )
        and not any(
            f in read_source(root / t) or Path(f).name in read_source(root / t)
            for t in tests
            if (root / t).is_file()
        )
    ]
    needs_review = [
        cid for cid in sorted(direct) if cid in by_id and is_stale(root, by_id[cid], inv)
    ]
    from .testtree import test_functions

    function_counts = {}
    for path in inv.tests if tests else ():
        if path.endswith(".py"):
            try:
                function_counts[path] = len(test_functions(read_source(root / path)))
            except OSError:
                pass
    report = Impact(
        changed=changed,
        direct=sorted(direct),
        dependents=sorted(affected - direct),
        unmapped=[
            f
            for f in changed
            if f not in matched
            and not inv.is_test(f)
            and (f in inv.source or Path(f).suffix in SOURCE_EXTS)
            and not matches_any(f, ignore_patterns(data))
        ],
        tests=sorted(tests),
        models=models,
        needs_review=needs_review,
        review_models={cid: [n.id for n in tree.models_for_component(cid)] for cid in needs_review},
        test_command=data.get("test_command") or DEFAULT_TEST_COMMAND,
        total_tests=sum(is_collectable_test(t) for t in inv.tests),
        selected_test_functions=sum(function_counts.get(path, 0) for path in tests),
        total_test_functions=sum(function_counts.values()),
        map_changed=".flowguard/map.json" in changed,
        depth=depth,
        uncertainty=uncertainty,
        blocked=sorted(set(blocked)),
        map_review=sorted(map_review),
        model_ids=[registered[m].id for m in models],
        test_commands=test_commands,
        no_checks=no_checks,
        comment_only=comment_only,
        relied_models=relied,
        flow_models=flow_lines,
        unexplained=list(dict.fromkeys(unexplained)),
        port_lines=port_lines,
    )
    report._test_function_counts = function_counts
    return report


def test_groups(imp: Impact) -> tuple[dict[str, list[str]], list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    no_command = []
    for test in imp.tests:
        command = next((cmd for pattern, cmd in imp.test_commands.items() if glob_match(test, pattern)), None)
        if command is None and test.endswith(".py"):
            command = imp.test_command
        if command:
            nodes=imp.test_functions.get(test)
            groups[command].extend(test+'::'+symbol.replace('.', '::') for symbol in nodes) if nodes else groups[command].append(test)
        else:
            no_command.append(test)
    return groups, no_command


def run_commands(imp: Impact, *, moving_models: set[str] | None = None) -> list[str]:
    """The exact commands of the ``run:`` lines, in order (tests per command, then the selected models)."""
    import shlex

    groups, _ = test_groups(imp)
    commands = []
    for command, tests in groups.items():
        line=f"{command} " + " ".join(shlex.quote(t) for t in tests)
        if len(line)>8000:
            line=f"{command} " + " ".join(shlex.quote(t) for t in dict.fromkeys(test.split('::',1)[0] for test in tests))
        commands.append(line)
    model_ids = [mid for path, mid in zip(imp.models, imp.model_ids) if path not in (moving_models or set())]
    if model_ids:
        commands.append("python -m flowguard map models " + " ".join(model_ids))
    return commands


def render_impact(
    imp: Impact,
    *,
    moving_models: set[str] | None = None,
    verbose: bool = False,
    unmapped: list[str] | None = None,
) -> str:
    missing = imp.unmapped if unmapped is None else unmapped
    selected = list(zip(imp.models, imp.model_ids))
    moving = [(path, mid) for path, mid in selected if path in (moving_models or set())]
    models = (
        [path for path, mid in selected if path not in (moving_models or set())]
        if moving_models
        else imp.models
    )
    model_ids = (
        [mid for path, mid in selected if path not in (moving_models or set())]
        if moving_models
        else imp.model_ids
    )
    lines = [
        f"changed files: {len(imp.changed)}  directly affected: {', '.join(imp.direct) or '-'}",
        f"dependents: {', '.join(imp.dependents) or '-'}",
    ]
    if imp.depth is not None:
        lines.append(
            f"TRUNCATED impact: explicit --depth {imp.depth}; callers beyond this depth were not selected"
        )
    if missing:
        lines.append(
            "UNMAPPED changed files (add each to one component's files): " + ", ".join(missing)
        )
    lines.extend("UNCERTAIN " + message for message in imp.uncertainty[:5])
    if len(imp.uncertainty) > 5:
        lines.append(
            f"UNCERTAIN {len(imp.uncertainty) - 5} more surfaces; use map impact --json for all paths"
        )
    lines.extend("BLOCKED " + message for message in imp.blocked)
    lines.extend("NO CHECKS for: " + path for path in imp.no_checks)
    if imp.comment_only:
        lines.append(
            "comment-only edits (no tests or models selected): " + ", ".join(imp.comment_only)
        )
    lines.extend(
        f"UNEXPLAINED {item} has no model anchor, test or NOT_MODELED reason"
        for item in imp.unexplained[:5]
    )
    if len(imp.unexplained) > 5:
        lines.append(
            f"UNEXPLAINED +{len(imp.unexplained) - 5} more "
            f"(python -m flowguard read --component {imp.unexplained[5].partition(':')[0]})"
        )
    lines.extend(imp.flow_models[:5])
    lines.extend("relies on: " + item for item in imp.relied_models[:5])
    if len(imp.relied_models) > 5:
        lines.append(f"relies on: +{len(imp.relied_models) - 5} more")
    if imp.no_git:
        lines.append(imp.no_git)
    if imp.changed_functions:
        lines.append(
            "changed functions: "
            + ", ".join(imp.changed_functions[:5])
            + (f" +{len(imp.changed_functions)-5}" if len(imp.changed_functions) > 5 else "")
        )
    lines.extend(
        f"UNCERTAIN: {path}: {reason}; this file uses the broad selection"
        for path, reason in sorted(imp.uncertain_files.items())
    )
    if imp.unreached:
        lines.append("no model reaches: " + ", ".join(imp.unreached[:5]))
    lines.extend("also reached: " + line for line in imp.also_reached)
    lines.extend(imp.port_lines)
    if imp.changed_functions or imp.no_git:
        choices = [
            mid + (" (" + imp.model_reasons[mid][0] + ")" if imp.model_reasons.get(mid) else "")
            for mid in model_ids
        ]
        lines.append(
            f"models to run ({len(choices)}): "
            + (", ".join(choices[:8]) or "-")
            + (f" +{len(choices)-8}" if len(choices) > 8 else "")
        )
    else:
        lines.append(
            f"models to run: {len(models)} selected (full list: python -m flowguard map impact --json)"
            if len(models) > 8
            else f"models to run: {', '.join(models) or '-'}"
        )
    if moving:
        lines.append(
            "moving to target: "
            + ", ".join(mid for path, mid in moving)
            + " (python -m flowguard target check runs their target versions)"
        )
    lines.extend(imp.consumer_lines)
    lines.extend(imp.promise_lines)
    lines.extend(
        "WARN promise_removed " + finding["component"] + ": " + finding["message"]
        for finding in imp.promise_findings
    )
    groups, no_command = test_groups(imp)
    commands = run_commands(imp, moving_models=moving_models)
    if imp.changed_functions or imp.test_functions:
        lines.append(
            f"tests to run ({imp.selected_test_functions} of {imp.total_test_functions} test functions, {len(imp.tests)} file"
            + ("s" if len(imp.tests) != 1 else "")
            + f"): bound {imp.bound_test_count}, calling {imp.calling_test_count}, whole files {len(imp.whole_test_files)}"
        )
    else:
        lines.append(
            f"tests to run ({len(imp.tests)} of {imp.total_tests}): "
            + ("see run below" if imp.tests else "-")
        )
    import shlex

    counts = getattr(imp, "_test_function_counts", {})
    for (command, selectors), rendered in zip(groups.items(), commands):
        argv = shlex.split(command)
        pytest = (
            len(argv) >= 3
            and argv[1:3] == ["-m", "pytest"]
            or bool(argv)
            and Path(argv[0]).name in {"pytest", "pytest.exe"}
        )
        if verbose or not pytest:
            lines.append("run: " + rendered)
            continue
        files = list(dict.fromkeys(selector.partition("::")[0] for selector in selectors))
        tests = sum(1 if "::" in selector else counts.get(selector, 1) for selector in selectors)
        names = ", ".join(files[:3])
        if len(files) > 3:
            names += f", +{len(files)-3} more"
        lines.append(
            f"run: python -m flowguard change --run (pytest: {tests} tests in {len(files)} files: {names})"
        )
    lines.extend("NO TEST COMMAND for: " + test for test in no_command)
    lines.extend("run: " + command for command in commands[len(groups) :])
    for cid in imp.needs_review:
        message = f"REVIEW {cid}: its files changed; update its description if behavior changed, then confirm {cid}"
        if imp.review_models.get(cid):
            message += (
                f"; models to re-read: {', '.join(imp.review_models[cid])} "
                "(does the change need a new input, state or invariant?)"
            )
        lines.append(message)
    for cid in imp.map_review:
        lines.append(f"NOTE {cid}: map description changed; no verification fields changed")
    return "\n".join(lines)

class ChangedFiles(list):
    """An operation-local file list carrying the explicit no-git explanation."""
    def __init__(self, paths, no_git=''):
        super().__init__(paths)
        self.no_git=no_git


def _no_git_changes(root, data=None, inv=None):
    from .mapfile import load_map, owner_index
    from .inventory import build_inventory
    data=data if data is not None else load_map(root)
    inv=inv if inv is not None else build_inventory(root,ignore_patterns(data))
    stale=[c for c in data['components'] if c.get('status')!='confirmed' or is_stale(root,c,inv)]
    owned,_=owner_index(data,inv)
    unmapped=[path for path in inv.source if path not in owned and not inv.is_test(path)
              and not path.startswith('.flowguard/') and not any(part.endswith('.egg-info') or part in ('build','dist') for part in Path(path).parts)]
    paths=sorted({path for comp in stale for path in component_files(comp,inv)}|set(unmapped))
    ids=', '.join(c['id'] for c in stale) or '-'
    note=(f'NO GIT: changed files = the files of {len(stale)} component(s) whose fingerprint differs from map.json ({ids}) and {len(unmapped)} unmapped file(s); '
          'tests come from those components; a test file edited alone is not seen: run it by path; there is no old text, so these files use the file-level selection; model files are compared by target check, not here')
    return ChangedFiles(paths,note)

def _closure(edges, start):
    # Keep the internal call site compatible; discovery owns reachability for all views.
    from .discover import reachable_functions
    return reachable_functions(edges, start)


def _changed_symbols(root, inv, changed, base, raw):
    """Qualified changed symbols and explicit uncertainty, using the one AST digest owner."""
    from .inventory import function_digests, resolve_module
    functions, uncertain = set(), {}
    reverse = defaultdict(set)
    for caller, targets in raw.get('edges', {}).items():
        for target in targets: reverse[target].add(caller)
    for path in changed:
        if inv.is_test(path) or path.startswith('.flowguard/') or path not in inv.source and Path(path).suffix not in SOURCE_EXTS:
            continue
        if not path.endswith('.py'):
            uncertain[path] = 'not Python'; continue
        if path in inv.dynamic_files:
            uncertain[path] = 'dynamic imports'; continue
        if path.endswith('__init__.py') and path in inv.py and inv.py[path].lazy_exports:
            uncertain[path] = 'lazy package exports'; continue
        previous = subprocess.run(['git','-C',str(root),'show',f'{base}:{path}'],capture_output=True) if base else None
        if previous is None or previous.returncode:
            uncertain[path] = 'no old source text'; continue
        try:
            before = function_digests(normalize_newlines(previous.stdout))
            source = read_source(root/path)
            after = function_digests(source)
        except (OSError, SyntaxError, ValueError):
            uncertain[path] = 'source cannot be parsed'; continue
        if set(before['functions']) - set(after['functions']) or set(before['classes']) - set(after['classes']):
            uncertain[path] = 'a symbol was removed or renamed'; continue
        if before['statements'] != after['statements']:
            uncertain[path] = 'a nonbinding module statement changed'; continue
        signature_changed = set()
        for symbol, value in after['functions'].items():
            old = before['functions'].get(symbol)
            if old != value:
                functions.add(path+'#'+symbol)
            if old and old['sig_digest'] != value['sig_digest']:
                signature_changed.add(path+'#'+symbol)
        for symbol, value in after['classes'].items():
            old = before['classes'].get(symbol)
            if old and set(old['names']) - set(value['names']):
                uncertain[path] = 'a class binding was removed or renamed'
            if old != value:
                class_node = path+'#'+symbol
                functions.add(class_node)
                signature_changed.add(class_node)
                functions.update(path+'#'+name for name in after['functions'] if name.startswith(symbol+'.'))
                _binding_users(root,inv,path,symbol.split('.')[0],functions,raw)
        for node in signature_changed:
            functions.update(reverse.get(node, ()))
        for name, value in before['bindings'].items():
            if after['bindings'].get(name) != value:
                _binding_users(root,inv,path,name,functions,raw)
        for importer,info in inv.py.items():
            if path in inv.file_deps.get(importer, ()):
                try:
                    syntax=ast.parse(read_source(root/importer))
                    if any(isinstance(n,ast.ImportFrom) and any(a.name=='*' for a in n.names) for n in ast.walk(syntax)):
                        uncertain[path]='a project file imports this file with *'
                except (OSError,SyntaxError): pass
    return functions, uncertain


def _binding_users(root, inv, path, name, functions, raw):
    """Resolve imported names/aliases before matching actual function references."""
    from .inventory import resolve_module
    for other in inv.py:
        if other != path and path not in inv.file_deps.get(other, ()):
            continue
        try: syntax = ast.parse(read_source(root/other))
        except (OSError,SyntaxError): continue
        names = {name} if other == path else set()
        modules = set()
        # Local imports are included; shadowing can only conservatively add callers.
        for statement in ast.walk(syntax):
            if isinstance(statement,ast.ImportFrom):
                parts=other.removesuffix('.py').split('/')[:-1]
                module='.'.join(parts[:len(parts)-statement.level+1]+([statement.module] if statement.module else [])) if statement.level else statement.module or ''
                target=resolve_module(module,other,inv.mod_to_path,inv.py,inv.import_roots)
                if target == path:
                    names.update(alias.asname or alias.name for alias in statement.names if alias.name==name)
            elif isinstance(statement,ast.Import):
                for alias in statement.names:
                    target=resolve_module(alias.name,other,inv.mod_to_path,inv.py,inv.import_roots)
                    if target==path: modules.add(alias.asname or alias.name)
        def dotted(node):
            if isinstance(node,ast.Name): return node.id
            if isinstance(node,ast.Attribute): return dotted(node.value)+'.'+node.attr
            return ''
        def visit(nodes,prefix=''):
            for statement in nodes:
                if isinstance(statement,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    symbol=prefix+statement.name
                    class References(ast.NodeVisitor):
                        found=False
                        def visit_FunctionDef(self,node): pass
                        visit_AsyncFunctionDef=visit_FunctionDef
                        def visit_ClassDef(self,node): pass
                        def visit_Name(self,node):
                            if isinstance(node.ctx,ast.Load) and node.id in names: self.found=True
                        def visit_Attribute(self,node):
                            if node.attr==name and dotted(node.value) in modules: self.found=True
                            self.generic_visit(node)
                    references=References()
                    for item in [*statement.body,*statement.decorator_list,*statement.args.defaults,*statement.args.kw_defaults]:
                        if item is not None: references.visit(item)
                    if references.found: functions.add(other+'#'+symbol)
                    visit(statement.body,symbol+'.')
                elif isinstance(statement,ast.ClassDef): visit(statement.body,prefix+statement.name+'.')
                else:
                    for attribute in ('body','orelse','finalbody'):
                        if isinstance(getattr(statement,attribute,None),list): visit(getattr(statement,attribute),prefix)
        visit(syntax.body)


def select_tests(root, data, inv, tree, selected, changed_functions, *, changed=(), uncertain=(), raw=None, extra_files=()):
    """Select bound/direct-call nodes; only the listed fallback cases select whole files."""
    import re
    from .testtree import test_functions, resolve_test_anchor, test_calls
    from .discover import discover_inventory
    raw = raw if raw is not None else discover_inventory(root,inv,data=data,write_cache=False)
    sources, collected, calls = {}, {}, {}
    for path in inv.tests:
        if not path.endswith('.py') or not is_collectable_test(path): continue
        try: sources[path]=read_source(root/path)
        except OSError: continue
        collected[path]=test_functions(sources[path])
        calls[path]=test_calls(path,sources[path],inv)
    nodes=defaultdict(set)
    bound=set()
    for mid in selected:
        if mid not in tree.nodes: continue
        for anchors in tree.nodes[mid].contract.get('TESTED_BY',{}).values():
            for anchor in anchors:
                path,_,symbol=anchor.partition(':')
                resolved=resolve_test_anchor(root/path,symbol)
                if resolved is None: continue
                parameters='['+symbol.split('[',1)[1] if '[' in symbol else ''
                qualified=resolved+parameters
                nodes[path].add(qualified); bound.add((path,qualified))
    targets={fn.replace('#',':',1) for fn in changed_functions}
    closures={}
    def reaches(call):
        start=call.replace(':','#',1)
        if start not in closures: closures[start]=_closure(raw.get('edges',{}),start)
        return closures[start]
    calling=set(); indirect=defaultdict(int)
    for path, tests in calls.items():
        for symbol, sites in tests.items():
            direct=sites & targets
            if direct:
                nodes[path].add(symbol); calling.add((path,symbol))
            for target in targets - direct:
                if any(target.replace(':','#',1) in reaches(site) for site in sites): indirect[target]+=1
    whole={path for path in changed if path in collected}
    whole.update(extra_files)
    for path in changed:
        if Path(path).name=='conftest.py':
            prefix=path.rpartition('/')[0]
            whole.update(t for t in collected if not prefix or t.startswith(prefix+'/'))
    if uncertain: whole.update(_tests_reaching(inv,list(uncertain),package_init=False))
    # A direct imported symbol mentioned without a resolved call is a file-level fallback.
    for path, source in sources.items():
        for fn in changed_functions:
            target,_,symbol=fn.partition('#')
            if target not in inv.file_deps.get(path,()): continue
            leaf=symbol.rpartition('.')[2]
            any_call=any(target+':'+symbol in sites for sites in calls[path].values())
            if not any_call and re.search(r'\b'+re.escape(leaf)+r'\b',source): whole.add(path)
    for path, chosen in nodes.items():
        resolved={name.split('[',1)[0] for name in chosen}
        if collected.get(path) and len(resolved)*2>=len(collected[path]): whole.add(path)
    whole.intersection_update(set(inv.tests))
    for path in whole: nodes.setdefault(path,set())
    # All-case anchors dominate parameter-specific anchors of the same function.
    for path, chosen in nodes.items():
        chosen.difference_update(name for name in list(chosen) if '[' in name and name.split('[',1)[0] in chosen)
    return dict(nodes={path:sorted(chosen) for path,chosen in sorted(nodes.items())},whole_files=sorted(whole),
                bound=len(bound),calling=len(calling-bound),total=sum(map(len,collected.values())),
                selected=sum(len(collected.get(path,{})) if path in whole else len({name.split('[',1)[0] for name in chosen}) for path,chosen in nodes.items()),
                also_reached=[f'{count} test functions call {fn} only through other functions (python -m flowguard change --broad)' for fn,count in sorted(indirect.items())])


def compute_impact(root: Path, data: dict, inv: Inventory, changed: list[str], depth: int | None = None,
                   *, base: str | None = None, broad: bool = False) -> Impact:
    """Select exact owned/reachable functions, with explicit conservative uncertainty."""
    from .discover import discover_inventory, relied_models
    from .mapfile import owner_index
    if changed is None: changed=changed_files(root,base or 'HEAD',data=data,inv=inv)
    no_git=getattr(changed,'no_git','')
    if broad:
        result=_broad_impact(root,data,inv,changed,depth,base=base,broad=True)
        result.no_git=no_git
        return result
    changed=sorted({project_relative(root,path) for path in changed if not project_relative(root,path).startswith('.flowguard/target/')})
    if not changed:
        result=_broad_impact(root,data,inv,[],depth,base=base,package_init=False)
        result.no_git=no_git
        return result
    comments={path for path in changed if _comment_only(root,base,path)}
    source_changes=[path for path in changed if path not in comments and not inv.is_test(path) and not path.startswith('.flowguard/') and (path in inv.source or Path(path).suffix in SOURCE_EXTS)]
    literal_tree=build_tree(root,data,inv)
    consumer_lines,literal_models,literal_functions,literal_tests=_literal_impact(root,data,inv,literal_tree,changed,base)
    raw=discover_inventory(root,inv,data=data,write_cache=False) if source_changes or literal_functions else {'files':{},'edges':{}}
    functions,uncertain=_changed_symbols(root,inv,source_changes,base,raw)
    functions.update(literal_functions)
    certain=set(source_changes)-set(uncertain)
    result=_broad_impact(root,data,inv,[path for path in changed if path not in certain],depth,base=base,package_init=False)
    tree=build_tree(root,data,inv)
    owner,_=owner_index(data,inv)
    direct={owner[path] for path in changed if path in owner}
    result.changed=changed;result.direct=sorted(set(result.direct)|direct)
    result.needs_review=sorted(set(result.needs_review)|{c['id'] for c in data['components'] if c['id'] in direct and is_stale(root,c,inv)})
    result.review_models.update({cid:[node.id for node in tree.models_for_component(cid)] for cid in direct})
    result.comment_only=sorted(comments)
    result.unmapped=sorted(set(result.unmapped)|{path for path in certain if path not in owner and not matches_any(path,ignore_patterns(data))})
    selected=set(result.model_ids)|literal_models
    result.consumer_lines=consumer_lines
    result.promise_lines,result.promise_findings=_git_promise_notes(root,data,changed,base)
    from .discover import select_model_functions, anchor_matches
    chosen,reasons,flow_lines,unreached=select_model_functions(data,inv,tree,raw,functions)
    selected.update(chosen)
    result.flow_models.extend(flow_lines)
    own={mid:node.contract.get('IMPLEMENTED_BY',{}) for mid,node in tree.nodes.items()}
    if source_changes:
        sites=relied_models(raw,data,inv,{mid:list(anchors.values()) for mid,anchors in own.items()},files=list(certain))
        result.relied_models=sorted(set(result.relied_models)|{f'{mid} via {cid}:{symbol}' for mid,locations in sites.items() for cid,symbol in locations})
        # Full unexplained facts are needed for unowned entrypoints/writers, not owned edits.
        if certain and (not functions or any(not any(anchor_matches(anchor,fn) for anchors in own.values() for anchor in anchors.values()) for fn in functions)):
            from .lint import coverage_facts
            for cid,record in coverage_facts(root,data,inv,tree,raw).items():
                entries=set(record.get('unexplained_entries',()))
                result.unexplained.extend(f"{cid}: {anchor} ({'entrypoint' if anchor in entries else 'state writer'})" for anchor in record['unexplained'] if anchor.partition(':')[0] in certain)
    pairs=sorted((node.path,mid) for mid,node in tree.nodes.items() if mid in selected)
    result.models=[path for path,mid in pairs];result.model_ids=[mid for path,mid in pairs]
    result.changed_functions=sorted(fn.replace('#',':',1) for fn in functions)
    result.uncertain_files=uncertain;result.unreached=unreached;result.model_reasons=dict(reasons);result.no_git=no_git
    whole_fallback = bool(uncertain) or any(
        (path not in source_changes and not inv.is_test(path) and not path.startswith('.flowguard/models/') and path not in comments)
        or (path.startswith('.flowguard/models/') and not (root/path).is_file())
        or (inv.is_test(path) and not is_collectable_test(path))
        for path in changed)
    extra=set(result.tests) if whole_fallback else {path for path in result.tests if path in changed}
    if no_git:
        extra.update(path for c in data['components'] if c['id'] in direct for path in inv.tests if matches_any(path,c.get('tests',())))
    selection=select_tests(root,data,inv,tree,selected,functions,changed=changed,uncertain=uncertain,raw=raw,extra_files=extra|literal_tests)
    result.tests=sorted(selection['nodes'])
    result.test_commands, command_problems = _commands_for_tests(data,_previous_map(root,base) if '.flowguard/map.json' in changed else None,result.tests)
    result.blocked=sorted(set(result.blocked)|set(command_problems))
    result.test_functions={path:names for path,names in selection['nodes'].items() if path not in selection['whole_files']}
    result.whole_test_files=selection['whole_files'];result.selected_test_functions=selection['selected'];result.total_test_functions=selection['total']
    result.bound_test_count=selection['bound'];result.calling_test_count=selection['calling'];result.also_reached=selection['also_reached']
    return result


from .impact_history import (_anchor_changed, _binding_indexes, _commands_for_tests, _comment_only, _git_promise_notes, _literal_impact, _owner_model_paths, _previous_map, _read_git_paths, _removed_model_context, _tests_reaching, project_relative)
